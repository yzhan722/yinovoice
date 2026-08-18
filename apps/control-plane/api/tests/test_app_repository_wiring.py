"""create_app persistence wiring tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
PLATFORM_API_ROOT = Path(__file__).resolve().parents[1]


def test_create_app_defaults_to_memory_without_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app()
    assert app.state.persistence == "memory"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
def test_create_app_uses_postgres_when_database_url_set() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PLATFORM_API_ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout

    app = create_app()
    assert app.state.persistence == "postgres"
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/customer-services/{DEMO_CUSTOMER_SERVICE_ID}",
            headers={"X-Tenant-ID": str(DEMO_TENANT_ID)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["voice"]["tts_voice"] == "longanqian"
        assert body["platform_prompt"]


def test_explicit_repositories_keep_memory_even_with_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform",
    )
    app = create_app(
        InMemoryCustomerServiceRepository(),
        call_record_repository=InMemoryCallRecordRepository(),
        appointment_repository=InMemoryAppointmentRepository(),
        callback_task_repository=InMemoryCallbackTaskRepository(),
    )
    assert app.state.persistence == "memory"
