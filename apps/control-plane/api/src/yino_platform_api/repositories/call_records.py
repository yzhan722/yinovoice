from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ..domain.call_record import CallRecord


class CallRecordRepository(Protocol):
    async def save(self, record: CallRecord) -> CallRecord: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CallRecord], int]: ...

    async def get(self, record_id: UUID, tenant_id: UUID) -> CallRecord | None: ...


class InMemoryCallRecordRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[UUID, UUID], CallRecord] = {}

    async def save(self, record: CallRecord) -> CallRecord:
        stored = record.model_copy(deep=True)
        self._records[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CallRecord], int]:
        records = sorted(
            (
                record
                for (record_tenant_id, _), record in self._records.items()
                if record_tenant_id == tenant_id
            ),
            key=lambda record: (record.created_at, record.id.int),
            reverse=True,
        )
        page = records[offset : offset + limit]
        return [record.model_copy(deep=True) for record in page], len(records)

    async def get(self, record_id: UUID, tenant_id: UUID) -> CallRecord | None:
        record = self._records.get((tenant_id, record_id))
        return record.model_copy(deep=True) if record is not None else None
