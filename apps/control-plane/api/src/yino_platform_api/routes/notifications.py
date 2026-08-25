from datetime import UTC, datetime

from fastapi import APIRouter

from ..dependencies import TenantId
from ..services.notifications import (
    NotificationService,
    NotificationSettings,
    NotificationSettingsUpdate,
)


def create_router(service: NotificationService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/notification-settings")

    @router.get("", response_model=NotificationSettings)
    async def get_settings(tenant_id: TenantId) -> NotificationSettings:
        existing = await service.get_settings(tenant_id)
        if existing is not None:
            return existing
        return NotificationSettings(
            tenant_id=tenant_id,
            email="",
            enabled=True,
            updated_at=datetime.now(UTC),
        )

    @router.put("", response_model=NotificationSettings)
    async def put_settings(
        payload: NotificationSettingsUpdate,
        tenant_id: TenantId,
    ) -> NotificationSettings:
        return await service.upsert_settings(
            NotificationSettings(
                tenant_id=tenant_id,
                email=payload.email,
                enabled=payload.enabled,
                updated_at=datetime.now(UTC),
            )
        )

    return router
