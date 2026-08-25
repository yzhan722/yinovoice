from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..dependencies import TenantId
from ..domain.tool_invocation import (
    ToolInvocation,
    ToolInvocationCreate,
    ToolInvocationResponse,
)
from ..services.tool_execution import ToolExecutionService


def create_router(service: ToolExecutionService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/tool-invocations")

    @router.post("", response_model=ToolInvocationResponse)
    async def create_invocation(
        payload: ToolInvocationCreate,
        tenant_id: TenantId,
    ) -> ToolInvocationResponse:
        return await service.execute(tenant_id, payload)

    @router.get("", response_model=list[ToolInvocation])
    async def list_invocations(
        tenant_id: TenantId,
        session_id: str | None = Query(default=None),
        call_record_id: UUID | None = Query(default=None),
    ) -> list[ToolInvocation]:
        if session_id:
            return await service.list_for_session(tenant_id, session_id)
        if call_record_id is not None:
            return await service.list_for_call_record(tenant_id, call_record_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="session_id or call_record_id is required",
        )

    return router
