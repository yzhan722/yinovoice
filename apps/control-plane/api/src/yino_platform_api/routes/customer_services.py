from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from ..dependencies import TenantId
from ..domain.customer_service import (
    CustomerServiceCreate,
    CustomerServiceInstance,
    CustomerServiceUpdate,
)
from ..repositories.call_records import CallRecordRepository
from ..repositories.config_revisions import (
    ConfigRevisionRepository,
    record_snapshot,
)
from ..repositories.customer_services import (
    CustomerServiceAlreadyExists,
    CustomerServiceRepository,
    CustomerServiceVersionConflict,
)
from ..services.livekit_tokens import LiveKitDispatchError, LiveKitTokenIssuer


class LiveKitTokenRequest(BaseModel):
    participant_identity: str = Field(min_length=1, max_length=120)


class LiveKitTokenResponse(BaseModel):
    server_url: str
    room_name: str
    participant_identity: str
    token: str


class CustomerServicePage(BaseModel):
    items: list[CustomerServiceInstance]
    total: int


def create_router(
    repository: CustomerServiceRepository,
    token_issuer: LiveKitTokenIssuer,
    call_records: CallRecordRepository,
    config_revisions: ConfigRevisionRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/customer-services")

    @router.get("", response_model=CustomerServicePage)
    async def list_customer_services(
        tenant_id: TenantId,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        include_deleted: bool = False,
    ) -> CustomerServicePage:
        items, total = await repository.list_for_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        return CustomerServicePage(items=items, total=total)

    @router.post(
        "",
        response_model=CustomerServiceInstance,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_customer_service(
        request: CustomerServiceCreate,
        tenant_id: TenantId,
    ) -> CustomerServiceInstance:
        instance = CustomerServiceInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            version=1,
            display_name=request.display_name,
            organization_name=request.organization_name,
            greeting=request.greeting,
            platform_prompt=request.platform_prompt,
            tenant_prompt=request.tenant_prompt,
            voice=request.voice,
            response=request.response,
            insights_profile=request.insights_profile,
        )
        try:
            created = await repository.create(instance)
        except CustomerServiceAlreadyExists as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service already exists",
            ) from error
        if config_revisions is not None:
            await record_snapshot(config_revisions, created, "create")
        return created

    @router.get("/{instance_id}", response_model=CustomerServiceInstance)
    async def get_customer_service(
        instance_id: UUID, tenant_id: TenantId
    ) -> CustomerServiceInstance:
        instance = await repository.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        return instance

    @router.post(
        "/{instance_id}/livekit-token",
        response_model=LiveKitTokenResponse,
    )
    async def issue_livekit_token(
        instance_id: UUID,
        request: LiveKitTokenRequest,
        tenant_id: TenantId,
    ) -> LiveKitTokenResponse:
        instance = await repository.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        try:
            join = await token_issuer.issue(
                instance,
                request.participant_identity,
            )
        except LiveKitDispatchError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiveKit voice session is temporarily unavailable",
            ) from error
        return LiveKitTokenResponse(
            server_url=join.server_url,
            room_name=join.room_name,
            participant_identity=join.participant_identity,
            token=join.token,
        )

    @router.put("/{instance_id}", response_model=CustomerServiceInstance)
    async def update_customer_service(
        instance_id: UUID,
        update: CustomerServiceUpdate,
        tenant_id: TenantId,
    ) -> CustomerServiceInstance:
        instance = await repository.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        if update.expected_version != instance.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            )

        updated = instance.model_copy(
            update={
                "version": instance.version + 1,
                "display_name": update.display_name,
                "organization_name": update.organization_name,
                "greeting": update.greeting,
                "platform_prompt": update.platform_prompt,
                "tenant_prompt": update.tenant_prompt,
                "voice": update.voice,
                "response": update.response,
                "insights_profile": update.insights_profile,
            }
        )
        try:
            return await repository.save(updated)
        except CustomerServiceVersionConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            ) from error

    @router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_customer_service(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        instance = await repository.get_including_deleted(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        await repository.soft_delete(instance_id, tenant_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{instance_id}/restore", response_model=CustomerServiceInstance)
    async def restore_customer_service(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> CustomerServiceInstance:
        instance = await repository.get_including_deleted(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        restored = await repository.restore(instance_id, tenant_id)
        assert restored is not None
        return restored

    @router.post("/{instance_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
    async def purge_customer_service(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        instance = await repository.get_including_deleted(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        if instance.deleted_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service must be soft-deleted before purge",
            )
        if await call_records.exists_for_customer_service(tenant_id, instance_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service still has call records",
            )
        await repository.hard_delete(instance_id, tenant_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
