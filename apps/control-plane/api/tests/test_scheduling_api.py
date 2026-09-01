from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.repositories.scheduling import InMemorySchedulingRepository


def _client(ids) -> tuple[TestClient, InMemoryAppointmentRepository]:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    appointments = InMemoryAppointmentRepository()
    client = TestClient(
        create_app(
            InMemoryCustomerServiceRepository([instance]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=appointments,
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
        )
    )
    return client, appointments


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def _seed_schedule(client: TestClient, ids) -> str:
    headers = _headers(ids.tenant_id)
    offering = client.post(
        "/api/v1/service-offerings",
        headers=headers,
        json={
            "voice_agent_instance_id": str(ids.instance_id),
            "name": "洁牙",
            "duration_minutes": 30,
            "buffer_minutes": 0,
        },
    )
    assert offering.status_code == 201, offering.text
    offering_id = offering.json()["id"]

    profile = client.put(
        f"/api/v1/scheduling-profiles/{ids.instance_id}",
        headers=headers,
        json={
            "timezone": "Australia/Melbourne",
            "slot_interval_minutes": 30,
            "minimum_notice_minutes": 0,
            "booking_horizon_days": 365,
        },
    )
    assert profile.status_code == 200, profile.text

    hours = []
    for weekday in range(5):
        hours.append(
            {"weekday": weekday, "start_local": "09:00", "end_local": "12:00"}
        )
        hours.append(
            {"weekday": weekday, "start_local": "13:00", "end_local": "17:00"}
        )
    replaced = client.put(
        f"/api/v1/business-hours?voice_agent_instance_id={ids.instance_id}",
        headers=headers,
        json=hours,
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()) == 10
    return offering_id


def test_availability_skips_lunch_and_occupied_slot(ids) -> None:
    client, _ = _client(ids)
    offering_id = _seed_schedule(client, ids)
    headers = _headers(ids.tenant_id)
    day = date(2026, 9, 1)  # Tuesday
    listed = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": day.isoformat(),
            "date_to": day.isoformat(),
        },
    )
    assert listed.status_code == 200, listed.text
    starts = [item["slot_start_local"] for item in listed.json()["items"]]
    assert any("T09:00:00" in item for item in starts)
    assert not any("T12:00:00" in item for item in starts)
    morning = next(
        item
        for item in listed.json()["items"]
        if "T09:00:00" in item["slot_start_local"]
    )

    booked = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_name": "王芳",
            "phone": "13800138000",
            "service": "洁牙",
            "slot_start": morning["slot_start_utc"],
            "slot_end": morning["slot_end_utc"],
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
        },
    )
    assert booked.status_code == 201, booked.text

    conflict = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_name": "李明",
            "phone": "13900139000",
            "service": "洁牙",
            "slot_start": morning["slot_start_utc"],
            "slot_end": morning["slot_end_utc"],
            "voice_agent_instance_id": str(ids.instance_id),
        },
    )
    assert conflict.status_code == 409

    after = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": day.isoformat(),
            "date_to": day.isoformat(),
        },
    )
    remaining = [item["slot_start_utc"] for item in after.json()["items"]]
    assert morning["slot_start_utc"] not in remaining

    cancelled = client.delete(
        f"/api/v1/appointments/{booked.json()['id']}",
        headers=headers,
    )
    assert cancelled.status_code == 204
    restored = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": day.isoformat(),
            "date_to": day.isoformat(),
        },
    )
    restored_starts = [item["slot_start_utc"] for item in restored.json()["items"]]
    assert morning["slot_start_utc"] in restored_starts


def test_modify_conflict_and_cancelled_is_terminal(ids) -> None:
    client, _ = _client(ids)
    offering_id = _seed_schedule(client, ids)
    headers = _headers(ids.tenant_id)
    day = date(2026, 9, 1)
    listed = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": day.isoformat(),
            "date_to": day.isoformat(),
        },
    )
    morning = next(
        item
        for item in listed.json()["items"]
        if "T09:00:00" in item["slot_start_local"]
    )
    later = next(
        item
        for item in listed.json()["items"]
        if "T10:00:00" in item["slot_start_local"]
    )
    first = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_name": "王芳",
            "phone": "13800138000",
            "service": "洁牙",
            "slot_start": morning["slot_start_utc"],
            "slot_end": morning["slot_end_utc"],
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
        },
    )
    second = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_name": "李明",
            "phone": "13900139000",
            "service": "洁牙",
            "slot_start": later["slot_start_utc"],
            "slot_end": later["slot_end_utc"],
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
        },
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    conflict = client.patch(
        f"/api/v1/appointments/{second.json()['id']}",
        headers=headers,
        json={
            "slot_start": morning["slot_start_utc"],
            "slot_end": morning["slot_end_utc"],
        },
    )
    assert conflict.status_code == 409
    cancelled = client.delete(
        f"/api/v1/appointments/{first.json()['id']}",
        headers=headers,
    )
    assert cancelled.status_code == 204
    again = client.delete(
        f"/api/v1/appointments/{first.json()['id']}",
        headers=headers,
    )
    assert again.status_code == 204
    blocked = client.patch(
        f"/api/v1/appointments/{first.json()['id']}",
        headers=headers,
        json={"notes": "should not revive"},
    )
    assert blocked.status_code == 409


def test_closed_exception_hides_day(ids) -> None:
    client, _ = _client(ids)
    offering_id = _seed_schedule(client, ids)
    headers = _headers(ids.tenant_id)
    created = client.post(
        "/api/v1/schedule-exceptions",
        headers=headers,
        json={
            "voice_agent_instance_id": str(ids.instance_id),
            "date_local": "2026-09-01",
            "closed": True,
            "reason": "public holiday",
        },
    )
    assert created.status_code == 201, created.text
    listed = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": "2026-09-01",
            "date_to": "2026-09-01",
        },
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 0


def test_wrong_duration_rejected_when_offering_bound(ids) -> None:
    client, _ = _client(ids)
    offering_id = _seed_schedule(client, ids)
    created = client.post(
        "/api/v1/appointments",
        headers=_headers(ids.tenant_id),
        json={
            "patient_name": "王芳",
            "phone": "13800138000",
            "service": "洁牙",
            "slot_start": "2026-09-01T23:00:00+00:00",
            "slot_end": "2026-09-01T23:45:00+00:00",
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
        },
    )
    assert created.status_code == 409
