from uuid import UUID

from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import (
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.repositories.scheduling import InMemorySchedulingRepository
from yino_platform_api.services.auth import AuthService


def _client() -> TestClient:
    tenant_id = DEMO_TENANT_ID
    instance = CustomerServiceInstance.demo(
        instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        tenant_id=tenant_id,
    )
    return TestClient(
        create_app(
            InMemoryCustomerServiceRepository([instance]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            scheduling_repository=InMemorySchedulingRepository(),
            auth_service=AuthService(
                secret="test-auth-secret",
                account="demo",
                password="demo123",
                tenant_id=tenant_id,
            ),
        )
    )


def test_login_issues_tenant_token_and_me_reads_it() -> None:
    client = _client()
    login = client.post(
        "/api/v1/auth/login",
        json={"account": "demo", "password": "demo123"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["tenant_id"] == str(DEMO_TENANT_ID)
    assert body["account"] == "demo"
    assert body["token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert me.status_code == 200
    assert me.json()["tenant_id"] == str(DEMO_TENANT_ID)
    assert me.json()["account"] == "demo"


def test_login_rejects_bad_password() -> None:
    client = _client()
    response = client.post(
        "/api/v1/auth/login",
        json={"account": "demo", "password": "wrong"},
    )
    assert response.status_code == 401


def test_bearer_tenant_overrides_header_and_rejects_mismatch() -> None:
    client = _client()
    token = client.post(
        "/api/v1/auth/login",
        json={"account": "demo", "password": "demo123"},
    ).json()["token"]
    listed = client.get(
        "/api/v1/customer-services",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    mismatch = client.get(
        "/api/v1/customer-services",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert mismatch.status_code == 403


def test_missing_tenant_and_token_is_unauthorized() -> None:
    client = _client()
    response = client.get("/api/v1/customer-services")
    assert response.status_code == 401


def test_invalid_bearer_is_unauthorized_even_with_tenant_header() -> None:
    client = _client()
    response = client.get(
        "/api/v1/customer-services",
        headers={
            "Authorization": "Bearer not-a-token",
            "X-Tenant-ID": str(DEMO_TENANT_ID),
        },
    )
    assert response.status_code == 401
