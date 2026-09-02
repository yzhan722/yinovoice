from __future__ import annotations

import asyncio
import json
from uuid import UUID

import httpx
import pytest
from hardening_support import FailureScenario, FakePlatform

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.runtime_config import DispatchMetadata
from yino_voice_agent.session_trace import SessionTrace
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker

TENANT = UUID("00000000-0000-4000-8000-000000000001")
SERVICE = UUID("00000000-0000-4000-8000-000000000101")


def _metadata() -> DispatchMetadata:
    return DispatchMetadata.from_json(
        json.dumps(
            {
                "customer_service_id": str(SERVICE),
                "tenant_id": str(TENANT),
                "config_version": 1,
            }
        )
    )


async def _storm(lifecycle: CallLifecycleClient) -> None:
    await asyncio.gather(
        lifecycle.finish(status="completed", ended_reason="user_hangup"),
        lifecycle.finish(status="failed", ended_reason="agent_error"),
        lifecycle.finish(status="completed", ended_reason="completed"),
        lifecycle.finish(status="completed", ended_reason="user_hangup"),
        lifecycle.finish(status="failed", ended_reason="agent_error"),
    )


@pytest.mark.asyncio
async def test_race_matrix_finish_exactly_once() -> None:
    cases = [
        "hangup_shutdown",
        "hangup_agent_error",
        "hangup_tool_timeout",
        "agent_error_shutdown",
        "qwen_and_livekit_disconnect",
        "session_close_and_shutdown",
        "multiple_close_callbacks",
        "finish_while_append_in_flight",
    ]
    for _ in range(20):
        for case in cases:
            await _run_case(case)


async def _run_case(case: str) -> None:
    scenario = FailureScenario()
    if case == "hangup_tool_timeout":
        scenario.tool_timeout = True
    if case == "finish_while_append_in_flight":
        scenario.message_delay_s = 0.01
    platform = FakePlatform(scenario)
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(
            http, TENANT, trace=SessionTrace(session_id=case)
        )
        await lifecycle.start_from_dispatch(_metadata(), f"room-{case}")
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT, timeout_s=0.05),
            lifecycle=lifecycle,
            session_id=f"room-{case}",
            voice_agent_instance_id=SERVICE,
        )
        await orchestrator.handle_user_final("hello")
        if case == "hangup_tool_timeout":
            marker = encode_tool_marker("check_availability", {"day": "2026-09-02"})
            task = orchestrator.spawn(
                orchestrator.handle_assistant_final(f"wait\n{marker}")
            )
            await asyncio.wait_for(platform.tool_started.wait(), timeout=0.5)
            orchestrator.mark_closed()
            await lifecycle.finish(status="completed", ended_reason="user_hangup")
            await asyncio.gather(task, return_exceptions=True)
        elif case == "finish_while_append_in_flight":
            append = asyncio.create_task(lifecycle.append_final("assistant", "late", 2))
            await lifecycle.finish(status="completed", ended_reason="user_hangup")
            await append
        elif case in {"hangup_agent_error", "agent_error_shutdown"}:
            await asyncio.gather(
                lifecycle.finish(status="completed", ended_reason="user_hangup"),
                lifecycle.finish(status="failed", ended_reason="agent_error"),
            )
        else:
            await _storm(lifecycle)
        orchestrator.mark_closed()
    assert platform.finish_count() == 1
    if case in {"hangup_agent_error", "agent_error_shutdown"}:
        assert lifecycle.finish_selected == ("failed", "agent_error")


@pytest.mark.asyncio
async def test_qwen_close_and_livekit_disconnect_one_finish() -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(http, TENANT)
        await lifecycle.start_from_dispatch(_metadata(), "room-dual-close")
        await asyncio.gather(
            lifecycle.finish(status="completed", ended_reason="user_hangup"),
            lifecycle.finish(status="completed", ended_reason="completed"),
        )
    assert platform.finish_count() == 1
    assert lifecycle.finish_selected == ("completed", "user_hangup")


@pytest.mark.asyncio
async def test_record_id_unique_per_start() -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        first = CallLifecycleClient(http, TENANT)
        second = CallLifecycleClient(http, TENANT)
        await first.start_from_dispatch(_metadata(), "room-a")
        await second.start_from_dispatch(_metadata(), "room-b")
        assert first.record_id != second.record_id
        await first.finish()
        await second.finish()
    assert platform.finish_count() == 2
    assert len(set(platform.record_to_session.values())) == 2
