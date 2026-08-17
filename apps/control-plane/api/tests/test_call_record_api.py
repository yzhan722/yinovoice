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


@pytest.fixture
def api() -> CallRecordApi:
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
        )
    )
    return CallRecordApi(
        client=client,
        repository=call_repository,
        tenant_id=tenant_id,
        other_tenant_id=other_tenant_id,
        service_id=service_id,
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


def test_created_call_record_defaults_recording_none(api: CallRecordApi) -> None:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["recording_status"] == "none"
    assert body["recording_mime_type"] is None
    assert body["recording_size_bytes"] is None
    assert body["recording_failure_code"] is None


def test_create_list_and_detail_call_records(api: CallRecordApi) -> None:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    )

    assert created.status_code == 201
    record = created.json()
    assert record["tenant_id"] == str(api.tenant_id)
    assert record["direction"] == "web"
    assert record["messages"][1] == {
        "role": "assistant",
        "text": "好的",
        "sequence": 2,
    }
    assert "created_at" in record

    listed = api.client.get(
        "/api/v1/call-records?limit=20&offset=0",
        headers=headers(api.tenant_id),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"] == [record]

    detail = api.client.get(
        f"/api/v1/call-records/{record['id']}",
        headers=headers(api.tenant_id),
    )
    assert detail.status_code == 200
    assert detail.json() == record


def test_call_records_are_isolated_by_tenant(api: CallRecordApi) -> None:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    ).json()

    other_list = api.client.get(
        "/api/v1/call-records",
        headers=headers(api.other_tenant_id),
    )
    other_detail = api.client.get(
        f"/api/v1/call-records/{created['id']}",
        headers=headers(api.other_tenant_id),
    )

    assert other_list.status_code == 200
    assert other_list.json() == {"items": [], "total": 0}
    assert other_detail.status_code == 404


def test_create_requires_customer_service_owned_by_tenant(api: CallRecordApi) -> None:
    response = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.other_tenant_id),
        json=payload(api),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Customer service not found"}


def test_list_is_newest_first_and_paginated(api: CallRecordApi) -> None:
    first = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api, "room-first"),
    ).json()
    second = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api, "room-second"),
    ).json()

    response = api.client.get(
        "/api/v1/call-records?limit=1&offset=0",
        headers=headers(api.tenant_id),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"] == [second]
    assert first["id"] != second["id"]


def test_invalid_payload_is_never_persisted(api: CallRecordApi) -> None:
    invalid = {
        **payload(api),
        "ended_at": "2026-08-03T00:59:59Z",
        "provider_token": "must-not-be-stored",
    }

    response = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=invalid,
    )
    listed = api.client.get(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
    )

    assert response.status_code == 422
    assert listed.json() == {"items": [], "total": 0}


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:5173",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:3004",
    ],
)
def test_cors_allows_local_console_development_ports(
    api: CallRecordApi, origin: str
) -> None:
    response = api.client.options(
        "/api/v1/call-records",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Tenant-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    ("query", "expected_status"),
    [
        ("limit=0", 422),
        ("limit=101", 422),
        ("offset=-1", 422),
    ],
)
def test_list_rejects_unbounded_pagination(
    api: CallRecordApi, query: str, expected_status: int
) -> None:
    response = api.client.get(
        f"/api/v1/call-records?{query}",
        headers=headers(api.tenant_id),
    )

    assert response.status_code == expected_status


def test_update_soft_delete_and_restore_call_record(api: CallRecordApi) -> None:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    ).json()
    record_id = created["id"]

    updated = api.client.put(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
        json={
            "status": "interrupted",
            "messages": [
                {"role": "assistant", "text": "更新后的开场", "sequence": 0},
                {"role": "user", "text": "更新后的用户话", "sequence": 1},
            ],
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "interrupted"
    assert body["messages"][0]["text"] == "更新后的开场"
    assert body["deleted_at"] is None

    deleted = api.client.delete(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
    )
    assert deleted.status_code == 204

    listed = api.client.get(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
    )
    assert listed.status_code == 200
    assert listed.json() == {"items": [], "total": 0}

    detail = api.client.get(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
    )
    assert detail.status_code == 404

    listed_deleted = api.client.get(
        "/api/v1/call-records?include_deleted=true",
        headers=headers(api.tenant_id),
    )
    assert listed_deleted.status_code == 200
    assert listed_deleted.json()["total"] == 1
    assert listed_deleted.json()["items"][0]["deleted_at"] is not None

    restored = api.client.post(
        f"/api/v1/call-records/{record_id}/restore",
        headers=headers(api.tenant_id),
    )
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    listed_again = api.client.get(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
    )
    assert listed_again.status_code == 200
    assert listed_again.json()["total"] == 1

    # Idempotent delete
    assert (
        api.client.delete(
            f"/api/v1/call-records/{record_id}",
            headers=headers(api.tenant_id),
        ).status_code
        == 204
    )
    assert (
        api.client.delete(
            f"/api/v1/call-records/{record_id}",
            headers=headers(api.tenant_id),
        ).status_code
        == 204
    )


def test_update_rejected_for_soft_deleted_record(api: CallRecordApi) -> None:
    created = api.client.post(
        "/api/v1/call-records",
        headers=headers(api.tenant_id),
        json=payload(api),
    ).json()
    record_id = created["id"]
    api.client.delete(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
    )

    response = api.client.put(
        f"/api/v1/call-records/{record_id}",
        headers=headers(api.tenant_id),
        json={"status": "failed"},
    )
    assert response.status_code == 404
