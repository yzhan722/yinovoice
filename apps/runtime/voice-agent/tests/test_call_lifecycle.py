from __future__ import annotations

import asyncio
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


def _finish_counting_client() -> tuple[
    CallLifecycleClient, dict[str, object], httpx.AsyncClient
]:
    record_id = uuid4()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/start"):
            return httpx.Response(201, json={"id": str(record_id)})
        if request.url.path.endswith("/finish"):
            return httpx.Response(
                200,
                json={"id": str(record_id), "status": "completed"},
            )
        return httpx.Response(200, json={"id": str(record_id)})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://platform.test")
    client = CallLifecycleClient(
        http,
        UUID("00000000-0000-0000-0000-000000000001"),
    )
    return client, {"record_id": record_id, "seen": seen}, http


@pytest.mark.asyncio
async def test_concurrent_finish_callers_send_one_http() -> None:
    client, state, http = _finish_counting_client()
    seen: list[httpx.Request] = state["seen"]  # type: ignore[assignment]
    async with http:
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        await asyncio.gather(
            client.finish(status="completed", ended_reason="user_hangup"),
            client.finish(status="completed", ended_reason="completed"),
            client.finish(status="failed", ended_reason="agent_error"),
        )

    finish_requests = [item for item in seen if item.url.path.endswith("/finish")]
    assert len(finish_requests) == 1
    body = json.loads(finish_requests[0].content)
    assert body["status"] == "failed"
    assert body["ended_reason"] == "agent_error"


@pytest.mark.asyncio
async def test_finish_includes_accumulated_usage() -> None:
    client, state, http = _finish_counting_client()
    seen: list[httpx.Request] = state["seen"]  # type: ignore[assignment]
    async with http:
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        client.record_usage(
            {
                "type": "response.done",
                "response": {
                    "usage": {
                        "total_tokens": 20,
                        "input_tokens": 12,
                        "output_tokens": 8,
                        "input_tokens_details": {
                            "text_tokens": 4,
                            "audio_tokens": 8,
                        },
                        "output_tokens_details": {
                            "text_tokens": 1,
                            "audio_tokens": 7,
                        },
                    }
                },
            }
        )
        await client.finish(status="completed", ended_reason="completed")

    finish_requests = [item for item in seen if item.url.path.endswith("/finish")]
    body = json.loads(finish_requests[0].content)
    assert body["usage"]["total_tokens"] == 20
    assert body["usage"]["input_audio_tokens"] == 8
    assert body["usage"]["response_count"] == 1


@pytest.mark.asyncio
async def test_second_finish_does_not_overwrite_committed_agent_error() -> None:
    client, state, http = _finish_counting_client()
    seen: list[httpx.Request] = state["seen"]  # type: ignore[assignment]
    async with http:
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        await client.finish(status="failed", ended_reason="agent_error")
        await client.finish(status="completed", ended_reason="user_hangup")

    finish_requests = [item for item in seen if item.url.path.endswith("/finish")]
    assert len(finish_requests) == 1
    body = json.loads(finish_requests[0].content)
    assert body["status"] == "failed"
    assert body["ended_reason"] == "agent_error"


_FINISH_INTERLEAVINGS: tuple[tuple[tuple[str, str], ...], ...] = (
    (
        ("completed", "user_hangup"),
        ("completed", "completed"),
        ("failed", "agent_error"),
    ),
    (
        ("completed", "completed"),
        ("failed", "agent_error"),
        ("completed", "user_hangup"),
    ),
    (
        ("failed", "agent_error"),
        ("completed", "user_hangup"),
        ("completed", "completed"),
    ),
    (
        ("completed", "user_hangup"),
        ("failed", "agent_error"),
        ("completed", "completed"),
    ),
)


class _GatedFinishTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, fail_finish: bool = False) -> None:
        self.record_id = uuid4()
        self.finish_started = asyncio.Event()
        self.release_finish = asyncio.Event()
        self.finish_requests: list[httpx.Request] = []
        self.fail_finish = fail_finish

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(201, json={"id": str(self.record_id)})
        if path.endswith("/finish"):
            self.finish_requests.append(request)
            self.finish_started.set()
            await self.release_finish.wait()
            if self.fail_finish:
                return httpx.Response(500, json={"detail": "down"})
            return httpx.Response(
                200,
                json={"id": str(self.record_id), "status": "completed"},
            )
        return httpx.Response(200, json={"id": str(self.record_id)})


@pytest.mark.asyncio
@pytest.mark.parametrize("outcomes", _FINISH_INTERLEAVINGS)
async def test_interleaved_finish_outcomes_send_one_http(
    outcomes: tuple[tuple[str, str], ...],
) -> None:
    client, state, http = _finish_counting_client()
    seen: list[httpx.Request] = state["seen"]  # type: ignore[assignment]
    async with http:
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        await asyncio.gather(
            *[
                client.finish(status=status, ended_reason=reason)
                for status, reason in outcomes
            ]
        )

    finish_requests = [item for item in seen if item.url.path.endswith("/finish")]
    assert len(finish_requests) == 1
    body = json.loads(finish_requests[0].content)
    assert body["status"] == "failed"
    assert body["ended_reason"] == "agent_error"


@pytest.mark.asyncio
async def test_cancelled_finish_caller_does_not_deadlock_or_double_http() -> None:
    transport = _GatedFinishTransport()
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://platform.test",
    ) as http:
        client = CallLifecycleClient(
            http, UUID("00000000-0000-0000-0000-000000000001")
        )
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        blocked = asyncio.create_task(
            client.finish(status="completed", ended_reason="user_hangup")
        )
        await transport.finish_started.wait()
        blocked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked
        transport.release_finish.set()
        await client.finish(status="failed", ended_reason="agent_error")

    assert len(transport.finish_requests) == 1
    assert client._finish_committed is True
    assert client._finish_http_started is True


@pytest.mark.asyncio
async def test_finish_http_failure_does_not_retry_on_second_caller() -> None:
    record_id = uuid4()
    finish_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            return httpx.Response(201, json={"id": str(record_id)})
        if request.url.path.endswith("/finish"):
            finish_count["n"] += 1
            return httpx.Response(500, json={"detail": "down"})
        return httpx.Response(200, json={"id": str(record_id)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://platform.test",
    ) as http:
        client = CallLifecycleClient(
            http, UUID("00000000-0000-0000-0000-000000000001")
        )
        await client.start_from_dispatch(_metadata(), "sip-room-1")
        await client.finish(status="completed", ended_reason="user_hangup")
        await client.finish(status="failed", ended_reason="agent_error")

    assert finish_count["n"] == 1
    assert client._finish_committed is True

