from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from ..clock import NowProvider, utc_now
from ..domain.call_record import (
    CallRecord,
    CallSessionFinish,
    CallSessionMessage,
    CallSessionStart,
    TranscriptMessage,
)
from ..repositories.appointments import AppointmentRepository
from ..repositories.call_records import CallRecordRepository
from ..repositories.callback_tasks import CallbackTaskRepository
from ..repositories.customer_services import CustomerServiceRepository
from ..repositories.insights_dispatch import InsightsDispatchRepository
from ..repositories.scheduling import SchedulingRepository
from ..repositories.tool_invocations import ToolInvocationRepository
from .insights_dispatch import try_enqueue_ended_call
from .intent_extract import try_extract_intents
from .livekit_egress import RecordingEgressService
from .notifications import NotificationService


class CallSessionNotFound(Exception):  # noqa: N818
    def __init__(self, detail: str = "Call session not found") -> None:
        super().__init__(detail)
        self.detail = detail


class CallSessionConflict(Exception):  # noqa: N818
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _duration_sec(started_at: datetime, ended_at: datetime) -> int:
    seconds = int((ended_at - started_at).total_seconds())
    return max(0, min(seconds, 86_400))


class CallLifecycleService:
    def __init__(
        self,
        call_records: CallRecordRepository,
        customer_services: CustomerServiceRepository,
        *,
        appointments: AppointmentRepository,
        callbacks: CallbackTaskRepository,
        tools: ToolInvocationRepository | None = None,
        scheduling: SchedulingRepository | None = None,
        notifications: NotificationService | None = None,
        egress: RecordingEgressService | None = None,
        insights_dispatch: InsightsDispatchRepository | None = None,
        now_provider: NowProvider = utc_now,
    ) -> None:
        self._call_records = call_records
        self._customer_services = customer_services
        self._appointments = appointments
        self._callbacks = callbacks
        self._tools = tools
        self._scheduling = scheduling
        self._notifications = notifications
        self._egress = egress
        self._insights_dispatch = insights_dispatch
        self._now_provider = now_provider

    async def start(
        self,
        tenant_id: UUID,
        request: CallSessionStart,
    ) -> tuple[CallRecord, bool]:
        service = await self._customer_services.get(
            request.customer_service_id,
            tenant_id,
        )
        if service is None:
            raise CallSessionNotFound("Customer service not found")

        if request.provider_call_id is not None:
            existing = await self._call_records.find_by_provider_call_id(
                tenant_id,
                request.provider_call_id,
            )
            if existing is not None:
                return existing, False

        existing_room = await self._call_records.find_in_progress_by_room_name(
            tenant_id,
            request.room_name,
        )
        if existing_room is not None:
            return existing_room, False

        now = self._now_provider()
        started_at = request.started_at or now
        record = CallRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            created_at=now,
            customer_service_id=request.customer_service_id,
            room_name=request.room_name,
            status="in_progress",
            started_at=started_at,
            direction=request.direction,
            caller_number=request.caller_number,
            callee_number=request.callee_number,
            provider_call_id=request.provider_call_id,
            connected_at=request.connected_at or started_at,
            messages=[],
        )
        saved = await self._call_records.save(record)
        if self._egress is not None:
            recorded = await self._egress.start_for_inbound(saved)
            if recorded is not saved:
                saved = await self._call_records.save(recorded)
        return saved, True

    async def append_message(
        self,
        tenant_id: UUID,
        record_id: UUID,
        request: CallSessionMessage,
    ) -> CallRecord:
        record = await self._require_active(record_id, tenant_id)
        if record.status != "in_progress":
            raise CallSessionConflict("Call session is already finished")

        for message in record.messages:
            if message.sequence == request.sequence:
                if (
                    message.role == request.role
                    and message.text == request.text
                ):
                    return record
                raise CallSessionConflict(
                    "sequence already exists with different content"
                )

        if record.messages:
            last_sequence = max(message.sequence for message in record.messages)
            if request.sequence <= last_sequence:
                raise CallSessionConflict(
                    "message sequence must strictly increase"
                )

        updated = record.model_copy(
            update={
                "messages": [
                    *record.messages,
                    TranscriptMessage(
                        role=request.role,
                        text=request.text,
                        sequence=request.sequence,
                    ),
                ]
            },
            deep=True,
        )
        return await self._call_records.save(updated)

    async def finish(
        self,
        tenant_id: UUID,
        record_id: UUID,
        request: CallSessionFinish,
    ) -> CallRecord:
        record = await self._require_active(record_id, tenant_id)
        if record.status != "in_progress":
            return record

        ended_at = request.ended_at or self._now_provider()
        if ended_at < record.started_at:
            raise CallSessionConflict("ended_at must not be before started_at")

        updated = record.model_copy(
            update={
                "status": request.status,
                "ended_reason": request.ended_reason,
                "ended_at": ended_at,
                "duration_sec": _duration_sec(record.started_at, ended_at),
            },
            deep=True,
        )
        saved = await self._call_records.save(updated)
        if saved.messages:
            await try_extract_intents(
                saved,
                appointments=self._appointments,
                callbacks=self._callbacks,
                tools=self._tools,
                scheduling=self._scheduling,
                notifications=self._notifications,
            )
        await try_enqueue_ended_call(
            saved,
            customer_services=self._customer_services,
            insights_dispatch=self._insights_dispatch,
        )
        return saved

    async def _require_active(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord:
        record = await self._call_records.get(record_id, tenant_id)
        if record is None or record.deleted_at is not None:
            raise CallSessionNotFound()
        return record
