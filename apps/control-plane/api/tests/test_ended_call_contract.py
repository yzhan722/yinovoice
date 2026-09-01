from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from yino_platform_api.domain.call_record import CallRecord, TranscriptMessage
from yino_platform_api.domain.insights_dispatch import build_ended_call_body

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "packages" / "contracts" / "ended-call" / "fixtures"
VALIDATE = ROOT / "packages" / "contracts" / "ended-call" / "validate.py"

_spec = importlib.util.spec_from_file_location("ended_call_validate", VALIDATE)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_ended_call = _mod.validate_ended_call
ContractError = _mod.ContractError


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_shared_valid_fixture_passes_contract() -> None:
    payload = _load("valid-yino-ended-call.json")
    validate_ended_call(payload)
    assert payload["channel"] == "yino"
    assert payload["recordingUrl"] is None
    assert payload["durationSeconds"] == 252


def test_shared_invalid_fixtures_are_rejected() -> None:
    for name in (
        "invalid-empty-content.json",
        "invalid-extra-field.json",
        "invalid-timestamp.json",
    ):
        with pytest.raises(ContractError):
            validate_ended_call(_load(name))


def test_builder_output_matches_shared_contract(ids) -> None:
    record = CallRecord(
        id=UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        tenant_id=ids.tenant_id,
        created_at=datetime(2026, 8, 31, 10, 0, 0, tzinfo=UTC),
        customer_service_id=ids.instance_id,
        room_name="room-1",
        status="completed",
        started_at=datetime(2026, 8, 31, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 8, 31, 10, 4, 12, tzinfo=UTC),
        duration_sec=252,
        messages=[
            TranscriptMessage(role="user", text="hello", sequence=1),
            TranscriptMessage(role="assistant", text="hi", sequence=2),
        ],
    )
    body = build_ended_call_body(profile="demo-clinic", record=record)
    validate_ended_call(body)
    fixture = _load("valid-yino-ended-call.json")
    assert body["schemaVersion"] == fixture["schemaVersion"]
    assert body["channel"] == fixture["channel"]
    assert body["callId"] == fixture["callId"]
    assert body["startedAt"] == fixture["startedAt"]
    assert body["endedAt"] == fixture["endedAt"]
    assert body["durationSeconds"] == fixture["durationSeconds"]
    assert body["transcript"] == fixture["transcript"]
    assert body["summary"] == fixture["summary"]
    assert body["recordingUrl"] is None
