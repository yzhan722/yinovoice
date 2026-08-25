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
from yino_platform_api.repositories.tool_invocations import (
    InMemoryToolInvocationRepository,
)


def _client(ids) -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    return TestClient(
        create_app(
            InMemoryCustomerServiceRepository([instance]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
            tool_invocation_repository=InMemoryToolInvocationRepository(),
        )
    )


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def test_create_callback_tool_is_idempotent_and_skips_extract(ids) -> None:
    client = _client(ids)
    headers = _headers(ids.tenant_id)
    payload = {
        "session_id": "sip-room-1",
        "voice_agent_instance_id": str(ids.instance_id),
        "tool_name": "create_callback",
        "arguments": {
            "phone": "13800138000",
            "reason": "要求回电确认洁牙档期",
        },
        "idempotency_key": "sip-room-1:create_callback:once",
    }
    first = client.post("/api/v1/tool-invocations", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "ok"
    callback_id = first.json()["result"]["callback_task_id"]
    assert callback_id

    replay = client.post("/api/v1/tool-invocations", headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json()["invocation_id"] == first.json()["invocation_id"]

    listed = client.get("/api/v1/callback-tasks", headers=headers)
    assert listed.json()["total"] == 1

    created = client.post(
        "/api/v1/call-records",
        headers=headers,
        json={
            "customer_service_id": str(ids.instance_id),
            "room_name": "sip-room-1",
            "status": "completed",
            "started_at": "2026-08-17T01:00:00Z",
            "ended_at": "2026-08-17T01:02:00Z",
            "duration_sec": 120,
            "messages": [
                {
                    "role": "user",
                    "text": "请回电，我叫王芳，号码13800138000",
                    "sequence": 1,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    extract = client.post(
        f"/api/v1/call-records/{created.json()['id']}/extract-intents",
        headers=headers,
    )
    assert extract.status_code == 200
    assert extract.json()["skipped_reason"] == "tool_already_wrote"
    assert extract.json()["callback_task_id"] == callback_id
    assert client.get("/api/v1/callback-tasks", headers=headers).json()["total"] == 1


def test_create_appointment_missing_slot_is_http_200_error(ids) -> None:
    client = _client(ids)
    response = client.post(
        "/api/v1/tool-invocations",
        headers=_headers(ids.tenant_id),
        json={
            "session_id": "sip-room-2",
            "voice_agent_instance_id": str(ids.instance_id),
            "tool_name": "create_appointment",
            "arguments": {
                "patient_name": "王芳",
                "phone": "13800138000",
                "service": "洁牙",
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "error"
    assert "slot_start" in response.json()["result"]["message"]
    assert client.get(
        "/api/v1/appointments", headers=_headers(ids.tenant_id)
    ).json()["total"] == 0


def test_create_appointment_tool_writes_once_per_session(ids) -> None:
    client = _client(ids)
    headers = _headers(ids.tenant_id)
    payload = {
        "session_id": "sip-room-3",
        "voice_agent_instance_id": str(ids.instance_id),
        "tool_name": "create_appointment",
        "arguments": {
            "patient_name": "王芳",
            "phone": "13800138000",
            "service": "洁牙",
            "slot_start": "2026-09-01T23:00:00+00:00",
            "slot_end": "2026-09-01T23:30:00+00:00",
        },
    }
    first = client.post("/api/v1/tool-invocations", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "ok"
    second = client.post(
        "/api/v1/tool-invocations",
        headers=headers,
        json={**payload, "idempotency_key": "different-key"},
    )
    assert second.status_code == 200
    assert second.json()["invocation_id"] == first.json()["invocation_id"]
    assert client.get("/api/v1/appointments", headers=headers).json()["total"] == 1
