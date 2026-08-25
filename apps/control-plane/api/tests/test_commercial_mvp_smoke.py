"""Synthetic commercial MVP smoke (manual checklist A-E).

Uses in-memory repositories only. No network, no secrets, no production data.
Run via scripts/smoke_commercial_mvp.py or:

    .venv\\Scripts\\python.exe -m pytest tests/test_commercial_mvp_smoke.py -q
"""

from __future__ import annotations

from datetime import date
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
from yino_platform_api.services.notifications import InMemoryNotificationRepository


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
            notification_repository=InMemoryNotificationRepository(),
        )
    )


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def test_commercial_mvp_synthetic_loop_a_to_e(ids) -> None:
    client = _client(ids)
    headers = _headers(ids.tenant_id)

    created_phone = client.post(
        "/api/v1/phone-numbers",
        headers=headers,
        json={
            "e164_number": "+61 400 000 001",
            "voice_agent_instance_id": str(ids.instance_id),
        },
    )
    assert created_phone.status_code == 201, created_phone.text
    lookup = client.get("/api/v1/phone-numbers/lookup?number=%2B61400000001")
    assert lookup.status_code == 200
    assert lookup.json()["voice_agent_instance_id"] == str(ids.instance_id)

    started = client.post(
        "/api/v1/call-sessions/start",
        headers=headers,
        json={
            "customer_service_id": str(ids.instance_id),
            "room_name": "sip-smoke-1",
            "direction": "inbound",
            "caller_number": "+61400000001",
            "callee_number": "+61400000099",
            "provider_call_id": "livekit-sip-smoke",
        },
    )
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "in_progress"
    record_id = started.json()["id"]

    offering = client.post(
        "/api/v1/service-offerings",
        headers=headers,
        json={
            "voice_agent_instance_id": str(ids.instance_id),
            "name": "洁牙",
            "duration_minutes": 30,
            "buffer_minutes": 0,
        },
    )
    assert offering.status_code == 201, offering.text
    offering_id = offering.json()["id"]
    profile = client.put(
        f"/api/v1/scheduling-profiles/{ids.instance_id}",
        headers=headers,
        json={
            "timezone": "Australia/Melbourne",
            "slot_interval_minutes": 30,
            "minimum_notice_minutes": 0,
            "booking_horizon_days": 365,
        },
    )
    assert profile.status_code == 200, profile.text
    hours = []
    for weekday in range(5):
        hours.append({"weekday": weekday, "start_local": "09:00", "end_local": "12:00"})
        hours.append({"weekday": weekday, "start_local": "13:00", "end_local": "17:00"})
    replaced = client.put(
        f"/api/v1/business-hours?voice_agent_instance_id={ids.instance_id}",
        headers=headers,
        json=hours,
    )
    assert replaced.status_code == 200, replaced.text
    day = date(2026, 9, 1)
    availability = client.get(
        "/api/v1/availability",
        headers=headers,
        params={
            "voice_agent_instance_id": str(ids.instance_id),
            "service_offering_id": offering_id,
            "date_from": day.isoformat(),
            "date_to": day.isoformat(),
        },
    )
    assert availability.status_code == 200, availability.text
    morning = next(
        item
        for item in availability.json()["items"]
        if "T09:00:00" in item["slot_start_local"]
    )

    tool = client.post(
        "/api/v1/tool-invocations",
        headers=headers,
        json={
            "session_id": "sip-smoke-1",
            "call_record_id": record_id,
            "voice_agent_instance_id": str(ids.instance_id),
            "tool_name": "create_appointment",
            "arguments": {
                "patient_name": "王芳",
                "phone": "13800138000",
                "service": "洁牙",
                "slot_start": morning["slot_start_utc"],
                "slot_end": morning["slot_end_utc"],
                "service_offering_id": offering_id,
            },
            "idempotency_key": "sip-smoke-1:create_appointment:once",
        },
    )
    assert tool.status_code == 200, tool.text
    assert tool.json()["status"] == "ok"
    replay = client.post(
        "/api/v1/tool-invocations",
        headers=headers,
        json={
            "session_id": "sip-smoke-1",
            "call_record_id": record_id,
            "voice_agent_instance_id": str(ids.instance_id),
            "tool_name": "create_appointment",
            "arguments": {
                "patient_name": "王芳",
                "phone": "13800138000",
                "service": "洁牙",
                "slot_start": morning["slot_start_utc"],
                "slot_end": morning["slot_end_utc"],
                "service_offering_id": offering_id,
            },
            "idempotency_key": "sip-smoke-1:create_appointment:once",
        },
    )
    assert replay.json()["invocation_id"] == tool.json()["invocation_id"]
    listed_tools = client.get(
        f"/api/v1/tool-invocations?call_record_id={record_id}",
        headers=headers,
    )
    assert listed_tools.status_code == 200
    assert listed_tools.json()[0]["tool_name"] == "create_appointment"

    notify = client.put(
        "/api/v1/notification-settings",
        headers=headers,
        json={"email": "ops@example.test", "enabled": True},
    )
    assert notify.status_code == 200, notify.text
    assert notify.json()["email"] == "ops@example.test"

    finished = client.post(
        f"/api/v1/call-sessions/{record_id}/finish",
        headers=headers,
        json={
            "status": "completed",
            "ended_reason": "completed",
            "ended_at": "2026-09-01T01:20:00Z",
        },
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"

    summary = client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert "callStats" in body
    assert len(body["callStats"]["trend"]) == 7
    assert client.get("/api/v1/appointments", headers=headers).json()["total"] == 1
