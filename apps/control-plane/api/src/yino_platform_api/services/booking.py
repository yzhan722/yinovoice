from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ..clock import utc_now
from ..domain.appointment import Appointment
from ..repositories.appointments import AppointmentRepository
from ..repositories.scheduling import SchedulingRepository
from .availability import occupying_ranges, ranges_overlap, slot_still_available


class SlotUnavailableError(ValueError):
    """Raised when a requested appointment slot cannot be booked."""


async def overlapping_occupants(
    appointments: AppointmentRepository,
    *,
    tenant_id: UUID,
    instance_id: UUID,
    slot_start: datetime,
    slot_end: datetime,
    exclude_id: UUID | None = None,
) -> list[Appointment]:
    occupying = await appointments.list_occupying(tenant_id, instance_id)
    return [
        item
        for item in occupying
        if item.id != exclude_id
        and ranges_overlap(slot_start, slot_end, item.slot_start, item.slot_end)
    ]


async def ensure_slot_available(
    *,
    appointments: AppointmentRepository,
    scheduling: SchedulingRepository,
    tenant_id: UUID,
    instance_id: UUID | None,
    slot_start: datetime,
    slot_end: datetime,
    service_offering_id: UUID | None,
    exclude_id: UUID | None = None,
    now: datetime | None = None,
) -> None:
    if instance_id is None:
        return
    conflicts = await overlapping_occupants(
        appointments,
        tenant_id=tenant_id,
        instance_id=instance_id,
        slot_start=slot_start,
        slot_end=slot_end,
        exclude_id=exclude_id,
    )
    if conflicts:
        raise SlotUnavailableError("slot occupied")
    if service_offering_id is None:
        return
    offering = await scheduling.get_offering(service_offering_id, tenant_id)
    if offering is None or offering.voice_agent_instance_id != instance_id:
        raise SlotUnavailableError("service offering not found")
    if not offering.enabled:
        raise SlotUnavailableError("service offering is disabled")
    profile = await scheduling.get_profile(tenant_id, instance_id)
    if profile is None:
        raise SlotUnavailableError("scheduling profile not found")
    hours = await scheduling.list_hours(tenant_id, instance_id)
    exceptions = await scheduling.list_exceptions(tenant_id, instance_id)
    occupying = occupying_ranges(
        [
            item
            for item in await appointments.list_occupying(tenant_id, instance_id)
            if item.id != exclude_id
        ]
    )
    if not slot_still_available(
        profile=profile,
        offering=offering,
        hours=hours,
        exceptions=exceptions,
        occupying=occupying,
        slot_start_utc=slot_start,
        slot_end_utc=slot_end,
        now=now or utc_now(),
    ):
        raise SlotUnavailableError("slot not available")
