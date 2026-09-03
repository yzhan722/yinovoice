"""Idempotent demo seed rows for local PostgreSQL MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from ..industry_scenarios import (
    INDUSTRY_SCENARIOS,
    PACIFIC_DEMO_HOURS,
    PACIFIC_DEMO_OFFERINGS,
    HourWindow,
    IndustryScenario,
    KnowledgeSpec,
    OfferingSpec,
)
from .models import (
    AgentTemplateVersion,
    BusinessHoursRow,
    KnowledgeDocumentRow,
    SchedulingProfileRow,
    ServiceOfferingRow,
    Tenant,
    VoiceAgentInstance,
)

DEMO_TEMPLATE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000201")
DEMO_TEMPLATE_KEY = "pacific-dental-demo"


def _voice_row(instance: CustomerServiceInstance) -> VoiceAgentInstance:
    return VoiceAgentInstance(
        id=instance.id,
        tenant_id=instance.tenant_id,
        template_version_id=DEMO_TEMPLATE_VERSION_ID,
        version=instance.version,
        display_name=instance.display_name,
        organization_name=instance.organization_name,
        business_profile=instance.business_profile,
        primary_language=instance.primary_language,
        greeting=instance.greeting,
        platform_prompt=instance.platform_prompt,
        tenant_prompt=instance.tenant_prompt,
        voice_config=instance.voice.model_dump(mode="json"),
        response_config=instance.response.model_dump(mode="json"),
        insights_profile=instance.insights_profile,
    )


async def _ensure_offerings(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    instance_id: UUID,
    offerings: tuple[OfferingSpec, ...],
) -> None:
    existing = await session.scalar(
        select(func.count())
        .select_from(ServiceOfferingRow)
        .where(
            ServiceOfferingRow.tenant_id == tenant_id,
            ServiceOfferingRow.voice_agent_instance_id == instance_id,
        )
    )
    if int(existing or 0) > 0:
        return
    now = datetime.now(UTC)
    for spec in offerings:
        session.add(
            ServiceOfferingRow(
                id=uuid5(instance_id, f"offering:{spec.name}"),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                name=spec.name,
                description=spec.description,
                duration_minutes=spec.duration_minutes,
                buffer_minutes=0,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )


async def _ensure_hours(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    instance_id: UUID,
    hours: tuple[HourWindow, ...],
    timezone: str,
) -> None:
    profile = await session.scalar(
        select(SchedulingProfileRow).where(
            SchedulingProfileRow.tenant_id == tenant_id,
            SchedulingProfileRow.voice_agent_instance_id == instance_id,
        )
    )
    if profile is None:
        session.add(
            SchedulingProfileRow(
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                timezone=timezone,
                slot_interval_minutes=15,
                minimum_notice_minutes=60,
                booking_horizon_days=60,
                updated_at=datetime.now(UTC),
            )
        )
    existing_hours = await session.scalar(
        select(func.count())
        .select_from(BusinessHoursRow)
        .where(
            BusinessHoursRow.tenant_id == tenant_id,
            BusinessHoursRow.voice_agent_instance_id == instance_id,
        )
    )
    if int(existing_hours or 0) > 0:
        return
    for index, window in enumerate(hours):
        hour_key = f"hours:{index}:{window.weekday}:{window.start_local}"
        session.add(
            BusinessHoursRow(
                id=uuid5(instance_id, hour_key),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                weekday=window.weekday,
                start_local=window.start_local,
                end_local=window.end_local,
                enabled=True,
            )
        )


async def _ensure_knowledge(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    instance_id: UUID,
    documents: tuple[KnowledgeSpec, ...],
) -> None:
    existing = await session.scalar(
        select(func.count())
        .select_from(KnowledgeDocumentRow)
        .where(
            KnowledgeDocumentRow.tenant_id == tenant_id,
            KnowledgeDocumentRow.instance_id == instance_id,
        )
    )
    if int(existing or 0) > 0:
        return
    now = datetime.now(UTC)
    for spec in documents:
        session.add(
            KnowledgeDocumentRow(
                id=uuid5(instance_id, f"knowledge:{spec.title}"),
                tenant_id=tenant_id,
                instance_id=instance_id,
                title=spec.title,
                body=spec.body,
                created_at=now,
                updated_at=now,
            )
        )


async def _ensure_scenario_runtime(
    session: AsyncSession,
    scenario: IndustryScenario,
) -> None:
    instance_id = scenario.instance_id_for(DEMO_TENANT_ID)
    existing = await session.scalar(
        select(VoiceAgentInstance).where(
            VoiceAgentInstance.tenant_id == DEMO_TENANT_ID,
            VoiceAgentInstance.id == instance_id,
        )
    )
    if existing is None:
        session.add(
            _voice_row(
                scenario.to_instance(
                    tenant_id=DEMO_TENANT_ID, instance_id=instance_id
                )
            )
        )
        await session.flush()
    await _ensure_offerings(
        session,
        tenant_id=DEMO_TENANT_ID,
        instance_id=instance_id,
        offerings=scenario.offerings,
    )
    await _ensure_hours(
        session,
        tenant_id=DEMO_TENANT_ID,
        instance_id=instance_id,
        hours=scenario.hours,
        timezone=scenario.timezone,
    )
    await _ensure_knowledge(
        session,
        tenant_id=DEMO_TENANT_ID,
        instance_id=instance_id,
        documents=scenario.knowledge,
    )


async def ensure_demo_seed(session: AsyncSession) -> None:
    """Insert Demo tenant, template, Pacific instance, and industry scenarios."""

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
        await session.flush()

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
        await session.flush()

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
        session.add(_voice_row(demo))
        await session.flush()

    await _ensure_offerings(
        session,
        tenant_id=DEMO_TENANT_ID,
        instance_id=DEMO_CUSTOMER_SERVICE_ID,
        offerings=PACIFIC_DEMO_OFFERINGS,
    )
    await _ensure_hours(
        session,
        tenant_id=DEMO_TENANT_ID,
        instance_id=DEMO_CUSTOMER_SERVICE_ID,
        hours=PACIFIC_DEMO_HOURS,
        timezone="Asia/Shanghai",
    )

    for scenario in INDUSTRY_SCENARIOS:
        await _ensure_scenario_runtime(session, scenario)

    await session.commit()
