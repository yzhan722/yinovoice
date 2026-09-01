from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.domain.insights_dispatch import InsightsDispatchJob
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.insights_dispatch import (
    InMemoryInsightsDispatchRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def _start_payload(ids) -> dict[str, object]:
    return {
        "customer_service_id": str(ids.instance_id),
        "room_name": "sip-melbourne-insights",
        "direction": "inbound",
        "caller_number": "+61 400 000 001",
        "callee_number": "+61400000099",
        "provider_call_id": "livekit-sip-insights",
        "started_at": "2026-08-24T01:00:00Z",
    }


def _client(ids, *, instance=None, insights=None) -> TestClient:
    demo = instance or CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    return TestClient(
        create_app(
            InMemoryCustomerServiceRepository([demo]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            insights_dispatch_repository=insights,
        )
    )


def _finish_with_message(client: TestClient, ids) -> None:
    started = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids),
    )
    assert started.status_code == 201, started.text
    record_id = started.json()["id"]
    posted = client.post(
        f"/api/v1/call-sessions/{record_id}/messages",
        headers=_headers(ids.tenant_id),
        json={"role": "user", "text": "请回电", "sequence": 1},
    )
    assert posted.status_code == 200
    finished = client.post(
        f"/api/v1/call-sessions/{record_id}/finish",
        headers=_headers(ids.tenant_id),
        json={
            "status": "completed",
            "ended_reason": "completed",
            "ended_at": "2026-08-24T01:02:00Z",
        },
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"


def test_finish_without_binding_does_not_enqueue(ids) -> None:
    repo = InMemoryInsightsDispatchRepository()
    _finish_with_message(_client(ids, insights=repo), ids)
    assert repo.all() == []


def test_finish_with_empty_messages_does_not_enqueue(ids) -> None:
    repo = InMemoryInsightsDispatchRepository()
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    ).model_copy(update={"insights_profile": "demo-clinic"})
    client = _client(ids, instance=instance, insights=repo)
    started = client.post(
        "/api/v1/call-sessions/start",
        headers=_headers(ids.tenant_id),
        json=_start_payload(ids),
    )
    assert started.status_code == 201, started.text
    finished = client.post(
        f"/api/v1/call-sessions/{started.json()['id']}/finish",
        headers=_headers(ids.tenant_id),
        json={
            "status": "completed",
            "ended_reason": "completed",
            "ended_at": "2026-08-24T01:02:00Z",
        },
    )
    assert finished.status_code == 200
    assert repo.all() == []


def test_finish_with_binding_enqueues_once(ids) -> None:
    repo = InMemoryInsightsDispatchRepository()
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    ).model_copy(update={"insights_profile": "demo-clinic"})
    _finish_with_message(_client(ids, instance=instance, insights=repo), ids)
    jobs = repo.all()
    assert len(jobs) == 1
    assert jobs[0].profile == "demo-clinic"
    assert jobs[0].status == "pending"
    assert jobs[0].body["channel"] == "yino"
    assert jobs[0].body["recordingUrl"] is None
    assert jobs[0].body["summary"] == ""
    assert "user: 请回电" in str(jobs[0].body["transcript"])


class _RaisingRepo(InMemoryInsightsDispatchRepository):
    async def enqueue(self, job: InsightsDispatchJob) -> InsightsDispatchJob:
        raise RuntimeError("queue down")


def test_finish_survives_queue_error(ids) -> None:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    ).model_copy(update={"insights_profile": "demo-clinic"})
    _finish_with_message(
        _client(ids, instance=instance, insights=_RaisingRepo()),
        ids,
    )
