from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.industry_scenarios import INDUSTRY_SCENARIOS
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.knowledge import InMemoryKnowledgeRepository
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.repositories.scheduling import InMemorySchedulingRepository


def test_import_industry_demos_is_tenant_scoped_and_idempotent(ids) -> None:
    services = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=ids.instance_id,
                tenant_id=ids.tenant_id,
            )
        ]
    )
    scheduling = InMemorySchedulingRepository()
    knowledge = InMemoryKnowledgeRepository()
    client = TestClient(
        create_app(
            services,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=scheduling,
            knowledge_repository=knowledge,
        )
    )
    headers = {"X-Tenant-ID": str(ids.tenant_id)}
    first = client.post("/api/v1/customer-services/industry-demos", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"created": 7, "skipped": 0}

    listed = client.get(
        "/api/v1/customer-services?limit=100&offset=0",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 8
    names = {item["display_name"] for item in listed.json()["items"]}
    assert "银杏口腔前台" in names
    assert "青禾私房菜订位" in names

    dental = next(
        item
        for item in listed.json()["items"]
        if item["display_name"] == "银杏口腔前台"
    )
    offerings = client.get(
        f"/api/v1/service-offerings?voice_agent_instance_id={dental['id']}",
        headers=headers,
    )
    assert offerings.status_code == 200, offerings.text
    offering_names = {item["name"] for item in offerings.json()}
    assert "洁牙" in offering_names

    second = client.post("/api/v1/customer-services/industry-demos", headers=headers)
    assert second.status_code == 200
    assert second.json() == {"created": 0, "skipped": 7}

    other = client.post(
        "/api/v1/customer-services/industry-demos",
        headers={"X-Tenant-ID": str(ids.other_tenant_id)},
    )
    assert other.status_code == 200
    assert other.json()["created"] == 7
    assert len(INDUSTRY_SCENARIOS) == 7
