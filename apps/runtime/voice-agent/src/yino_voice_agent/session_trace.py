"""In-process session timings. No external metrics backend."""

from __future__ import annotations

import logging
import re
import time
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_E164_LIKE = re.compile(r"\+[1-9]\d{7,14}")
_BARE_MSISDN = re.compile(r"(?<![\dA-Fa-f])[1-9]\d{8,14}(?![\dA-Fa-f])")
_MAX_ORDER = 512
_EVENT_ALIASES = {
    "final_user_transcript": "first_user_transcript",
    "first_user_transcript": "final_user_transcript",
    "tool_response": "tool_result",
    "tool_result": "tool_response",
}


def redact_phone_numbers(text: str) -> str:
    """Strip phone-like strings from log text. Do not use for Platform payloads."""

    return _BARE_MSISDN.sub("***", _E164_LIKE.sub("+***", text))


def sanitize_url_for_log(url: str) -> str:
    """Drop query strings so lookup numbers never reach logs."""

    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


# Only events the runtime can actually observe. Do not invent SDK-invisible points.
OBSERVED_EVENTS = frozenset(
    {
        "session_start",
        "runtime_ready",
        "first_user_audio",
        "user_speech_end",
        "first_user_transcript",
        "final_user_transcript",
        "model_request_start",
        "model_first_event",
        "tool_request",
        "tool_result",
        "tool_response",
        "assistant_response_start",
        "first_assistant_audio",
        "interrupt_start",
        "interrupt_complete",
        "session_close",
        "finish_start",
        "finish_complete",
        "sip_normalized",
        "destination_resolved",
        "silence_prompt",
        "idle_timeout",
        "session_timeout",
        "greeting_started",
        "greeting_skipped",
        "provider_disconnect",
        "response_cancelled",
    }
)

_FIRST_ONLY = frozenset(
    {
        "session_start",
        "runtime_ready",
        "first_user_audio",
        "user_speech_end",
        "first_user_transcript",
        "final_user_transcript",
        "model_request_start",
        "model_first_event",
        "assistant_response_start",
        "first_assistant_audio",
        "session_close",
        "sip_normalized",
        "destination_resolved",
        "idle_timeout",
        "session_timeout",
        "greeting_started",
        "greeting_skipped",
        "provider_disconnect",
    }
)


class Clock(Protocol):
    def monotonic(self) -> float:
        """Return a monotonic timestamp in seconds."""


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()


class FakeClock:
    """Deterministic clock for tests. Never sleeps."""

    def __init__(self, start: float = 1_000.0) -> None:
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("clock cannot go backwards")
        self._now += seconds


class SessionTrace:
    """Correlate timings by session_id. Never stores transcripts or audio."""

    def __init__(
        self,
        *,
        session_id: str,
        call_id: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.session_id = session_id
        self.call_id = call_id
        self._clock: Clock = clock or SystemClock()
        self._marks: dict[str, float] = {}
        self._order: list[str] = []

    @property
    def order(self) -> tuple[str, ...]:
        return tuple(self._order)

    def mark(self, name: str) -> None:
        if name not in OBSERVED_EVENTS:
            raise ValueError(f"unknown timing event: {name}")
        self._record(name)
        alias = _EVENT_ALIASES.get(name)
        if alias is not None:
            self._record(alias)

    def _record(self, name: str) -> None:
        if name in _FIRST_ONLY and name in self._marks:
            return
        timestamp = self._clock.monotonic()
        self._marks[name] = timestamp
        self._order.append(name)
        overflow = len(self._order) - _MAX_ORDER
        if overflow > 0:
            del self._order[:overflow]
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "runtime timing event=%s session_id=%s call_id=%s t=%.6f",
                name,
                redact_phone_numbers(self.session_id),
                redact_phone_numbers(self.call_id or "-"),
                timestamp,
            )

    def timestamp(self, name: str) -> float | None:
        return self._marks.get(name)

    def latency_s(self, start: str, end: str) -> float | None:
        begin = self._marks.get(start)
        finish = self._marks.get(end)
        if begin is None or finish is None:
            return None
        return finish - begin

    def derived(self) -> dict[str, float]:
        mapping = {
            "startup": ("session_start", "runtime_ready"),
            "startup_latency": ("session_start", "runtime_ready"),
            "tool_rtt": ("tool_request", "tool_result"),
            "turn": ("first_user_transcript", "assistant_response_start"),
            "close_to_finish": ("session_close", "finish_complete"),
            "speech_end_to_transcript": (
                "user_speech_end",
                "final_user_transcript",
            ),
            "transcript_to_model": (
                "final_user_transcript",
                "model_request_start",
            ),
            "model_to_first_audio": (
                "model_request_start",
                "first_assistant_audio",
            ),
            "speech_end_to_first_audio": (
                "user_speech_end",
                "first_assistant_audio",
            ),
            "barge_in_stop": ("interrupt_start", "interrupt_complete"),
        }
        out: dict[str, float] = {}
        for label, pair in mapping.items():
            value = self.latency_s(*pair)
            if value is not None:
                out[label] = value
        return out
