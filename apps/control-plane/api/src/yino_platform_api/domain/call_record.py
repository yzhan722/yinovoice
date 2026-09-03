from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .phone_number import normalize_e164

EndedCallRecordStatus = Literal["completed", "interrupted", "failed"]
CallRecordStatus = Literal["in_progress", EndedCallRecordStatus]
CallDirection = Literal["web", "inbound", "outbound"]
EndedReason = Literal["completed", "user_hangup", "agent_error"]
RecordingStatus = Literal["none", "uploading", "ready", "failed"]
TranscriptRole = Literal["user", "assistant"]


def _require_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include UTC timezone")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must use UTC timezone")
    return value.astimezone(UTC)


def _optional_e164(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return normalize_e164(stripped)


def _optional_token(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > 128:
        raise ValueError(f"{field_name} is too long")
    return stripped


class TranscriptMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: TranscriptRole
    text: str = Field(min_length=1, max_length=4_000)
    sequence: int = Field(ge=0, le=1_000_000)

    @field_validator("text")
    @classmethod
    def strip_nonempty_text(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("transcript text must not be blank")
        return result


class CallRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_service_id: UUID
    room_name: str = Field(min_length=1, max_length=128)
    status: CallRecordStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_sec: int | None = Field(default=None, ge=0, le=86_400)
    direction: CallDirection = "web"
    caller_number: str | None = None
    callee_number: str | None = None
    provider_call_id: str | None = None
    connected_at: datetime | None = None
    ended_reason: EndedReason | None = None
    messages: list[TranscriptMessage] = Field(default_factory=list, max_length=200)

    @field_validator("room_name")
    @classmethod
    def strip_room_name(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("room name must not be blank")
        return result

    @field_validator("started_at", "ended_at", "connected_at")
    @classmethod
    def require_utc(
        cls, value: datetime | None, info: object
    ) -> datetime | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "timestamp")
        return _require_utc(value, field_name=str(field_name))

    @field_validator("caller_number", "callee_number")
    @classmethod
    def normalize_optional_e164(cls, value: str | None) -> str | None:
        return _optional_e164(value)

    @field_validator("provider_call_id")
    @classmethod
    def normalize_provider_call_id(cls, value: str | None) -> str | None:
        return _optional_token(value, field_name="provider_call_id")

    @model_validator(mode="after")
    def validate_ordering(self) -> CallRecordData:
        if self.status == "in_progress":
            if self.ended_at is not None or self.duration_sec is not None:
                raise ValueError(
                    "in-progress call must not include ended_at or duration_sec"
                )
            if self.ended_reason is not None:
                raise ValueError("in-progress call must not include ended_reason")
        else:
            if self.ended_at is None or self.duration_sec is None:
                raise ValueError("ended call requires ended_at and duration_sec")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at must not be before started_at")
        sequences = [message.sequence for message in self.messages]
        if any(
            current <= previous
            for previous, current in pairwise(sequences)
        ):
            raise ValueError("message sequence must be unique and strictly increasing")
        return self


class CallRecordCreate(CallRecordData):
    status: EndedCallRecordStatus
    ended_at: datetime
    duration_sec: int = Field(ge=0, le=86_400)


class CallRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EndedCallRecordStatus
    messages: list[TranscriptMessage] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_message_sequences(self) -> CallRecordUpdate:
        if self.messages is None:
            return self
        sequences = [message.sequence for message in self.messages]
        if any(
            current <= previous
            for previous, current in pairwise(sequences)
        ):
            raise ValueError("message sequence must be unique and strictly increasing")
        return self


class CallUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_audio_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    input_text_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    output_audio_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    output_text_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    input_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    output_tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    total_tokens: int = Field(default=0, ge=0, le=2_000_000_000)
    response_count: int = Field(default=0, ge=0, le=100_000)


class CallRecord(CallRecordData):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    recording_status: RecordingStatus = "none"
    recording_mime_type: str | None = None
    recording_size_bytes: int | None = Field(default=None, ge=0)
    recording_failure_code: str | None = None
    recording_egress_id: str | None = None
    recording_object_key: str | None = None
    usage: CallUsage | None = None
    deleted_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def require_created_at_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, field_name="created_at")

    @field_validator("deleted_at")
    @classmethod
    def require_deleted_at_utc(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value, field_name="deleted_at")


class CallRecordPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CallRecord]
    total: int = Field(ge=0)


class CallSessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_service_id: UUID
    room_name: str = Field(min_length=1, max_length=128)
    direction: Literal["web", "inbound"] = "inbound"
    caller_number: str | None = None
    callee_number: str | None = None
    provider_call_id: str | None = None
    started_at: datetime | None = None
    connected_at: datetime | None = None

    @field_validator("room_name")
    @classmethod
    def strip_room_name(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("room name must not be blank")
        return result

    @field_validator("caller_number", "callee_number")
    @classmethod
    def normalize_optional_e164(cls, value: str | None) -> str | None:
        return _optional_e164(value)

    @field_validator("provider_call_id")
    @classmethod
    def normalize_provider_call_id(cls, value: str | None) -> str | None:
        return _optional_token(value, field_name="provider_call_id")

    @field_validator("started_at", "connected_at")
    @classmethod
    def require_session_timestamps_utc(
        cls, value: datetime | None, info: object
    ) -> datetime | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "timestamp")
        return _require_utc(value, field_name=str(field_name))


class CallSessionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: TranscriptRole
    text: str = Field(min_length=1, max_length=4_000)
    sequence: int = Field(ge=0, le=1_000_000)

    @field_validator("text")
    @classmethod
    def strip_nonempty_text(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("transcript text must not be blank")
        return result


class CallSessionFinish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EndedCallRecordStatus = "completed"
    ended_reason: EndedReason = "completed"
    ended_at: datetime | None = None
    usage: CallUsage | None = None

    @field_validator("ended_at")
    @classmethod
    def require_ended_at_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value, field_name="ended_at")
