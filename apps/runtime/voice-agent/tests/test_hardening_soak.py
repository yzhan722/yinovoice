from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from hardening_support import (
    FakePlatform,
    make_spec,
    run_synthetic_session,
    runtime_tasks,
)
from test_qwen_realtime_output import (
    FakeQwenSocket,
    connected_session,
    response_created,
)

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.runtime_config import DispatchMetadata
from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker
from yino_voice_agent.usage import CallUsageAccumulator


@pytest.mark.asyncio
async def test_thirty_minute_and_five_hundred_turns() -> None:
    platform = FakePlatform()
    clock = FakeClock()
    spec = make_spec(0, session_id="soak-room", room_name="soak-room")
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        metadata = DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": str(spec.customer_service_id),
                    "tenant_id": str(spec.tenant_id),
                    "config_version": 1,
                }
            )
        )
        trace = SessionTrace(session_id=spec.session_id, clock=clock)
        lifecycle = CallLifecycleClient(http, spec.tenant_id, trace=trace)
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(
                http, spec.tenant_id, timeout_s=0.2, trace=trace
            ),
            lifecycle=lifecycle,
            session_id=spec.session_id,
            voice_agent_instance_id=spec.customer_service_id,
            trace=trace,
        )
        await lifecycle.start_from_dispatch(metadata, spec.room_name)
        for turn in range(500):
            clock.advance(3.6)
            await orchestrator.handle_user_final(f"user-{turn}")
            spoken = f"assistant-{turn}"
            if turn % 10 == 0:
                marker = encode_tool_marker("check_availability", {"day": "2026-09-02"})
                spoken = f"{spoken}\n{marker}"
            await orchestrator.handle_assistant_final(spoken)
            if turn % 7 == 0:
                trace.mark("interrupt_start")
                trace.mark("interrupt_complete")
            lifecycle.record_usage(
                {
                    "type": "response.done",
                    "response": {
                        "id": f"resp-soak-{turn}",
                        "usage": {
                            "total_tokens": 3,
                            "input_tokens": 2,
                            "output_tokens": 1,
                        },
                    },
                }
            )
        orchestrator.mark_closed()
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        await orchestrator.wait_idle()
    assert clock.monotonic() == pytest.approx(1_000.0 + 3.6 * 500, rel=1e-9, abs=0.01)
    assert lifecycle.usage.snapshot().response_count == 500
    assert platform.finish_count() == 1
    assert len(platform.messages_by_session[spec.session_id]) == 1000


def test_thousand_response_done_usage_is_stable() -> None:
    acc = CallUsageAccumulator()
    for index in range(1000):
        acc.add(
            {
                "type": "response.done",
                "response": {
                    "id": f"resp-{index}",
                    "usage": {
                        "total_tokens": 2,
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                },
            }
        )
        acc.add(
            {
                "type": "response.done",
                "response": {
                    "id": f"resp-{index}",
                    "usage": {
                        "total_tokens": 2,
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                },
            }
        )
    snapshot = acc.snapshot()
    assert snapshot.response_count == 1000
    assert snapshot.total_tokens == 2000
    assert snapshot.input_tokens == 1000


@pytest.mark.asyncio
async def test_repeated_qwen_sessions_do_not_leak_tasks() -> None:
    before = runtime_tasks()
    for _ in range(8):
        socket = FakeQwenSocket()
        model, session = await connected_session(socket)
        await socket.push(response_created("resp-leak"))
        await asyncio.sleep(0)
        await session.aclose()
        await model.aclose()
    leftover = runtime_tasks() - before
    assert leftover == set()


@pytest.mark.asyncio
async def test_http_client_is_shared_not_created_per_request() -> None:
    platform = FakePlatform()
    specs = [
        make_spec(
            index,
            session_id=f"share-{index}",
            room_name=f"share-{index}",
        )
        for index in range(5)
    ]
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client_id = id(http)
        await asyncio.gather(*[run_synthetic_session(http, spec) for spec in specs])
        assert id(http) == client_id
    assert platform.finish_count() == 5
