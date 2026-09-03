from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..domain.account import (
    AccountStatus,
    TenantCreate,
    TenantView,
    UserAccount,
    UserAccountCreate,
)


class AccountConflict(Exception):  # noqa: N818
    """Raised when an account name is already taken."""


class TenantConflict(Exception):  # noqa: N818
    """Raised when a tenant id already exists."""


class UserAccountRepository(Protocol):
    async def count(self) -> int: ...

    async def get(self, user_id: UUID) -> UserAccount | None: ...

    async def get_by_account(self, account: str) -> tuple[UserAccount, str] | None:
        """Return the account and its password hash."""
        ...

    async def list(self, tenant_id: UUID | None = None) -> list[UserAccount]: ...

    async def create(
        self, payload: UserAccountCreate, password_hash: str
    ) -> UserAccount: ...

    async def set_password(self, user_id: UUID, password_hash: str) -> bool: ...

    async def set_status(
        self, user_id: UUID, status: AccountStatus
    ) -> UserAccount | None: ...


class TenantRepository(Protocol):
    async def list(self) -> list[TenantView]: ...

    async def get(self, tenant_id: UUID) -> TenantView | None: ...

    async def create(self, payload: TenantCreate) -> TenantView: ...


class InMemoryUserAccountRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, UserAccount] = {}
        self._hashes: dict[UUID, str] = {}

    def _by_account(self, account: str) -> UserAccount | None:
        key = account.strip().casefold()
        for item in self._items.values():
            if item.account.casefold() == key:
                return item
        return None

    async def count(self) -> int:
        return len(self._items)

    async def get(self, user_id: UUID) -> UserAccount | None:
        return self._items.get(user_id)

    async def get_by_account(self, account: str) -> tuple[UserAccount, str] | None:
        item = self._by_account(account)
        if item is None:
            return None
        return item, self._hashes[item.id]

    async def list(self, tenant_id: UUID | None = None) -> list[UserAccount]:
        items = [
            item
            for item in self._items.values()
            if tenant_id is None or item.tenant_id == tenant_id
        ]
        items.sort(key=lambda item: item.created_at)
        return items

    async def create(
        self, payload: UserAccountCreate, password_hash: str
    ) -> UserAccount:
        if self._by_account(payload.account) is not None:
            raise AccountConflict()
        now = datetime.now(UTC)
        item = UserAccount(
            id=uuid4(),
            tenant_id=payload.tenant_id,
            account=payload.account,
            nickname=payload.nickname or payload.account,
            role=payload.role,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self._items[item.id] = item
        self._hashes[item.id] = password_hash
        return item

    async def set_password(self, user_id: UUID, password_hash: str) -> bool:
        if user_id not in self._items:
            return False
        self._hashes[user_id] = password_hash
        self._items[user_id] = self._items[user_id].model_copy(
            update={"updated_at": datetime.now(UTC)}
        )
        return True

    async def set_status(
        self, user_id: UUID, status: AccountStatus
    ) -> UserAccount | None:
        item = self._items.get(user_id)
        if item is None:
            return None
        updated = item.model_copy(
            update={"status": status, "updated_at": datetime.now(UTC)}
        )
        self._items[user_id] = updated
        return updated


class InMemoryTenantRepository:
    def __init__(self, tenants: list[TenantView] | None = None) -> None:
        self._items: dict[UUID, TenantView] = {
            item.id: item for item in (tenants or [])
        }

    async def list(self) -> list[TenantView]:
        return sorted(self._items.values(), key=lambda item: item.created_at)

    async def get(self, tenant_id: UUID) -> TenantView | None:
        return self._items.get(tenant_id)

    async def create(self, payload: TenantCreate) -> TenantView:
        tenant_id = payload.id or uuid4()
        if tenant_id in self._items:
            raise TenantConflict()
        item = TenantView(
            id=tenant_id,
            name=payload.name,
            home_region=payload.home_region,
            status="active",
            created_at=datetime.now(UTC),
        )
        self._items[tenant_id] = item
        return item
