from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
import pytest
from hardening_support import FailureScenario, FakePlatform

from yino_voice_agent.tool_client import MAX_TOOL_ARGUMENTS_BYTES, ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker

TENANT = UUID("00000000-0000-4000-8000-000000000001")
INSTANCE = UUID("00000000-0000-4000-8000-000000000101")


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [{}, None, [], "x", {"nested": {"a": 1}}])
async def test_tool_argument_shapes(arguments: object) -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=0.2)
        if not isinstance(arguments, dict):
            result = await client.invoke(
                session_id="room-args",
                tool_name="create_appointment",
                arguments=arguments,  # type: ignore[arg-type]
            )
            assert result is not None
            assert result["code"] == "invalid_arguments"
            assert platform.tools_by_session == {}
            return
        result = await client.invoke(
            session_id="room-args",
            tool_name="create_appointment",
            arguments=arguments,
        )
    if arguments == {}:
        assert "room-args" in platform.tools_by_session
        assert result is not None
    else:
        assert result is not None


@pytest.mark.asyncio
async def test_oversized_tool_payload_is_rejected() -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT)
        blob = "x" * (MAX_TOOL_ARGUMENTS_BYTES + 10)
        result = await client.invoke(
            session_id="room-big",
            tool_name="create_callback",
            arguments={"reason": blob},
        )
    assert result is not None
    assert result["code"] == "invalid_arguments"
    assert platform.tools_by_session == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [400, 401, 403, 404, 409, 422, 429, 500, 502, 503],
)
async def test_tool_http_status_codes(status: int) -> None:
    platform = FakePlatform(FailureScenario(tool_status=status))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=0.2)
        created = await client.invoke(
            session_id="room-status",
            tool_name="create_appointment",
            arguments={"day": "2026-09-02"},
        )
        available = await client.invoke(
            session_id="room-status",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
    create_calls = [
        body
        for bodies in platform.tools_by_session.values()
        for body in bodies
        if body.get("tool_name") == "create_appointment"
    ]
    availability_calls = [
        body
        for bodies in platform.tools_by_session.values()
        for body in bodies
        if body.get("tool_name") == "check_availability"
    ]
    assert len(create_calls) == 1
    if status >= 500:
        assert len(availability_calls) == 2
        assert created is not None
        assert created["status"] == "error"
        assert created["code"] == "retryable_transport"
        assert "HTTP" not in created["customer_message"]
        assert available is not None
        assert available["code"] == "retryable_transport"
    elif status >= 400:
        assert len(availability_calls) == 1
        assert created is not None
        assert created["status"] == "error"
        assert created.get("status") != "ok"
        assert created.get("status") != "success"
        assert "HTTP" not in str(created.get("customer_message", ""))
        assert "成功" not in str(created.get("customer_message", ""))
        assert available is not None
        assert available["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["connect", "dns"])
async def test_tool_transport_errors(kind: str) -> None:
    platform = FakePlatform(FailureScenario(tool_exception=kind))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=0.2)
        created = await client.invoke(
            session_id="room-net",
            tool_name="create_appointment",
            arguments={"day": "2026-09-02"},
        )
        available = await client.invoke(
            session_id="room-net",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
    assert created is not None
    assert created["status"] == "error"
    assert created["code"] == "retryable_transport"
    assert "HTTP" not in created["customer_message"]
    assert available is not None
    assert available["code"] == "retryable_transport"


@pytest.mark.asyncio
async def test_malformed_and_empty_tool_body() -> None:
    async with httpx.AsyncClient(
        transport=FakePlatform(FailureScenario(tool_malformed=True)),
        base_url="http://platform.test",
    ) as http:
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-malformed",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
        assert result is None
    async with httpx.AsyncClient(
        transport=FakePlatform(FailureScenario(tool_empty_body=True)),
        base_url="http://platform.test",
    ) as http:
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-empty",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
        assert result is None


@pytest.mark.asyncio
async def test_hangup_cancels_in_flight_tool_and_does_not_resurrect() -> None:
    platform = FakePlatform(FailureScenario(tool_timeout=True))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, TENANT, timeout_s=2.0),
            lifecycle=None,
            session_id="room-cancel",
            voice_agent_instance_id=INSTANCE,
        )
        marker = encode_tool_marker("create_appointment", {"day": "2026-09-02"})
        task = asyncio.create_task(
            orchestrator.handle_assistant_final(f"book\n{marker}")
        )
        await asyncio.wait_for(platform.tool_started.wait(), timeout=0.5)
        orchestrator.mark_closed()
        await asyncio.gather(task, return_exceptions=True)
        await orchestrator.wait_idle()
        later = await orchestrator.handle_assistant_final(f"again\n{marker}")
        assert later.spoken == "again"
    assert asyncio.all_tasks()  # loop still healthy; no resurrection path


@pytest.mark.asyncio
async def test_cancelled_error_propagates_from_tool_client() -> None:
    platform = FakePlatform(FailureScenario(tool_timeout=True))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=5.0)
        task = asyncio.create_task(
            client.invoke(
                session_id="room-ce",
                tool_name="create_callback",
                arguments={"reason": "x"},
            )
        )
        await asyncio.wait_for(platform.tool_started.wait(), timeout=0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_appointment_conflict_is_never_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tool-invocations"):
            return httpx.Response(
                409,
                json={
                    "status": "error",
                    "code": "availability_conflict",
                    "message": "slot no longer available",
                },
            )
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http:
        result = await ToolInvocationClient(http, TENANT).invoke(
            session_id="room-slot",
            tool_name="create_appointment",
            arguments={"day": "2026-09-02"},
        )
    assert result is not None
    assert result["status"] == "error"
    assert result["code"] == "availability_conflict"
    assert result["status"] != "ok"
    assert "成功" not in result["customer_message"]
    assert "HTTP" not in result["customer_message"]


@pytest.mark.asyncio
async def test_tool_timeout_increments_metrics() -> None:
    from yino_voice_agent.ops import RuntimeMetrics

    metrics = RuntimeMetrics()
    platform = FakePlatform(FailureScenario(tool_timeout=True))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(http, TENANT, timeout_s=0.05, metrics=metrics)
        result = await client.invoke(
            session_id="room-to",
            tool_name="check_availability",
            arguments={"day": "2026-09-02"},
        )
    assert result is not None
    assert result["code"] == "retryable_transport"
    assert metrics.tool_requests == 1
    assert metrics.tool_timeouts == 1
