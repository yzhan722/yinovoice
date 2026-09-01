"""In-process session timings. No external metrics backend."""

from __future__ import annotations

import logging
import time
from typing import Protocol

logger = logging.getLogger(__name__)

# Only events the runtime can actually observe. Do not invent SDK-invisible points.
OBSERVED_EVENTS = frozenset(
    {
        "session_start",
        "runtime_ready",
        "first_user_transcript",
        "tool_request",
        "tool_result",
        "assistant_response_start",
        "session_close",
        "finish_start",
        "finish_complete",
    }
)

_FIRST_ONLY = frozenset(
    {
        "session_start",
        "runtime_ready",
        "first_user_transcript",
        "assistant_response_start",
        "session_close",
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

    def mark(self, name: str) -> None:
        if name not in OBSERVED_EVENTS:
            raise ValueError(f"unknown timing event: {name}")
        if name in _FIRST_ONLY and name in self._marks:
            return
        timestamp = self._clock.monotonic()
        self._marks[name] = timestamp
        self._order.append(name)
        logger.info(
            "runtime timing event=%s session_id=%s call_id=%s t=%.6f",
            name,
            self.session_id,
            self.call_id or "-",
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
            "tool_rtt": ("tool_request", "tool_result"),
            "turn": ("first_user_transcript", "assistant_response_start"),
            "close_to_finish": ("session_close", "finish_complete"),
        }
        out: dict[str, float] = {}
        for label, pair in mapping.items():
            value = self.latency_s(*pair)
            if value is not None:
                out[label] = value
        return out
