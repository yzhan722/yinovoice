from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from yino_platform_api.domain.appointment import Appointment
from yino_platform_api.domain.scheduling import (
    BusinessHours,
    ScheduleException,
    SchedulingProfile,
    ServiceOffering,
)
from yino_platform_api.services.availability import (
    generate_available_slots,
    occupying_ranges,
    slot_still_available,
)


def _offering(**overrides: object) -> ServiceOffering:
    values: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "voice_agent_instance_id": uuid4(),
        "name": "洁牙",
        "description": "",
        "duration_minutes": 30,
        "buffer_minutes": 0,
        "enabled": True,
        "created_at": datetime(2026, 8, 25, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 25, tzinfo=UTC),
    }
    values.update(overrides)
    return ServiceOffering.model_validate(values)


def _profile(**overrides: object) -> SchedulingProfile:
    values: dict[str, object] = {
        "tenant_id": uuid4(),
        "voice_agent_instance_id": uuid4(),
        "timezone": "Australia/Melbourne",
        "slot_interval_minutes": 30,
        "minimum_notice_minutes": 60,
        "booking_horizon_days": 14,
        "updated_at": datetime(2026, 8, 25, tzinfo=UTC),
    }
    values.update(overrides)
    return SchedulingProfile.model_validate(values)


def _hours(instance_id, tenant_id) -> list[BusinessHours]:
    rows = []
    for weekday in range(5):
        rows.append(
            BusinessHours(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                weekday=weekday,
                start_local="09:00",
                end_local="12:00",
                enabled=True,
            )
        )
        rows.append(
            BusinessHours(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                weekday=weekday,
                start_local="13:00",
                end_local="17:00",
                enabled=True,
            )
        )
    return rows


def test_weekday_slots_skip_lunch_and_use_melbourne_timezone() -> None:
    offering = _offering()
    profile = _profile(
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        minimum_notice_minutes=0,
    )
    now = datetime(2026, 8, 24, 22, 0, tzinfo=UTC)  # Tuesday 08:00 Melbourne
    slots = generate_available_slots(
        profile=profile,
        offering=offering,
        hours=_hours(offering.voice_agent_instance_id, offering.tenant_id),
        exceptions=[],
        occupying=[],
        date_from=datetime(2026, 8, 25, tzinfo=UTC).date(),
        date_to=datetime(2026, 8, 25, tzinfo=UTC).date(),
        now=now,
    )
    locals_ = [item.slot_start_local.strftime("%H:%M") for item in slots]
    assert "09:00" in locals_
    assert "11:30" in locals_
    assert "12:00" not in locals_
    assert "12:30" not in locals_
    assert "13:00" in locals_
    melbourne = ZoneInfo("Australia/Melbourne")
    first = slots[0]
    assert first.slot_start_local.tzinfo == melbourne
    assert first.slot_start_utc == first.slot_start_local.astimezone(UTC)


def test_pending_appointment_blocks_slot_cancelled_does_not() -> None:
    offering = _offering()
    profile = _profile(
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        minimum_notice_minutes=0,
    )
    zone = ZoneInfo("Australia/Melbourne")
    busy_start = datetime(2026, 8, 25, 9, 0, tzinfo=zone)
    busy = Appointment(
        id=uuid4(),
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        patient_name="A",
        phone="1",
        service="洁牙",
        slot_start=busy_start.astimezone(UTC),
        slot_end=(busy_start + timedelta(minutes=30)).astimezone(UTC),
        status="pending",
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        updated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    cancelled = busy.model_copy(update={"id": uuid4(), "status": "cancelled"})
    now = datetime(2026, 8, 24, 22, 0, tzinfo=UTC)
    hours = _hours(offering.voice_agent_instance_id, offering.tenant_id)
    blocked = generate_available_slots(
        profile=profile,
        offering=offering,
        hours=hours,
        exceptions=[],
        occupying=occupying_ranges([busy]),
        date_from=busy_start.date(),
        date_to=busy_start.date(),
        now=now,
    )
    released = generate_available_slots(
        profile=profile,
        offering=offering,
        hours=hours,
        exceptions=[],
        occupying=occupying_ranges([cancelled]),
        date_from=busy_start.date(),
        date_to=busy_start.date(),
        now=now,
    )
    assert "09:00" not in [item.slot_start_local.strftime("%H:%M") for item in blocked]
    assert "09:00" in [item.slot_start_local.strftime("%H:%M") for item in released]


def test_minimum_notice_horizon_and_closed_exception() -> None:
    offering = _offering()
    profile = _profile(
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        minimum_notice_minutes=24 * 60,
        booking_horizon_days=2,
    )
    hours = _hours(offering.voice_agent_instance_id, offering.tenant_id)
    now = datetime(2026, 8, 24, 23, 0, tzinfo=UTC)  # Tuesday 09:00 Melbourne
    exception = ScheduleException(
        id=uuid4(),
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        date_local=date.fromisoformat("2026-08-26"),
        closed=True,
        reason="公休",
    )
    slots = generate_available_slots(
        profile=profile,
        offering=offering,
        hours=hours,
        exceptions=[exception],
        occupying=[],
        date_from=date.fromisoformat("2026-08-25"),
        date_to=date.fromisoformat("2026-08-28"),
        now=now,
    )
    days = {item.slot_start_local.date().isoformat() for item in slots}
    assert "2026-08-25" not in days  # inside minimum notice
    assert "2026-08-26" not in days  # closed exception
    assert "2026-08-27" in days
    assert "2026-08-28" not in days  # beyond 2-day horizon from Tuesday 09:00


def test_slot_still_available_rejects_wrong_duration() -> None:
    offering = _offering()
    profile = _profile(
        tenant_id=offering.tenant_id,
        voice_agent_instance_id=offering.voice_agent_instance_id,
        minimum_notice_minutes=0,
    )
    zone = ZoneInfo("Australia/Melbourne")
    start = datetime(2026, 8, 25, 9, 0, tzinfo=zone).astimezone(UTC)
    assert not slot_still_available(
        profile=profile,
        offering=offering,
        hours=_hours(offering.voice_agent_instance_id, offering.tenant_id),
        exceptions=[],
        occupying=[],
        slot_start_utc=start,
        slot_end_utc=start + timedelta(minutes=45),
        now=datetime(2026, 8, 24, 22, 0, tzinfo=UTC),
    )
