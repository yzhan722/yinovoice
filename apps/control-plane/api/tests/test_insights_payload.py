from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from yino_platform_api.domain.call_record import CallRecord, TranscriptMessage
from yino_platform_api.domain.insights_dispatch import (
    build_ended_call_body,
    build_event_id,
    format_transcript,
    format_utc_ms,
)

CALL_ID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
ENDED_AT = datetime(2026, 8, 25, 3, 4, 12, tzinfo=UTC)
EXPECTED_EVENT_ID = hashlib.sha256(
    f"yino|demo-clinic|{CALL_ID}|2026-08-25T03:04:12.000Z".encode()
).hexdigest()


def test_format_utc_ms_uses_millisecond_zulu() -> None:
    value = datetime(2026, 8, 25, 3, 0, 0, 123456, tzinfo=UTC)
    assert format_utc_ms(value) == "2026-08-25T03:00:00.123Z"


def test_build_event_id_is_stable() -> None:
    assert build_event_id("demo-clinic", CALL_ID, ENDED_AT) == EXPECTED_EVENT_ID


def test_format_transcript_orders_by_sequence() -> None:
    messages = [
        TranscriptMessage(role="assistant", text="hi", sequence=2),
        TranscriptMessage(role="user", text="hello", sequence=1),
    ]
    assert format_transcript(messages) == "user: hello\nassistant: hi"


def test_build_ended_call_body_is_strict_yino_payload() -> None:
    record = CallRecord(
        id=CALL_ID,
        tenant_id=uuid4(),
        created_at=datetime(2026, 8, 25, 3, 0, 0, tzinfo=UTC),
        customer_service_id=uuid4(),
        room_name="room-1",
        status="completed",
        started_at=datetime(2026, 8, 25, 3, 0, 0, tzinfo=UTC),
        ended_at=ENDED_AT,
        duration_sec=252,
        messages=[
            TranscriptMessage(role="user", text="hello", sequence=1),
            TranscriptMessage(role="assistant", text="hi", sequence=2),
        ],
    )
    body = build_ended_call_body(profile="demo-clinic", record=record)
    assert body == {
        "schemaVersion": 1,
        "channel": "yino",
        "callId": str(CALL_ID),
        "eventId": EXPECTED_EVENT_ID,
        "startedAt": "2026-08-25T03:00:00.000Z",
        "endedAt": "2026-08-25T03:04:12.000Z",
        "durationSeconds": 252,
        "transcript": "user: hello\nassistant: hi",
        "summary": "",
        "recordingUrl": None,
    }


def test_duration_matches_serialized_utc_ms_not_stored_field() -> None:
    record = CallRecord(
        id=CALL_ID,
        tenant_id=uuid4(),
        created_at=datetime(2026, 8, 25, 3, 0, 0, tzinfo=UTC),
        customer_service_id=uuid4(),
        room_name="room-1",
        status="completed",
        started_at=datetime(2026, 8, 25, 3, 0, 0, 999, tzinfo=UTC),
        ended_at=datetime(2026, 8, 25, 3, 0, 1, 1, tzinfo=UTC),
        duration_sec=99,
        messages=[TranscriptMessage(role="user", text="hello", sequence=1)],
    )
    body = build_ended_call_body(profile="demo-clinic", record=record)
    assert body["startedAt"] == "2026-08-25T03:00:00.000Z"
    assert body["endedAt"] == "2026-08-25T03:00:01.000Z"
    assert body["durationSeconds"] == 1
