from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..domain.config_revision import ConfigRevisionSource, InstanceConfigRevision
from ..domain.customer_service import CustomerServiceInstance, publishable_snapshot


class ConfigRevisionRepository(Protocol):
    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[InstanceConfigRevision]: ...

    async def get_by_revision(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        revision: int,
    ) -> InstanceConfigRevision | None: ...

    async def latest(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> InstanceConfigRevision | None: ...

    async def add(
        self, revision: InstanceConfigRevision
    ) -> InstanceConfigRevision: ...


async def record_snapshot(
    repository: ConfigRevisionRepository,
    instance: CustomerServiceInstance,
    source: ConfigRevisionSource,
) -> InstanceConfigRevision:
    latest = await repository.latest(instance.tenant_id, instance.id)
    next_revision = 1 if latest is None else latest.revision + 1
    revision = InstanceConfigRevision(
        id=uuid4(),
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        revision=next_revision,
        source=source,
        snapshot=publishable_snapshot(instance),
        created_at=datetime.now(UTC),
    )
    return await repository.add(revision)


class InMemoryConfigRevisionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID, int], InstanceConfigRevision] = {}

    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[InstanceConfigRevision]:
        items = [
            item
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.instance_id == instance_id
        ]
        items.sort(key=lambda item: item.revision, reverse=True)
        return items

    async def get_by_revision(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        revision: int,
    ) -> InstanceConfigRevision | None:
        return self._items.get((tenant_id, instance_id, revision))

    async def latest(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> InstanceConfigRevision | None:
        items = await self.list_for_instance(tenant_id, instance_id)
        return items[0] if items else None

    async def add(
        self, revision: InstanceConfigRevision
    ) -> InstanceConfigRevision:
        key = (revision.tenant_id, revision.instance_id, revision.revision)
        self._items[key] = revision
        return revision
