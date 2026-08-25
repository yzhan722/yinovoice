from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal[0, 1, 2, 3, 4, 5, 6]


def parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("time must be HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("time must be HH:MM")
    return time(hour, minute)


def validate_iana_timezone(value: str) -> str:
    name = value.strip()
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("timezone must be a valid IANA name") from error
    return name


class ServiceOfferingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_agent_instance_id: UUID
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    duration_minutes: int = Field(ge=5, le=480)
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    enabled: bool = True


class ServiceOfferingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    buffer_minutes: int | None = Field(default=None, ge=0, le=120)
    enabled: bool | None = None


class ServiceOffering(ServiceOfferingCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class SchedulingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    voice_agent_instance_id: UUID
    timezone: str
    slot_interval_minutes: int = Field(default=15, ge=5, le=60)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=10_080)
    booking_horizon_days: int = Field(default=60, ge=1, le=365)
    updated_at: datetime

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return validate_iana_timezone(value)


class SchedulingProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str
    slot_interval_minutes: int = Field(default=15, ge=5, le=60)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=10_080)
    booking_horizon_days: int = Field(default=60, ge=1, le=365)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return validate_iana_timezone(value)


class BusinessHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    voice_agent_instance_id: UUID
    weekday: int = Field(ge=0, le=6)
    start_local: str
    end_local: str
    enabled: bool = True

    @field_validator("start_local", "end_local")
    @classmethod
    def validate_hhmm(cls, value: str) -> str:
        parsed = parse_hhmm(value)
        return f"{parsed.hour:02d}:{parsed.minute:02d}"

    @model_validator(mode="after")
    def validate_window(self) -> BusinessHours:
        if parse_hhmm(self.end_local) <= parse_hhmm(self.start_local):
            raise ValueError("end_local must be after start_local")
        return self


class BusinessHoursWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    start_local: str
    end_local: str
    enabled: bool = True

    @field_validator("start_local", "end_local")
    @classmethod
    def validate_hhmm(cls, value: str) -> str:
        parsed = parse_hhmm(value)
        return f"{parsed.hour:02d}:{parsed.minute:02d}"

    @model_validator(mode="after")
    def validate_window(self) -> BusinessHoursWrite:
        if parse_hhmm(self.end_local) <= parse_hhmm(self.start_local):
            raise ValueError("end_local must be after start_local")
        return self


class ScheduleExceptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_agent_instance_id: UUID
    date_local: date
    closed: bool = True
    start_local: str | None = None
    end_local: str | None = None
    reason: str = Field(default="", max_length=200)

    @field_validator("start_local", "end_local")
    @classmethod
    def validate_optional_hhmm(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = parse_hhmm(value)
        return f"{parsed.hour:02d}:{parsed.minute:02d}"

    @model_validator(mode="after")
    def validate_open_window(self) -> ScheduleExceptionCreate:
        if self.closed:
            return self
        if self.start_local is None or self.end_local is None:
            raise ValueError("open exceptions require start_local and end_local")
        if parse_hhmm(self.end_local) <= parse_hhmm(self.start_local):
            raise ValueError("end_local must be after start_local")
        return self


class ScheduleException(ScheduleExceptionCreate):
    id: UUID
    tenant_id: UUID


class AvailabilitySlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_start_utc: datetime
    slot_end_utc: datetime
    slot_start_local: datetime
    slot_end_local: datetime
    timezone: str
    service_offering_id: UUID


class AvailabilityPage(BaseModel):
    items: list[AvailabilitySlot]
    total: int
