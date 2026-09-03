from __future__ import annotations

from uuid import uuid4

from livekit import api

from ..domain.call_record import CallRecord


def recording_object_key(record: CallRecord) -> str:
    stamp = record.started_at
    return (
        f"recordings/{record.tenant_id}/{stamp.year:04d}/"
        f"{stamp.month:02d}/{record.id}.ogg"
    )


class RecordingEgressSink:
    async def start_room_file(
        self,
        *,
        room_name: str,
        object_key: str,
    ) -> str:
        raise NotImplementedError


class DisabledRecordingEgressSink(RecordingEgressSink):
    async def start_room_file(
        self,
        *,
        room_name: str,
        object_key: str,
    ) -> str:
        raise RuntimeError("recording egress is disabled")


class FakeRecordingEgressSink(RecordingEgressSink):
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []

    async def start_room_file(
        self,
        *,
        room_name: str,
        object_key: str,
    ) -> str:
        self.started.append((room_name, object_key))
        return f"fake-egress-{uuid4()}"


class LiveKitRecordingEgressSink(RecordingEgressSink):
    """Start LiveKit RoomComposite audio egress into S3-compatible storage."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        api_secret: str,
        s3_endpoint: str,
        s3_bucket: str,
        s3_access_key: str,
        s3_secret_key: str,
        s3_region: str = "us-east-1",
        force_path_style: bool = True,
    ) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._s3_endpoint = s3_endpoint
        self._s3_bucket = s3_bucket
        self._s3_access_key = s3_access_key
        self._s3_secret_key = s3_secret_key
        self._s3_region = s3_region
        self._force_path_style = force_path_style

    def build_request(
        self, *, room_name: str, object_key: str
    ) -> api.RoomCompositeEgressRequest:
        return api.RoomCompositeEgressRequest(
            room_name=room_name,
            audio_only=True,
            file_outputs=[
                api.EncodedFileOutput(
                    file_type=api.EncodedFileType.OGG,
                    filepath=object_key,
                    s3=api.S3Upload(
                        access_key=self._s3_access_key,
                        secret=self._s3_secret_key,
                        endpoint=self._s3_endpoint,
                        bucket=self._s3_bucket,
                        region=self._s3_region,
                        force_path_style=self._force_path_style,
                    ),
                )
            ],
        )

    async def start_room_file(
        self,
        *,
        room_name: str,
        object_key: str,
    ) -> str:
        request = self.build_request(room_name=room_name, object_key=object_key)
        async with api.LiveKitAPI(
            url=self._api_url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        ) as livekit:
            info = await livekit.egress.start_room_composite_egress(request)
        egress_id = getattr(info, "egress_id", None)
        if not isinstance(egress_id, str) or not egress_id.strip():
            raise RuntimeError("livekit egress did not return egress_id")
        return egress_id.strip()


class RecordingEgressService:
    def __init__(self, sink: RecordingEgressSink | None) -> None:
        self._sink = sink

    @property
    def enabled(self) -> bool:
        return self._sink is not None and not isinstance(
            self._sink, DisabledRecordingEgressSink
        )

    async def start_for_inbound(self, record: CallRecord) -> CallRecord:
        if not self.enabled or record.direction != "inbound":
            return record
        if record.recording_egress_id:
            return record
        assert self._sink is not None
        key = recording_object_key(record)
        try:
            egress_id = await self._sink.start_room_file(
                room_name=record.room_name,
                object_key=key,
            )
        except Exception:
            return record.model_copy(
                update={
                    "recording_status": "failed",
                    "recording_failure_code": "egress_start_failed",
                }
            )
        return record.model_copy(
            update={
                "recording_egress_id": egress_id,
                "recording_object_key": key,
                "recording_status": "uploading",
                "recording_mime_type": "audio/ogg",
            }
        )


def _present(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def sink_from_settings(
    *,
    endpoint: str | None,
    bucket: str | None,
    access_key: str | None,
    secret_key: str | None,
    livekit_api_url: str | None = None,
    livekit_api_key: str | None = None,
    livekit_api_secret: str | None = None,
    region: str | None = None,
) -> RecordingEgressSink | None:
    s3_values = [endpoint, bucket, access_key, secret_key]
    if not any(s3_values):
        return None
    resolved_s3 = [_present(item) for item in s3_values]
    if not all(resolved_s3):
        return None
    livekit_values = [
        _present(livekit_api_url),
        _present(livekit_api_key),
        _present(livekit_api_secret),
    ]
    if not all(livekit_values):
        return None
    s3_endpoint, s3_bucket, s3_access_key, s3_secret_key = resolved_s3
    api_url, api_key, api_secret = livekit_values
    return LiveKitRecordingEgressSink(
        api_url=api_url,
        api_key=api_key,
        api_secret=api_secret,
        s3_endpoint=s3_endpoint,
        s3_bucket=s3_bucket,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key,
        s3_region=_present(region) or "us-east-1",
    )
