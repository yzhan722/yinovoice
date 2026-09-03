"""Phase 2: extract appointment/callback intents from call transcripts."""

from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.call_record import CallRecord, TranscriptMessage
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.domain.scheduling import (
    BusinessHours,
    SchedulingProfile,
    ServiceOffering,
)
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.repositories.scheduling import InMemorySchedulingRepository
from yino_platform_api.services.intent_extract import (
    extract_intents_from_text,
    persist_extracted_intents,
)
from yino_platform_api.services.notifications import (
    FakeNotificationSink,
    InMemoryNotificationRepository,
    NotificationService,
    NotificationSettings,
)


def _ids() -> tuple[UUID, UUID]:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    service_id = UUID("00000000-0000-0000-0000-000000000101")
    return tenant_id, service_id


def _record(tenant_id: UUID, service_id: UUID) -> CallRecord:
    return CallRecord(
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


async def _seed_memory_schedule(
    scheduling: InMemorySchedulingRepository,
    tenant_id: UUID,
    instance_id: UUID,
) -> UUID:
    stamp = datetime.now(UTC)
    offering = ServiceOffering(
        id=UUID("00000000-0000-0000-0000-000000000401"),
        tenant_id=tenant_id,
        voice_agent_instance_id=instance_id,
        name="洁牙",
        duration_minutes=30,
        buffer_minutes=0,
        created_at=stamp,
        updated_at=stamp,
    )
    await scheduling.create_offering(offering)
    await scheduling.upsert_profile(
        SchedulingProfile(
            tenant_id=tenant_id,
            voice_agent_instance_id=instance_id,
            timezone="Australia/Melbourne",
            slot_interval_minutes=30,
            minimum_notice_minutes=0,
            booking_horizon_days=365,
            updated_at=stamp,
        )
    )
    hours: list[BusinessHours] = []
    for weekday in range(5):
        hours.append(
            BusinessHours(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                weekday=weekday,
                start_local="09:00",
                end_local="12:00",
            )
        )
        hours.append(
            BusinessHours(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                weekday=weekday,
                start_local="13:00",
                end_local="17:00",
            )
        )
    await scheduling.replace_hours(tenant_id, instance_id, hours)
    return offering.id


def _seed_schedule_http(client: TestClient, tenant_id: UUID, instance_id: UUID) -> str:
    headers = {"X-Tenant-ID": str(tenant_id)}
    offering = client.post(
        "/api/v1/service-offerings",
        headers=headers,
        json={
            "voice_agent_instance_id": str(instance_id),
            "name": "洁牙",
            "duration_minutes": 30,
            "buffer_minutes": 0,
        },
    )
    assert offering.status_code == 201, offering.text
    profile = client.put(
        f"/api/v1/scheduling-profiles/{instance_id}",
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
        hours.append(
            {"weekday": weekday, "start_local": "09:00", "end_local": "12:00"}
        )
        hours.append(
            {"weekday": weekday, "start_local": "13:00", "end_local": "17:00"}
        )
    replaced = client.put(
        f"/api/v1/business-hours?voice_agent_instance_id={instance_id}",
        headers=headers,
        json=hours,
    )
    assert replaced.status_code == 200, replaced.text
    return offering.json()["id"]


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


def test_extract_slot_uses_clinic_timezone() -> None:
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    result = extract_intents_from_text(
        "我想约周五下午洁牙，我叫王芳，电话13800138000",
        now=now,
        timezone="Australia/Melbourne",
    )
    assert result.kind == "appointment"
    assert result.slot_start is not None
    local = result.slot_start.astimezone(ZoneInfo("Australia/Melbourne"))
    assert local.weekday() == 4
    assert local.hour == 14
    assert result.slot_start.tzinfo is not None
    assert result.slot_start.utcoffset() == UTC.utcoffset(result.slot_start)


def test_extract_au_mobile_phone() -> None:
    result = extract_intents_from_text("请回电，我叫王芳，号码+61400000001")
    assert result.kind == "callback"
    assert result.phone == "+61400000001"


def test_extract_appointment_even_when_incomplete() -> None:
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)  # Monday
    result = extract_intents_from_text("我想预约洁牙，回头再说时间", now=now)
    assert result.kind == "callback"
    assert result.phone == "待确认电话"
    assert result.service == "洁牙"
    assert result.slot_start is None
    assert "时段未确认" in result.reason


def test_extract_skips_when_caller_declines_booking() -> None:
    result = extract_intents_from_text("先不预约，谢谢")
    assert result.kind == "skip"


def test_extract_callback_includes_name_in_reason() -> None:
    result = extract_intents_from_text("请回电，我叫王芳，号码13900139000")
    assert result.kind == "callback"
    assert result.patient_name == "王芳"
    assert result.reason.startswith("王芳")


def test_extract_restaurant_and_education_booking_phrases() -> None:
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    dinner = extract_intents_from_text(
        "我想订桌周五晚上，我叫王芳，电话13800138000",
        now=now,
        timezone="Asia/Shanghai",
    )
    assert dinner.kind == "appointment"
    assert dinner.service == "晚市4人桌"

    trial = extract_intents_from_text(
        "帮我约周六上午少儿英语试听，我叫李明，电话13900139000",
        now=now,
        timezone="Asia/Shanghai",
    )
    assert trial.kind == "appointment"
    assert trial.service == "少儿英语试听"


@pytest.mark.asyncio
async def test_persist_without_schedule_writes_callback() -> None:
    tenant_id, service_id = _ids()
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)

    first = await persist_extracted_intents(
        _record(tenant_id, service_id),
        appointments=appointments,
        callbacks=callbacks,
        now=now,
    )
    second = await persist_extracted_intents(
        _record(tenant_id, service_id),
        appointments=appointments,
        callbacks=callbacks,
        now=now,
    )
    assert first.appointment_id is None
    assert first.callback_task_id is not None
    assert first.callback_task_id == second.callback_task_id
    listed, total = await appointments.list_for_tenant(tenant_id, limit=20, offset=0)
    assert total == 0
    assert listed == []
    tasks, task_total = await callbacks.list_for_tenant(tenant_id, limit=20, offset=0)
    assert task_total == 1
    assert "未配置排期" in tasks[0].reason


