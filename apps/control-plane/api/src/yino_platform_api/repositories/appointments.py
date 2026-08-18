from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from ..domain.appointment import Appointment


class AppointmentRepository(Protocol):
    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[Appointment], int]: ...

    async def get(
        self, appointment_id: UUID, tenant_id: UUID
    ) -> Appointment | None: ...

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> Appointment | None: ...

    async def create(self, appointment: Appointment) -> Appointment: ...

    async def save(self, appointment: Appointment) -> Appointment: ...


class InMemoryAppointmentRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], Appointment] = {}

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[Appointment], int]:
        items = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == tenant_id
            and (status is None or item.status == status)
            and (include_cancelled or item.status != "cancelled")
        ]
        items.sort(key=lambda item: item.slot_start)
        return items[offset : offset + limit], len(items)

    async def get(
        self, appointment_id: UUID, tenant_id: UUID
    ) -> Appointment | None:
        return self._items.get((tenant_id, appointment_id))

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> Appointment | None:
        matches = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == tenant_id and item.call_record_id == call_record_id
        ]
        matches.sort(key=lambda item: item.created_at)
        return matches[0] if matches else None

    async def create(self, appointment: Appointment) -> Appointment:
        self._items[(appointment.tenant_id, appointment.id)] = appointment
        return appointment

    async def save(self, appointment: Appointment) -> Appointment:
        stored = appointment.model_copy(
            update={"updated_at": datetime.now(UTC)}
        )
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored
