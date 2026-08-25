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


def test_dashboard_summary_uses_live_counts(ids) -> None:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    client = TestClient(
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
    headers = {"X-Tenant-ID": str(ids.tenant_id)}
    created = client.post(
        "/api/v1/callback-tasks",
        headers=headers,
        json={"caller_phone": "13800138000", "reason": "确认档期"},
    )
    assert created.status_code == 201, created.text
    summary = client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["callbacks"]["open"] == 1
    assert "callStats" in body
    assert len(body["callStats"]["trend"]) == 7
