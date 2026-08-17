from uuid import uuid4

import pytest

from yino_platform_api.demo_seed import seed_demo_instances
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)


@pytest.mark.asyncio
async def test_demo_seed_refuses_unknown_or_production_environment() -> None:
    repository = InMemoryCustomerServiceRepository()

    for environment in ("", "production", "staging"):
        with pytest.raises(ValueError, match="local or test"):
            await seed_demo_instances(
                repository,
                tenant_id=uuid4(),
                environment=environment,
                allow_demo_seed=True,
            )

    with pytest.raises(ValueError, match="explicitly enabled"):
        await seed_demo_instances(
            repository,
            tenant_id=uuid4(),
            environment="local",
            allow_demo_seed=False,
        )


@pytest.mark.asyncio
async def test_demo_seed_creates_four_synthetic_instances_idempotently() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    repository = InMemoryCustomerServiceRepository()

    first = await seed_demo_instances(
        repository,
        tenant_id=tenant_id,
        environment="test",
        allow_demo_seed=True,
    )
    second = await seed_demo_instances(
        repository,
        tenant_id=tenant_id,
        environment="test",
        allow_demo_seed=True,
    )

    assert first.created == 4
    assert first.skipped == 0
    assert second.created == 0
    assert second.skipped == 4
    items, total = await repository.list_for_tenant(tenant_id, limit=100, offset=0)
    assert total == 4
    assert {item.display_name for item in items} == {
        "Demo General Reception",
        "Demo Follow-up",
        "Demo Event Information",
        "Demo Internal Hotline",
    }
    assert all("Demo" in item.organization_name for item in items)
    _, other_total = await repository.list_for_tenant(
        other_tenant_id, limit=100, offset=0
    )
    assert other_total == 0
