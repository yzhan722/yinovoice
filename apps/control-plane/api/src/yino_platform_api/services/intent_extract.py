"""Rule-based appointment / callback intent extraction from call transcripts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from ..domain.appointment import Appointment
from ..domain.call_record import CallRecord
from ..domain.callback_task import CallbackTask
from ..repositories.appointments import AppointmentRepository
from ..repositories.callback_tasks import CallbackTaskRepository

logger = logging.getLogger(__name__)

IntentKind = Literal["appointment", "callback", "skip"]

_APPOINTMENT_WORDS = re.compile(
    r"(预约|想约|约个|挂号|约一下|帮我约|想挂号)"
)
_CALLBACK_WORDS = re.compile(
    r"(回电|回拨|打电话给我|请联系我|联系我|请.*回电)"
)
_PHONE_RE = re.compile(r"1[3-9]\d{9}")
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


@dataclass(frozen=True)
class IntentExtractResult:
    appointment_id: UUID | None
    callback_task_id: UUID | None
    skipped_reason: str | None


def extract_intents_from_text(
    text: str,
    *,
    now: datetime | None = None,
) -> ParsedIntent:
    blob = (text or "").strip()
    if not blob:
        return ParsedIntent(kind="skip", reason="empty transcript")

    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    else:
        clock = clock.astimezone(UTC)

    wants_appointment = bool(_APPOINTMENT_WORDS.search(blob))
    wants_callback = bool(_CALLBACK_WORDS.search(blob))
    if not wants_appointment and not wants_callback:
        return ParsedIntent(kind="skip", reason="no appointment or callback intent")

    phone_match = _PHONE_RE.search(blob)
    phone = phone_match.group(0) if phone_match else "未知号码"
    patient_name = _extract_name(blob)
    service = _extract_service(blob)
    slot_start, slot_end = _extract_slot(blob, clock)

    if wants_appointment:
        pending: list[str] = []
        if patient_name == "来电客户":
            pending.append("姓名待确认")
        if phone == "未知号码":
            phone = "待确认电话"
            pending.append("电话待确认")
        if slot_start is None or slot_end is None:
            slot_start, slot_end = _default_next_weekday_morning(clock)
            pending.append("时段待确认（已填下一工作日上午占位）")
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
    now: datetime | None = None,
) -> IntentExtractResult:
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

    parsed = extract_intents_from_text(transcript_text(record), now=now)
    if parsed.kind == "skip":
        return IntentExtractResult(
            appointment_id=None,
            callback_task_id=None,
            skipped_reason=parsed.reason or "no intent",
        )

    stamp = datetime.now(UTC)
    transcript = transcript_text(record)
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
) -> IntentExtractResult | None:
    """Best-effort extract; never raise to callers that must keep the call record."""
    try:
        return await persist_extracted_intents(
            record,
            appointments=appointments,
            callbacks=callbacks,
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


def _extract_service(text: str) -> str:
    for keyword, label in _SERVICE_KEYWORDS:
        if keyword in text:
            return label
    return "咨询到店"


def _extract_slot(
    text: str, now: datetime
) -> tuple[datetime | None, datetime | None]:
    hour = 10
    if "下午" in text or "晚上" in text:
        hour = 14
    elif "上午" in text or "早上" in text:
        hour = 10

    if "明天" in text:
        base_date = (now + timedelta(days=1)).date()
    elif "后天" in text:
        base_date = (now + timedelta(days=2)).date()
    else:
        weekday_match = re.search(r"周([一二三四五六日天])", text)
        if weekday_match is None:
            weekday_match = re.search(r"星期([一二三四五六日天])", text)
        if weekday_match is None:
            return None, None
        target = _WEEKDAY_MAP[weekday_match.group(1)]
        days_ahead = (target - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = (now + timedelta(days=days_ahead)).date()

    start = datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hour,
        0,
        tzinfo=UTC,
    )
    end = start + timedelta(minutes=30)
    return start, end


def _default_next_weekday_morning(
    now: datetime,
) -> tuple[datetime, datetime]:
    """Placeholder slot: next Mon–Fri at 10:00–10:30 UTC."""
    candidate = now + timedelta(days=1)
    while candidate.weekday() >= 5:  # Sat/Sun
        candidate += timedelta(days=1)
    start = datetime(
        candidate.year,
        candidate.month,
        candidate.day,
        10,
        0,
        tzinfo=UTC,
    )
    return start, start + timedelta(minutes=30)
