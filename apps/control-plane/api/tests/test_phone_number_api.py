from datetime import UTC, datetime
from uuid import uuid4

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


def _client(ids, extra=None) -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    repository = InMemoryCustomerServiceRepository([instance, *(extra or [])])
    return TestClient(
        create_app(
            repository,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
        )
    )


def test_create_and_lookup_phone_number(ids) -> None:
    client = _client(ids)
    created = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "+61 400 000 001",
            "voice_agent_instance_id": str(ids.instance_id),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["e164_number"] == "+61400000001"
    assert body["tenant_id"] == str(ids.tenant_id)
    assert body["voice_agent_instance_id"] == str(ids.instance_id)
    assert body["config_version"] == 1
    assert body["provider"] == "livekit_sip"

    listed = client.get(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    lookup = client.get("/api/v1/phone-numbers/lookup?number=%2B61%20400%20000%20001")
    assert lookup.status_code == 200
    assert lookup.json()["id"] == body["id"]
    assert lookup.json()["tenant_id"] == str(ids.tenant_id)
    assert lookup.json()["config_version"] == 1


def test_duplicate_e164_is_conflict(ids) -> None:
    client = _client(ids)
    payload = {
        "e164_number": "+61400000001",
        "voice_agent_instance_id": str(ids.instance_id),
    }
    assert (
        client.post(
            "/api/v1/phone-numbers",
            headers={"X-Tenant-ID": str(ids.tenant_id)},
            json=payload,
        ).status_code
        == 201
    )
    duplicate = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json=payload,
    )
    assert duplicate.status_code == 409


def test_cannot_bind_other_tenant_or_deleted_instance(ids) -> None:
    deleted = CustomerServiceInstance.demo(
        instance_id=uuid4(),
        tenant_id=ids.tenant_id,
    ).model_copy(update={"deleted_at": datetime.now(UTC)})
    foreign = CustomerServiceInstance.demo(
        instance_id=uuid4(),
        tenant_id=ids.other_tenant_id,
    )
    client = _client(ids, extra=[deleted, foreign])

    missing = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "+61400000002",
            "voice_agent_instance_id": str(foreign.id),
        },
    )
    assert missing.status_code == 404

    soft_deleted = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "+61400000003",
            "voice_agent_instance_id": str(deleted.id),
        },
    )
    assert soft_deleted.status_code == 404


def test_disabled_number_is_hidden_from_lookup(ids) -> None:
    client = _client(ids)
    created = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "+61400000004",
            "voice_agent_instance_id": str(ids.instance_id),
        },
    ).json()
    updated = client.put(
        f"/api/v1/phone-numbers/{created['id']}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={"enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    lookup = client.get("/api/v1/phone-numbers/lookup?number=%2B61400000004")
    assert lookup.status_code == 404


def test_delete_phone_number(ids) -> None:
    client = _client(ids)
    created = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "+61400000005",
            "voice_agent_instance_id": str(ids.instance_id),
        },
    ).json()
    deleted = client.delete(
        f"/api/v1/phone-numbers/{created['id']}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/v1/phone-numbers/{created['id']}",
            headers={"X-Tenant-ID": str(ids.tenant_id)},
        ).status_code
        == 404
    )


def test_invalid_e164_is_rejected(ids) -> None:
    client = _client(ids)
    response = client.post(
        "/api/v1/phone-numbers",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "e164_number": "400000001",
            "voice_agent_instance_id": str(ids.instance_id),
        },
    )
    assert response.status_code == 422
