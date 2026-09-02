from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.runtime_config import DispatchMetadata
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker

TENANT_BASE = UUID("00000000-0000-0000-0000-000000000001")


class _SessionTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, slow_tools: bool = False, tool_status: int = 200) -> None:
        self.record_id = uuid4()
        self.requests: list[httpx.Request] = []
        self.slow_tools = slow_tools
        self.tool_status = tool_status
        self.tool_started = asyncio.Event()
        self.release_tool = asyncio.Event()
        if not slow_tools:
            self.release_tool.set()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(201, json={"id": str(self.record_id)})
        if path.endswith("/tool-invocations"):
            self.tool_started.set()
            await self.release_tool.wait()
            if self.tool_status >= 400:
                return httpx.Response(self.tool_status, json={"detail": "down"})
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "invocation_id": str(uuid4()),
                    "status": "ok",
                    "session_id": body["session_id"],
                    "tool_name": body["tool_name"],
                },
            )
        if path.endswith("/finish"):
            body = json.loads(request.content)
            return httpx.Response(200, json={"id": str(self.record_id), **body})
        return httpx.Response(200, json={"id": str(self.record_id)})


async def _run_session(
    *,
    session_id: str,
    call_id: str,
    transcript: str,
    hangup: bool = True,
    fail_agent: bool = False,
    transport: _SessionTransport | None = None,
) -> tuple[_SessionTransport, CallLifecycleClient, dict[str, object]]:
    owned = transport or _SessionTransport()
    tenant = TENANT_BASE
    async with httpx.AsyncClient(
        transport=owned, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(http, tenant)
        metadata = DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": "00000000-0000-0000-0000-000000000101",
                    "tenant_id": str(tenant),
                    "config_version": 1,
                    "provider_call_id": call_id,
                }
            )
        )
        await lifecycle.start_from_dispatch(metadata, session_id)
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, tenant, timeout_s=0.2),
            lifecycle=lifecycle,
            session_id=session_id,
            voice_agent_instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        )
        await orchestrator.handle_user_final(transcript)
        if fail_agent:
            await lifecycle.finish(status="failed", ended_reason="agent_error")
            orchestrator.mark_closed()
            return owned, lifecycle, {"session_id": session_id}
        marker = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": transcript}
        )
        await orchestrator.handle_assistant_final(f"ack-{transcript}\n{marker}")
        if hangup:
            orchestrator.mark_closed()
            await lifecycle.finish(status="completed", ended_reason="user_hangup")
        return owned, lifecycle, {"session_id": session_id}


def _finish_bodies(transport: _SessionTransport) -> list[dict[str, object]]:
    bodies: list[dict[str, object]] = []
    for request in transport.requests:
        if request.url.path.endswith("/finish"):
            bodies.append(json.loads(request.content))
    return bodies


def _tool_bodies(transport: _SessionTransport) -> list[dict[str, object]]:
    bodies: list[dict[str, object]] = []
    for request in transport.requests:
        if request.url.path.endswith("/tool-invocations"):
            bodies.append(json.loads(request.content))
    return bodies


@pytest.mark.asyncio
async def test_five_sessions_are_isolated() -> None:
    results = await asyncio.gather(
        *[
            _run_session(
                session_id=f"room-{index}",
                call_id=f"call-{index}",
                transcript=f"hello-{index}",
            )
            for index in range(5)
        ]
    )
    session_ids = []
    for transport, _lifecycle, _meta in results:
        tools = _tool_bodies(transport)
        finishes = _finish_bodies(transport)
        assert len(tools) == 1
        assert len(finishes) == 1
        session_ids.append(tools[0]["session_id"])
        assert tools[0]["arguments"]["reason"].startswith("hello-")
        assert finishes[0]["ended_reason"] == "user_hangup"
    assert len(set(session_ids)) == 5


@pytest.mark.asyncio
async def test_ten_fake_sessions_are_isolated() -> None:
    results = await asyncio.gather(
        *[
            _run_session(
                session_id=f"room-10-{index}",
                call_id=f"call-10-{index}",
                transcript=f"ten-{index}",
            )
            for index in range(10)
        ]
    )
    assert len(results) == 10
    ids = [_tool_bodies(item[0])[0]["session_id"] for item in results]
    assert len(set(ids)) == 10


