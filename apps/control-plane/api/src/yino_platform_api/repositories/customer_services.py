from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from ..domain.customer_service import CustomerServiceInstance


class CustomerServiceVersionConflict(Exception):
    """Raised when optimistic version compare-and-swap fails."""


class CustomerServiceAlreadyExists(Exception):
    """Raised when an instance identifier is already persisted."""


class CustomerServiceRepository(Protocol):
    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        include_deleted: bool = False,
    ) -> tuple[list[CustomerServiceInstance], int]: ...

    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def get_including_deleted(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def save(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance: ...

    async def create(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance: ...

    async def soft_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def restore(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def hard_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...


class InMemoryCustomerServiceRepository:
    def __init__(
        self, instances: Iterable[CustomerServiceInstance] = ()
    ) -> None:
        self._instances = {
            (item.tenant_id, item.id): item for item in instances
        }

    async def get_including_deleted(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        return self._instances.get((tenant_id, instance_id))

    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        instance = self._instances.get((tenant_id, instance_id))
        if instance is None or instance.deleted_at is not None:
            return None
        return instance

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        include_deleted: bool = False,
    ) -> tuple[list[CustomerServiceInstance], int]:
        items = sorted(
            (
                instance
                for (item_tenant_id, _), instance in self._instances.items()
                if item_tenant_id == tenant_id
                and (include_deleted or instance.deleted_at is None)
            ),
            key=lambda instance: str(instance.id),
            reverse=True,
        )
        return items[offset : offset + limit], len(items)

    async def save(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance:
        self._instances[(instance.tenant_id, instance.id)] = instance
        return instance

    async def create(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance:
        key = (instance.tenant_id, instance.id)
        if key in self._instances:
            raise CustomerServiceAlreadyExists()
        self._instances[key] = instance
        return instance

    async def soft_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        instance = self._instances.get((tenant_id, instance_id))
        if instance is None:
            return None
        if instance.deleted_at is None:
            instance = instance.model_copy(
                update={"deleted_at": datetime.now(UTC)}
            )
            self._instances[(tenant_id, instance_id)] = instance
        return instance

    async def restore(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        instance = self._instances.get((tenant_id, instance_id))
        if instance is None:
            return None
        if instance.deleted_at is not None:
            instance = instance.model_copy(update={"deleted_at": None})
            self._instances[(tenant_id, instance_id)] = instance
        return instance

    async def hard_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        key = (tenant_id, instance_id)
        instance = self._instances.get(key)
        if instance is None:
            return None
        del self._instances[key]
        return instance
