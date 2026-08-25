from __future__ import annotations

import json
from uuid import UUID, uuid4

import httpx
import pytest

from yino_voice_agent.call_lifecycle import (
    CallLifecycleClient,
    direction_for_channel,
)
from yino_voice_agent.runtime_config import DispatchMetadata


def _metadata(**overrides: object) -> DispatchMetadata:
    payload = {
        "customer_service_id": "00000000-0000-0000-0000-000000000101",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "config_version": 1,
        "channel": "sip",
        "caller_number": "+61400000001",
        "callee_number": "+61400000099",
        "provider_call_id": "livekit-sip-1",
    }
    payload.update(overrides)
    return DispatchMetadata.from_json(json.dumps(payload))


def test_sip_channel_maps_to_inbound_direction() -> None:
    assert direction_for_channel("sip") == "inbound"
    assert direction_for_channel("web") == "web"


@pytest.mark.asyncio
async def test_start_posts_inbound_session_payload() -> None:
    record_id = uuid4()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            201,
            json={
                "id": str(record_id),
                "status": "in_progress",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://platform.test",
    ) as http:
        client = CallLifecycleClient(
            http,
            UUID("00000000-0000-0000-0000-000000000001"),
        )
        await client.start_from_dispatch(_metadata(), "sip-room-1")

    assert client.record_id == record_id
    assert len(seen) == 1
    assert seen[0].url.path == "/api/v1/call-sessions/start"
    assert seen[0].headers["x-tenant-id"] == "00000000-0000-0000-0000-000000000001"
    body = json.loads(seen[0].content)
    assert body["direction"] == "inbound"
    assert body["room_name"] == "sip-room-1"
    assert body["caller_number"] == "+61400000001"
    assert body["callee_number"] == "+61400000099"
    assert body["provider_call_id"] == "livekit-sip-1"


@pytest.mark.asyncio
async def test_messages_buffer_until_start_then_flush() -> None:
    record_id = uuid4()
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/start"):
            return httpx.Response(201, json={"id": str(record_id)})
        return httpx.Response(200, json={"id": str(record_id)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://platform.test",
    ) as http:
        client = CallLifecycleClient(
            http,
            UUID("00000000-0000-0000-0000-000000000001"),
        )
        await client.append_final("user", "你好", 1)
        await client.start_from_dispatch(_metadata(), "sip-room-1")

    assert paths == [
        "/api/v1/call-sessions/start",
        f"/api/v1/call-sessions/{record_id}/messages",
    ]


@pytest.mark.asyncio
async def test_start_failure_does_not_raise_and_finish_retries_once() -> None:
    record_id = uuid4()
    attempts = {"start": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            attempts["start"] += 1
            if attempts["start"] == 1:
                return httpx.Response(503, json={"detail": "down"})
            return httpx.Response(201, json={"id": str(record_id)})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"id": str(record_id)})
        if request.url.path.endswith("/finish"):
            return httpx.Response(
                200,
                json={"id": str(record_id), "status": "completed"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://platform.test",
    ) as http:
        client = CallLifecycleClient(
            http,
            UUID("00000000-0000-0000-0000-000000000001"),
        )
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        assert client.record_id is None
        await client.append_final("user", "你好", 1)
        await client.finish(status="completed", ended_reason="completed")

    assert attempts["start"] == 2
    assert client.record_id == record_id
