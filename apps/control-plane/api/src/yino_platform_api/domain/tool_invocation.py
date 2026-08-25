from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ToolName = Literal["check_availability", "create_appointment", "create_callback"]
ToolStatus = Literal["ok", "error", "skipped"]


class ToolInvocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    call_record_id: UUID | None = None
    voice_agent_instance_id: UUID | None = None
    tool_name: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)

    @field_validator("session_id")
    @classmethod
    def strip_session_id(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("session_id must not be blank")
        return result

    @field_validator("idempotency_key")
    @classmethod
    def strip_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        return result or None


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    session_id: str
    call_record_id: UUID | None = None
    voice_agent_instance_id: UUID | None = None
    tool_name: ToolName
    arguments: dict[str, Any]
    status: ToolStatus
    result: dict[str, Any]
    idempotency_key: str
    created_at: datetime


class ToolInvocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_id: UUID
    status: ToolStatus
    tool_name: ToolName
    result: dict[str, Any]
