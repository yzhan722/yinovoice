from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from yino_platform_api.domain.insights_dispatch import InsightsDispatchJob
from yino_platform_api.repositories.insights_dispatch import (
    InMemoryInsightsDispatchRepository,
)


def _job(**overrides: object) -> InsightsDispatchJob:
    values: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "call_id": uuid4(),
        "profile": "demo-clinic",
        "event_id": "a" * 64,
        "body": {"schemaVersion": 1, "channel": "yino"},
        "status": "pending",
        "attempts": 0,
    }
    values.update(overrides)
    return InsightsDispatchJob.model_validate(values)


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_on_call_id() -> None:
    repo = InMemoryInsightsDispatchRepository()
    call_id = uuid4()
    first = await repo.enqueue(_job(call_id=call_id, event_id="b" * 64))
    second = await repo.enqueue(_job(call_id=call_id, event_id="c" * 64))

    assert first.id == second.id
    assert second.event_id == first.event_id
    assert len(repo.all()) == 1


@pytest.mark.asyncio
async def test_claim_due_skips_future_and_non_pending() -> None:
    repo = InMemoryInsightsDispatchRepository()
    now = datetime(2026, 8, 25, 3, 0, 0, tzinfo=UTC)
    future = await repo.enqueue(
        _job(next_attempt_at=now + timedelta(seconds=30))
    )
    sent = await repo.enqueue(_job())
    await repo.mark_sent(sent.id)
    due = await repo.enqueue(_job())

    claimed = await repo.claim_due(now)
    assert claimed is not None
    assert claimed.id == due.id

    later = await repo.claim_due(now + timedelta(seconds=31))
    assert later is not None
    assert later.id == future.id
