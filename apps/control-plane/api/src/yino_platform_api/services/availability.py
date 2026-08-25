from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..domain.appointment import Appointment
from ..domain.scheduling import (
    AvailabilitySlot,
    BusinessHours,
    ScheduleException,
    SchedulingProfile,
    ServiceOffering,
    parse_hhmm,
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ranges_overlap(
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> bool:
    return _aware_utc(left_start) < _aware_utc(right_end) and _aware_utc(
        right_start
    ) < _aware_utc(left_end)


def occupying_ranges(appointments: list[Appointment]) -> list[tuple[datetime, datetime]]:
    return [
        (_aware_utc(item.slot_start), _aware_utc(item.slot_end))
        for item in appointments
        if item.status in {"pending", "confirmed"}
    ]


def windows_for_day(
    day: date,
    hours: list[BusinessHours],
    exceptions: list[ScheduleException],
) -> list[tuple[str, str]]:
    matching = [item for item in exceptions if item.date_local == day]
    if matching:
        exception = matching[0]
        if exception.closed:
            return []
        assert exception.start_local is not None
        assert exception.end_local is not None
        return [(exception.start_local, exception.end_local)]
    weekday = day.weekday()
    return [
        (item.start_local, item.end_local)
        for item in hours
        if item.enabled and item.weekday == weekday
    ]


def generate_available_slots(
    *,
    profile: SchedulingProfile,
    offering: ServiceOffering,
    hours: list[BusinessHours],
    exceptions: list[ScheduleException],
    occupying: list[tuple[datetime, datetime]],
    date_from: date,
    date_to: date,
    now: datetime,
) -> list[AvailabilitySlot]:
    if not offering.enabled:
        return []
    zone = ZoneInfo(profile.timezone)
    clock = _aware_utc(now)
    earliest = clock + timedelta(minutes=profile.minimum_notice_minutes)
    latest = clock + timedelta(days=profile.booking_horizon_days)
    duration = timedelta(minutes=offering.duration_minutes + offering.buffer_minutes)
    interval = timedelta(minutes=profile.slot_interval_minutes)
    slots: list[AvailabilitySlot] = []
    day = date_from
    while day <= date_to:
        for start_local, end_local in windows_for_day(day, hours, exceptions):
            window_start = datetime.combine(day, parse_hhmm(start_local), tzinfo=zone)
            window_end = datetime.combine(day, parse_hhmm(end_local), tzinfo=zone)
            cursor = window_start
            while cursor + duration <= window_end:
                slot_end = cursor + timedelta(minutes=offering.duration_minutes)
                occupied_end = cursor + duration
                start_utc = cursor.astimezone(UTC)
                end_utc = slot_end.astimezone(UTC)
                if start_utc >= earliest and start_utc <= latest and occupied_end <= window_end:
                    busy = any(
                        ranges_overlap(start_utc, occupied_end, busy_start, busy_end)
                        for busy_start, busy_end in occupying
                    )
                    if not busy:
                        slots.append(
                            AvailabilitySlot(
                                slot_start_utc=start_utc,
                                slot_end_utc=end_utc,
                                slot_start_local=cursor,
                                slot_end_local=slot_end,
                                timezone=profile.timezone,
                                service_offering_id=offering.id,
                            )
                        )
                cursor += interval
        day += timedelta(days=1)
    return slots


def slot_still_available(
    *,
    profile: SchedulingProfile,
    offering: ServiceOffering,
    hours: list[BusinessHours],
    exceptions: list[ScheduleException],
    occupying: list[tuple[datetime, datetime]],
    slot_start_utc: datetime,
    slot_end_utc: datetime,
    now: datetime,
) -> bool:
    start = _aware_utc(slot_start_utc)
    end = _aware_utc(slot_end_utc)
    expected = start + timedelta(minutes=offering.duration_minutes)
    if end != expected:
        return False
    local_date = start.astimezone(ZoneInfo(profile.timezone)).date()
    available = generate_available_slots(
        profile=profile,
        offering=offering,
        hours=hours,
        exceptions=exceptions,
        occupying=occupying,
        date_from=local_date,
        date_to=local_date,
        now=now,
    )
    return any(
        item.slot_start_utc == start and item.slot_end_utc == end for item in available
    )
