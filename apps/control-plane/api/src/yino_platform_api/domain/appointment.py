from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AppointmentStatus = Literal["pending", "confirmed", "cancelled"]
AppointmentSource = Literal["manual", "voice_tool", "import"]


class Appointment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    voice_agent_instance_id: UUID | None = None
    call_record_id: UUID | None = None
    patient_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=32)
    service: str = Field(min_length=1, max_length=120)
    slot_start: datetime
    slot_end: datetime
    status: AppointmentStatus = "pending"
    source: AppointmentSource = "manual"
    notes: str = ""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_slot_order(self) -> Appointment:
        if self.slot_end < self.slot_start:
            raise ValueError("slot_end must be >= slot_start")
        return self


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=32)
    service: str = Field(min_length=1, max_length=120)
    slot_start: datetime
    slot_end: datetime
    voice_agent_instance_id: UUID | None = None
    notes: str = Field(default="", max_length=2000)
    status: AppointmentStatus = "pending"

    @model_validator(mode="after")
    def validate_slot_order(self) -> AppointmentCreate:
        if self.slot_end < self.slot_start:
            raise ValueError("slot_end must be >= slot_start")
        return self


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = Field(default=None, min_length=1, max_length=80)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    service: str | None = Field(default=None, min_length=1, max_length=120)
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentPage(BaseModel):
    items: list[Appointment]
    total: int
