from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from yino_platform_api.domain.call_record import (
    CallRecord,
    CallRecordCreate,
    TranscriptMessage,
)
from yino_platform_api.repositories.call_records import (
    InMemoryCallRecordRepository,
)


def valid_request_values() -> dict[str, object]:
    return {
        "customer_service_id": uuid4(),
        "room_name": "yino-demo-room-1",
        "status": "completed",
        "started_at": "2026-08-03T01:00:00Z",
        "ended_at": "2026-08-03T01:00:12Z",
        "duration_sec": 12,
        "messages": [
            {"role": "user", "text": "你好", "sequence": 1},
            {"role": "assistant", "text": "您好", "sequence": 2},
        ],
    }


def test_call_record_create_accepts_only_bounded_final_demo_data() -> None:
    request = CallRecordCreate.model_validate(valid_request_values())

    assert request.direction == "web"
    assert request.status == "completed"
    assert request.messages[1].text == "您好"
    assert request.started_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("room_name", ""),
        ("room_name", "r" * 129),
        ("duration_sec", -1),
        ("duration_sec", 86_401),
        ("status", "connected"),
        ("direction", "phone"),
    ],
)
def test_call_record_create_rejects_out_of_contract_fields(
    field: str, value: object
) -> None:
    values = {**valid_request_values(), field: value}

    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)


@pytest.mark.parametrize(
    "timestamps",
    [
        {
            "started_at": "2026-08-03T01:00:12Z",
            "ended_at": "2026-08-03T01:00:00Z",
        },
        {
            "started_at": "2026-08-03T09:00:00+08:00",
            "ended_at": "2026-08-03T09:00:12+08:00",
        },
        {
            "started_at": "2026-08-03T01:00:00",
            "ended_at": "2026-08-03T01:00:12",
        },
    ],
)
def test_call_record_create_requires_ordered_utc_timestamps(
    timestamps: dict[str, str],
) -> None:
    values = {**valid_request_values(), **timestamps}

    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "system", "text": "hidden", "sequence": 1}],
        [{"role": "user", "text": "x" * 4_001, "sequence": 1}],
        [
            {"role": "user", "text": "first", "sequence": 1},
            {"role": "assistant", "text": "duplicate", "sequence": 1},
        ],
        [
            {"role": "user", "text": "later", "sequence": 2},
            {"role": "assistant", "text": "earlier", "sequence": 1},
        ],
        [
            {"role": "user", "text": "message", "sequence": sequence}
            for sequence in range(201)
        ],
    ],
)
def test_call_record_create_rejects_unsafe_transcript_messages(
    messages: list[dict[str, object]],
) -> None:
    values = {**valid_request_values(), "messages": messages}

    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)


@pytest.mark.parametrize(
    "values",
    [
        {**valid_request_values(), "provider_payload": "secret"},
        {
            **valid_request_values(),
            "messages": [
                {
                    "role": "user",
                    "text": "你好",
                    "sequence": 1,
                    "raw_delta": "secret",
                }
            ],
        },
    ],
)
def test_call_record_create_forbids_unknown_fields(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)


@pytest.mark.asyncio
async def test_repository_lists_newest_first_with_tenant_pagination() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    service_id = uuid4()
    base_time = datetime(2026, 8, 3, tzinfo=UTC)
    repository = InMemoryCallRecordRepository()
    older = CallRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        customer_service_id=service_id,
        room_name="older-room",
        status="completed",
        started_at=base_time,
        ended_at=base_time + timedelta(seconds=2),
        duration_sec=2,
        messages=[TranscriptMessage(role="user", text="一", sequence=1)],
        created_at=base_time,
    )
    newer = older.model_copy(
        update={
            "id": uuid4(),
            "room_name": "newer-room",
            "created_at": base_time + timedelta(minutes=1),
        }
    )

    await repository.save(older)
    await repository.save(newer)

    page, total = await repository.list_for_tenant(tenant_id, limit=1, offset=0)
    assert page == [newer]
    assert total == 2
    assert await repository.get(newer.id, other_tenant_id) is None


@pytest.mark.asyncio
async def test_repository_copy_boundaries_prevent_caller_mutation() -> None:
    tenant_id = uuid4()
    service_id = uuid4()
    record_id = uuid4()
    timestamp = datetime(2026, 8, 3, tzinfo=UTC)
    repository = InMemoryCallRecordRepository()
    source = CallRecord(
        id=record_id,
        tenant_id=tenant_id,
        customer_service_id=service_id,
        room_name="immutable-room",
        status="completed",
        started_at=timestamp,
        ended_at=timestamp + timedelta(seconds=2),
        duration_sec=2,
        messages=[TranscriptMessage(role="user", text="original", sequence=1)],
        created_at=timestamp,
    )

    saved = await repository.save(source)
    source.room_name = "mutated-source"
    source.messages[0].text = "mutated-source-message"
    saved.messages[0].text = "mutated-save-result"

    fetched = await repository.get(record_id, tenant_id)
    assert fetched is not None
    assert fetched.room_name == "immutable-room"
    assert fetched.messages[0].text == "original"

    fetched.messages[0].text = "mutated-get-result"
    listed, total = await repository.list_for_tenant(
        tenant_id,
        limit=10,
        offset=0,
    )
    assert total == 1
    assert listed[0].messages[0].text == "original"


def test_in_progress_call_record_allows_open_lifecycle_fields() -> None:
    started = datetime(2026, 8, 24, 1, 0, tzinfo=UTC)
    record = CallRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        customer_service_id=uuid4(),
        room_name="sip-melbourne-1",
        status="in_progress",
        started_at=started,
        direction="inbound",
        caller_number="+61 400 000 001",
        callee_number="+61400000099",
        provider_call_id="livekit-sip-abc",
        messages=[],
        created_at=started,
    )

    assert record.ended_at is None
    assert record.duration_sec is None
    assert record.ended_reason is None
    assert record.caller_number == "+61400000001"
    assert record.callee_number == "+61400000099"
    assert record.direction == "inbound"


def test_call_record_create_rejects_in_progress_one_shot_hangup() -> None:
    values = {**valid_request_values(), "status": "in_progress"}
    del values["ended_at"]
    del values["duration_sec"]

    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)


def test_completed_call_record_still_requires_end_fields() -> None:
    started = datetime(2026, 8, 24, 1, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CallRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            customer_service_id=uuid4(),
            room_name="web-room",
            status="completed",
            started_at=started,
            created_at=started,
        )


def test_sip_inbound_direction_alias_is_rejected() -> None:
    values = {**valid_request_values(), "direction": "sip_inbound"}
    with pytest.raises(ValidationError):
        CallRecordCreate.model_validate(values)
