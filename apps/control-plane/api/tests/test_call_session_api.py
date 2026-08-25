from uuid import UUID, uuid4

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


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def _start_payload(ids, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_service_id": str(ids.instance_id),
        "room_name": "sip-melbourne-1",
        "direction": "inbound",
        "caller_number": "+61 400 000 001",
        "callee_number": "+61400000099",
        "provider_call_id": "livekit-sip-abc",
    }
    payload.update(overrides)
    return payload


def test_start_creates_in_progress_inbound_session(ids) -> None:
    client = _client(ids)
    created = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids),
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "in_progress"
    assert body["direction"] == "inbound"
    assert body["ended_at"] is None
    assert body["duration_sec"] is None
    assert body["caller_number"] == "+61400000001"
    assert body["callee_number"] == "+61400000099"
    assert body["provider_call_id"] == "livekit-sip-abc"
    assert body["room_name"] == "sip-melbourne-1"
    assert body["messages"] == []


def test_start_is_idempotent_for_provider_call_id_and_in_progress_room(ids) -> None:
    client = _client(ids)
    first = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids),
    )
    replay_provider = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids, room_name="sip-other-room"),
    )
    replay_room = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids, provider_call_id="livekit-sip-other"),
    )

    assert first.status_code == 201
    assert replay_provider.status_code == 200
    assert replay_room.status_code == 200
    assert replay_provider.json()["id"] == first.json()["id"]
    assert replay_room.json()["id"] == first.json()["id"]


def test_start_unknown_instance_is_not_found(ids) -> None:
    client = _client(ids)
    response = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids, customer_service_id=str(uuid4())),
    )
    assert response.status_code == 404


def test_messages_append_finals_with_sequence_idempotency_and_reject_out_of_order(
    ids,
) -> None:
    client = _client(ids)
    started = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids),
    )
    record_id = started.json()["id"]
    first = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "user", "text": "我想预约", "sequence": 1},
    )
    replay = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "user", "text": "我想预约", "sequence": 1},
    )
    conflict = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "user", "text": "另一句", "sequence": 1},
    )
    out_of_order = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "assistant", "text": "好的", "sequence": 0},
    )
    second = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "assistant", "text": "好的", "sequence": 2},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["messages"] == first.json()["messages"]
    assert conflict.status_code == 409
    assert out_of_order.status_code == 409
    assert second.status_code == 200
    assert [item["sequence"] for item in second.json()["messages"]] == [1, 2]


def test_finish_is_idempotent_and_records_end_reasons(ids) -> None:
    client = _client(ids)
    started = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids, started_at="2026-08-24T01:00:00Z"),
    )
    record_id = started.json()["id"]
    client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "user", "text": "请回电", "sequence": 1},
    )
    finished = client.post(
        f"/api/v1/call-sessions/{record_id}/finish",
        headers=_headers(ids.tenant_id),
        json={
            "status": "interrupted",
            "ended_reason": "user_hangup",
            "ended_at": "2026-08-24T01:02:00Z",
        },
    )
    replay = client.post(
        f"/api/v1/call-sessions/{record_id}/finish",
        headers=_headers(ids.tenant_id),
        json={
            "status": "failed",
            "ended_reason": "agent_error",
        },
    )
    after_close = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "assistant", "text": "迟到的一句", "sequence": 2},
    )

    assert finished.status_code == 200
    body = finished.json()
    assert body["status"] == "interrupted"
    assert body["ended_reason"] == "user_hangup"
    assert body["ended_at"].startswith("2026-08-24T01:02:00")
    assert body["duration_sec"] == 120
    assert replay.status_code == 200
    assert replay.json()["status"] == "interrupted"
    assert replay.json()["ended_reason"] == "user_hangup"
    assert after_close.status_code == 409


def test_one_shot_web_call_record_create_still_works(ids) -> None:
    client = _client(ids)
    created = client.post(
        "/api/v1/call-records",
        headers=_headers(ids.tenant_id),
        json={
            "customer_service_id": str(ids.instance_id),
            "room_name": "web-room",
            "status": "completed",
            "started_at": "2026-08-03T01:00:00Z",
            "ended_at": "2026-08-03T01:00:12Z",
            "duration_sec": 12,
            "messages": [
                {"role": "user", "text": "你好", "sequence": 1},
            ],
        },
    )
    assert created.status_code == 201
    assert created.json()["direction"] == "web"
    assert created.json()["status"] == "completed"
