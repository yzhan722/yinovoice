from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CallbackStatus = Literal["open", "done", "cancelled"]
CallbackSource = Literal["manual", "voice_tool", "from_call"]


class CallbackTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    voice_agent_instance_id: UUID | None = None
    call_record_id: UUID | None = None
    caller_phone: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=1, max_length=200)
    summary: str = ""
    status: CallbackStatus = "open"
    source: CallbackSource = "manual"
    created_at: datetime
    updated_at: datetime


class CallbackTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller_phone: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    voice_agent_instance_id: UUID | None = None


class CallbackTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller_phone: str | None = Field(default=None, min_length=1, max_length=32)
    reason: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    status: CallbackStatus | None = None


class CallbackTaskPage(BaseModel):
    items: list[CallbackTask]
    total: int
