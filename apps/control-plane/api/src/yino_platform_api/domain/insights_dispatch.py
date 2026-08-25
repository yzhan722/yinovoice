from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .call_record import CallRecord, TranscriptMessage


class InsightsDispatchJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    call_id: UUID
    profile: str
    event_id: str
    body: dict[str, object]
    status: Literal["pending", "sent", "failed"]
    attempts: int = Field(ge=0)
    next_attempt_at: datetime | None = None
    last_error: str = ""


def format_utc_ms(value: datetime) -> str:
    utc = value.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def duration_seconds_from_utc_ms(started_at: str, ended_at: str) -> int:
    start = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    end = datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    seconds = int((end - start).total_seconds())
    return max(0, min(seconds, 86_400))


def build_event_id(profile: str, call_id: UUID, ended_at: datetime) -> str:
    payload = f"yino|{profile}|{call_id}|{format_utc_ms(ended_at)}"
    return hashlib.sha256(payload.encode()).hexdigest()


def format_transcript(messages: list[TranscriptMessage]) -> str:
    ordered = sorted(messages, key=lambda item: item.sequence)
    return "\n".join(f"{item.role}: {item.text}" for item in ordered)


def build_ended_call_body(*, profile: str, record: CallRecord) -> dict[str, object]:
    if record.ended_at is None:
        raise ValueError("ended_at is required")
    started_at = format_utc_ms(record.started_at)
    ended_at = format_utc_ms(record.ended_at)
    return {
        "schemaVersion": 1,
        "channel": "yino",
        "callId": str(record.id),
        "eventId": build_event_id(profile, record.id, record.ended_at),
        "startedAt": started_at,
        "endedAt": ended_at,
        "durationSeconds": duration_seconds_from_utc_ms(started_at, ended_at),
        "transcript": format_transcript(record.messages),
        "summary": "",
        "recordingUrl": None,
    }
