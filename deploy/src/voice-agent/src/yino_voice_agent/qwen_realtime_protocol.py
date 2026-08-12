from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass


class QwenProtocolError(ValueError):
    """Raised for malformed Qwen events without exposing raw payloads."""


@dataclass(frozen=True, slots=True)
class QwenSessionOptions:
    instructions: str
    voice: str


def build_session_update(options: QwenSessionOptions) -> dict[str, object]:
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": options.voice,
            "instructions": options.instructions,
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "turn_detection": {"type": "smart_turn"},
        },
    }


def build_instructions_update(instructions: str) -> dict[str, object]:
    return {
        "type": "session.update",
        "session": {"instructions": instructions},
    }


def build_audio_append(pcm: bytes) -> dict[str, object]:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm).decode("ascii"),
    }


def build_response_create() -> dict[str, object]:
    return {
        "type": "response.create",
        "response": {"modalities": ["audio", "text"]},
    }


def build_user_text_item(text: str) -> dict[str, object]:
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def build_response_cancel() -> dict[str, object]:
    return {"type": "response.cancel"}


def parse_server_event(raw: str) -> Mapping[str, object]:
    invalid_json = False
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        invalid_json = True
        value = None
    if invalid_json:
        raise QwenProtocolError("invalid Qwen event JSON")
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise QwenProtocolError("invalid Qwen event envelope")
    return value


def decode_audio_delta(event: Mapping[str, object]) -> bytes:
    delta = event.get("delta")
    if not isinstance(delta, str):
        raise QwenProtocolError("invalid Qwen audio delta")
    try:
        pcm = base64.b64decode(delta, validate=True)
    except (binascii.Error, ValueError) as error:
        raise QwenProtocolError("invalid Qwen audio delta") from error
    if not pcm or len(pcm) % 2:
        raise QwenProtocolError("invalid Qwen PCM16 audio")
    return pcm
