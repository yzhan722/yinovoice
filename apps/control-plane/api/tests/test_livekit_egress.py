from datetime import UTC, datetime
from uuid import UUID

import pytest

from yino_platform_api.domain.call_record import CallRecord
from yino_platform_api.services.livekit_egress import (
    FakeRecordingEgressSink,
    RecordingEgressService,
    recording_object_key,
    sink_from_settings,
)


def _record(*, direction: str = "inbound") -> CallRecord:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    record_id = UUID("00000000-0000-0000-0000-000000000201")
    return CallRecord(
        id=record_id,
        tenant_id=tenant_id,
        created_at=datetime(2026, 8, 25, 1, 0, tzinfo=UTC),
        customer_service_id=UUID("00000000-0000-0000-0000-000000000101"),
        room_name="sip-melbourne-1",
        status="in_progress",
        started_at=datetime(2026, 8, 25, 1, 0, tzinfo=UTC),
        direction=direction,  # type: ignore[arg-type]
        messages=[],
    )


def test_recording_object_key_uses_tenant_year_month_and_ogg() -> None:
    record = _record()
    assert recording_object_key(record) == (
        f"recordings/{record.tenant_id}/2026/08/{record.id}.ogg"
    )


@pytest.mark.asyncio
async def test_disabled_egress_does_not_change_record() -> None:
    service = RecordingEgressService(sink_from_settings(
        endpoint=None, bucket=None, access_key=None, secret_key=None
    ))
    record = _record()
    result = await service.start_for_inbound(record)
    assert result.recording_status == "none"
    assert result.recording_egress_id is None


@pytest.mark.asyncio
async def test_fake_egress_starts_for_inbound_only() -> None:
    sink = FakeRecordingEgressSink()
    service = RecordingEgressService(sink)
    inbound = await service.start_for_inbound(_record(direction="inbound"))
    web = await service.start_for_inbound(_record(direction="web"))
    assert inbound.recording_status == "uploading"
    assert inbound.recording_object_key.endswith(".ogg")
    assert inbound.recording_egress_id
    assert web.recording_egress_id is None
    assert sink.started[0][0] == "sip-melbourne-1"
