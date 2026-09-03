from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.runtime_config import DispatchMetadata
from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker

TENANT = UUID("00000000-0000-0000-0000-000000000001")
INSTANCE = UUID("00000000-0000-0000-0000-000000000101")


def _metadata() -> DispatchMetadata:
    return DispatchMetadata.from_json(
        json.dumps(
            {
                "customer_service_id": str(INSTANCE),
                "tenant_id": str(TENANT),
                "config_version": 1,
            }
        )
    )


class _RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.record_id = uuid4()
        self.requests: list[httpx.Request] = []
        self.tool_started = asyncio.Event()
        self.release_tool = asyncio.Event()
        self.tool_status = 200
        self.tool_body: dict[str, object] = {
            "invocation_id": str(uuid4()),
            "status": "ok",
        }
        self.availability_attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(201, json={"id": str(self.record_id)})
        if path.endswith("/tool-invocations"):
            self.tool_started.set()
            await self.release_tool.wait()
            return httpx.Response(self.tool_status, json=self.tool_body)
        if path.endswith("/finish"):
            return httpx.Response(
                200, json={"id": str(self.record_id), "status": "completed"}
            )
        return httpx.Response(200, json={"id": str(self.record_id)})


def _tool_paths(requests: list[httpx.Request]) -> list[httpx.Request]:
    return [item for item in requests if item.url.path.endswith("/tool-invocations")]


@pytest.mark.asyncio
async def test_malformed_marker_does_not_call_platform() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": str(uuid4())})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT),
            lifecycle=None,
            session_id="room-malformed",
            voice_agent_instance_id=INSTANCE,
        )
        turn = await orchestrator.handle_assistant_final(
            "please wait\n[[tool:create_appointment|not-json"
        )
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-malformed",
            tool_name="create_appointment",
            arguments=["not", "an", "object"],  # type: ignore[arg-type]
        )

    assert turn.marker is None
    assert result is not None
    assert result["code"] == "invalid_arguments"
    assert _tool_paths(seen) == []


@pytest.mark.asyncio
async def test_unknown_tool_does_not_call_platform() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT),
            lifecycle=None,
            session_id="room-unknown",
            voice_agent_instance_id=INSTANCE,
        )
        turn = await orchestrator.handle_assistant_final(
            "ok\n[[tool:transfer_human|phone=13800138000]]"
        )
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-unknown",
            tool_name="nonsense_tool",
            arguments={"phone": "13800138000"},
        )

    assert turn.marker is None
    assert result is not None
    assert result["code"] == "unknown_tool"
    assert _tool_paths(seen) == []


@pytest.mark.asyncio
async def test_platform_timeout_is_bounded_and_does_not_hang() -> None:
    started = asyncio.Event()

    class _HangTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            started.set()
            await asyncio.Event().wait()
            return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(
        transport=_HangTransport(),
        base_url="http://platform.test",
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=0.05)
        result = await client.invoke(
            session_id="room-timeout",
            tool_name="create_appointment",
            arguments={"day": "2026-09-02"},
        )

    assert started.is_set()
    assert result is not None
    assert result["status"] == "error"
    assert result["code"] == "retryable_transport"
    assert "HTTP" not in result["customer_message"]


@pytest.mark.asyncio
async def test_duplicate_marker_invokes_platform_once() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/tool-invocations"):
            return httpx.Response(
                200,
                json={"invocation_id": str(uuid4()), "status": "ok"},
            )
        return httpx.Response(200, json={"id": str(uuid4())})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT),
            lifecycle=None,
            session_id="room-dup",
            voice_agent_instance_id=INSTANCE,
        )
        marker = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": "call-back"}
        )
        spoken = f"noted\n{marker}"
        await orchestrator.handle_assistant_final(spoken)
        await orchestrator.handle_assistant_final(spoken)

    tools = _tool_paths(seen)
    assert len(tools) == 1
    body = json.loads(tools[0].content)
    assert body["idempotency_key"] == f"room-dup:{marker}"


