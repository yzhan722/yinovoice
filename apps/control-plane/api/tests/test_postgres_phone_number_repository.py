"""Postgres adapter tests for PhoneNumberRepository."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)
from yino_platform_api.domain.phone_number import PhoneNumberCreate
from yino_platform_api.repositories.phone_numbers import PhoneNumberConflict
from yino_platform_api.repositories.postgres.phone_numbers import (
    PostgresPhoneNumberRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare_repo() -> tuple[PostgresPhoneNumberRepository, object]:
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
    return PostgresPhoneNumberRepository(sessions), engine


@pytest.mark.asyncio
async def test_postgres_phone_number_round_trip_and_unique_e164() -> None:
    repo, engine = await _prepare_repo()
    try:
        created = await repo.create(
            DEMO_TENANT_ID,
            PhoneNumberCreate(
                e164_number="+61400999001",
                voice_agent_instance_id=DEMO_CUSTOMER_SERVICE_ID,
            ),
        )
        loaded = await repo.get_by_e164("+61400999001")
        assert loaded is not None
        assert loaded.id == created.id
        with pytest.raises(PhoneNumberConflict):
            await repo.create(
                DEMO_TENANT_ID,
                PhoneNumberCreate(
                    e164_number="+61400999001",
                    voice_agent_instance_id=DEMO_CUSTOMER_SERVICE_ID,
                ),
            )
        assert await repo.delete(created.id, DEMO_TENANT_ID) is True
    finally:
        await engine.dispose()
