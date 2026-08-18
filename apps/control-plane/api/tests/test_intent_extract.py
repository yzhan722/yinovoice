"""Phase 2: extract appointment/callback intents from call transcripts."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.call_record import CallRecord, TranscriptMessage
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.services.intent_extract import (
    extract_intents_from_text,
    persist_extracted_intents,
)


def _ids() -> tuple[UUID, UUID]:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    service_id = UUID("00000000-0000-0000-0000-000000000101")
    return tenant_id, service_id


def test_extract_appointment_from_clear_intent() -> None:
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)  # Monday
    result = extract_intents_from_text(
        "我想约周五下午洁牙，我叫王芳，电话13800138000",
        now=now,
    )
    assert result.kind == "appointment"
    assert result.patient_name == "王芳"
    assert result.phone == "13800138000"
    assert result.service == "洁牙"
    assert result.slot_start is not None
    assert result.slot_start.weekday() == 4  # Friday
    assert result.slot_start.hour == 14


def test_extract_appointment_even_when_incomplete() -> None:
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)  # Monday
    result = extract_intents_from_text("我想预约洁牙，回头再说时间", now=now)
    assert result.kind == "appointment"
    assert result.phone == "待确认电话"
    assert result.service == "洁牙"
    assert result.slot_start is not None
    assert result.slot_start.weekday() < 5
    assert "时段待确认" in result.notes
    assert "电话待确认" in result.notes


def test_extract_callback_includes_name_in_reason() -> None:
    result = extract_intents_from_text("请回电，我叫王芳，号码13900139000")
    assert result.kind == "callback"
    assert result.patient_name == "王芳"
    assert result.reason.startswith("王芳")


def test_extract_skips_when_no_intent() -> None:
    result = extract_intents_from_text("你们几点开门？")
    assert result.kind == "skip"


@pytest.mark.asyncio
async def test_persist_is_idempotent_for_same_call_record() -> None:
    tenant_id, service_id = _ids()
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    record = CallRecord(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        tenant_id=tenant_id,
        customer_service_id=service_id,
        room_name="r1",
        status="completed",
        started_at=datetime(2026, 8, 17, 1, 0, tzinfo=UTC),
        ended_at=datetime(2026, 8, 17, 1, 1, tzinfo=UTC),
        duration_sec=60,
        messages=[
            TranscriptMessage(
                role="user",
                text="我想约周五下午洁牙，电话13800138000，我叫李明",
                sequence=1,
            )
        ],
        created_at=datetime(2026, 8, 17, 1, 1, tzinfo=UTC),
    )
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)

    first = await persist_extracted_intents(
        record,
        appointments=appointments,
        callbacks=callbacks,
        now=now,
    )
    second = await persist_extracted_intents(
        record,
        appointments=appointments,
        callbacks=callbacks,
        now=now,
    )
    assert first.appointment_id is not None
    assert first.appointment_id == second.appointment_id
    listed, total = await appointments.list_for_tenant(
        tenant_id, limit=20, offset=0
    )
    assert total == 1
    assert listed[0].source == "voice_tool"
    assert listed[0].call_record_id == record.id
    assert "语音自动登记意向" in listed[0].notes
    assert "摘要：" in listed[0].notes


def test_extract_intents_api_and_auto_on_create() -> None:
    tenant_id, service_id = _ids()
    services = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=service_id,
                tenant_id=tenant_id,
            )
        ]
    )
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    client = TestClient(
        create_app(
            services,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=appointments,
            callback_task_repository=callbacks,
        )
    )
    headers = {"X-Tenant-ID": str(tenant_id)}

    created = client.post(
        "/api/v1/call-records",
        headers=headers,
        json={
            "customer_service_id": str(service_id),
            "room_name": "extract-room",
            "status": "completed",
            "started_at": "2026-08-17T01:00:00Z",
            "ended_at": "2026-08-17T01:02:00Z",
            "duration_sec": 120,
            "messages": [
                {
                    "role": "user",
                    "text": "我想约周五下午洁牙，我叫王芳，电话13800138000",
                    "sequence": 1,
                },
                {
                    "role": "assistant",
                    "text": "已记下您的意向，工作人员会联系确认档期。",
                    "sequence": 2,
                },
            ],
        },
    )
    assert created.status_code == 201
    record_id = created.json()["id"]

    listed = client.get("/api/v1/appointments", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["source"] == "voice_tool"
    assert listed.json()["items"][0]["call_record_id"] == record_id

    again = client.post(
        f"/api/v1/call-records/{record_id}/extract-intents",
        headers=headers,
    )
    assert again.status_code == 200
    body = again.json()
    assert body["appointment_id"] == listed.json()["items"][0]["id"]
    assert body["callback_task_id"] is None
    assert body["skipped_reason"] == "already extracted"
