from __future__ import annotations

from datetime import UTC, datetime
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
        include_deleted: bool = False,
    ) -> tuple[list[CallRecord], int]: ...

    async def get(self, record_id: UUID, tenant_id: UUID) -> CallRecord | None: ...

    async def soft_delete(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None: ...

    async def restore(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None: ...

    async def exists_for_customer_service(
        self,
        tenant_id: UUID,
        customer_service_id: UUID,
    ) -> bool: ...


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
        include_deleted: bool = False,
    ) -> tuple[list[CallRecord], int]:
        records = sorted(
            (
                record
                for (record_tenant_id, _), record in self._records.items()
                if record_tenant_id == tenant_id
                and (include_deleted or record.deleted_at is None)
            ),
            key=lambda record: (record.created_at, record.id.int),
            reverse=True,
        )
        page = records[offset : offset + limit]
        return [record.model_copy(deep=True) for record in page], len(records)

    async def get(self, record_id: UUID, tenant_id: UUID) -> CallRecord | None:
        record = self._records.get((tenant_id, record_id))
        return record.model_copy(deep=True) if record is not None else None

    async def soft_delete(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None:
        record = self._records.get((tenant_id, record_id))
        if record is None:
            return None
        if record.deleted_at is None:
            record = record.model_copy(
                update={"deleted_at": datetime.now(UTC)},
                deep=True,
            )
            self._records[(tenant_id, record_id)] = record
        return record.model_copy(deep=True)

    async def restore(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None:
        record = self._records.get((tenant_id, record_id))
        if record is None:
            return None
        if record.deleted_at is not None:
            record = record.model_copy(update={"deleted_at": None}, deep=True)
            self._records[(tenant_id, record_id)] = record
        return record.model_copy(deep=True)

    async def exists_for_customer_service(
        self,
        tenant_id: UUID,
        customer_service_id: UUID,
    ) -> bool:
        return any(
            record.tenant_id == tenant_id
            and record.customer_service_id == customer_service_id
            for record in self._records.values()
        )
