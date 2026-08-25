from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import TenantId
from ..domain.config_revision import InstanceConfigRevision
from ..domain.customer_service import (
    CustomerServiceInstance,
    apply_publishable_snapshot,
    publishable_snapshot,
)
from ..repositories.config_revisions import (
    ConfigRevisionRepository,
    record_snapshot,
)
from ..repositories.customer_services import (
    CustomerServiceRepository,
    CustomerServiceVersionConflict,
)
from ..services.config_publish import config_diff_changes


class ConfigRevisionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InstanceConfigRevision]
    total: int


class ConfigDiffChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    before: object = None
    after: object = None


class ConfigDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_version: int
    published_revision: int | None
    changes: list[ConfigDiffChange]


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    expected_version: int = Field(ge=1)


class RollbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance: CustomerServiceInstance
    revision: InstanceConfigRevision


def create_router(
    instances: CustomerServiceRepository,
    revisions: ConfigRevisionRepository,
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

    @router.get("/{instance_id}/revisions", response_model=ConfigRevisionPage)
    async def list_revisions(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> ConfigRevisionPage:
        await _require_instance(instance_id, tenant_id)
        items = await revisions.list_for_instance(tenant_id, instance_id)
        return ConfigRevisionPage(items=items, total=len(items))

    @router.get("/{instance_id}/config-diff", response_model=ConfigDiffResponse)
    async def config_diff(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> ConfigDiffResponse:
        instance = await _require_instance(instance_id, tenant_id)
        latest = await revisions.latest(tenant_id, instance_id)
        published = latest.snapshot if latest is not None else None
        changes = [
            ConfigDiffChange.model_validate(change)
            for change in config_diff_changes(
                publishable_snapshot(instance),
                published,
            )
        ]
        return ConfigDiffResponse(
            current_version=instance.version,
            published_revision=None if latest is None else latest.revision,
            changes=changes,
        )

    @router.post("/{instance_id}/publish", response_model=InstanceConfigRevision)
    async def publish_config(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> InstanceConfigRevision:
        instance = await _require_instance(instance_id, tenant_id)
        return await record_snapshot(revisions, instance, "publish")

    @router.post("/{instance_id}/rollback", response_model=RollbackResponse)
    async def rollback_config(
        instance_id: UUID,
        payload: RollbackRequest,
        tenant_id: TenantId,
    ) -> RollbackResponse:
        instance = await _require_instance(instance_id, tenant_id)
        if payload.expected_version != instance.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            )
        target = await revisions.get_by_revision(
            tenant_id, instance_id, payload.revision
        )
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Config revision not found",
            )
        restored = apply_publishable_snapshot(
            instance,
            target.snapshot,
            version=instance.version + 1,
        )
        try:
            saved = await instances.save(restored)
        except CustomerServiceVersionConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer service version conflict",
            ) from error
        recorded = await record_snapshot(revisions, saved, "rollback")
        return RollbackResponse(instance=saved, revision=recorded)

    return router
