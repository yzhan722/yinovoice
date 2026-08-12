"""Strictly load a published customer-service snapshot from Platform API."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx


class RuntimeConfigurationError(ValueError):
    """Raised when authoritative runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class DispatchMetadata:
    """Authoritative service identity included in the LiveKit dispatch."""

    customer_service_id: UUID
    tenant_id: UUID
    config_version: int

    @classmethod
    def from_json(cls, raw: str) -> DispatchMetadata:
        """Parse only the complete, authoritative dispatch metadata schema."""

        try:
            value = json.loads(raw, object_pairs_hook=_json_object_without_duplicates)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeConfigurationError(
                "Dispatch metadata must be valid JSON"
            ) from error

        data = _mapping_with_exact_keys(
            value,
            {"customer_service_id", "tenant_id", "config_version"},
            "Dispatch metadata",
        )
        return cls(
            customer_service_id=_uuid(
                data["customer_service_id"], "customer service ID"
            ),
            tenant_id=_uuid(data["tenant_id"], "tenant ID"),
            config_version=_positive_int(data["config_version"], "config version"),
        )


@dataclass(frozen=True, slots=True)
class RuntimeVoiceProfile:
    """Published voice settings, retained for later runtime application."""

    preset_id: str
    locale: str
    speaking_rate: float
    volume: float
    pitch: float
    style: str
    emotion: str
    pause_profile: str

    @classmethod
    def from_mapping(cls, value: object) -> RuntimeVoiceProfile:
        data = _mapping_with_exact_keys(
            value,
            {
                "preset_id",
                "locale",
                "speaking_rate",
                "volume",
                "pitch",
                "style",
                "emotion",
                "pause_profile",
            },
            "Voice profile",
        )
        return cls(
            preset_id=_allowed_string(
                data["preset_id"],
                "voice preset",
                {"mandarin-standard"},
            ),
            locale=_allowed_string(
                data["locale"],
                "voice locale",
                {"zh-CN"},
            ),
            speaking_rate=_bounded_number(
                data["speaking_rate"], "speaking rate", 0.5, 2.0
            ),
            volume=_bounded_number(data["volume"], "volume", 0.0, 1.0),
            pitch=_bounded_number(data["pitch"], "pitch", -1.0, 1.0),
            style=_allowed_string(
                data["style"],
                "voice style",
                {"professional-friendly"},
            ),
            emotion=_allowed_string(
                data["emotion"],
                "voice emotion",
                {"neutral"},
            ),
            pause_profile=_allowed_string(
                data["pause_profile"],
                "pause profile",
                {"receptionist"},
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeResponseProfile:
    """Published response settings, retained for later runtime application."""

    brevity: str
    max_spoken_sentences: int
    ask_one_question_at_a_time: bool

    @classmethod
    def from_mapping(cls, value: object) -> RuntimeResponseProfile:
        data = _mapping_with_exact_keys(
            value,
            {
                "brevity",
                "max_spoken_sentences",
                "ask_one_question_at_a_time",
            },
            "Response profile",
        )
        brevity = _str(data["brevity"], "response brevity")
        if brevity not in {"concise", "balanced", "detailed"}:
            raise RuntimeConfigurationError("Response brevity is invalid")
        ask_one_question = _bool(
            data["ask_one_question_at_a_time"], "ask-one-question flag"
        )
        if not ask_one_question:
            raise RuntimeConfigurationError(
                "Ask-one-question-at-a-time is a protected rule"
            )
        return cls(
            brevity=brevity,
            max_spoken_sentences=_bounded_int(
                data["max_spoken_sentences"], "max spoken sentences", 1, 6
            ),
            ask_one_question_at_a_time=True,
        )


@dataclass(frozen=True, slots=True)
class RuntimeCustomerService:
    """A tenant-scoped, versioned configuration snapshot from Platform API."""

    id: UUID
    tenant_id: UUID
    version: int
    display_name: str
    organization_name: str
    greeting: str
    tenant_prompt: str
    voice: RuntimeVoiceProfile
    response: RuntimeResponseProfile
    business_profile: str
    primary_language: str

    @classmethod
    def from_mapping(cls, value: object) -> RuntimeCustomerService:
        data = _mapping_with_exact_keys(
            value,
            {
                "id",
                "tenant_id",
                "version",
                "display_name",
                "organization_name",
                "greeting",
                "tenant_prompt",
                "voice",
                "response",
                "business_profile",
                "primary_language",
            },
            "Customer service snapshot",
        )
        return cls(
            id=_uuid(data["id"], "snapshot customer service ID"),
            tenant_id=_uuid(data["tenant_id"], "snapshot tenant ID"),
            version=_positive_int(data["version"], "snapshot version"),
            display_name=_single_line_str(data["display_name"], "display name"),
            organization_name=_single_line_str(
                data["organization_name"], "organization name"
            ),
            greeting=_safe_greeting(data["greeting"]),
            tenant_prompt=_str(data["tenant_prompt"], "tenant prompt"),
            voice=RuntimeVoiceProfile.from_mapping(data["voice"]),
            response=RuntimeResponseProfile.from_mapping(data["response"]),
            business_profile=_allowed_string(
                data["business_profile"],
                "business profile",
                {"generic-receptionist"},
            ),
            primary_language=_allowed_string(
                data["primary_language"],
                "primary language",
                {"zh-CN"},
            ),
        )


class PlatformConfigClient:
    """Fetch published customer-service snapshots through the Platform boundary."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def get(self, metadata: DispatchMetadata) -> RuntimeCustomerService:
        """Fetch and prove a snapshot belongs to the dispatched service/version."""

        response = await self._http_client.get(
            f"/api/v1/customer-services/{metadata.customer_service_id}",
            headers={"X-Tenant-ID": str(metadata.tenant_id)},
            timeout=5.0,
        )
        response.raise_for_status()
        try:
            payload: Any = json.loads(
                response.content,
                object_pairs_hook=_json_object_without_duplicates,
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeConfigurationError(
                "Platform returned an invalid customer service snapshot"
            ) from error

        snapshot = RuntimeCustomerService.from_mapping(payload)
        if snapshot.id != metadata.customer_service_id:
            raise RuntimeConfigurationError(
                "Platform snapshot customer service ID does not match dispatch metadata"
            )
        if snapshot.tenant_id != metadata.tenant_id:
            raise RuntimeConfigurationError(
                "Platform snapshot tenant ID does not match dispatch metadata"
            )
        if snapshot.version != metadata.config_version:
            raise RuntimeConfigurationError(
                "Platform snapshot version does not match dispatch metadata"
            )
        return snapshot


def _mapping_with_exact_keys(
    value: object,
    expected_keys: set[str],
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise RuntimeConfigurationError(
            f"{name} must contain exactly the expected keys"
        )
    return value


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise json.JSONDecodeError("Duplicate object key", key, 0)
        result[key] = value
    return result


def _uuid(value: object, name: str) -> UUID:
    if not isinstance(value, str):
        raise RuntimeConfigurationError(f"{name} must be a UUID")
    try:
        return UUID(value)
    except ValueError as error:
        raise RuntimeConfigurationError(f"{name} must be a UUID") from error


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeConfigurationError(f"{name} must be a positive integer")
    return value


def _bounded_int(value: object, name: str, minimum: int, maximum: int) -> int:
    value = _positive_int(value, name)
    if value < minimum or value > maximum:
        raise RuntimeConfigurationError(f"{name} is outside its allowed range")
    return value


def _bounded_number(
    value: object,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RuntimeConfigurationError(f"{name} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise RuntimeConfigurationError(f"{name} is outside its allowed range")
    return result


def _str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise RuntimeConfigurationError(f"{name} must be a string")
    return value


def _nonempty_str(value: object, name: str) -> str:
    result = _str(value, name)
    if not result:
        raise RuntimeConfigurationError(f"{name} must not be empty")
    return result


def _single_line_str(value: object, name: str) -> str:
    result = _nonempty_str(value, name).strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in result):
        raise RuntimeConfigurationError(f"{name} contains invalid control characters")
    return result


def _allowed_string(
    value: object,
    name: str,
    allowed: set[str],
) -> str:
    result = _str(value, name)
    if result not in allowed:
        raise RuntimeConfigurationError(f"{name} is not an allowed business option")
    return result


_GREETING_DISCLOSURE_OVERRIDE = re.compile(
    r"(?:(?<![A-Za-z])AI(?![A-Za-z])|人工|真人|机器人|大模型|语音模型)",
    re.IGNORECASE,
)


def _safe_greeting(value: object) -> str:
    result = _single_line_str(value, "greeting")
    if _GREETING_DISCLOSURE_OVERRIDE.search(result):
        raise RuntimeConfigurationError(
            "greeting must not make proactive AI or human identity claims"
        )
    return result


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeConfigurationError(f"{name} must be a boolean")
    return value
