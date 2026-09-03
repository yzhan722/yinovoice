"""Guarded, idempotent synthetic instance seed helpers.

This module never discovers a database or tenant. Callers must inject both.
"""

from dataclasses import dataclass
from uuid import UUID

from .domain.knowledge import KnowledgeDocumentCreate
from .domain.scheduling import (
    BusinessHoursWrite,
    SchedulingProfileUpdate,
    ServiceOfferingCreate,
)
from .industry_scenarios import INDUSTRY_SCENARIOS, IndustryScenario
from .repositories.customer_services import CustomerServiceRepository
from .repositories.knowledge import KnowledgeRepository
from .repositories.scheduling import (
    SchedulingRepository,
    hours_from_writes,
    new_offering,
    profile_from_update,
)


@dataclass(frozen=True)
class SeedResult:
    created: int
    skipped: int


async def _ensure_scenario_accessories(
    *,
    scheduling: SchedulingRepository,
    knowledge: KnowledgeRepository,
    tenant_id: UUID,
    instance_id: UUID,
    scenario: IndustryScenario,
) -> None:
    if not await scheduling.list_offerings(tenant_id, instance_id):
        for spec in scenario.offerings:
            await scheduling.create_offering(
                new_offering(
                    tenant_id,
                    ServiceOfferingCreate(
                        voice_agent_instance_id=instance_id,
                        name=spec.name,
                        description=spec.description,
                        duration_minutes=spec.duration_minutes,
                    ),
                )
            )
    if await scheduling.get_profile(tenant_id, instance_id) is None:
        await scheduling.upsert_profile(
            profile_from_update(
                tenant_id,
                instance_id,
                SchedulingProfileUpdate(
                    timezone=scenario.timezone,
                    slot_interval_minutes=scenario.slot_interval_minutes,
                    minimum_notice_minutes=scenario.minimum_notice_minutes,
                    booking_horizon_days=scenario.booking_horizon_days,
                ),
            )
        )
    if not await scheduling.list_hours(tenant_id, instance_id):
        await scheduling.replace_hours(
            tenant_id,
            instance_id,
            hours_from_writes(
                tenant_id,
                instance_id,
                [
                    BusinessHoursWrite(
                        weekday=window.weekday,
                        start_local=window.start_local,
                        end_local=window.end_local,
                    )
                    for window in scenario.hours
                ],
            ),
        )
    if not await knowledge.list_for_instance(tenant_id, instance_id):
        for spec in scenario.knowledge:
            await knowledge.create(
                tenant_id,
                instance_id,
                KnowledgeDocumentCreate(title=spec.title, body=spec.body),
            )


async def import_industry_scenarios(
    *,
    services: CustomerServiceRepository,
    scheduling: SchedulingRepository,
    knowledge: KnowledgeRepository,
    tenant_id: UUID,
) -> SeedResult:
    created = 0
    skipped = 0
    for scenario in INDUSTRY_SCENARIOS:
        instance_id = scenario.instance_id_for(tenant_id)
        existing = await services.get(instance_id, tenant_id)
        if existing is None:
            await services.create(
                scenario.to_instance(tenant_id=tenant_id, instance_id=instance_id)
            )
            created += 1
        else:
            skipped += 1
        await _ensure_scenario_accessories(
            scheduling=scheduling,
            knowledge=knowledge,
            tenant_id=tenant_id,
            instance_id=instance_id,
            scenario=scenario,
        )
    return SeedResult(created=created, skipped=skipped)


async def seed_demo_instances(
    repository: CustomerServiceRepository,
    *,
    tenant_id: UUID,
    environment: str,
    allow_demo_seed: bool,
) -> SeedResult:
    if environment not in {"local", "test"}:
        raise ValueError("demo seed environment must be local or test")
    if not allow_demo_seed:
        raise ValueError("demo seed must be explicitly enabled")

    created = 0
    skipped = 0
    for scenario in INDUSTRY_SCENARIOS:
        instance_id = scenario.instance_id_for(tenant_id)
        if await repository.get(instance_id, tenant_id) is not None:
            skipped += 1
            continue
        await repository.create(
            scenario.to_instance(tenant_id=tenant_id, instance_id=instance_id)
        )
        created += 1
    return SeedResult(created=created, skipped=skipped)
