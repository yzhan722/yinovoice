"""Postgres adapter tests for InsightsDispatchRepository."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.customer_service import DEMO_TENANT_ID
from yino_platform_api.domain.insights_dispatch import InsightsDispatchJob
from yino_platform_api.repositories.postgres.insights_dispatch import (
    PostgresInsightsDispatchRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


def _job(**overrides: object) -> InsightsDispatchJob:
    values: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": DEMO_TENANT_ID,
        "call_id": uuid4(),
        "profile": "demo-clinic",
        "event_id": "a" * 64,
        "body": {"schemaVersion": 1, "channel": "yino"},
        "status": "pending",
        "attempts": 0,
    }
    values.update(overrides)
    return InsightsDispatchJob.model_validate(values)


async def _prepare_repo() -> tuple[PostgresInsightsDispatchRepository, object]:
    database_url = os.environ["DATABASE_URL"]
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PLATFORM_API_ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    engine = create_db_engine(database_url)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        await ensure_demo_seed(session)
    return PostgresInsightsDispatchRepository(sessions), engine


@pytest.mark.asyncio
async def test_postgres_enqueue_is_idempotent_on_call_id() -> None:
    repo, engine = await _prepare_repo()
    try:
        call_id = uuid4()
        first = await repo.enqueue(_job(call_id=call_id))
        second = await repo.enqueue(_job(call_id=call_id, event_id="b" * 64))
        assert first.id == second.id
        assert second.event_id == first.event_id
        await repo.mark_sent(first.id)
    finally:
        await engine.dispose()
