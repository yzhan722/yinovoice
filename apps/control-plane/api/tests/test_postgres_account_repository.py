"""Postgres adapter tests for user accounts and tenants."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from yino_platform_api.db.engine import create_db_engine, create_session_factory
from yino_platform_api.db.seed import ensure_demo_seed
from yino_platform_api.domain.account import TenantCreate, UserAccountCreate
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)
from yino_platform_api.repositories.accounts import AccountConflict, TenantConflict
from yino_platform_api.repositories.postgres.accounts import (
    PostgresTenantRepository,
    PostgresUserAccountRepository,
)
from yino_platform_api.services.passwords import hash_password, verify_password

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


async def _prepare() -> tuple[
    PostgresUserAccountRepository, PostgresTenantRepository, object
]:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PLATFORM_API_ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    engine = create_db_engine(os.environ["DATABASE_URL"])
    sessions = create_session_factory(engine)
    async with sessions() as session:
        await ensure_demo_seed(session)
    return (
        PostgresUserAccountRepository(sessions),
        PostgresTenantRepository(sessions),
        engine,
    )


@pytest.mark.asyncio
async def test_reassigning_an_instance_carries_its_child_rows() -> None:
    """Migration 20260906_0014 makes the instance foreign keys cascade."""
    from datetime import UTC, datetime

    from sqlalchemy import text

    from yino_platform_api.domain.call_record import CallRecordCreate
    from yino_platform_api.repositories.postgres.call_records import (
        PostgresCallRecordRepository,
    )
    from yino_platform_api.repositories.postgres.customer_services import (
        PostgresCustomerServiceRepository,
    )

    users, tenants, engine = await _prepare()
    sessions = users._sessions  # same factory, already migrated and seeded
    services = PostgresCustomerServiceRepository(sessions)
    calls = PostgresCallRecordRepository(sessions)
    try:
        target = await tenants.create(
            TenantCreate(id=uuid4(), name="Move Target", home_region="ap-southeast")
        )
        started = datetime.now(UTC)
        record = await calls.create(
            DEMO_TENANT_ID,
            CallRecordCreate(
                customer_service_id=DEMO_CUSTOMER_SERVICE_ID,
                room_name=f"move-{uuid4().hex[:8]}",
                status="completed",
                started_at=started,
                ended_at=started,
                duration_sec=1,
                direction="web",
                messages=[{"role": "user", "text": "hello", "sequence": 0}],
            ),
        )

        moved = await services.reassign_tenant(
            DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID, target.id
        )
        assert moved is not None
        assert moved.tenant_id == target.id

        async with sessions() as session:
            call_tenant = await session.scalar(
                text("select tenant_id from call_records where id = :i").bindparams(
                    i=record.id
                )
            )
            assert call_tenant == target.id
            knowledge = await session.scalar(
                text(
                    "select count(*) from knowledge_documents "
                    "where instance_id = :i and tenant_id <> :t"
                ).bindparams(i=DEMO_CUSTOMER_SERVICE_ID, t=target.id)
            )
            assert knowledge == 0
        assert await services.get(DEMO_CUSTOMER_SERVICE_ID, DEMO_TENANT_ID) is None
        assert await services.get(DEMO_CUSTOMER_SERVICE_ID, target.id) is not None

        # Put it back so repeated runs start from the seeded state.
        await services.reassign_tenant(
            DEMO_CUSTOMER_SERVICE_ID, target.id, DEMO_TENANT_ID
        )
        await calls.hard_delete(record.id, DEMO_TENANT_ID)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_accounts_roundtrip_case_insensitive_and_tenant_create() -> None:
    users, tenants, engine = await _prepare()
    try:
        account = f"pg-{uuid4().hex[:10]}"
        created = await users.create(
            UserAccountCreate(
                tenant_id=DEMO_TENANT_ID,
                account=account,
                password="initial-pass",
                nickname="PG 测试",
            ),
            hash_password("initial-pass"),
        )
        assert created.role == "tenant_operator"
        assert created.status == "active"

        found = await users.get_by_account(account.upper())
        assert found is not None
        user, stored_hash = found
        assert user.id == created.id
        assert verify_password("initial-pass", stored_hash)

        with pytest.raises(AccountConflict):
            await users.create(
                UserAccountCreate(
                    tenant_id=DEMO_TENANT_ID,
                    account=account.upper(),
                    password="whatever-pass",
                ),
                hash_password("whatever-pass"),
            )

        assert await users.set_password(created.id, hash_password("rotated-pass"))
        rotated = await users.get_by_account(account)
        assert rotated is not None and verify_password("rotated-pass", rotated[1])

        disabled = await users.set_status(created.id, "disabled")
        assert disabled is not None and disabled.status == "disabled"
        assert any(item.id == created.id for item in await users.list(DEMO_TENANT_ID))
        assert await users.count() >= 1

        tenant_id = uuid4()
        tenant = await tenants.create(
            TenantCreate(id=tenant_id, name="PG Tenant", home_region="ap-southeast")
        )
        assert tenant.status == "active"
        assert (await tenants.get(tenant_id)) is not None
        assert any(item.id == tenant_id for item in await tenants.list())
        with pytest.raises(TenantConflict):
            await tenants.create(TenantCreate(id=tenant_id, name="dup"))
    finally:
        await engine.dispose()
