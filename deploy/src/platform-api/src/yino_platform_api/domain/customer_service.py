from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

VoicePresetId = Literal["mandarin-standard"]
VoiceLocale = Literal["zh-CN"]
VoiceStyle = Literal["professional-friendly"]
VoiceEmotion = Literal["neutral"]
VoicePauseProfile = Literal["receptionist"]

_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_GREETING_DISCLOSURE_OVERRIDE = re.compile(
    r"(?:(?<![A-Za-z])AI(?![A-Za-z])|人工|真人|机器人|大模型|语音模型)",
    re.IGNORECASE,
)


def _clean_single_line(value: str) -> str:
    result = value.strip()
    if _CONTROL_CHARACTER.search(result):
        raise ValueError("must not contain control characters")
    return result


def _validate_greeting(value: str) -> str:
    result = _clean_single_line(value)
    if _GREETING_DISCLOSURE_OVERRIDE.search(result):
        raise ValueError("must not make proactive AI or human identity claims")
    return result


class VoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: VoicePresetId = "mandarin-standard"
    locale: VoiceLocale = "zh-CN"
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    pitch: float = Field(default=0.0, ge=-1.0, le=1.0)
    style: VoiceStyle = "professional-friendly"
    emotion: VoiceEmotion = "neutral"
    pause_profile: VoicePauseProfile = "receptionist"


class ResponseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brevity: Literal["concise", "balanced", "detailed"] = "concise"
    max_spoken_sentences: int = Field(default=3, ge=1, le=6)
    ask_one_question_at_a_time: Literal[True] = True


class CustomerServiceInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    version: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=120)
    business_profile: str = "generic-receptionist"
    primary_language: str = "zh-CN"
    greeting: str
    tenant_prompt: str = ""
    voice: VoiceProfile
    response: ResponseProfile

    @field_validator("display_name", "organization_name")
    @classmethod
    def validate_single_line_tenant_text(cls, value: str) -> str:
        return _clean_single_line(value)

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, value: str) -> str:
        return _validate_greeting(value)

    @classmethod
    def demo(
        cls,
        *,
        instance_id: UUID,
        tenant_id: UUID,
    ) -> CustomerServiceInstance:
        return cls(
            id=instance_id,
            tenant_id=tenant_id,
            version=1,
            display_name="演示 AI 语音客服",
            organization_name="Yino 演示机构",
            greeting="您好，这里是Yino演示机构客服，请问有什么可以帮您？",
            voice=VoiceProfile(preset_id="mandarin-standard"),
            response=ResponseProfile(),
        )


class CustomerServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=120)
    greeting: str = Field(min_length=1, max_length=300)
    tenant_prompt: str = Field(default="", max_length=8000)
    voice: VoiceProfile
    response: ResponseProfile

    @field_validator("display_name", "organization_name")
    @classmethod
    def validate_single_line_tenant_text(cls, value: str) -> str:
        return _clean_single_line(value)

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, value: str) -> str:
        return _validate_greeting(value)


DEMO_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_CUSTOMER_SERVICE_ID = UUID("00000000-0000-0000-0000-000000000101")
