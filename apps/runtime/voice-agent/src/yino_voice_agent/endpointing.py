"""Model of Qwen server_vad turn-end. Not a second detector."""

from __future__ import annotations

from dataclasses import dataclass

from .voice_ux_config import DEFAULT_ENDPOINT_SILENCE_MS, ENDPOINT_AUTHORITY


@dataclass(frozen=True, slots=True)
class SpeechSpan:
    start_ms: int
    end_ms: int


def gap_ms(previous_end_ms: int, next_start_ms: int) -> int:
    return max(0, next_start_ms - previous_end_ms)


def is_turn_end(gap_after_speech_ms: int, silence_duration_ms: int) -> bool:
    """True when the pause is long enough for the authoritative VAD to commit."""

    return gap_after_speech_ms >= silence_duration_ms


def utterance_complete_at(
    spans: tuple[SpeechSpan, ...],
    *,
    now_ms: int,
    silence_duration_ms: int = DEFAULT_ENDPOINT_SILENCE_MS,
) -> bool:
    """Whether `now_ms` is a sentence end under Qwen server_vad timing."""

    if not spans:
        return False
    last = spans[-1]
    if now_ms < last.end_ms:
        return False
    return is_turn_end(now_ms - last.end_ms, silence_duration_ms)


def endpoint_authority() -> str:
    return ENDPOINT_AUTHORITY
