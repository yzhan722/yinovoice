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


def _client_and_ids():
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    other_tenant_id = UUID("00000000-0000-0000-0000-000000000002")
    service_id = UUID("00000000-0000-0000-0000-000000000101")
    repository = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=service_id,
                tenant_id=tenant_id,
            )
        ]
    )
    client = TestClient(
        create_app(
            repository=repository,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
        )
    )
    return client, tenant_id, other_tenant_id, service_id


def test_appointment_crud_and_tenant_isolation() -> None:
    client, tenant_id, other_tenant_id, service_id = _client_and_ids()
    headers = {"X-Tenant-ID": str(tenant_id)}

    created = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_name": "张先生",
            "phone": "13800138000",
            "service": "洁牙",
            "slot_start": "2026-08-18T10:00:00+00:00",
            "slot_end": "2026-08-18T10:30:00+00:00",
            "voice_agent_instance_id": str(service_id),
        },
    )
    assert created.status_code == 201
    apt_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    listed = client.get("/api/v1/appointments", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    other = client.get(
        "/api/v1/appointments",
        headers={"X-Tenant-ID": str(other_tenant_id)},
    )
    assert other.json()["total"] == 0

    patched = client.patch(
        f"/api/v1/appointments/{apt_id}",
        headers=headers,
        json={"status": "confirmed"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "confirmed"

    deleted = client.delete(f"/api/v1/appointments/{apt_id}", headers=headers)
    assert deleted.status_code == 204
    hidden = client.get("/api/v1/appointments", headers=headers)
    assert hidden.json()["total"] == 0
    with_cancelled = client.get(
        "/api/v1/appointments?include_cancelled=true",
        headers=headers,
    )
    assert with_cancelled.json()["total"] == 1


def test_callback_create_complete_reopen() -> None:
    client, tenant_id, _, _ = _client_and_ids()
    headers = {"X-Tenant-ID": str(tenant_id)}

    created = client.post(
        "/api/v1/callback-tasks",
        headers=headers,
        json={
            "caller_phone": "13900139000",
            "reason": "改期确认",
            "summary": "希望周四回电",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "open"

    done = client.post(
        f"/api/v1/callback-tasks/{task_id}/complete",
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "done"

    reopened = client.post(
        f"/api/v1/callback-tasks/{task_id}/reopen",
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"

    listed = client.get("/api/v1/callback-tasks", headers=headers)
    assert listed.json()["total"] == 1
