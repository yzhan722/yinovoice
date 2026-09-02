from __future__ import annotations

import json
from uuid import UUID, uuid4

import httpx
import pytest

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker


@pytest.mark.asyncio
async def test_orchestrator_strips_marker_posts_tool_and_transcript() -> None:
    record_id = uuid4()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/start"):
            return httpx.Response(201, json={"id": str(record_id)})
        if request.url.path.endswith("/tool-invocations"):
            return httpx.Response(
                200,
                json={
                    "invocation_id": str(uuid4()),
                    "status": "ok",
                    "tool_name": "create_callback",
                    "result": {"callback_task_id": str(uuid4())},
                },
            )
        return httpx.Response(200, json={"id": str(record_id)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        lifecycle = CallLifecycleClient(http, tenant_id)
        await lifecycle.start_from_dispatch(
            __import__(
                "yino_voice_agent.runtime_config", fromlist=["DispatchMetadata"]
            ).DispatchMetadata.from_json(
                json.dumps(
                    {
                        "customer_service_id": "00000000-0000-0000-0000-000000000101",
                        "tenant_id": str(tenant_id),
                        "config_version": 1,
                    }
                )
            ),
            "sip-room-tools",
        )
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, tenant_id),
            lifecycle=lifecycle,
            session_id="sip-room-tools",
            voice_agent_instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        )
        marker = encode_tool_marker(
            "create_callback",
            {"phone": "13800138000", "reason": "要求回电"},
        )
        turn = await orchestrator.handle_assistant_final(
            f"已记下您的回拨意向。\n{marker}"
        )
        assert turn.spoken == "已记下您的回拨意向。"
        assert turn.marker is not None

    paths = [request.url.path for request in seen]
    assert "/api/v1/tool-invocations" in paths
    message = next(
        request for request in seen if request.url.path.endswith("/messages")
    )
    body = json.loads(message.content)
    assert body["text"] == "已记下您的回拨意向。"
    assert "[[tool:" not in body["text"]


@pytest.mark.asyncio
async def test_tool_http_failure_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "down"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        client = ToolInvocationClient(
            http, UUID("00000000-0000-0000-0000-000000000001")
        )
        result = await client.invoke(
            session_id="room",
            tool_name="create_callback",
            arguments={"phone": "13800138000"},
        )
    assert result is not None
    assert result["status"] == "error"
    assert result["code"] == "retryable_transport"
    assert "503" not in result["customer_message"]
    assert "HTTP" not in result["customer_message"]
