"""Postgres adapter tests for config revisions and knowledge documents."""

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
from yino_platform_api.domain.knowledge import KnowledgeDocumentCreate
from yino_platform_api.repositories.config_revisions import record_snapshot
from yino_platform_api.repositories.postgres.config_revisions import (
    PostgresConfigRevisionRepository,
)
from yino_platform_api.repositories.postgres.customer_services import (
    PostgresCustomerServiceRepository,
)
from yino_platform_api.repositories.postgres.knowledge import (
    PostgresKnowledgeRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare():
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
    return sessions, engine


@pytest.mark.asyncio
async def test_postgres_revision_and_knowledge_round_trip() -> None:
    sessions, engine = await _prepare()
    try:
        instances = PostgresCustomerServiceRepository(sessions)
        revisions = PostgresConfigRevisionRepository(sessions)
        knowledge = PostgresKnowledgeRepository(sessions)
        instance = await instances.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID)
        assert instance is not None
        recorded = await record_snapshot(revisions, instance, "publish")
        loaded = await revisions.get_by_revision(
            DEMO_TENANT_ID, DEMO_CUSTOMER_SERVICE_ID, recorded.revision
        )
        assert loaded is not None
        assert loaded.snapshot["display_name"] == instance.display_name

        document = await knowledge.create(
            DEMO_TENANT_ID,
            DEMO_CUSTOMER_SERVICE_ID,
            KnowledgeDocumentCreate(title="合成热线", body="400-000-0000"),
        )
        listed = await knowledge.list_for_instance(
            DEMO_TENANT_ID, DEMO_CUSTOMER_SERVICE_ID
        )
        assert any(item.id == document.id for item in listed)
        assert await knowledge.delete(
            document.id, DEMO_TENANT_ID, DEMO_CUSTOMER_SERVICE_ID
        )
    finally:
        await engine.dispose()
