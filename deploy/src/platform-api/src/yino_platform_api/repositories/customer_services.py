from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from ..domain.customer_service import CustomerServiceInstance


class CustomerServiceRepository(Protocol):
    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None: ...

    async def save(
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

    async def save(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance:
        self._instances[(instance.tenant_id, instance.id)] = instance
        return instance
