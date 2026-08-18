from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict

from ..dependencies import TenantId
from ..domain.call_record import (
    CallRecord,
    CallRecordCreate,
    CallRecordPage,
    CallRecordUpdate,
)
from ..repositories.appointments import AppointmentRepository
from ..repositories.call_records import CallRecordRepository
from ..repositories.callback_tasks import CallbackTaskRepository
from ..repositories.customer_services import CustomerServiceRepository
from ..services.call_recordings import (
    RecordingBadRequestError,
    RecordingNotFoundError,
    RecordingTooLargeError,
    open_recording,
    save_recording,
)
from ..services.intent_extract import (
    IntentExtractResult,
    persist_extracted_intents,
    try_extract_intents,
)


class IntentExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appointment_id: UUID | None = None
    callback_task_id: UUID | None = None
    skipped_reason: str | None = None


def create_router(
    call_records: CallRecordRepository,
    customer_services: CustomerServiceRepository,
    *,
    appointments: AppointmentRepository,
    callbacks: CallbackTaskRepository,
    recording_dir: Path,
    recording_max_bytes: int,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/call-records")

    def _active_or_404(record: CallRecord | None) -> CallRecord:
        if record is None or record.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call record not found",
            )
        return record

    def _to_response(result: IntentExtractResult) -> IntentExtractResponse:
        return IntentExtractResponse(
            appointment_id=result.appointment_id,
            callback_task_id=result.callback_task_id,
            skipped_reason=result.skipped_reason,
        )

    @router.post("", response_model=CallRecord, status_code=status.HTTP_201_CREATED)
    async def create_call_record(
        request: CallRecordCreate,
        tenant_id: TenantId,
    ) -> CallRecord:
        service = await customer_services.get(request.customer_service_id, tenant_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        record = CallRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            created_at=datetime.now(UTC),
            **request.model_dump(),
        )
        saved = await call_records.save(record)
        if saved.messages:
            await try_extract_intents(
                saved,
                appointments=appointments,
                callbacks=callbacks,
            )
        return saved

    @router.get("", response_model=CallRecordPage)
    async def list_call_records(
        tenant_id: TenantId,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        include_deleted: bool = False,
    ) -> CallRecordPage:
        items, total = await call_records.list_for_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        return CallRecordPage(items=items, total=total)

    @router.get("/{record_id}", response_model=CallRecord)
    async def get_call_record(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> CallRecord:
        record = await call_records.get(record_id, tenant_id)
        return _active_or_404(record)

    @router.put("/{record_id}", response_model=CallRecord)
    async def update_call_record(
        record_id: UUID,
        update: CallRecordUpdate,
        tenant_id: TenantId,
    ) -> CallRecord:
        record = _active_or_404(await call_records.get(record_id, tenant_id))
        updated = record.model_copy(
            update={
                "status": update.status,
                "messages": (
                    update.messages
                    if update.messages is not None
                    else record.messages
                ),
            },
            deep=True,
        )
        saved = await call_records.save(updated)
        if saved.messages:
            await try_extract_intents(
                saved,
                appointments=appointments,
                callbacks=callbacks,
            )
        return saved

    @router.post(
        "/{record_id}/extract-intents",
        response_model=IntentExtractResponse,
    )
    async def extract_call_record_intents(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> IntentExtractResponse:
        record = _active_or_404(await call_records.get(record_id, tenant_id))
        result = await persist_extracted_intents(
            record,
            appointments=appointments,
            callbacks=callbacks,
        )
        return _to_response(result)

    @router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_call_record(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        record = await call_records.get(record_id, tenant_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call record not found",
            )
        await call_records.soft_delete(record_id, tenant_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{record_id}/restore", response_model=CallRecord)
    async def restore_call_record(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> CallRecord:
        record = await call_records.get(record_id, tenant_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call record not found",
            )
        restored = await call_records.restore(record_id, tenant_id)
        assert restored is not None
        return restored

    @router.post("/{record_id}/recording", response_model=CallRecord)
    async def upload_call_recording(
        record_id: UUID,
        tenant_id: TenantId,
        file: UploadFile,
    ) -> CallRecord:
        existing = await call_records.get(record_id, tenant_id)
        _active_or_404(existing)
        try:
            return await save_recording(
                call_records,
                tenant_id,
                record_id,
                file,
                base_dir=recording_dir,
                max_bytes=recording_max_bytes,
            )
        except RecordingNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call record not found",
            ) from exc
        except RecordingBadRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RecordingTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Recording exceeds maximum allowed size",
            ) from exc

    @router.get("/{record_id}/recording")
    async def play_call_recording(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> FileResponse:
        existing = await call_records.get(record_id, tenant_id)
        _active_or_404(existing)
        try:
            record, path = await open_recording(
                call_records,
                tenant_id,
                record_id,
                base_dir=recording_dir,
            )
        except RecordingNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found",
            ) from exc

        media_type = record.recording_mime_type or "application/octet-stream"
        return FileResponse(path, media_type=media_type)

    return router
