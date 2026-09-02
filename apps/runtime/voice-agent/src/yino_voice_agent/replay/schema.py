"""Replay fixture schema. Reject secrets, audio, transcripts, and full numbers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from ..session_trace import redact_phone_numbers

SCHEMA_VERSION = 1
ALLOWED_SOURCES = frozenset(
    {"livekit", "qwen", "platform", "tool", "lifecycle", "runtime"}
)
_FORBIDDEN_KEYS = frozenset(
    {
        "audio",
        "transcript",
        "prompt",
        "api_key",
        "token",
        "authorization",
        "secret",
        "password",
        "caller_number",
        "callee_number",
        "phone",
        "email",
        "address",
        "recording_url",
    }
)
SourceName = Literal["livekit", "qwen", "platform", "tool", "lifecycle", "runtime"]


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    at_ms: int
    source: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayFixture:
    schema_version: int
    events: tuple[ReplayEvent, ...]


def sanitize_event_data(data: Mapping[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key in _FORBIDDEN_KEYS:
            continue
        if isinstance(value, str):
            cleaned[key] = redact_phone_numbers(value)
        elif isinstance(value, Mapping):
            cleaned[key] = sanitize_event_data(value)
        else:
            cleaned[key] = value
    return cleaned


def load_fixture(raw: str | Mapping[str, Any]) -> ReplayFixture:
    payload: Mapping[str, Any]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("replay fixture must be valid JSON") from error
        if not isinstance(parsed, dict):
            raise ValueError("replay fixture must be an object")
        payload = parsed
    else:
        payload = raw
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError("unsupported replay schema_version")
    events_raw = payload.get("events")
    if not isinstance(events_raw, list):
        raise ValueError("replay events must be a list")
    events: list[ReplayEvent] = []
    for item in events_raw:
        if not isinstance(item, dict):
            raise ValueError("replay event must be an object")
        at_ms = item.get("at_ms")
        source = item.get("source")
        event_type = item.get("type")
        data = item.get("data", {})
        if not isinstance(at_ms, int) or at_ms < 0:
            raise ValueError("replay event at_ms must be a non-negative int")
        if source not in ALLOWED_SOURCES:
            raise ValueError("replay event source is not allowed")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("replay event type is required")
        if not isinstance(data, dict):
            raise ValueError("replay event data must be an object")
        events.append(
            ReplayEvent(
                at_ms=at_ms,
                source=source,
                type=event_type,
                data=sanitize_event_data(data),
            )
        )
    return ReplayFixture(schema_version=SCHEMA_VERSION, events=tuple(events))
