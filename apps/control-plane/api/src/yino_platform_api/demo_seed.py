"""Guarded, idempotent synthetic instance seed helpers.

This module never discovers a database or tenant. Callers must inject both.
"""

from dataclasses import dataclass
from uuid import UUID, uuid5

from .domain.customer_service import (
    CustomerServiceInstance,
    ResponseProfile,
    VoiceProfile,
)
from .repositories.customer_services import CustomerServiceRepository


@dataclass(frozen=True)
class SeedResult:
    created: int
    skipped: int


_SYNTHETIC_INSTANCES = (
    (
        "general-reception",
        "Demo General Reception",
        "Welcome to the synthetic demo reception.",
    ),
    (
        "follow-up",
        "Demo Follow-up",
        "Welcome to the synthetic demo follow-up service.",
    ),
    (
        "event-information",
        "Demo Event Information",
        "Welcome to the synthetic demo information service.",
    ),
    (
        "internal-hotline",
        "Demo Internal Hotline",
        "Welcome to the synthetic demo internal hotline.",
    ),
)


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
    for stable_key, display_name, greeting in _SYNTHETIC_INSTANCES:
        instance_id = uuid5(tenant_id, f"yinovoice-demo:{stable_key}")
        if await repository.get(instance_id, tenant_id) is not None:
            skipped += 1
            continue
        await repository.create(
            CustomerServiceInstance(
                id=instance_id,
                tenant_id=tenant_id,
                version=1,
                display_name=display_name,
                organization_name="Synthetic Demo Organization",
                greeting=greeting,
                platform_prompt=(
                    "Provide concise, safe, synthetic demonstration responses."
                ),
                tenant_prompt=(
                    "Use only fictional facts supplied during this demo session."
                ),
                voice=VoiceProfile(),
                response=ResponseProfile(),
            )
        )
        created += 1
    return SeedResult(created=created, skipped=skipped)
