from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ..domain.tool_invocation import ToolInvocation


class ToolInvocationRepository(Protocol):
    async def get(
        self, invocation_id: UUID, tenant_id: UUID
    ) -> ToolInvocation | None: ...

    async def find_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> ToolInvocation | None: ...

    async def list_for_session(
        self, tenant_id: UUID, session_id: str
    ) -> list[ToolInvocation]: ...

    async def list_for_call_record(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> list[ToolInvocation]: ...

    async def create(self, item: ToolInvocation) -> ToolInvocation: ...

    async def save(self, item: ToolInvocation) -> ToolInvocation: ...

    async def bind_call_record(
        self, tenant_id: UUID, session_id: str, call_record_id: UUID
    ) -> int: ...


class InMemoryToolInvocationRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], ToolInvocation] = {}

    async def get(
        self, invocation_id: UUID, tenant_id: UUID
    ) -> ToolInvocation | None:
        item = self._items.get((tenant_id, invocation_id))
        return item.model_copy(deep=True) if item is not None else None

    async def find_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> ToolInvocation | None:
        matches = [
            item
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.idempotency_key == idempotency_key
        ]
        matches.sort(key=lambda item: item.created_at)
        return matches[0].model_copy(deep=True) if matches else None

    async def list_for_session(
        self, tenant_id: UUID, session_id: str
    ) -> list[ToolInvocation]:
        items = [
            item.model_copy(deep=True)
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.session_id == session_id
        ]
        items.sort(key=lambda item: (item.created_at, item.id))
        return items

    async def list_for_call_record(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> list[ToolInvocation]:
        items = [
            item.model_copy(deep=True)
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.call_record_id == call_record_id
        ]
        items.sort(key=lambda item: (item.created_at, item.id))
        return items

    async def create(self, item: ToolInvocation) -> ToolInvocation:
        stored = item.model_copy(deep=True)
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def save(self, item: ToolInvocation) -> ToolInvocation:
        stored = item.model_copy(deep=True)
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def bind_call_record(
        self, tenant_id: UUID, session_id: str, call_record_id: UUID
    ) -> int:
        changed = 0
        for key, item in list(self._items.items()):
            if (
                item.tenant_id == tenant_id
                and item.session_id == session_id
                and item.call_record_id is None
            ):
                self._items[key] = item.model_copy(
                    update={"call_record_id": call_record_id}
                )
                changed += 1
        return changed


def stamp_now() -> datetime:
    return datetime.now(UTC)
