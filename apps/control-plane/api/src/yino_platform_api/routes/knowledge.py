from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import TenantId
from ..domain.customer_service import CustomerServiceInstance
from ..domain.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
)
from ..repositories.customer_services import (
    CustomerServiceRepository,
    CustomerServiceVersionConflict,
)
from ..repositories.knowledge import KnowledgeRepository
from ..services.knowledge_compile import apply_knowledge_block, compile_knowledge_block

TENANT_PROMPT_MAX = 8000


class KnowledgeDocumentPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[KnowledgeDocument]
    total: int


class KnowledgeApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


def create_router(
    instances: CustomerServiceRepository,
    knowledge: KnowledgeRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/customer-services")

    async def _require_instance(
        instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance:
        instance = await instances.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        return instance

    @router.get("/{instance_id}/knowledge", response_model=KnowledgeDocumentPage)
    async def list_knowledge(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> KnowledgeDocumentPage:
        await _require_instance(instance_id, tenant_id)
        items = await knowledge.list_for_instance(tenant_id, instance_id)
        return KnowledgeDocumentPage(items=items, total=len(items))

    @router.post(
        "/{instance_id}/knowledge",
        response_model=KnowledgeDocument,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_knowledge(
        instance_id: UUID,
        payload: KnowledgeDocumentCreate,
        tenant_id: TenantId,
    ) -> KnowledgeDocument:
        await _require_instance(instance_id, tenant_id)
        return await knowledge.create(tenant_id, instance_id, payload)

    @router.post(
        "/{instance_id}/knowledge/apply",
        response_model=CustomerServiceInstance,
    )
    async def apply_knowledge(
        instance_id: UUID,
        payload: KnowledgeApplyRequest,
        tenant_id: TenantId,
    ) -> CustomerServiceInstance:
        instance = await _require_instance(instance_id, tenant_id)
        if payload.expected_version != instance.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            )
        documents = await knowledge.list_for_instance(tenant_id, instance_id)
        compiled = apply_knowledge_block(
            instance.tenant_prompt,
            compile_knowledge_block(documents),
        )
        if len(compiled) > TENANT_PROMPT_MAX:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="compiled knowledge exceeds tenant prompt limit",
            )
        updated = instance.model_copy(
            update={
                "version": instance.version + 1,
                "tenant_prompt": compiled,
            }
        )
        try:
            return await instances.save(updated)
        except CustomerServiceVersionConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            ) from error

    @router.put(
        "/{instance_id}/knowledge/{document_id}",
        response_model=KnowledgeDocument,
    )
    async def update_knowledge(
        instance_id: UUID,
        document_id: UUID,
        payload: KnowledgeDocumentUpdate,
        tenant_id: TenantId,
    ) -> KnowledgeDocument:
        await _require_instance(instance_id, tenant_id)
        existing = await knowledge.get(document_id, tenant_id, instance_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge document not found",
            )
        return await knowledge.save(
            existing.model_copy(update={"title": payload.title, "body": payload.body})
        )

    @router.delete(
        "/{instance_id}/knowledge/{document_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_knowledge(
        instance_id: UUID,
        document_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        await _require_instance(instance_id, tenant_id)
        deleted = await knowledge.delete(document_id, tenant_id, instance_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge document not found",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
