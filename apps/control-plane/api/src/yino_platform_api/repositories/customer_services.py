from __future__ import annotations

from collections.abc import Iterable
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
    ) -> tuple[list[CustomerServiceInstance], int]: ...

    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def save(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance: ...

    async def create(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance: ...


class InMemoryCustomerServiceRepository:
    def __init__(
        self, instances: Iterable[CustomerServiceInstance] = ()
    ) -> None:
        self._instances = {
            (item.tenant_id, item.id): item for item in instances
        }

    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        return self._instances.get((tenant_id, instance_id))

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CustomerServiceInstance], int]:
        items = sorted(
            (
                instance
                for (item_tenant_id, _), instance in self._instances.items()
                if item_tenant_id == tenant_id
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
