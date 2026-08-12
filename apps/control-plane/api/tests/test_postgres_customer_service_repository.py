"""Postgres adapter tests for CustomerServiceRepository."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from yino_platform_api.repositories.customer_services import (
    CustomerServiceVersionConflict,
)
from yino_platform_api.repositories.postgres.customer_services import (
    PostgresCustomerServiceRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare_repo() -> tuple[
    PostgresCustomerServiceRepository,
    object,
]:
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
    return PostgresCustomerServiceRepository(sessions), engine


@pytest.mark.asyncio
async def test_get_demo_instance_maps_prompt_and_voice() -> None:
    repo, engine = await _prepare_repo()
    try:
        instance = await repo.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID)
        assert instance is not None
        assert instance.platform_prompt
        assert instance.tenant_prompt
        assert instance.voice.tts_voice == "longanqian"
        assert instance.voice.preset_id == "mandarin-standard"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_wrong_tenant_returns_none() -> None:
    repo, engine = await _prepare_repo()
    try:
        missing = await repo.get(DEMO_CUSTOMER_SERVICE_ID, uuid4())
        assert missing is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_cas_increments_and_persists() -> None:
    repo, engine = await _prepare_repo()
    try:
        current = await repo.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID)
        assert current is not None
        # Reset path: save next version from whatever is stored.
        next_version = current.version + 1
        updated = current.model_copy(
            update={
                "version": next_version,
                "display_name": f"持久化客服 v{next_version}",
            }
        )
        saved = await repo.save(updated)
        assert saved.version == next_version
        assert saved.display_name == f"持久化客服 v{next_version}"

        reloaded = await repo.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID)
        assert reloaded is not None
        assert reloaded.version == next_version
        assert reloaded.display_name == f"持久化客服 v{next_version}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_stale_version_raises_conflict() -> None:
    repo, engine = await _prepare_repo()
    try:
        current = await repo.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID)
        assert current is not None
        stale = current.model_copy(
            update={
                "version": current.version + 5,
                "display_name": "should-fail",
            }
        )
        with pytest.raises(CustomerServiceVersionConflict):
            await repo.save(stale)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_inserts_new_instance_for_existing_tenant() -> None:
    repo, engine = await _prepare_repo()
    try:
        new_id = uuid4()
        created = CustomerServiceInstance.demo(
            instance_id=new_id,
            tenant_id=DEMO_TENANT_ID,
        ).model_copy(update={"display_name": "新增实例"})
        saved = await repo.save(created)
        assert saved.id == new_id
        loaded = await repo.get(new_id, DEMO_TENANT_ID)
        assert loaded is not None
        assert loaded.display_name == "新增实例"
        assert loaded.voice.tts_voice == "longanqian"
    finally:
        await engine.dispose()
