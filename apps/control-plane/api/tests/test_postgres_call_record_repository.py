"""Postgres adapter tests for CallRecordRepository."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.call_record import CallRecord, TranscriptMessage
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)
from yino_platform_api.repositories.postgres.call_records import (
    PostgresCallRecordRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare_repo() -> tuple[PostgresCallRecordRepository, object]:
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
    return PostgresCallRecordRepository(sessions), engine


def _record(
    *,
    record_id=None,
    tenant_id=DEMO_TENANT_ID,
    customer_service_id=DEMO_CUSTOMER_SERVICE_ID,
    messages: list[TranscriptMessage] | None = None,
    created_at: datetime | None = None,
    room_name: str = "room-demo",
) -> CallRecord:
    started = datetime(2026, 8, 11, 6, 0, tzinfo=UTC)
    return CallRecord(
        id=record_id or uuid4(),
        tenant_id=tenant_id,
        customer_service_id=customer_service_id,
        room_name=room_name,
        status="completed",
        started_at=started,
        ended_at=started + timedelta(seconds=30),
        duration_sec=30,
        direction="web",
        messages=messages or [],
        created_at=created_at or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_save_and_get_preserves_message_order() -> None:
    repo, engine = await _prepare_repo()
    try:
        record = _record(
            messages=[
                TranscriptMessage(role="user", text="你好", sequence=0),
                TranscriptMessage(role="assistant", text="您好", sequence=1),
            ]
        )
        saved = await repo.save(record)
        loaded = await repo.get(saved.id, DEMO_TENANT_ID)
        assert loaded is not None
        assert [message.sequence for message in loaded.messages] == [0, 1]
        assert loaded.messages[0].text == "你好"
        assert loaded.messages[1].text == "您好"
        assert loaded.customer_service_id == DEMO_CUSTOMER_SERVICE_ID
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_replaces_messages_instead_of_appending() -> None:
    repo, engine = await _prepare_repo()
    try:
        record_id = uuid4()
        await repo.save(
            _record(
                record_id=record_id,
                messages=[
                    TranscriptMessage(role="user", text="第一句", sequence=0),
                    TranscriptMessage(role="assistant", text="第二句", sequence=1),
                ],
            )
        )
        await repo.save(
            _record(
                record_id=record_id,
                messages=[
                    TranscriptMessage(role="user", text="只留一句", sequence=0),
                ],
            )
        )
        loaded = await repo.get(record_id, DEMO_TENANT_ID)
        assert loaded is not None
        assert len(loaded.messages) == 1
        assert loaded.messages[0].text == "只留一句"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_for_tenant_orders_and_counts() -> None:
    repo, engine = await _prepare_repo()
    try:
        older = _record(
            room_name="older",
            created_at=datetime(2026, 8, 11, 1, 0, tzinfo=UTC),
        )
        newer = _record(
            room_name="newer",
            created_at=datetime(2026, 8, 11, 2, 0, tzinfo=UTC),
        )
        await repo.save(older)
        await repo.save(newer)

        page, total = await repo.list_for_tenant(
            DEMO_TENANT_ID, limit=1000, offset=0
        )
        assert total >= 2
        demo_page = [item for item in page if item.id in {older.id, newer.id}]
        assert [item.room_name for item in demo_page] == ["newer", "older"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_wrong_tenant_returns_none() -> None:
    repo, engine = await _prepare_repo()
    try:
        saved = await repo.save(_record())
        missing = await repo.get(saved.id, uuid4())
        assert missing is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_rejects_unknown_instance_foreign_key() -> None:
    repo, engine = await _prepare_repo()
    try:
        with pytest.raises(IntegrityError):
            await repo.save(
                _record(customer_service_id=uuid4(), room_name="bad-fk")
            )
    finally:
        await engine.dispose()
