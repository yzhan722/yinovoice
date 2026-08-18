from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)


def test_list_customer_services_is_tenant_scoped(client, ids) -> None:
    response = client.get(
        "/api/v1/customer-services?limit=20&offset=0",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [
        str(ids.instance_id)
    ]

    other = client.get(
        "/api/v1/customer-services",
        headers={"X-Tenant-ID": str(ids.other_tenant_id)},
    )
    assert other.status_code == 200
    assert other.json() == {"items": [], "total": 0}


def test_list_customer_services_validates_pagination(client, ids) -> None:
    response = client.get(
        "/api/v1/customer-services?limit=0&offset=-1",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    )

    assert response.status_code == 422


def test_create_customer_service_owns_identity_and_is_queryable(client, ids) -> None:
    response = client.post(
        "/api/v1/customer-services",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "display_name": "Synthetic Support",
            "organization_name": "Demo Organization",
            "greeting": "Hello, how may I help you?",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["tenant_id"] == str(ids.tenant_id)
    assert created["version"] == 1
    assert created["voice"]["tts_voice"] == "longanqian"
    assert client.get(
        f"/api/v1/customer-services/{created['id']}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    ).status_code == 200
    denied = client.get(
        f"/api/v1/customer-services/{created['id']}",
        headers={"X-Tenant-ID": str(ids.other_tenant_id)},
    )
    assert denied.status_code == 404


def test_create_customer_service_rejects_server_owned_fields(client, ids) -> None:
    response = client.post(
        "/api/v1/customer-services",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={
            "id": str(ids.instance_id),
            "tenant_id": str(ids.other_tenant_id),
            "version": 99,
            "display_name": "Synthetic Support",
            "organization_name": "Demo Organization",
            "greeting": "Hello, how may I help you?",
        },
    )

    assert response.status_code == 422


def test_get_customer_service_is_tenant_scoped(client, ids) -> None:
    response = client.get(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "常州太平洋口腔语音客服"
    assert body["voice"]["preset_id"] == "mandarin-standard"
    assert body["voice"]["tts_voice"] == "longanqian"
    assert "platform_prompt" in body
    assert "tenant_prompt" in body
    assert not {
        "provider_config_id",
        "model_id",
        "voice_id",
    }.intersection(body["voice"])

    denied = client.get(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.other_tenant_id)},
    )
    assert denied.status_code == 404


def test_update_requires_matching_version(client, ids) -> None:
    current = client.get(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    ).json()
    current["expected_version"] = current.pop("version")
    current.pop("id")
    current.pop("tenant_id")
    current.pop("business_profile")
    current.pop("primary_language")
    current.pop("deleted_at", None)
    current["display_name"] = "Yino \u524d\u53f0\u5ba2\u670d"

    updated = client.put(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json=current,
    )

    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["display_name"] == "Yino \u524d\u53f0\u5ba2\u670d"

    conflict = client.put(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json=current,
    )
    assert conflict.status_code == 409


def test_update_rejects_unknown_voice_preset(client, ids) -> None:
    current = client.get(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    ).json()
    current["expected_version"] = current.pop("version")
    for field in ("id", "tenant_id", "business_profile", "primary_language", "deleted_at"):
        current.pop(field, None)
    current["voice"]["preset_id"] = "tenant-selected-provider-model-voice"

    response = client.put(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json=current,
    )

    assert response.status_code == 422


def test_update_rejects_disabling_one_question_at_a_time(client, ids) -> None:
    current = client.get(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
    ).json()
    current["expected_version"] = current.pop("version")
    for field in ("id", "tenant_id", "business_profile", "primary_language", "deleted_at"):
        current.pop(field, None)
    current["response"]["ask_one_question_at_a_time"] = False

    response = client.put(
        f"/api/v1/customer-services/{ids.instance_id}",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json=current,
    )

    assert response.status_code == 422


def test_default_app_seeds_stable_demo_customer_service() -> None:
    client = TestClient(create_app())

    response = client.get(
        f"/api/v1/customer-services/{DEMO_CUSTOMER_SERVICE_ID}",
        headers={"X-Tenant-ID": str(DEMO_TENANT_ID)},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(DEMO_CUSTOMER_SERVICE_ID)


def test_soft_delete_restore_and_purge_customer_service(client, ids) -> None:
    headers = {"X-Tenant-ID": str(ids.tenant_id)}
    created = client.post(
        "/api/v1/customer-services",
        headers=headers,
        json={
            "display_name": "Purge Candidate",
            "organization_name": "Demo Organization",
            "greeting": "Hello, how may I help you?",
        },
    )
    assert created.status_code == 201
    instance_id = created.json()["id"]

    deleted = client.delete(
        f"/api/v1/customer-services/{instance_id}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/v1/customer-services/{instance_id}",
            headers=headers,
        ).status_code
        == 404
    )
    listed = client.get("/api/v1/customer-services", headers=headers)
    assert instance_id not in [item["id"] for item in listed.json()["items"]]

    with_deleted = client.get(
        "/api/v1/customer-services?include_deleted=true",
        headers=headers,
    )
    assert with_deleted.status_code == 200
    soft = next(
        item for item in with_deleted.json()["items"] if item["id"] == instance_id
    )
    assert soft["deleted_at"] is not None

    assert (
        client.delete(
            f"/api/v1/customer-services/{instance_id}",
            headers=headers,
        ).status_code
        == 204
    )

    restored = client.post(
        f"/api/v1/customer-services/{instance_id}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None
    assert (
        client.get(
            f"/api/v1/customer-services/{instance_id}",
            headers=headers,
        ).status_code
        == 200
    )

    assert (
        client.post(
            f"/api/v1/customer-services/{instance_id}/purge",
            headers=headers,
        ).status_code
        == 409
    )

    assert (
        client.delete(
            f"/api/v1/customer-services/{instance_id}",
            headers=headers,
        ).status_code
        == 204
    )
    purged = client.post(
        f"/api/v1/customer-services/{instance_id}/purge",
        headers=headers,
    )
    assert purged.status_code == 204
    remaining = client.get(
        "/api/v1/customer-services?include_deleted=true",
        headers=headers,
    ).json()["items"]
    assert instance_id not in [item["id"] for item in remaining]


def test_purge_blocked_when_call_records_exist(client, ids) -> None:
    headers = {"X-Tenant-ID": str(ids.tenant_id)}
    created = client.post(
        "/api/v1/customer-services",
        headers=headers,
        json={
            "display_name": "With Calls",
            "organization_name": "Demo Organization",
            "greeting": "Hello, how may I help you?",
        },
    )
    instance_id = created.json()["id"]
    record = client.post(
        "/api/v1/call-records",
        headers=headers,
        json={
            "customer_service_id": instance_id,
            "room_name": "room-a3-purge-block",
            "status": "completed",
            "started_at": "2026-08-17T01:00:00+00:00",
            "ended_at": "2026-08-17T01:01:00+00:00",
            "duration_sec": 60,
            "messages": [],
        },
    )
    assert record.status_code == 201

    assert (
        client.delete(
            f"/api/v1/customer-services/{instance_id}",
            headers=headers,
        ).status_code
        == 204
    )
    blocked = client.post(
        f"/api/v1/customer-services/{instance_id}/purge",
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "call records" in blocked.json()["detail"]
