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
from yino_platform_api.services.knowledge_compile import KNOWLEDGE_END, KNOWLEDGE_START

TENANT_HEADER = {"X-Tenant-ID": str(DEMO_TENANT_ID)}
DEMO_INSTANCE_ID = UUID("00000000-0000-0000-0000-000000000101")


def _client() -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=DEMO_INSTANCE_ID,
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


def test_knowledge_document_apply_compiles_into_tenant_prompt() -> None:
    client = _client()
    instance_id = str(DEMO_INSTANCE_ID)
    created = client.post(
        f"/api/v1/customer-services/{instance_id}/knowledge",
        headers=TENANT_HEADER,
        json={"title": "客服热线", "body": "400-0519-020"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["title"] == "客服热线"

    applied = client.post(
        f"/api/v1/customer-services/{instance_id}/knowledge/apply",
        headers=TENANT_HEADER,
        json={"expected_version": 1},
    )
    assert applied.status_code == 200, applied.text
    prompt = applied.json()["tenant_prompt"]
    assert KNOWLEDGE_START in prompt
    assert KNOWLEDGE_END in prompt
    assert "400-0519-020" in prompt
    assert applied.json()["version"] == 2

    listed = client.get(
        f"/api/v1/customer-services/{instance_id}/knowledge",
        headers=TENANT_HEADER,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_knowledge_apply_replaces_previous_block() -> None:
    client = _client()
    instance_id = str(DEMO_INSTANCE_ID)
    first = client.post(
        f"/api/v1/customer-services/{instance_id}/knowledge",
        headers=TENANT_HEADER,
        json={"title": "旧条目", "body": "旧知识"},
    ).json()
    client.post(
        f"/api/v1/customer-services/{instance_id}/knowledge/apply",
        headers=TENANT_HEADER,
        json={"expected_version": 1},
    )
    client.put(
        f"/api/v1/customer-services/{instance_id}/knowledge/{first['id']}",
        headers=TENANT_HEADER,
        json={"title": "新条目", "body": "新知识"},
    )
    applied = client.post(
        f"/api/v1/customer-services/{instance_id}/knowledge/apply",
        headers=TENANT_HEADER,
        json={"expected_version": 2},
    )
    assert applied.status_code == 200, applied.text
    prompt = applied.json()["tenant_prompt"]
    assert prompt.count(KNOWLEDGE_START) == 1
    assert "新知识" in prompt
    assert "旧知识" not in prompt


def test_knowledge_apply_rejects_version_conflict() -> None:
    client = _client()
    response = client.post(
        f"/api/v1/customer-services/{DEMO_INSTANCE_ID}/knowledge/apply",
        headers=TENANT_HEADER,
        json={"expected_version": 99},
    )
    assert response.status_code == 409
