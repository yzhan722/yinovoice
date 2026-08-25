from __future__ import annotations

from uuid import uuid4

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


def sink_from_settings(
    *,
    endpoint: str | None,
    bucket: str | None,
    access_key: str | None,
    secret_key: str | None,
) -> RecordingEgressSink | None:
    values = [endpoint, bucket, access_key, secret_key]
    if not any(values):
        return None
    if not all(item and item.strip() for item in values):
        return None
    return FakeRecordingEgressSink()
