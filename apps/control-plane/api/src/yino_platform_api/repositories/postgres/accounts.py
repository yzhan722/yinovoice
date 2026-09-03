"""PostgreSQL adapters for UserAccountRepository and TenantRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import Tenant, UserAccountRow
from ...domain.account import (
    AccountStatus,
    TenantCreate,
    TenantView,
    UserAccount,
    UserAccountCreate,
)
from ..accounts import AccountConflict, TenantConflict


def _account_to_domain(row: UserAccountRow) -> UserAccount:
    return UserAccount(
        id=row.id,
        tenant_id=row.tenant_id,
        account=row.account,
        nickname=row.nickname,
        role=row.role,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _tenant_to_domain(row: Tenant) -> TenantView:
    return TenantView(
        id=row.id,
        name=row.name,
        home_region=row.home_region,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
    )


class PostgresUserAccountRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def count(self) -> int:
        async with self._sessions() as session:
            value = await session.scalar(select(func.count(UserAccountRow.id)))
            return int(value or 0)

    async def get(self, user_id: UUID) -> UserAccount | None:
        async with self._sessions() as session:
            row = await session.get(UserAccountRow, user_id)
            return _account_to_domain(row) if row is not None else None

    async def get_by_account(self, account: str) -> tuple[UserAccount, str] | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(UserAccountRow).where(
                    func.lower(UserAccountRow.account) == account.strip().lower()
                )
            )
            if row is None:
                return None
            return _account_to_domain(row), row.password_hash

    async def list(self, tenant_id: UUID | None = None) -> list[UserAccount]:
        async with self._sessions() as session:
            query = select(UserAccountRow).order_by(
                UserAccountRow.created_at.asc(), UserAccountRow.id.asc()
            )
            if tenant_id is not None:
                query = query.where(UserAccountRow.tenant_id == tenant_id)
            rows = (await session.scalars(query)).all()
            return [_account_to_domain(row) for row in rows]

    async def create(
        self, payload: UserAccountCreate, password_hash: str
    ) -> UserAccount:
        now = datetime.now(UTC)
        row = UserAccountRow(
            id=uuid4(),
            tenant_id=payload.tenant_id,
            account=payload.account,
            nickname=payload.nickname or payload.account,
            password_hash=password_hash,
            role=payload.role,
            status="active",
            created_at=now,
            updated_at=now,
        )
        async with self._sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise AccountConflict() from error
            await session.refresh(row)
            return _account_to_domain(row)

    async def set_password(self, user_id: UUID, password_hash: str) -> bool:
        async with self._sessions() as session:
            row = await session.get(UserAccountRow, user_id)
            if row is None:
                return False
            row.password_hash = password_hash
            row.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def set_status(
        self, user_id: UUID, status: AccountStatus
    ) -> UserAccount | None:
        async with self._sessions() as session:
            row = await session.get(UserAccountRow, user_id)
            if row is None:
                return None
            row.status = status
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _account_to_domain(row)


class PostgresTenantRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> list[TenantView]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(Tenant).order_by(Tenant.created_at.asc(), Tenant.id.asc())
                )
            ).all()
            return [_tenant_to_domain(row) for row in rows]

    async def get(self, tenant_id: UUID) -> TenantView | None:
        async with self._sessions() as session:
            row = await session.get(Tenant, tenant_id)
            return _tenant_to_domain(row) if row is not None else None

    async def create(self, payload: TenantCreate) -> TenantView:
        now = datetime.now(UTC)
        row = Tenant(
            id=payload.id or uuid4(),
            name=payload.name,
            home_region=payload.home_region,
            status="active",
            created_at=now,
            updated_at=now,
        )
        async with self._sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise TenantConflict() from error
            await session.refresh(row)
            return _tenant_to_domain(row)
