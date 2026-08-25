from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARATORS = re.compile(r"[\s\-()]")

PhoneNumberProvider = Literal["livekit_sip"]


def normalize_e164(value: str) -> str:
    compact = _SEPARATORS.sub("", value.strip())
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    if not E164_PATTERN.fullmatch(compact):
        raise ValueError("must be an E.164 number")
    return compact


class PhoneNumberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    e164_number: str
    voice_agent_instance_id: UUID
    inbound_trunk_id: str | None = None
    dispatch_rule_id: str | None = None
    enabled: bool = True
    provider: PhoneNumberProvider = "livekit_sip"

    @field_validator("e164_number")
    @classmethod
    def validate_e164(cls, value: str) -> str:
        return normalize_e164(value)


class PhoneNumberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    e164_number: str | None = None
    voice_agent_instance_id: UUID | None = None
    inbound_trunk_id: str | None = None
    dispatch_rule_id: str | None = None
    enabled: bool | None = None

    @field_validator("e164_number")
    @classmethod
    def validate_optional_e164(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_e164(value)


class PhoneNumber(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    voice_agent_instance_id: UUID
    e164_number: str
    provider: PhoneNumberProvider = "livekit_sip"
    inbound_trunk_id: str | None = None
    dispatch_rule_id: str | None = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class PhoneNumberView(PhoneNumber):
    config_version: int = Field(ge=1)


class PhoneNumberPage(BaseModel):
    items: list[PhoneNumberView]
    total: int
