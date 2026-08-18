from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from ..domain.callback_task import CallbackTask


class CallbackTaskRepository(Protocol):
    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[CallbackTask], int]: ...

    async def get(
        self, task_id: UUID, tenant_id: UUID
    ) -> CallbackTask | None: ...

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> CallbackTask | None: ...

    async def create(self, task: CallbackTask) -> CallbackTask: ...

    async def save(self, task: CallbackTask) -> CallbackTask: ...


class InMemoryCallbackTaskRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], CallbackTask] = {}

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[CallbackTask], int]:
        items = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == tenant_id
            and (status is None or item.status == status)
            and (include_cancelled or item.status != "cancelled")
        ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[offset : offset + limit], len(items)

    async def get(
        self, task_id: UUID, tenant_id: UUID
    ) -> CallbackTask | None:
        return self._items.get((tenant_id, task_id))

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> CallbackTask | None:
        matches = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == tenant_id and item.call_record_id == call_record_id
        ]
        matches.sort(key=lambda item: item.created_at)
        return matches[0] if matches else None

    async def create(self, task: CallbackTask) -> CallbackTask:
        self._items[(task.tenant_id, task.id)] = task
        return task

    async def save(self, task: CallbackTask) -> CallbackTask:
        stored = task.model_copy(update={"updated_at": datetime.now(UTC)})
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored
