from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from livekit import api

from yino_platform_api.domain.call_record import CallRecord
from yino_platform_api.services.livekit_egress import (
    FakeRecordingEgressSink,
    LiveKitRecordingEgressSink,
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


def test_sink_from_settings_requires_s3_and_livekit() -> None:
    s3 = {
        "endpoint": "https://s3.example.test",
        "bucket": "yino-recordings",
        "access_key": "access-placeholder",
        "secret_key": "secret-placeholder",
    }
    assert sink_from_settings(**s3) is None
    sink = sink_from_settings(
        **s3,
        livekit_api_url="http://localhost:7880",
        livekit_api_key="devkey",
        livekit_api_secret="secret",
        region="oss-cn-hangzhou",
    )
    assert isinstance(sink, LiveKitRecordingEgressSink)


def test_livekit_sink_builds_audio_ogg_s3_request() -> None:
    sink = LiveKitRecordingEgressSink(
        api_url="http://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        s3_endpoint="https://s3.example.test",
        s3_bucket="yino-recordings",
        s3_access_key="access-placeholder",
        s3_secret_key="secret-placeholder",
        s3_region="us-east-1",
    )
    request = sink.build_request(
        room_name="sip-melbourne-1",
        object_key="recordings/tenant/2026/08/id.ogg",
    )
    assert request.room_name == "sip-melbourne-1"
    assert request.audio_only is True
    assert len(request.file_outputs) == 1
    output = request.file_outputs[0]
    assert output.file_type == api.EncodedFileType.OGG
    assert output.filepath == "recordings/tenant/2026/08/id.ogg"
    assert output.s3.bucket == "yino-recordings"
    assert output.s3.endpoint == "https://s3.example.test"
    assert output.s3.force_path_style is True


@pytest.mark.asyncio
async def test_livekit_sink_returns_egress_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[api.RoomCompositeEgressRequest] = []

    class FakeEgressService:
        async def start_room_composite_egress(
            self, request: api.RoomCompositeEgressRequest
        ) -> SimpleNamespace:
            requests.append(request)
            return SimpleNamespace(egress_id="EG_test_1")

    class FakeLiveKitAPI:
        egress = FakeEgressService()

        async def __aenter__(self) -> "FakeLiveKitAPI":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        "yino_platform_api.services.livekit_egress.api.LiveKitAPI",
        lambda **_kwargs: FakeLiveKitAPI(),
    )
    sink = LiveKitRecordingEgressSink(
        api_url="http://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        s3_endpoint="https://s3.example.test",
        s3_bucket="yino-recordings",
        s3_access_key="access-placeholder",
        s3_secret_key="secret-placeholder",
    )
    egress_id = await sink.start_room_file(
        room_name="sip-melbourne-1",
        object_key="recordings/t/2026/08/id.ogg",
    )
    assert egress_id == "EG_test_1"
    assert requests[0].room_name == "sip-melbourne-1"