@pytest.mark.asyncio
async def test_persist_with_available_slot_is_idempotent() -> None:
    tenant_id, service_id = _ids()
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    scheduling = InMemorySchedulingRepository()
    await _seed_memory_schedule(scheduling, tenant_id, service_id)
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    record = _record(tenant_id, service_id)

    first = await persist_extracted_intents(
        record,
        appointments=appointments,
        callbacks=callbacks,
        scheduling=scheduling,
        now=now,
    )
    second = await persist_extracted_intents(
        record,
        appointments=appointments,
        callbacks=callbacks,
        scheduling=scheduling,
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
    assert listed[0].service_offering_id is not None
    assert "语音自动登记意向" in listed[0].notes
    assert "摘要：" in listed[0].notes
    local = listed[0].slot_start.astimezone(ZoneInfo("Australia/Melbourne"))
    assert local.hour == 14
    assert local.weekday() == 4


@pytest.mark.asyncio
async def test_persist_unavailable_slot_writes_callback() -> None:
    tenant_id, service_id = _ids()
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    scheduling = InMemorySchedulingRepository()
    offering_id = await _seed_memory_schedule(scheduling, tenant_id, service_id)
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    first = await persist_extracted_intents(
        _record(tenant_id, service_id),
        appointments=appointments,
        callbacks=callbacks,
        scheduling=scheduling,
        now=now,
    )
    assert first.appointment_id is not None
    occupied_record = _record(tenant_id, service_id).model_copy(
        update={"id": UUID("00000000-0000-0000-0000-000000000202")}
    )
    second = await persist_extracted_intents(
        occupied_record,
        appointments=appointments,
        callbacks=callbacks,
        scheduling=scheduling,
        now=now,
    )
    assert second.appointment_id is None
    assert second.callback_task_id is not None
    _, apt_total = await appointments.list_for_tenant(tenant_id, limit=20, offset=0)
    assert apt_total == 1
    tasks, _ = await callbacks.list_for_tenant(tenant_id, limit=20, offset=0)
    assert any("需人工确认档期" in item.reason for item in tasks)
    assert offering_id is not None


@pytest.mark.asyncio
async def test_persist_notifies_on_appointment() -> None:
    tenant_id, service_id = _ids()
    appointments = InMemoryAppointmentRepository()
    callbacks = InMemoryCallbackTaskRepository()
    scheduling = InMemorySchedulingRepository()
    await _seed_memory_schedule(scheduling, tenant_id, service_id)
    repo = InMemoryNotificationRepository()
    sink = FakeNotificationSink()
    notifications = NotificationService(repo, sink)
    await repo.upsert_settings(
        NotificationSettings(
            tenant_id=tenant_id,
            email="ops@example.test",
            enabled=True,
            updated_at=datetime.now(UTC),
        )
    )
    await persist_extracted_intents(
        _record(tenant_id, service_id),
        appointments=appointments,
        callbacks=callbacks,
        scheduling=scheduling,
        notifications=notifications,
        now=datetime(2026, 8, 17, 9, 0, tzinfo=UTC),
    )
    assert sink.sent[0][0] == "ops@example.test"
    assert repo._events[0].kind == "appointment"


def _client(tenant_id: UUID, service_id: UUID) -> TestClient:
    services = InMemoryCustomerServiceRepository(
        [
            CustomerServiceInstance.demo(
                instance_id=service_id,
                tenant_id=tenant_id,
            )
        ]
    )
    return TestClient(
        create_app(
            services,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
        )
    )


def test_extract_intents_api_writes_callback_without_schedule() -> None:
    tenant_id, service_id = _ids()
    client = _client(tenant_id, service_id)
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
    assert listed.json()["total"] == 0
    callbacks = client.get("/api/v1/callback-tasks", headers=headers)
    assert callbacks.status_code == 200
    assert callbacks.json()["total"] == 1

    again = client.post(
        f"/api/v1/call-records/{record_id}/extract-intents",
        headers=headers,
    )
    assert again.status_code == 200
    body = again.json()
    assert body["appointment_id"] is None
    assert body["callback_task_id"] == callbacks.json()["items"][0]["id"]
    assert body["skipped_reason"] == "already extracted"


def test_extract_intents_api_creates_appointment_when_slot_available() -> None:
    tenant_id, service_id = _ids()
    client = _client(tenant_id, service_id)
    headers = {"X-Tenant-ID": str(tenant_id)}
    _seed_schedule_http(client, tenant_id, service_id)

    created = client.post(
        "/api/v1/call-records",
        headers=headers,
        json={
            "customer_service_id": str(service_id),
            "room_name": "extract-room-bookable",
            "status": "completed",
            "started_at": "2026-08-17T01:00:00Z",
            "ended_at": "2026-08-17T01:02:00Z",
            "duration_sec": 120,
            "messages": [
                {
                    "role": "user",
                    "text": "我想约周五下午洁牙，我叫王芳，电话13800138000",
                    "sequence": 1,
                }
            ],
        },
    )
    assert created.status_code == 201
    listed = client.get("/api/v1/appointments", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    item = listed.json()["items"][0]
    assert item["source"] == "voice_tool"
    assert item["call_record_id"] == created.json()["id"]
    assert item["service_offering_id"] is not None
