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
async def test_demo_seed_creates_industry_instances_idempotently() -> None:
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

    assert first.created == 7
    assert first.skipped == 0
    assert second.created == 0
    assert second.skipped == 7
    items, total = await repository.list_for_tenant(tenant_id, limit=100, offset=0)
    assert total == 7
    assert {item.display_name for item in items} == {
        "银杏口腔前台",
        "青禾私房菜订位",
        "临江驿酒店前台",
        "澄光美容预约",
        "启明学堂试听",
        "北辰汽车售后",
        "青梧置业看房",
    }
    assert all("合成演示" in item.organization_name for item in items)
    _, other_total = await repository.list_for_tenant(
        other_tenant_id, limit=100, offset=0
    )
    assert other_total == 0