@pytest.mark.asyncio
async def test_slow_tool_does_not_block_other_sessions() -> None:
    slow = _SessionTransport(slow_tools=True)
    fast_done = asyncio.Event()

    async def slow_session() -> None:
        await _run_session(
            session_id="room-slow",
            call_id="call-slow",
            transcript="slow",
            transport=slow,
        )

    async def fast_session() -> None:
        await _run_session(
            session_id="room-fast",
            call_id="call-fast",
            transcript="fast",
        )
        fast_done.set()

    slow_task = asyncio.create_task(slow_session())
    await slow.tool_started.wait()
    await fast_session()
    assert fast_done.is_set()
    assert not slow_task.done()
    slow.release_tool.set()
    await slow_task


@pytest.mark.asyncio
async def test_platform_failure_is_isolated_to_one_session() -> None:
    failing = _SessionTransport(tool_status=500)
    failing.release_tool.set()
    ok, boom = await asyncio.gather(
        _run_session(session_id="room-ok", call_id="call-ok", transcript="ok"),
        _run_session(
            session_id="room-boom",
            call_id="call-boom",
            transcript="boom",
            transport=failing,
        ),
    )
    assert _finish_bodies(ok[0])[0]["ended_reason"] == "user_hangup"
    assert _finish_bodies(boom[0])[0]["ended_reason"] == "user_hangup"
    assert len(_tool_bodies(ok[0])) == 1
    assert len(_tool_bodies(boom[0])) == 1


@pytest.mark.asyncio
async def test_agent_crash_is_isolated_to_one_session() -> None:
    crashed, healthy = await asyncio.gather(
        _run_session(
            session_id="room-crash",
            call_id="call-crash",
            transcript="crash",
            fail_agent=True,
        ),
        _run_session(
            session_id="room-healthy",
            call_id="call-healthy",
            transcript="healthy",
        ),
    )
    assert _finish_bodies(crashed[0])[0]["ended_reason"] == "agent_error"
    assert _finish_bodies(healthy[0])[0]["ended_reason"] == "user_hangup"
    assert _tool_bodies(healthy[0])[0]["session_id"] == "room-healthy"


@pytest.mark.asyncio
async def test_early_hangup_during_tool_one_finish() -> None:
    transport = _SessionTransport(slow_tools=True)
    tenant = TENANT_BASE
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(http, tenant)
        metadata = DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": "00000000-0000-0000-0000-000000000101",
                    "tenant_id": str(tenant),
                    "config_version": 1,
                }
            )
        )
        await lifecycle.start_from_dispatch(metadata, "room-early")
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, tenant),
            lifecycle=lifecycle,
            session_id="room-early",
            voice_agent_instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        )
        marker = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": "early"}
        )
        task = asyncio.create_task(
            orchestrator.handle_assistant_final(f"ack\n{marker}")
        )
        await transport.tool_started.wait()
        orchestrator.mark_closed()
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        await lifecycle.finish(status="completed", ended_reason="completed")
        transport.release_tool.set()
        await task
    assert len(_finish_bodies(transport)) == 1


@pytest.mark.asyncio
async def test_close_storm_sends_one_finish() -> None:
    transport = _SessionTransport()
    tenant = TENANT_BASE
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(http, tenant)
        metadata = DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": "00000000-0000-0000-0000-000000000101",
                    "tenant_id": str(tenant),
                    "config_version": 1,
                }
            )
        )
        await lifecycle.start_from_dispatch(metadata, "room-storm")
        await asyncio.gather(
            lifecycle.finish(status="completed", ended_reason="user_hangup"),
            lifecycle.finish(status="completed", ended_reason="completed"),
            lifecycle.finish(status="completed", ended_reason="user_hangup"),
            lifecycle.finish(status="completed", ended_reason="completed"),
            lifecycle.finish(status="completed", ended_reason="user_hangup"),
        )
    assert len(_finish_bodies(transport)) == 1
    assert _finish_bodies(transport)[0]["ended_reason"] == "user_hangup"


@pytest.mark.asyncio
async def test_session_tasks_return_to_baseline() -> None:
    before = {id(task) for task in asyncio.all_tasks()}
    await test_five_sessions_are_isolated()
    pending = [
        task
        for task in asyncio.all_tasks()
        if id(task) not in before and not task.done()
    ]
    assert pending == []
