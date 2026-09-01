#!/usr/bin/env python3
"""Validate ended-call v1 fixtures against the shared JSON Schema plus runtime invariants.

This script is stdlib-only so CI/local verification does not need extra packages.
It does not import Yino API or Call Insights runtime code.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
EVENT_ID = re.compile(r"^[a-f0-9]{64}$")
CALL_ID = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED = (
    "schemaVersion",
    "channel",
    "callId",
    "eventId",
    "startedAt",
    "endedAt",
    "durationSeconds",
    "transcript",
    "summary",
    "recordingUrl",
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


class ContractError(ValueError):
    pass


def parse_utc_ms(value: str) -> datetime:
    if not UTC_MS.fullmatch(value):
        raise ContractError(f"timestamp is not UTC milliseconds Z: {value!r}")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z" != value:
        raise ContractError(f"timestamp is not canonical UTC milliseconds: {value!r}")
    return parsed


def validate_ended_call(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ContractError("payload must be an object")
    extra = set(payload) - set(REQUIRED)
    if extra:
        raise ContractError(f"unexpected fields: {sorted(extra)}")
    missing = [key for key in REQUIRED if key not in payload]
    if missing:
        raise ContractError(f"missing fields: {missing}")
    if payload["schemaVersion"] != 1:
        raise ContractError("schemaVersion must be 1")
    if payload["channel"] != "yino":
        raise ContractError("channel must be yino")
    call_id = payload["callId"]
    if not isinstance(call_id, str) or not CALL_ID.fullmatch(call_id) or call_id in {".", ".."}:
        raise ContractError("callId is not a safe path segment")
    if not isinstance(payload["eventId"], str) or not EVENT_ID.fullmatch(payload["eventId"]):
        raise ContractError("eventId must be 64 lowercase hex")
    started = parse_utc_ms(payload["startedAt"])
    ended = parse_utc_ms(payload["endedAt"])
    duration = payload["durationSeconds"]
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ContractError("durationSeconds must be an integer")
    if duration < 0 or duration > 86_400:
        raise ContractError("durationSeconds out of range")
    if ended < started:
        raise ContractError("endedAt before startedAt")
    expected = int((ended - started).total_seconds())
    expected = max(0, min(expected, 86_400))
    if duration != expected:
        raise ContractError("durationSeconds mismatch")
    if not isinstance(payload["transcript"], str) or not isinstance(payload["summary"], str):
        raise ContractError("transcript and summary must be strings")
    if payload["transcript"] == "" and payload["summary"] == "":
        raise ContractError("transcript or summary required")
    if payload["recordingUrl"] is not None:
        raise ContractError("recordingUrl must be null")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    schema = load_json(ROOT / "v1.schema.json")
    if schema.get("additionalProperties") is not False:
        print("schema must be strict", file=sys.stderr)
        return 1
    valid = FIXTURES / "valid-yino-ended-call.json"
    invalids = [
        FIXTURES / "invalid-empty-content.json",
        FIXTURES / "invalid-extra-field.json",
        FIXTURES / "invalid-timestamp.json",
    ]
    try:
        validate_ended_call(load_json(valid))
    except ContractError as error:
        print(f"valid fixture rejected: {error}", file=sys.stderr)
        return 1
    for path in invalids:
        try:
            validate_ended_call(load_json(path))
        except ContractError:
            continue
        print(f"invalid fixture accepted: {path.name}", file=sys.stderr)
        return 1
    print("ended-call v1 fixtures: 1 valid, 3 invalid, schema strict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
