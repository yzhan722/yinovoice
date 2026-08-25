from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from ..dependencies import TenantId
from ..domain.call_record import (
    CallRecord,
    CallSessionFinish,
    CallSessionMessage,
    CallSessionStart,
)
from ..services.call_lifecycle import (
    CallLifecycleService,
    CallSessionConflict,
    CallSessionNotFound,
)


def create_router(service: CallLifecycleService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/call-sessions")

    def _raise(error: CallSessionNotFound | CallSessionConflict) -> None:
        if isinstance(error, CallSessionNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error.detail,
            ) from error
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error.detail,
        ) from error

    @router.post("/start", response_model=CallRecord)
    async def start_call_session(
        request: CallSessionStart,
        tenant_id: TenantId,
    ) -> Response:
        try:
            record, created = await service.start(tenant_id, request)
        except (CallSessionNotFound, CallSessionConflict) as error:
            _raise(error)
        return Response(
            content=record.model_dump_json(),
            status_code=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
            media_type="application/json",
        )

    @router.post("/{record_id}/messages", response_model=CallRecord)
    async def append_call_session_message(
        record_id: UUID,
        request: CallSessionMessage,
        tenant_id: TenantId,
    ) -> CallRecord:
        try:
            return await service.append_message(tenant_id, record_id, request)
        except (CallSessionNotFound, CallSessionConflict) as error:
            _raise(error)
            raise

    @router.post("/{record_id}/finish", response_model=CallRecord)
    async def finish_call_session(
        record_id: UUID,
        request: CallSessionFinish,
        tenant_id: TenantId,
    ) -> CallRecord:
        try:
            return await service.finish(tenant_id, record_id, request)
        except (CallSessionNotFound, CallSessionConflict) as error:
            _raise(error)
            raise

    return router
