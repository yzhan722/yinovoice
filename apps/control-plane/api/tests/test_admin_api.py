import base64
import hashlib
import hmac
import json
import time
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

SECRET = "test-auth-secret"


def _client(*, with_admin: bool = True) -> TestClient:
    instance = CustomerServiceInstance.demo(
        instance_id=UUID("00000000-0000-0000-0000-000000000101"),
        tenant_id=DEMO_TENANT_ID,
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
                secret=SECRET,
                account="demo",
                password="demo123",
                tenant_id=DEMO_TENANT_ID,
                admin_account="root" if with_admin else None,
                admin_password="root-secret" if with_admin else None,
            ),
        )
    )


def _login(client: TestClient, account: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"account": account, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_bootstrap_and_role_gate() -> None:
    client = _client()
    admin = _login(client, "root", "root-secret")
    me = client.get("/api/v1/auth/me", headers=_bearer(admin))
    assert me.json()["roles"] == ["platform_admin"]

    operator = _login(client, "demo", "demo123")
    assert client.get("/api/v1/auth/me", headers=_bearer(operator)).json()["roles"] == [
        "tenant_operator"
    ]
    assert (
        client.get("/api/v1/admin/tenants", headers=_bearer(operator)).status_code
        == 403
    )
    assert client.get("/api/v1/admin/tenants").status_code == 401
    listed = client.get("/api/v1/admin/tenants", headers=_bearer(admin))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_no_admin_configured_means_no_admin_login() -> None:
    client = _client(with_admin=False)
    assert (
        client.post(
            "/api/v1/auth/login", json={"account": "root", "password": "root-secret"}
        ).status_code
        == 401
    )
    _login(client, "demo", "demo123")


def test_admin_creates_tenant_and_user_who_is_isolated() -> None:
    client = _client()
    admin = _login(client, "root", "root-secret")

    tenant = client.post(
        "/api/v1/admin/tenants",
        headers=_bearer(admin),
        json={"id": "00000000-0000-0000-0000-000000000002", "name": "Clinic B"},
    )
    assert tenant.status_code == 201, tenant.text
    tenant_id = tenant.json()["id"]
    assert (
        client.post(
            "/api/v1/admin/tenants",
            headers=_bearer(admin),
            json={"id": tenant_id, "name": "dup"},
        ).status_code
        == 409
    )

    user = client.post(
        "/api/v1/admin/users",
        headers=_bearer(admin),
        json={
            "tenant_id": tenant_id,
            "account": "ops@clinic-b.test",
            "password": "clinic-b-pass",
            "nickname": "B 前台",
        },
    )
    assert user.status_code == 201, user.text
    assert user.json()["role"] == "tenant_operator"
    assert (
        client.post(
            "/api/v1/admin/users",
            headers=_bearer(admin),
            json={
                "tenant_id": tenant_id,
                "account": "OPS@clinic-b.test",
                "password": "another-pass",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/admin/users",
            headers=_bearer(admin),
            json={
                "tenant_id": "00000000-0000-0000-0000-000000000099",
                "account": "nobody",
                "password": "nobody-pass",
            },
        ).status_code
        == 404
    )

    users = client.get(
        "/api/v1/admin/users", headers=_bearer(admin), params={"tenant_id": tenant_id}
    )
    assert users.json()["total"] == 1

    operator = _login(client, "ops@clinic-b.test", "clinic-b-pass")
    me = client.get("/api/v1/auth/me", headers=_bearer(operator)).json()
    assert me["tenant_id"] == tenant_id
    own = client.get("/api/v1/customer-services", headers=_bearer(operator))
    assert own.status_code == 200
    assert own.json()["total"] == 0
    cross = client.get(
        "/api/v1/customer-services",
        headers={**_bearer(operator), "X-Tenant-ID": str(DEMO_TENANT_ID)},
    )
    assert cross.status_code == 403


def test_platform_admin_can_act_for_any_tenant_via_header() -> None:
    client = _client()
    admin = _login(client, "root", "root-secret")
    demo = client.get(
        "/api/v1/customer-services",
        headers={**_bearer(admin), "X-Tenant-ID": str(DEMO_TENANT_ID)},
    )
    assert demo.status_code == 200
    assert demo.json()["total"] == 1
    other = client.get(
        "/api/v1/customer-services",
        headers={
            **_bearer(admin),
            "X-Tenant-ID": "00000000-0000-0000-0000-000000000002",
        },
    )
    assert other.status_code == 200
    assert other.json()["total"] == 0


def test_password_reset_and_disable() -> None:
    client = _client()
    admin = _login(client, "root", "root-secret")
    created = client.post(
        "/api/v1/admin/users",
        headers=_bearer(admin),
        json={
            "tenant_id": str(DEMO_TENANT_ID),
            "account": "second",
            "password": "second-pass",
        },
    ).json()
    user_id = created["id"]

    reset = client.post(
        f"/api/v1/admin/users/{user_id}/password",
        headers=_bearer(admin),
        json={"password": "rotated-pass"},
    )
    assert reset.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/login", json={"account": "second", "password": "second-pass"}
        ).status_code
        == 401
    )
    _login(client, "second", "rotated-pass")

    disabled = client.post(
        f"/api/v1/admin/users/{user_id}/status",
        headers=_bearer(admin),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert (
        client.post(
            "/api/v1/auth/login", json={"account": "second", "password": "rotated-pass"}
        ).status_code
        == 401
    )

    me = client.get("/api/v1/auth/me", headers=_bearer(admin)).json()
    admin_id = next(
        item["id"]
        for item in client.get("/api/v1/admin/users", headers=_bearer(admin)).json()[
            "items"
        ]
        if item["account"] == me["account"]
    )
    assert (
        client.post(
            f"/api/v1/admin/users/{admin_id}/status",
            headers=_bearer(admin),
            json={"status": "disabled"},
        ).status_code
        == 409
    )


def test_legacy_token_without_role_is_treated_as_tenant_operator() -> None:
    client = _client()
    payload = json.dumps(
        {"tid": str(DEMO_TENANT_ID), "acc": "demo", "exp": int(time.time()) + 600},
        separators=(",", ":"),
    ).encode()
    body = base64.urlsafe_b64encode(payload).rstrip(b"=")
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    token = body.decode() + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    me = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["roles"] == ["tenant_operator"]
    assert (
        client.get("/api/v1/admin/tenants", headers=_bearer(token)).status_code == 403
    )
