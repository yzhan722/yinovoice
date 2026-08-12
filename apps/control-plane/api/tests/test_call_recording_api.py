from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.call_records import (
    InMemoryCallRecordRepository,
)
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)


@dataclass(frozen=True)
class CallRecordApi:
    client: TestClient
    repository: InMemoryCallRecordRepository
    tenant_id: UUID
    other_tenant_id: UUID
    service_id: UUID
    recording_dir: str


@pytest.fixture
def api(tmp_path, monkeypatch) -> CallRecordApi:
    monkeypatch.setenv("CALL_RECORDING_DIR", str(tmp_path))
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    other_tenant_id = UUID("00000000-0000-0000-0000-000000000002")
    service_id = UUID("00000000-0000-0000-0000-000000000101")
    service_repository = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=service_id,
                tenant_id=tenant_id,
            )
        ]
    )
    call_repository = InMemoryCallRecordRepository()
    client = TestClient(
        create_app(
            service_repository,
            call_record_repository=call_repository,
            recording_dir=tmp_path,
        )
    )
    return CallRecordApi(
        client=client,
        repository=call_repository,
        tenant_id=tenant_id,
        other_tenant_id=other_tenant_id,
        service_id=service_id,
        recording_dir=str(tmp_path),
    )


def payload(api: CallRecordApi, room_name: str = "demo-room") -> dict[str, object]:
    return {
        "customer_service_id": str(api.service_id),
        "room_name": room_name,
        "status": "completed",
        "started_at": "2026-08-03T01:00:00Z",
        "ended_at": "2026-08-03T01:00:12Z",
        "duration_sec": 12,
        "messages": [
            {"role": "user", "text": "我要咨询", "sequence": 1},
            {"role": "assistant", "text": "好的", "sequence": 2},
        ],
    }


def headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def create_record(api: CallRecordApi) -> str:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_upload_and_play_recording(api: CallRecordApi) -> None:
    record_id = create_record(api)
    files = {"file": ("call.webm", b"fake-webm-bytes", "audio/webm")}
    uploaded = api.client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
        files=files,
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["recording_status"] == "ready"
    assert body["recording_mime_type"].startswith("audio/webm")
    assert body["recording_size_bytes"] == len(b"fake-webm-bytes")
    assert "recording_dir" not in body
    assert "path" not in body

    played = api.client.get(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
    )
    assert played.status_code == 200
    assert played.content == b"fake-webm-bytes"
    assert played.headers["content-type"].startswith("audio/webm")


def test_other_tenant_cannot_play_recording(api: CallRecordApi) -> None:
    record_id = create_record(api)
    files = {"file": ("call.webm", b"fake-webm-bytes", "audio/webm")}
    uploaded = api.client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
        files=files,
    )
    assert uploaded.status_code == 200

    played = api.client.get(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.other_tenant_id),
    )
    assert played.status_code == 404


def test_other_tenant_cannot_upload_recording(api: CallRecordApi) -> None:
    record_id = create_record(api)
    files = {"file": ("call.webm", b"fake-webm-bytes", "audio/webm")}
    uploaded = api.client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.other_tenant_id),
        files=files,
    )
    assert uploaded.status_code == 404


def test_empty_upload_returns_400_without_deleting_transcript(
    api: CallRecordApi,
) -> None:
    record_id = create_record(api)
    files = {"file": ("call.webm", b"", "audio/webm")}
    uploaded = api.client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
        files=files,
    )
    assert uploaded.status_code == 400

    detail = api.client.get(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
    )
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["text"] == "我要咨询"
    assert body["recording_status"] == "failed"
    assert body["recording_failure_code"] is not None


def test_unsupported_mime_returns_400(api: CallRecordApi) -> None:
    record_id = create_record(api)
    files = {"file": ("call.txt", b"not-audio", "text/plain")}
    uploaded = api.client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
        files=files,
    )
    assert uploaded.status_code == 400


def test_oversize_upload_returns_413(api: CallRecordApi, tmp_path) -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    service_id = UUID("00000000-0000-0000-0000-000000000101")
    service_repository = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=service_id,
                tenant_id=tenant_id,
            )
        ]
    )
    call_repository = InMemoryCallRecordRepository()
    client = TestClient(
        create_app(
            service_repository,
            call_record_repository=call_repository,
            recording_dir=tmp_path,
            call_recording_max_bytes=10,
        )
    )
    created = client.post(
        "/api/v1/call-records",
        headers=headers(tenant_id),
        json={
            "customer_service_id": str(service_id),
            "room_name": "demo-room",
            "status": "completed",
            "started_at": "2026-08-03T01:00:00Z",
            "ended_at": "2026-08-03T01:00:12Z",
            "duration_sec": 12,
            "messages": [],
        },
    )
    record_id = created.json()["id"]
    files = {"file": ("call.webm", b"x" * 20, "audio/webm")}
    uploaded = client.post(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(tenant_id),
        files=files,
    )
    assert uploaded.status_code == 413


def test_play_recording_not_ready_returns_404(api: CallRecordApi) -> None:
    record_id = create_record(api)
    played = api.client.get(
        f"/api/v1/call-records/{record_id}/recording",
        headers=headers(api.tenant_id),
    )
    assert played.status_code == 404
