from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from yino_platform_api.domain.insights_dispatch import InsightsDispatchJob
from yino_platform_api.repositories.insights_dispatch import (
    InMemoryInsightsDispatchRepository,
)
from yino_platform_api.services.insights_http import drain_once, post_ended_call


def _job(**overrides: object) -> InsightsDispatchJob:
    values: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "call_id": uuid4(),
        "profile": "demo-clinic",
        "event_id": "a" * 64,
        "body": {
            "schemaVersion": 1,
            "channel": "yino",
            "callId": str(uuid4()),
        },
        "status": "pending",
        "attempts": 0,
    }
    values.update(overrides)
    return InsightsDispatchJob.model_validate(values)


@pytest.mark.asyncio
async def test_post_ended_call_maps_status_codes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer ingest-token"
        assert str(request.url).endswith("/v1/ingest/demo-clinic")
        return httpx.Response(202, json={"status": "accepted"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        assert (
            await post_ended_call(
                base_url="https://calls.example.test",
                token="ingest-token",
                profile="demo-clinic",
                body={"schemaVersion": 1},
                transport=client,
            )
            == "ok"
        )


@pytest.mark.asyncio
async def test_drain_marks_sent_retry_and_failed() -> None:
    now = datetime(2026, 8, 25, 4, 0, 0, tzinfo=UTC)

    async def ok_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"status": "accepted"})

    repo = InMemoryInsightsDispatchRepository()
    sent_job = await repo.enqueue(_job())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(ok_handler)
    ) as client:
        assert (
            await drain_once(
                repo,
                now=now,
                base_url="https://calls.example.test",
                token="token",
                transport=client,
            )
            == "ok"
        )
    assert repo.all()[0].id == sent_job.id
    assert repo.all()[0].status == "sent"

    async def server_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    retry_repo = InMemoryInsightsDispatchRepository()
    await retry_repo.enqueue(_job())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server_error)
    ) as client:
        assert (
            await drain_once(
                retry_repo,
                now=now,
                base_url="https://calls.example.test",
                token="token",
                transport=client,
            )
            == "retry"
        )
    retried = retry_repo.all()[0]
    assert retried.status == "pending"
    assert retried.attempts == 1
    assert retried.next_attempt_at == now + timedelta(seconds=10)
    assert await retry_repo.claim_due(now) is None

    async def not_found(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "unknown profile"})

    fail_repo = InMemoryInsightsDispatchRepository()
    await fail_repo.enqueue(_job())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(not_found)
    ) as client:
        assert (
            await drain_once(
                fail_repo,
                now=now,
                base_url="https://calls.example.test",
                token="token",
                transport=client,
            )
            == "fail"
        )
    assert fail_repo.all()[0].status == "failed"
