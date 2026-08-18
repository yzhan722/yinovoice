from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ..dependencies import TenantId
from ..domain.callback_task import (
    CallbackTask,
    CallbackTaskCreate,
    CallbackTaskPage,
    CallbackTaskUpdate,
)
from ..repositories.callback_tasks import CallbackTaskRepository
from ..repositories.customer_services import CustomerServiceRepository


def create_router(
    callbacks: CallbackTaskRepository,
    customer_services: CustomerServiceRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/callback-tasks")

    async def _resolve_instance(
        instance_id: UUID | None, tenant_id: UUID
    ) -> UUID | None:
        if instance_id is None:
            return None
        instance = await customer_services.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        return instance_id

    @router.get("", response_model=CallbackTaskPage)
    async def list_callback_tasks(
        tenant_id: TenantId,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        status_filter: str | None = Query(default=None, alias="status"),
        include_cancelled: bool = False,
    ) -> CallbackTaskPage:
        items, total = await callbacks.list_for_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
            status=status_filter,
            include_cancelled=include_cancelled,
        )
        return CallbackTaskPage(items=items, total=total)

    @router.post(
        "",
        response_model=CallbackTask,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_callback_task(
        request: CallbackTaskCreate,
        tenant_id: TenantId,
    ) -> CallbackTask:
        instance_id = await _resolve_instance(
            request.voice_agent_instance_id, tenant_id
        )
        now = datetime.now(UTC)
        return await callbacks.create(
            CallbackTask(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                caller_phone=request.caller_phone,
                reason=request.reason,
                summary=request.summary,
                status="open",
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )

    @router.get("/{task_id}", response_model=CallbackTask)
    async def get_callback_task(
        task_id: UUID,
        tenant_id: TenantId,
    ) -> CallbackTask:
        item = await callbacks.get(task_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback task not found",
            )
        return item

    @router.patch("/{task_id}", response_model=CallbackTask)
    async def update_callback_task(
        task_id: UUID,
        update: CallbackTaskUpdate,
        tenant_id: TenantId,
    ) -> CallbackTask:
        item = await callbacks.get(task_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback task not found",
            )
        updated = item.model_copy(update=update.model_dump(exclude_unset=True))
        return await callbacks.save(updated)

    @router.post("/{task_id}/complete", response_model=CallbackTask)
    async def complete_callback_task(
        task_id: UUID,
        tenant_id: TenantId,
    ) -> CallbackTask:
        item = await callbacks.get(task_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback task not found",
            )
        if item.status == "done":
            return item
        return await callbacks.save(item.model_copy(update={"status": "done"}))

    @router.post("/{task_id}/reopen", response_model=CallbackTask)
    async def reopen_callback_task(
        task_id: UUID,
        tenant_id: TenantId,
    ) -> CallbackTask:
        item = await callbacks.get(task_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback task not found",
            )
        if item.status == "open":
            return item
        return await callbacks.save(item.model_copy(update={"status": "open"}))

    return router
