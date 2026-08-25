"""Rule-based appointment / callback intent extraction from call transcripts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..domain.appointment import Appointment
from ..domain.call_record import CallRecord
from ..domain.callback_task import CallbackTask
from ..repositories.appointments import AppointmentRepository
from ..repositories.callback_tasks import CallbackTaskRepository
from ..repositories.scheduling import SchedulingRepository
from ..repositories.tool_invocations import ToolInvocationRepository
from .booking import SlotUnavailableError, ensure_slot_available
from .notifications import NotificationService

logger = logging.getLogger(__name__)

IntentKind = Literal["appointment", "callback", "skip"]

_APPOINTMENT_WORDS = re.compile(
    r"(预约|想约|约个|挂号|约一下|帮我约|想挂号)"
)
_DECLINE_APPOINTMENT = re.compile(
    r"(先不预约|不要预约|暂不预约|不用约|先不约)"
)
_CALLBACK_WORDS = re.compile(
    r"(回电|回拨|打电话给我|请联系我|联系我|请.*回电)"
)
_PHONE_CN_RE = re.compile(r"(?:\+?86)?(1[3-9]\d{9})")
_PHONE_AU_RE = re.compile(r"(\+614\d{8})")
_NAME_RE = re.compile(
    r"(?:我叫|我是|叫我|姓名是|姓名：|姓名:)\s*([^\s，,。！!？?]{1,8})"
    r"|我姓([一-龥])"
)
_SERVICE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("洁牙", "洁牙"),
    ("洗牙", "洁牙"),
    ("补牙", "补牙"),
    ("种植", "种植牙"),
    ("正畸", "正畸"),
    ("矫正", "正畸"),
    ("美白", "美白"),
    ("根管", "根管治疗"),
    ("拔牙", "拔牙"),
    ("贴面", "贴面"),
)
_WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


@dataclass(frozen=True)
class ParsedIntent:
    kind: IntentKind
    patient_name: str = "来电客户"
    phone: str = "未知号码"
    service: str = "咨询到店"
    reason: str = ""
    notes: str = ""
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    offering_id: UUID | None = None


@dataclass(frozen=True)
class IntentExtractResult:
    appointment_id: UUID | None
    callback_task_id: UUID | None
    skipped_reason: str | None


def extract_intents_from_text(
    text: str,
    *,
    now: datetime | None = None,
    timezone: str = "UTC",
) -> ParsedIntent:
    blob = (text or "").strip()
    if not blob:
        return ParsedIntent(kind="skip", reason="empty transcript")

    clock = now or datetime.now(UTC)
    clock = (
        clock.replace(tzinfo=UTC)
        if clock.tzinfo is None
        else clock.astimezone(UTC)
    )

    wants_appointment = bool(_APPOINTMENT_WORDS.search(blob))
    wants_callback = bool(_CALLBACK_WORDS.search(blob))
    if _DECLINE_APPOINTMENT.search(blob):
        wants_appointment = False
    if not wants_appointment and not wants_callback:
        return ParsedIntent(kind="skip", reason="no appointment or callback intent")

    phone = _extract_phone(blob)
    patient_name = _extract_name(blob)
    service = _extract_service(blob)
    slot_start, slot_end = _extract_slot(blob, clock, timezone)

    if wants_appointment:
        pending: list[str] = []
        if patient_name == "来电客户":
            pending.append("姓名待确认")
        if phone == "未知号码":
            phone = "待确认电话"
            pending.append("电话待确认")
        if slot_start is None or slot_end is None:
            pending.append("时段待确认")
            reason = (
                f"{patient_name} · 预约意向但时段未确认，需回电确认"
                if patient_name != "来电客户"
                else "预约意向但时段未确认，需回电确认"
            )
            return ParsedIntent(
                kind="callback",
                patient_name=patient_name,
                phone=phone,
                service=service,
                reason=reason[:200],
                notes=" · ".join(["语音自动登记意向", "；".join(pending)]),
            )
        note_bits = ["语音自动登记意向"]
        if pending:
            note_bits.append("；".join(pending))
        return ParsedIntent(
            kind="appointment",
            patient_name=patient_name,
            phone=phone,
            service=service,
            slot_start=slot_start,
            slot_end=slot_end,
            notes=" · ".join(note_bits),
        )

    reason = (
        f"{patient_name} · 客户要求回电跟进"
        if patient_name != "来电客户"
        else "客户要求回电跟进（姓名待确认）"
    )
    return ParsedIntent(
        kind="callback",
        patient_name=patient_name,
        phone=phone if phone != "未知号码" else "未知号码",
        service=service,
        reason=reason[:200],
    )


def transcript_text(record: CallRecord) -> str:
    return "\n".join(message.text for message in record.messages)


async def persist_extracted_intents(
    record: CallRecord,
    *,
    appointments: AppointmentRepository,
    callbacks: CallbackTaskRepository,
    tools: ToolInvocationRepository | None = None,
    scheduling: SchedulingRepository | None = None,
    notifications: NotificationService | None = None,
    now: datetime | None = None,
) -> IntentExtractResult:
    if tools is not None:
        await tools.bind_call_record(
            record.tenant_id, record.room_name, record.id
        )
        tool_items = [
            *await tools.list_for_session(record.tenant_id, record.room_name),
            *await tools.list_for_call_record(record.tenant_id, record.id),
        ]
        appointment_id = None
        callback_id = None
        wrote = False
        for item in tool_items:
            if item.status != "ok":
                continue
            if item.tool_name == "create_appointment":
                wrote = True
                raw = item.result.get("appointment_id")
                if isinstance(raw, str):
                    appointment_id = UUID(raw)
            if item.tool_name == "create_callback":
                wrote = True
                raw = item.result.get("callback_task_id")
                if isinstance(raw, str):
                    callback_id = UUID(raw)
        if wrote:
            return IntentExtractResult(
                appointment_id=appointment_id,
                callback_task_id=callback_id,
                skipped_reason="tool_already_wrote",
            )

    existing_appointment = await appointments.find_by_call_record_id(
        record.tenant_id, record.id
    )
    existing_callback = await callbacks.find_by_call_record_id(
        record.tenant_id, record.id
    )
    if existing_appointment is not None or existing_callback is not None:
        return IntentExtractResult(
            appointment_id=(
                existing_appointment.id if existing_appointment is not None else None
            ),
            callback_task_id=(
                existing_callback.id if existing_callback is not None else None
            ),
            skipped_reason="already extracted",
        )

    if not record.messages:
        return IntentExtractResult(
            appointment_id=None,
            callback_task_id=None,
            skipped_reason="no messages",
        )

    profile = None
    timezone = "UTC"
    if scheduling is not None:
        profile = await scheduling.get_profile(
            record.tenant_id, record.customer_service_id
        )
        if profile is not None:
            timezone = profile.timezone

    parsed = extract_intents_from_text(
        transcript_text(record),
        now=now,
        timezone=timezone,
    )
    if parsed.kind == "skip":
        return IntentExtractResult(
            appointment_id=None,
            callback_task_id=None,
            skipped_reason=parsed.reason or "no intent",
        )

    stamp = datetime.now(UTC)
    transcript = transcript_text(record)
    if parsed.kind == "appointment":
        parsed = await _appointment_or_callback(
            parsed,
            record=record,
            scheduling=scheduling,
            profile_exists=profile is not None,
            appointments=appointments,
            now=now,
        )

    if parsed.kind == "appointment":
        assert parsed.slot_start is not None
        assert parsed.slot_end is not None
        summary = transcript.replace("\n", " ").strip()[:400]
        notes = parsed.notes or "语音自动登记意向"
        if summary:
            notes = f"{notes}\n摘要：{summary}"[:2000]
        appointment = Appointment(
            id=uuid4(),
            tenant_id=record.tenant_id,
            voice_agent_instance_id=record.customer_service_id,
            call_record_id=record.id,
            service_offering_id=parsed.offering_id,
            patient_name=parsed.patient_name,
            phone=parsed.phone,
            service=parsed.service,
            slot_start=parsed.slot_start,
            slot_end=parsed.slot_end,
            status="pending",
            source="voice_tool",
            notes=notes,
            created_at=stamp,
            updated_at=stamp,
        )
        created = await appointments.create(appointment)
        await _try_notify(
            notifications,
            record.tenant_id,
            kind="appointment",
            subject="新预约意向",
            body=(
                f"{created.patient_name} {created.service} "
                f"{created.slot_start.isoformat()}"
            ),
        )
        return IntentExtractResult(
            appointment_id=created.id,
            callback_task_id=None,
            skipped_reason=None,
        )

    task = CallbackTask(
        id=uuid4(),
        tenant_id=record.tenant_id,
        voice_agent_instance_id=record.customer_service_id,
        call_record_id=record.id,
        caller_phone=parsed.phone,
        reason=parsed.reason or "客户要求回电跟进",
        summary=transcript[:4000],
        status="open",
        source="voice_tool",
        created_at=stamp,
        updated_at=stamp,
    )
    created_task = await callbacks.create(task)
    await _try_notify(
        notifications,
        record.tenant_id,
        kind="callback",
        subject="新回拨任务",
        body=f"{created_task.caller_phone} {created_task.reason}",
    )
    return IntentExtractResult(
        appointment_id=None,
        callback_task_id=created_task.id,
        skipped_reason=None,
    )


async def try_extract_intents(
    record: CallRecord,
    *,
    appointments: AppointmentRepository,
    callbacks: CallbackTaskRepository,
    tools: ToolInvocationRepository | None = None,
    scheduling: SchedulingRepository | None = None,
    notifications: NotificationService | None = None,
) -> IntentExtractResult | None:
    """Best-effort extract; never raise to callers that must keep the call record."""
    try:
        return await persist_extracted_intents(
            record,
            appointments=appointments,
            callbacks=callbacks,
            tools=tools,
            scheduling=scheduling,
            notifications=notifications,
        )
    except Exception:
        logger.exception(
            "intent extract failed for call_record_id=%s",
            record.id,
        )
        return None


def _extract_name(text: str) -> str:
    match = _NAME_RE.search(text)
    if match is None:
        return "来电客户"
    if match.group(1):
        return match.group(1).strip()[:80]
    return f"{match.group(2)}先生/女士"[:80]


def _extract_phone(text: str) -> str:
    au = _PHONE_AU_RE.search(text)
    if au is not None:
        return au.group(1)
    cn = _PHONE_CN_RE.search(text)
    if cn is not None:
        return cn.group(1)
    return "未知号码"


def _extract_service(text: str) -> str:
    for keyword, label in _SERVICE_KEYWORDS:
        if keyword in text:
            return label
    return "咨询到店"


def _clinic_zone(timezone: str) -> ZoneInfo:
    name = (timezone or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _extract_slot(
    text: str, now: datetime, timezone: str
) -> tuple[datetime | None, datetime | None]:
    hour = 10
    if "下午" in text or "晚上" in text:
        hour = 14
    elif "上午" in text or "早上" in text:
        hour = 10

    tz = _clinic_zone(timezone)
    local_now = now.astimezone(tz)

    if "明天" in text:
        base_date = (local_now + timedelta(days=1)).date()
    elif "后天" in text:
        base_date = (local_now + timedelta(days=2)).date()
    else:
        weekday_match = re.search(r"周([一二三四五六日天])", text)
        if weekday_match is None:
            weekday_match = re.search(r"星期([一二三四五六日天])", text)
        if weekday_match is None:
            return None, None
        target = _WEEKDAY_MAP[weekday_match.group(1)]
        days_ahead = (target - local_now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = (local_now + timedelta(days=days_ahead)).date()

    start_local = datetime.combine(base_date, time(hour, 0), tzinfo=tz)
    start = start_local.astimezone(UTC)
    end = start + timedelta(minutes=30)
    return start, end


def _as_callback(parsed: ParsedIntent, reason: str) -> ParsedIntent:
    notes = parsed.notes
    if parsed.slot_start is not None:
        extra = f"原意向时段：{parsed.slot_start.isoformat()}"
        notes = f"{notes} · {extra}".strip(" ·") if notes else extra
    return ParsedIntent(
        kind="callback",
        patient_name=parsed.patient_name,
        phone=parsed.phone,
        service=parsed.service,
        reason=reason[:200],
        notes=notes,
    )


async def _appointment_or_callback(
    parsed: ParsedIntent,
    *,
    record: CallRecord,
    scheduling: SchedulingRepository | None,
    profile_exists: bool,
    appointments: AppointmentRepository,
    now: datetime | None,
) -> ParsedIntent:
    if scheduling is None or not profile_exists:
        return _as_callback(parsed, "未配置排期，需人工确认档期")
    offering = await scheduling.find_offering_by_name(
        record.tenant_id,
        record.customer_service_id,
        parsed.service,
    )
    if offering is None:
        return _as_callback(parsed, "未匹配服务项目，需人工确认档期")
    assert parsed.slot_start is not None
    slot_start = parsed.slot_start
    slot_end = slot_start + timedelta(minutes=offering.duration_minutes)
    try:
        await ensure_slot_available(
            appointments=appointments,
            scheduling=scheduling,
            tenant_id=record.tenant_id,
            instance_id=record.customer_service_id,
            slot_start=slot_start,
            slot_end=slot_end,
            service_offering_id=offering.id,
            now=now,
        )
    except SlotUnavailableError as error:
        return _as_callback(parsed, f"{error}，需人工确认档期")
    return ParsedIntent(
        kind="appointment",
        patient_name=parsed.patient_name,
        phone=parsed.phone,
        service=offering.name,
        notes=parsed.notes,
        slot_start=slot_start,
        slot_end=slot_end,
        offering_id=offering.id,
    )


async def _try_notify(
    notifications: NotificationService | None,
    tenant_id: UUID,
    *,
    kind: str,
    subject: str,
    body: str,
) -> None:
    if notifications is None:
        return
    try:
        await notifications.notify(
            tenant_id, kind=kind, subject=subject, body=body
        )
    except Exception:
        logger.exception("intent extract notification failed")