@pytest.mark.asyncio
async def test_availability_retries_once_create_does_not() -> None:
    counts = {"availability": 0, "create": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if not request.url.path.endswith("/tool-invocations"):
            return httpx.Response(200, json={"id": str(uuid4())})
        body = json.loads(request.content)
        if body["tool_name"] == "check_availability":
            counts["availability"] += 1
            if counts["availability"] == 1:
                return httpx.Response(503, json={"detail": "down"})
            return httpx.Response(200, json={"status": "ok", "result": {"slots": []}})
        counts["create"] += 1
        return httpx.Response(503, json={"detail": "down"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT)
        available = await client.invoke(
            session_id="room-retry",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
        created = await client.invoke(
            session_id="room-retry",
            tool_name="create_appointment",
            arguments={"phone": "13800138000"},
        )

    assert counts["availability"] == 2
    assert counts["create"] == 1
    assert available is not None
    assert available["status"] == "ok"
    assert created is not None
    assert created["status"] == "error"
    assert created["code"] == "retryable_transport"
    assert "HTTP" not in created["customer_message"]


@pytest.mark.asyncio
async def test_close_during_tool_does_not_resurrect_or_finish() -> None:
    transport = _RecordingTransport()
    transport.release_tool.clear()
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        lifecycle = CallLifecycleClient(http, TENANT)
        await lifecycle.start_from_dispatch(_metadata(), "room-close-tool")
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT),
            lifecycle=lifecycle,
            session_id="room-close-tool",
            voice_agent_instance_id=INSTANCE,
        )
        marker = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": "call-back"}
        )
        in_flight = asyncio.create_task(
            orchestrator.handle_assistant_final(f"noted\n{marker}")
        )
        await transport.tool_started.wait()
        orchestrator.mark_closed()
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        transport.release_tool.set()
        turn = await in_flight
        marker2 = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": "second"}
        )
        later = await orchestrator.handle_assistant_final(f"again\n{marker2}")

    finish_paths = [
        item.url.path
        for item in transport.requests
        if item.url.path.endswith("/finish")
    ]
    assert len(finish_paths) == 1
    assert turn.marker is not None
    assert later.marker is not None
    assert len(_tool_paths(transport.requests)) == 1


@pytest.mark.asyncio
async def test_platform_business_error_is_passed_through() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "code": "slot_unavailable",
                "message": "requested slot is taken",
                "data": {"slot_id": "s-1"},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-biz",
            tool_name="create_appointment",
            arguments={"phone": "13800138000"},
        )

    assert result == {
        "status": "error",
        "code": "slot_unavailable",
        "message": "requested slot is taken",
        "customer_message": "requested slot is taken",
        "data": {"slot_id": "s-1"},
    }


@pytest.mark.asyncio
async def test_session_trace_pairs_and_isolates_two_sessions() -> None:
    clock = FakeClock()
    first = SessionTrace(session_id="s-1", call_id="c-1", clock=clock)
    second = SessionTrace(session_id="s-2", call_id="c-2", clock=clock)
    first.mark("session_start")
    clock.advance(0.2)
    first.mark("runtime_ready")
    second.mark("session_start")
    clock.advance(0.05)
    first.mark("first_user_transcript")
    clock.advance(0.1)
    first.mark("assistant_response_start")
    first.mark("session_close")
    clock.advance(0.03)
    first.mark("finish_start")
    first.mark("finish_complete")
    clock.advance(1.0)
    second.mark("runtime_ready")

    assert first.latency_s("session_start", "runtime_ready") == pytest.approx(0.2)
    assert first.derived()["turn"] == pytest.approx(0.1)
    assert first.derived()["close_to_finish"] == pytest.approx(0.03)
    assert second.latency_s("session_start", "runtime_ready") == pytest.approx(1.18)
    assert first.timestamp("session_start") != second.timestamp("session_start")


@pytest.mark.asyncio
async def test_exception_finish_records_terminal_timing() -> None:
    clock = FakeClock()
    trace = SessionTrace(session_id="err-session", call_id="err-call", clock=clock)
    record_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            return httpx.Response(201, json={"id": str(record_id)})
        if request.url.path.endswith("/finish"):
            return httpx.Response(500, json={"detail": "down"})
        return httpx.Response(200, json={"id": str(record_id)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        client = CallLifecycleClient(http, TENANT, trace=trace)
        await client.start_from_dispatch(_metadata(), "err-session")
        clock.advance(0.4)
        trace.mark("session_close")
        clock.advance(0.05)
        await client.finish(status="failed", ended_reason="agent_error")

    assert trace.timestamp("session_start") is not None
    assert trace.timestamp("finish_start") is not None
    assert trace.timestamp("finish_complete") is not None
    assert trace.derived()["close_to_finish"] == pytest.approx(0.05)
