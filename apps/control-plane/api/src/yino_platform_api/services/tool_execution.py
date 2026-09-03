from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from ..clock import NowProvider, utc_now
from ..domain.appointment import Appointment
from ..domain.callback_task import CallbackTask
from ..domain.tool_invocation import (
    ToolInvocation,
    ToolInvocationCreate,
    ToolInvocationResponse,
)
from ..repositories.appointments import AppointmentRepository
from ..repositories.call_records import CallRecordRepository
from ..repositories.callback_tasks import CallbackTaskRepository
from ..repositories.scheduling import SchedulingRepository
from ..repositories.tool_invocations import ToolInvocationRepository
from .availability import generate_available_slots, occupying_ranges
from .booking import SlotUnavailableError, ensure_slot_available
from .notifications import NotificationService

_WRITE_TOOLS = {"create_appointment", "create_callback"}


def default_idempotency_key(payload: ToolInvocationCreate) -> str:
    if payload.idempotency_key:
        return payload.idempotency_key
    fingerprint = json.dumps(
        payload.arguments,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"{payload.session_id}:{payload.tool_name}:{digest}"


def to_response(item: ToolInvocation) -> ToolInvocationResponse:
    return ToolInvocationResponse(
        invocation_id=item.id,
        status=item.status,
        tool_name=item.tool_name,
        result=item.result,
    )


class ToolExecutionService:
    def __init__(
        self,
        invocations: ToolInvocationRepository,
        *,
        appointments: AppointmentRepository,
        callbacks: CallbackTaskRepository,
        scheduling: SchedulingRepository,
        call_records: CallRecordRepository,
        notifications: NotificationService | None = None,
        now_provider: NowProvider = utc_now,
    ) -> None:
        self._invocations = invocations
        self._appointments = appointments
        self._callbacks = callbacks
        self._scheduling = scheduling
        self._call_records = call_records
        self._notifications = notifications
        self._now_provider = now_provider

    async def execute(
        self, tenant_id: UUID, payload: ToolInvocationCreate
    ) -> ToolInvocationResponse:
        key = default_idempotency_key(payload)
        existing = await self._invocations.find_by_idempotency_key(tenant_id, key)
        if existing is not None:
            return to_response(existing)

        if payload.tool_name in _WRITE_TOOLS:
            replay = await self._existing_successful_write(
                tenant_id,
                payload.session_id,
                payload.tool_name,
            )
            if replay is not None:
                return to_response(replay)

        call_record_id = payload.call_record_id
        if call_record_id is not None:
            record = await self._call_records.get(call_record_id, tenant_id)
            if record is None or record.deleted_at is not None:
                return await self._store(
                    tenant_id,
                    payload,
                    key,
                    status="error",
                    result={"message": "call record not found"},
                )

        if payload.tool_name == "check_availability":
            status, result = await self._check_availability(tenant_id, payload)
        elif payload.tool_name == "create_appointment":
            status, result = await self._create_appointment(tenant_id, payload)
        else:
            status, result = await self._create_callback(tenant_id, payload)

        stored = await self._store(
            tenant_id,
            payload,
            key,
            status=status,
            result=result,
            call_record_id=call_record_id,
        )
        return to_response(stored)

    async def list_for_session(
        self, tenant_id: UUID, session_id: str
    ) -> list[ToolInvocation]:
        return await self._invocations.list_for_session(tenant_id, session_id)

    async def list_for_call_record(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> list[ToolInvocation]:
        return await self._invocations.list_for_call_record(tenant_id, call_record_id)

    async def bind_session(
        self, tenant_id: UUID, session_id: str, call_record_id: UUID
    ) -> None:
        await self._invocations.bind_call_record(
            tenant_id, session_id, call_record_id
        )

    async def successful_write_ids(
        self,
        tenant_id: UUID,
        *,
        session_id: str | None = None,
        call_record_id: UUID | None = None,
    ) -> tuple[UUID | None, UUID | None]:
        items: list[ToolInvocation] = []
        if session_id:
            items.extend(await self._invocations.list_for_session(tenant_id, session_id))
        if call_record_id is not None:
            items.extend(
                await self._invocations.list_for_call_record(tenant_id, call_record_id)
            )
        appointment_id: UUID | None = None
        callback_id: UUID | None = None
        for item in items:
            if item.status != "ok":
                continue
            if item.tool_name == "create_appointment" and appointment_id is None:
                raw = item.result.get("appointment_id")
                if isinstance(raw, str):
                    appointment_id = UUID(raw)
            if item.tool_name == "create_callback" and callback_id is None:
                raw = item.result.get("callback_task_id")
                if isinstance(raw, str):
                    callback_id = UUID(raw)
        return appointment_id, callback_id

    async def _existing_successful_write(
        self, tenant_id: UUID, session_id: str, tool_name: str
    ) -> ToolInvocation | None:
        for item in await self._invocations.list_for_session(tenant_id, session_id):
            if item.tool_name == tool_name and item.status == "ok":
                return item
        return None

    async def _store(
        self,
        tenant_id: UUID,
        payload: ToolInvocationCreate,
        key: str,
        *,
        status: str,
        result: dict[str, Any],
        call_record_id: UUID | None = None,
    ) -> ToolInvocation:
        item = ToolInvocation(
            id=uuid4(),
            tenant_id=tenant_id,
            session_id=payload.session_id,
            call_record_id=call_record_id or payload.call_record_id,
            voice_agent_instance_id=payload.voice_agent_instance_id,
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            status=status,  # type: ignore[arg-type]
            result=result,
            idempotency_key=key,
            created_at=self._now_provider(),
        )
        return await self._invocations.create(item)

    async def _check_availability(
        self, tenant_id: UUID, payload: ToolInvocationCreate
    ) -> tuple[str, dict[str, Any]]:
        args = payload.arguments
        instance_id = _uuid_arg(
            args.get("voice_agent_instance_id"), payload.voice_agent_instance_id
        )
        offering_id = _uuid_arg(args.get("service_offering_id"), None)
        if instance_id is None:
            return "error", {"message": "voice_agent_instance_id is required"}
        offering = None
        if offering_id is not None:
            offering = await self._scheduling.get_offering(offering_id, tenant_id)
        elif isinstance(args.get("service"), str) and args["service"].strip():
            offering = await self._scheduling.find_offering_by_name(
                tenant_id, instance_id, args["service"].strip()
            )
        if offering is None or offering.voice_agent_instance_id != instance_id:
            return "error", {"message": "service offering not found"}
        profile = await self._scheduling.get_profile(tenant_id, instance_id)
        if profile is None:
            return "error", {"message": "scheduling profile not found"}
        date_from = _date_arg(args.get("date_from")) or date.today()
        date_to = _date_arg(args.get("date_to")) or (
            date_from + timedelta(days=min(7, profile.booking_horizon_days))
        )
        slots = generate_available_slots(
            profile=profile,
            offering=offering,
            hours=await self._scheduling.list_hours(tenant_id, instance_id),
            exceptions=await self._scheduling.list_exceptions(tenant_id, instance_id),
            occupying=occupying_ranges(
                await self._appointments.list_occupying(tenant_id, instance_id)
            ),
            date_from=date_from,
            date_to=date_to,
            now=self._now_provider(),
        )
        return "ok", {
            "message": f"found {len(slots)} available slots",
            "total": len(slots),
            "items": [item.model_dump(mode="json") for item in slots[:20]],
        }

    async def _create_appointment(
        self, tenant_id: UUID, payload: ToolInvocationCreate
    ) -> tuple[str, dict[str, Any]]:
        args = payload.arguments
        patient_name = _str_arg(args.get("patient_name"), "来电客户")
        phone = _str_arg(args.get("phone"), "")
        service = _str_arg(args.get("service"), "咨询到店")
        slot_start = _datetime_arg(args.get("slot_start"))
        slot_end = _datetime_arg(args.get("slot_end"))
        if not phone:
            return "error", {"message": "phone is required"}
        if slot_start is None or slot_end is None:
            return "error", {"message": "slot_start and slot_end are required"}
        instance_id = _uuid_arg(
            args.get("voice_agent_instance_id"), payload.voice_agent_instance_id
        )
        offering_id = _uuid_arg(args.get("service_offering_id"), None)
        try:
            await ensure_slot_available(
                appointments=self._appointments,
                scheduling=self._scheduling,
                tenant_id=tenant_id,
                instance_id=instance_id,
                slot_start=slot_start,
                slot_end=slot_end,
                service_offering_id=offering_id,
                now=self._now_provider(),
            )
        except SlotUnavailableError as error:
            return "error", {"message": str(error)}
        stamp = self._now_provider()
        created = await self._appointments.create(
            Appointment(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                call_record_id=payload.call_record_id,
                service_offering_id=offering_id,
                patient_name=patient_name,
                phone=phone,
                service=service,
                slot_start=slot_start,
                slot_end=slot_end,
                status="pending",
                source="voice_tool",
                notes=_str_arg(args.get("notes"), "通话中 Tool 登记"),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        await self._try_notify(
            tenant_id,
            kind="appointment",
            subject="新预约意向",
            body=f"{created.patient_name} {created.service} {created.slot_start.isoformat()}",
        )
        return "ok", {
            "message": "已登记预约意向，工作人员会确认档期",
            "appointment_id": str(created.id),
            "callback_task_id": None,
        }

    async def _create_callback(
        self, tenant_id: UUID, payload: ToolInvocationCreate
    ) -> tuple[str, dict[str, Any]]:
        args = payload.arguments
        phone = _str_arg(args.get("phone") or args.get("caller_phone"), "待确认电话")
        reason = _str_arg(args.get("reason"), "客户要求回电跟进")
        summary = _str_arg(args.get("summary"), "")
        stamp = self._now_provider()
        created = await self._callbacks.create(
            CallbackTask(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=_uuid_arg(
                    args.get("voice_agent_instance_id"),
                    payload.voice_agent_instance_id,
                ),
                call_record_id=payload.call_record_id,
                caller_phone=phone[:32],
                reason=reason[:200],
                summary=summary[:4000],
                status="open",
                source="voice_tool",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        await self._try_notify(
            tenant_id,
            kind="callback",
            subject="新回拨任务",
            body=f"{created.caller_phone} {created.reason}",
        )
        return "ok", {
            "message": "已登记回拨任务",
            "appointment_id": None,
            "callback_task_id": str(created.id),
        }

    async def _try_notify(
        self, tenant_id: UUID, *, kind: str, subject: str, body: str
    ) -> None:
        if self._notifications is None:
            return
        try:
            await self._notifications.notify(
                tenant_id, kind=kind, subject=subject, body=body
            )
        except Exception:
            return


def _str_arg(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _uuid_arg(value: object, fallback: UUID | None) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return UUID(value.strip())
        except ValueError:
            return fallback
    return fallback


def _datetime_arg(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _date_arg(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip()[:10])
    return None
