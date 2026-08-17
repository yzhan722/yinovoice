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

CallRecordStatus = Literal["completed", "interrupted", "failed"]
RecordingStatus = Literal["none", "uploading", "ready", "failed"]
TranscriptRole = Literal["user", "assistant"]


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
    ended_at: datetime
    duration_sec: int = Field(ge=0, le=86_400)
    direction: Literal["web"] = "web"
    messages: list[TranscriptMessage] = Field(default_factory=list, max_length=200)

    @field_validator("room_name")
    @classmethod
    def strip_room_name(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("room name must not be blank")
        return result

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("timestamp must use UTC timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_ordering(self) -> CallRecordData:
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
    pass


class CallRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CallRecordStatus
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


class CallRecord(CallRecordData):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    recording_status: RecordingStatus = "none"
    recording_mime_type: str | None = None
    recording_size_bytes: int | None = Field(default=None, ge=0)
    recording_failure_code: str | None = None
    deleted_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def require_created_at_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("created_at must use UTC timezone")
        return value.astimezone(UTC)

    @field_validator("deleted_at")
    @classmethod
    def require_deleted_at_utc(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deleted_at must include UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("deleted_at must use UTC timezone")
        return value.astimezone(UTC)


class CallRecordPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CallRecord]
    total: int = Field(ge=0)
