from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from ..dependencies import TenantId
from ..domain.call_record import CallRecord, CallRecordCreate, CallRecordPage
from ..repositories.call_records import CallRecordRepository
from ..repositories.customer_services import CustomerServiceRepository
from ..services.call_recordings import (
    RecordingBadRequestError,
    RecordingNotFoundError,
    RecordingTooLargeError,
    open_recording,
    save_recording,
)


def create_router(
    call_records: CallRecordRepository,
    customer_services: CustomerServiceRepository,
    *,
    recording_dir: Path,
    recording_max_bytes: int,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/call-records")

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
        return await call_records.save(record)

    @router.get("", response_model=CallRecordPage)
    async def list_call_records(
        tenant_id: TenantId,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> CallRecordPage:
        items, total = await call_records.list_for_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
        )
        return CallRecordPage(items=items, total=total)

    @router.get("/{record_id}", response_model=CallRecord)
    async def get_call_record(
        record_id: UUID,
        tenant_id: TenantId,
    ) -> CallRecord:
        record = await call_records.get(record_id, tenant_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call record not found",
            )
        return record

    @router.post("/{record_id}/recording", response_model=CallRecord)
    async def upload_call_recording(
        record_id: UUID,
        tenant_id: TenantId,
        file: UploadFile,
    ) -> CallRecord:
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
