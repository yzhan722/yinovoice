from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository


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
def fixed_now_provider() -> Callable[[], datetime]:
    fixed_now = datetime(2026, 8, 30, tzinfo=UTC)

    def now() -> datetime:
        return fixed_now

    return now


@pytest.fixture
def client(ids: TestIds) -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    repository = InMemoryCustomerServiceRepository([instance])
    return TestClient(
        create_app(
            repository,
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
        )
    )
