from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import TenantId
from ..domain.customer_service import (
    CustomerServiceInstance,
    CustomerServiceUpdate,
)
from ..repositories.customer_services import (
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


def create_router(
    repository: CustomerServiceRepository,
    token_issuer: LiveKitTokenIssuer,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/customer-services")

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
            }
        )
        try:
            return await repository.save(updated)
        except CustomerServiceVersionConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            ) from error

    return router
