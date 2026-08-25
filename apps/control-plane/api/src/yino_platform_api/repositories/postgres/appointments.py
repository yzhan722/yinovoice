"""PostgreSQL adapter for AppointmentRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import AppointmentRow
from ...domain.appointment import Appointment


def _to_domain(row: AppointmentRow) -> Appointment:
    return Appointment(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        call_record_id=row.call_record_id,
        service_offering_id=row.service_offering_id,
        patient_name=row.patient_name,
        phone=row.phone,
        service=row.service,
        slot_start=row.slot_start,
        slot_end=row.slot_end,
        status=row.status,  # type: ignore[arg-type]
        source=row.source,  # type: ignore[arg-type]
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresAppointmentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[Appointment], int]:
        async with self._sessions() as session:
            filters = [AppointmentRow.tenant_id == tenant_id]
            if status is not None:
                filters.append(AppointmentRow.status == status)
            elif not include_cancelled:
                filters.append(AppointmentRow.status != "cancelled")
            total = await session.scalar(
                select(func.count()).select_from(AppointmentRow).where(*filters)
            )
            rows = (
                await session.scalars(
                    select(AppointmentRow)
                    .where(*filters)
                    .order_by(AppointmentRow.slot_start.asc(), AppointmentRow.id.asc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [_to_domain(row) for row in rows], int(total or 0)

    async def get(
        self, appointment_id: UUID, tenant_id: UUID
    ) -> Appointment | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(AppointmentRow).where(
                    AppointmentRow.tenant_id == tenant_id,
                    AppointmentRow.id == appointment_id,
                )
            )
            return _to_domain(row) if row is not None else None

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> Appointment | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(AppointmentRow)
                .where(
                    AppointmentRow.tenant_id == tenant_id,
                    AppointmentRow.call_record_id == call_record_id,
                )
                .order_by(AppointmentRow.created_at.asc(), AppointmentRow.id.asc())
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def list_occupying(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[Appointment]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(AppointmentRow).where(
                        AppointmentRow.tenant_id == tenant_id,
                        AppointmentRow.voice_agent_instance_id == instance_id,
                        AppointmentRow.status.in_(("pending", "confirmed")),
                    )
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def create(self, appointment: Appointment) -> Appointment:
        async with self._sessions() as session:
            session.add(
                AppointmentRow(
                    id=appointment.id,
                    tenant_id=appointment.tenant_id,
                    voice_agent_instance_id=appointment.voice_agent_instance_id,
                    call_record_id=appointment.call_record_id,
                    service_offering_id=appointment.service_offering_id,
                    patient_name=appointment.patient_name,
                    phone=appointment.phone,
                    service=appointment.service,
                    slot_start=appointment.slot_start,
                    slot_end=appointment.slot_end,
                    status=appointment.status,
                    source=appointment.source,
                    notes=appointment.notes,
                    created_at=appointment.created_at,
                    updated_at=appointment.updated_at,
                )
            )
            await session.commit()
            return appointment

    async def save(self, appointment: Appointment) -> Appointment:
        async with self._sessions() as session:
            row = await session.scalar(
                select(AppointmentRow).where(
                    AppointmentRow.tenant_id == appointment.tenant_id,
                    AppointmentRow.id == appointment.id,
                )
            )
            if row is None:
                return await self.create(appointment)
            row.patient_name = appointment.patient_name
            row.phone = appointment.phone
            row.service = appointment.service
            row.slot_start = appointment.slot_start
            row.slot_end = appointment.slot_end
            row.status = appointment.status
            row.notes = appointment.notes
            row.voice_agent_instance_id = appointment.voice_agent_instance_id
            row.call_record_id = appointment.call_record_id
            row.service_offering_id = appointment.service_offering_id
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)
