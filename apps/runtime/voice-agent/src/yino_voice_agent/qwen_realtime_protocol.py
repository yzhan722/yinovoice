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
    turn_detection_disabled: bool = False


def _turn_detection_config(
    *, turn_detection_disabled: bool
) -> dict[str, object] | None:
    if turn_detection_disabled:
        return None
    # Balance end-of-turn latency vs false barge-in. ~450ms silence feels snappy
    # for demo Q&A; silence frames are still forwarded while speech_active.
    return {
        "type": "server_vad",
        "threshold": 0.35,
        "silence_duration_ms": 450,
    }


def build_session_update(options: QwenSessionOptions) -> dict[str, object]:
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": options.voice,
            "instructions": options.instructions,
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "input_audio_transcription": {"model": "qwen3-asr-flash-realtime"},
            "turn_detection": _turn_detection_config(
                turn_detection_disabled=options.turn_detection_disabled
            ),
        },
    }


def build_instructions_update(
    instructions: str, *, turn_detection_disabled: bool = False
) -> dict[str, object]:
    _ = turn_detection_disabled
    # Never resend turn_detection after the first session.update — Qwen rejects
    # turn_detection changes once audio processing has started.
    return {
        "type": "session.update",
        "session": {
            "instructions": instructions,
        },
    }


def build_audio_append(pcm: bytes) -> dict[str, object]:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm).decode("ascii"),
    }


def build_audio_commit() -> dict[str, object]:
    return {"type": "input_audio_buffer.commit"}


def build_audio_clear() -> dict[str, object]:
    return {"type": "input_audio_buffer.clear"}


def build_response_create() -> dict[str, object]:
    # Match DashScope push-to-talk examples: bare create, session modalities apply.
    return {"type": "response.create"}



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
