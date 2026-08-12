"""Idempotent demo seed rows for local PostgreSQL MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from .models import AgentTemplateVersion, Tenant, VoiceAgentInstance

DEMO_TEMPLATE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000201")
DEMO_TEMPLATE_KEY = "pacific-dental-demo"


async def ensure_demo_seed(session: AsyncSession) -> None:
    """Insert Demo tenant, template version, and voice agent instance if missing."""

    tenant = await session.get(Tenant, DEMO_TENANT_ID)
    if tenant is None:
        session.add(
            Tenant(
                id=DEMO_TENANT_ID,
                name="Demo Tenant",
                home_region="cn-mainland",
                status="active",
            )
        )

    template = await session.get(AgentTemplateVersion, DEMO_TEMPLATE_VERSION_ID)
    if template is None:
        session.add(
            AgentTemplateVersion(
                id=DEMO_TEMPLATE_VERSION_ID,
                template_key=DEMO_TEMPLATE_KEY,
                version=1,
                schema_version=1,
                package={
                    "kind": "customer-service",
                    "name": "Pacific Dental Demo",
                    "locale": "zh-CN",
                },
                published_at=datetime(2026, 8, 11, tzinfo=UTC),
            )
        )

    existing = await session.scalar(
        select(VoiceAgentInstance).where(
            VoiceAgentInstance.tenant_id == DEMO_TENANT_ID,
            VoiceAgentInstance.id == DEMO_CUSTOMER_SERVICE_ID,
        )
    )
    if existing is None:
        demo = CustomerServiceInstance.demo(
            instance_id=DEMO_CUSTOMER_SERVICE_ID,
            tenant_id=DEMO_TENANT_ID,
        )
        session.add(
            VoiceAgentInstance(
                id=demo.id,
                tenant_id=demo.tenant_id,
                template_version_id=DEMO_TEMPLATE_VERSION_ID,
                version=demo.version,
                display_name=demo.display_name,
                organization_name=demo.organization_name,
                business_profile=demo.business_profile,
                primary_language=demo.primary_language,
                greeting=demo.greeting,
                platform_prompt=demo.platform_prompt,
                tenant_prompt=demo.tenant_prompt,
                voice_config=demo.voice.model_dump(mode="json"),
                response_config=demo.response.model_dump(mode="json"),
            )
        )

    await session.commit()
