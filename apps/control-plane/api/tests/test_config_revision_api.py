from uuid import UUID

from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import (
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.repositories.scheduling import InMemorySchedulingRepository

TENANT_HEADER = {"X-Tenant-ID": str(DEMO_TENANT_ID)}


def _client() -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        tenant_id=DEMO_TENANT_ID,
    )
    return TestClient(
        create_app(
            InMemoryCustomerServiceRepository([instance]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
        )
    )


def _created_instance(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/customer-services",
        headers=TENANT_HEADER,
        json={
            "display_name": "发布测试客服",
            "organization_name": "合成诊所",
            "greeting": "您好，这里是合成诊所。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_auto_publishes_baseline_revision() -> None:
    client = _client()
    created = _created_instance(client)
    listed = client.get(
        f"/api/v1/customer-services/{created['id']}/revisions",
        headers=TENANT_HEADER,
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    revision = body["items"][0]
    assert revision["revision"] == 1
    assert revision["source"] == "create"
    assert revision["snapshot"]["greeting"] == "您好，这里是合成诊所。"


def test_publish_diff_and_rollback_restore_snapshot() -> None:
    client = _client()
    created = _created_instance(client)
    instance_id = created["id"]

    updated = client.put(
        f"/api/v1/customer-services/{instance_id}",
        headers=TENANT_HEADER,
        json={
            "expected_version": created["version"],
            "display_name": created["display_name"],
            "organization_name": created["organization_name"],
            "greeting": "改过的欢迎语。",
            "platform_prompt": created["platform_prompt"],
            "tenant_prompt": created["tenant_prompt"],
            "voice": created["voice"],
            "response": created["response"],
            "insights_profile": created.get("insights_profile"),
        },
    )
    assert updated.status_code == 200, updated.text
    current = updated.json()

    diff = client.get(
        f"/api/v1/customer-services/{instance_id}/config-diff",
        headers=TENANT_HEADER,
    )
    assert diff.status_code == 200, diff.text
    diff_body = diff.json()
    assert diff_body["published_revision"] == 1
    assert any(
        change["field"] == "greeting"
        and change["after"] == "改过的欢迎语。"
        for change in diff_body["changes"]
    )

    published = client.post(
        f"/api/v1/customer-services/{instance_id}/publish",
        headers=TENANT_HEADER,
    )
    assert published.status_code == 200, published.text
    assert published.json()["revision"] == 2
    assert published.json()["source"] == "publish"

    empty_diff = client.get(
        f"/api/v1/customer-services/{instance_id}/config-diff",
        headers=TENANT_HEADER,
    )
    assert empty_diff.json()["changes"] == []

    rolled = client.post(
        f"/api/v1/customer-services/{instance_id}/rollback",
        headers=TENANT_HEADER,
        json={"revision": 1, "expected_version": current["version"]},
    )
    assert rolled.status_code == 200, rolled.text
    restored = rolled.json()["instance"]
    assert restored["greeting"] == "您好，这里是合成诊所。"
    assert restored["version"] == current["version"] + 1
    assert rolled.json()["revision"]["source"] == "rollback"
    assert rolled.json()["revision"]["revision"] == 3


def test_rollback_rejects_version_conflict() -> None:
    client = _client()
    created = _created_instance(client)
    response = client.post(
        f"/api/v1/customer-services/{created['id']}/rollback",
        headers=TENANT_HEADER,
        json={"revision": 1, "expected_version": 99},
    )
    assert response.status_code == 409
