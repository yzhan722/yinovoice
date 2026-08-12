from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)


@dataclass(frozen=True)
class TestIds:
    tenant_id: UUID
    other_tenant_id: UUID
    instance_id: UUID


@pytest.fixture
def ids() -> TestIds:
    return TestIds(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        other_tenant_id=UUID("00000000-0000-0000-0000-000000000002"),
        instance_id=UUID("00000000-0000-0000-0000-000000000101"),
    )


@pytest.fixture
def client(ids: TestIds) -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    repository = InMemoryCustomerServiceRepository([instance])
    return TestClient(create_app(repository))
