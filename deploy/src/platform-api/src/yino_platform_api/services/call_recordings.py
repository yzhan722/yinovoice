from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from ..domain.call_record import CallRecord
from ..repositories.call_records import CallRecordRepository

ALLOWED_MIME_PREFIXES = ("audio/webm", "audio/ogg", "audio/mp4")

MIME_SUFFIX = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
}


class RecordingNotFoundError(Exception):
    pass


class RecordingBadRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class RecordingTooLargeError(Exception):
    pass


def _normalize_mime(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower()


def _suffix_for_mime(mime: str) -> str:
    for prefix, suffix in MIME_SUFFIX.items():
        if mime.startswith(prefix):
            return suffix
    raise RecordingBadRequestError("unsupported_mime", "Unsupported audio content type")


def _recording_path(base_dir: Path, tenant_id: UUID, record_id: UUID, suffix: str) -> Path:
    return base_dir / str(tenant_id) / f"{record_id}{suffix}"


async def _read_upload(upload: UploadFile, max_bytes: int) -> tuple[bytes, str]:
    mime = _normalize_mime(upload.content_type)
    if mime is None or not any(mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise RecordingBadRequestError("unsupported_mime", "Unsupported audio content type")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RecordingTooLargeError()
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise RecordingBadRequestError("empty_body", "Recording file must not be empty")
    return content, mime


async def save_recording(
    repo: CallRecordRepository,
    tenant_id: UUID,
    record_id: UUID,
    upload: UploadFile,
    *,
    base_dir: Path,
    max_bytes: int,
) -> CallRecord:
    record = await repo.get(record_id, tenant_id)
    if record is None:
        raise RecordingNotFoundError()

    try:
        content, mime = await _read_upload(upload, max_bytes)
        suffix = _suffix_for_mime(mime)
        destination = _recording_path(base_dir, tenant_id, record_id, suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

        updated = record.model_copy(
            update={
                "recording_status": "ready",
                "recording_mime_type": mime,
                "recording_size_bytes": len(content),
                "recording_failure_code": None,
            }
        )
        return await repo.save(updated)
    except (RecordingBadRequestError, RecordingTooLargeError) as exc:
        failure_code = "too_large" if isinstance(exc, RecordingTooLargeError) else exc.code
        failed = record.model_copy(
            update={
                "recording_status": "failed",
                "recording_failure_code": failure_code,
            }
        )
        await repo.save(failed)
        raise


async def open_recording(
    repo: CallRecordRepository,
    tenant_id: UUID,
    record_id: UUID,
    *,
    base_dir: Path,
) -> tuple[CallRecord, Path]:
    record = await repo.get(record_id, tenant_id)
    if record is None or record.recording_status != "ready":
        raise RecordingNotFoundError()

    mime = record.recording_mime_type
    if mime is None:
        raise RecordingNotFoundError()

    suffix = _suffix_for_mime(mime)
    path = _recording_path(base_dir, tenant_id, record_id, suffix)
    if not path.is_file():
        raise RecordingNotFoundError()

    return record, path
