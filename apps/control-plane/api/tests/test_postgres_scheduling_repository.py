"""Postgres adapter tests for SchedulingRepository."""

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
from yino_platform_api.domain.scheduling import SchedulingProfileUpdate, ServiceOfferingCreate
from yino_platform_api.repositories.postgres.scheduling import (
    PostgresSchedulingRepository,
)
from yino_platform_api.repositories.scheduling import (
    hours_from_writes,
    new_offering,
    profile_from_update,
)
from yino_platform_api.domain.scheduling import BusinessHoursWrite

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare_repo() -> tuple[PostgresSchedulingRepository, object]:
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
    return PostgresSchedulingRepository(sessions), engine


@pytest.mark.asyncio
async def test_postgres_scheduling_round_trip() -> None:
    repo, engine = await _prepare_repo()
    try:
        offering = await repo.create_offering(
            new_offering(
                DEMO_TENANT_ID,
                ServiceOfferingCreate(
                    voice_agent_instance_id=DEMO_CUSTOMER_SERVICE_ID,
                    name="洁牙",
                    duration_minutes=30,
                ),
            )
        )
        loaded = await repo.get_offering(offering.id, DEMO_TENANT_ID)
        assert loaded is not None
        assert loaded.name == "洁牙"
        profile = await repo.upsert_profile(
            profile_from_update(
                DEMO_TENANT_ID,
                DEMO_CUSTOMER_SERVICE_ID,
                SchedulingProfileUpdate(timezone="Australia/Melbourne"),
            )
        )
        assert profile.timezone == "Australia/Melbourne"
        hours = await repo.replace_hours(
            DEMO_TENANT_ID,
            DEMO_CUSTOMER_SERVICE_ID,
            hours_from_writes(
                DEMO_TENANT_ID,
                DEMO_CUSTOMER_SERVICE_ID,
                [
                    BusinessHoursWrite(
                        weekday=1, start_local="09:00", end_local="12:00"
                    )
                ],
            ),
        )
        assert len(hours) == 1
        listed = await repo.list_hours(DEMO_TENANT_ID, DEMO_CUSTOMER_SERVICE_ID)
        assert listed[0].start_local == "09:00"
    finally:
        await engine.dispose()
