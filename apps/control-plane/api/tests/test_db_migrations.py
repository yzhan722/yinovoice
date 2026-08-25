"""Smoke tests for Alembic upgrade and demo seed."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select, text

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.models import Tenant, VoiceAgentInstance
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_upgrade_and_seed_demo_tenant() -> None:
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
    try:
        async with sessions() as session:
            await ensure_demo_seed(session)

        async with sessions() as session:
            tenant = await session.get(Tenant, DEMO_TENANT_ID)
            assert tenant is not None
            assert tenant.name == "Demo Tenant"
            assert tenant.home_region == "cn-mainland"

            instance = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == DEMO_TENANT_ID,
                    VoiceAgentInstance.id == DEMO_CUSTOMER_SERVICE_ID,
                )
            )
            assert instance is not None
            assert instance.display_name
            assert instance.voice_config["tts_voice"] == "longanqian"
            assert instance.platform_prompt
            assert instance.tenant_prompt

            for table_name in (
                "tenants",
                "agent_template_versions",
                "voice_agent_instances",
                "call_records",
                "call_messages",
                "insights_dispatch_jobs",
                "instance_config_revisions",
                "knowledge_documents",
            ):
                exists = await session.scalar(
                    text("SELECT to_regclass(:name)").bindparams(
                        name=f"public.{table_name}"
                    )
                )
                assert exists is not None, table_name
    finally:
        await engine.dispose()
