"""PostgreSQL adapter for SchedulingRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import (
    BusinessHoursRow,
    ScheduleExceptionRow,
    SchedulingProfileRow,
    ServiceOfferingRow,
)
from ...domain.scheduling import (
    BusinessHours,
    ScheduleException,
    SchedulingProfile,
    ServiceOffering,
)


def _offering_to_domain(row: ServiceOfferingRow) -> ServiceOffering:
    return ServiceOffering(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        name=row.name,
        description=row.description,
        duration_minutes=row.duration_minutes,
        buffer_minutes=row.buffer_minutes,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _profile_to_domain(row: SchedulingProfileRow) -> SchedulingProfile:
    return SchedulingProfile(
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        timezone=row.timezone,
        slot_interval_minutes=row.slot_interval_minutes,
        minimum_notice_minutes=row.minimum_notice_minutes,
        booking_horizon_days=row.booking_horizon_days,
        updated_at=row.updated_at,
    )


def _hours_to_domain(row: BusinessHoursRow) -> BusinessHours:
    return BusinessHours(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        weekday=row.weekday,  # type: ignore[arg-type]
        start_local=row.start_local,
        end_local=row.end_local,
        enabled=row.enabled,
    )


def _exception_to_domain(row: ScheduleExceptionRow) -> ScheduleException:
    return ScheduleException(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        date_local=row.date_local,
        closed=row.closed,
        start_local=row.start_local,
        end_local=row.end_local,
        reason=row.reason,
    )


class PostgresSchedulingRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_offerings(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ServiceOffering]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ServiceOfferingRow)
                    .where(
                        ServiceOfferingRow.tenant_id == tenant_id,
                        ServiceOfferingRow.voice_agent_instance_id == instance_id,
                    )
                    .order_by(ServiceOfferingRow.created_at.asc(), ServiceOfferingRow.id)
                )
            ).all()
            return [_offering_to_domain(row) for row in rows]

    async def get_offering(
        self, offering_id: UUID, tenant_id: UUID
    ) -> ServiceOffering | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ServiceOfferingRow).where(
                    ServiceOfferingRow.tenant_id == tenant_id,
                    ServiceOfferingRow.id == offering_id,
                )
            )
            return _offering_to_domain(row) if row is not None else None

    async def find_offering_by_name(
        self, tenant_id: UUID, instance_id: UUID, name: str
    ) -> ServiceOffering | None:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ServiceOfferingRow).where(
                        ServiceOfferingRow.tenant_id == tenant_id,
                        ServiceOfferingRow.voice_agent_instance_id == instance_id,
                        ServiceOfferingRow.enabled.is_(True),
                        ServiceOfferingRow.name == name,
                    )
                )
            ).all()
            if len(rows) != 1:
                return None
            return _offering_to_domain(rows[0])

    async def create_offering(self, offering: ServiceOffering) -> ServiceOffering:
        async with self._sessions() as session:
            session.add(
                ServiceOfferingRow(
                    id=offering.id,
                    tenant_id=offering.tenant_id,
                    voice_agent_instance_id=offering.voice_agent_instance_id,
                    name=offering.name,
                    description=offering.description,
                    duration_minutes=offering.duration_minutes,
                    buffer_minutes=offering.buffer_minutes,
                    enabled=offering.enabled,
                    created_at=offering.created_at,
                    updated_at=offering.updated_at,
                )
            )
            await session.commit()
            return offering

    async def save_offering(self, offering: ServiceOffering) -> ServiceOffering:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ServiceOfferingRow).where(
                    ServiceOfferingRow.tenant_id == offering.tenant_id,
                    ServiceOfferingRow.id == offering.id,
                )
            )
            if row is None:
                return await self.create_offering(offering)
            row.name = offering.name
            row.description = offering.description
            row.duration_minutes = offering.duration_minutes
            row.buffer_minutes = offering.buffer_minutes
            row.enabled = offering.enabled
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _offering_to_domain(row)

    async def get_profile(
        self, tenant_id: UUID, instance_id: UUID
    ) -> SchedulingProfile | None:
        async with self._sessions() as session:
            row = await session.get(SchedulingProfileRow, (tenant_id, instance_id))
            return _profile_to_domain(row) if row is not None else None

    async def upsert_profile(self, profile: SchedulingProfile) -> SchedulingProfile:
        stamp = datetime.now(UTC)
        async with self._sessions() as session:
            row = await session.get(
                SchedulingProfileRow,
                (profile.tenant_id, profile.voice_agent_instance_id),
            )
            if row is None:
                row = SchedulingProfileRow(
                    tenant_id=profile.tenant_id,
                    voice_agent_instance_id=profile.voice_agent_instance_id,
                    timezone=profile.timezone,
                    slot_interval_minutes=profile.slot_interval_minutes,
                    minimum_notice_minutes=profile.minimum_notice_minutes,
                    booking_horizon_days=profile.booking_horizon_days,
                    updated_at=stamp,
                )
                session.add(row)
            else:
                row.timezone = profile.timezone
                row.slot_interval_minutes = profile.slot_interval_minutes
                row.minimum_notice_minutes = profile.minimum_notice_minutes
                row.booking_horizon_days = profile.booking_horizon_days
                row.updated_at = stamp
            await session.commit()
            await session.refresh(row)
            return _profile_to_domain(row)

    async def list_hours(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[BusinessHours]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(BusinessHoursRow)
                    .where(
                        BusinessHoursRow.tenant_id == tenant_id,
                        BusinessHoursRow.voice_agent_instance_id == instance_id,
                    )
                    .order_by(
                        BusinessHoursRow.weekday.asc(),
                        BusinessHoursRow.start_local.asc(),
                    )
                )
            ).all()
            return [_hours_to_domain(row) for row in rows]

    async def replace_hours(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        hours: list[BusinessHours],
    ) -> list[BusinessHours]:
        async with self._sessions() as session:
            await session.execute(
                delete(BusinessHoursRow).where(
                    BusinessHoursRow.tenant_id == tenant_id,
                    BusinessHoursRow.voice_agent_instance_id == instance_id,
                )
            )
            for item in hours:
                session.add(
                    BusinessHoursRow(
                        id=item.id,
                        tenant_id=item.tenant_id,
                        voice_agent_instance_id=item.voice_agent_instance_id,
                        weekday=item.weekday,
                        start_local=item.start_local,
                        end_local=item.end_local,
                        enabled=item.enabled,
                    )
                )
            await session.commit()
        return await self.list_hours(tenant_id, instance_id)

    async def list_exceptions(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ScheduleException]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ScheduleExceptionRow)
                    .where(
                        ScheduleExceptionRow.tenant_id == tenant_id,
                        ScheduleExceptionRow.voice_agent_instance_id == instance_id,
                    )
                    .order_by(ScheduleExceptionRow.date_local.asc())
                )
            ).all()
            return [_exception_to_domain(row) for row in rows]

    async def create_exception(self, item: ScheduleException) -> ScheduleException:
        async with self._sessions() as session:
            session.add(
                ScheduleExceptionRow(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    voice_agent_instance_id=item.voice_agent_instance_id,
                    date_local=item.date_local,
                    closed=item.closed,
                    start_local=item.start_local,
                    end_local=item.end_local,
                    reason=item.reason,
                )
            )
            await session.commit()
            return item

    async def delete_exception(self, exception_id: UUID, tenant_id: UUID) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ScheduleExceptionRow).where(
                    ScheduleExceptionRow.tenant_id == tenant_id,
                    ScheduleExceptionRow.id == exception_id,
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
