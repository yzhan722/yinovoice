"""Accumulate Qwen `response.done` token usage. Never stores audio or transcripts."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass

_MAX_SEEN_RESPONSE_IDS = 4096


def _nonneg_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _detail_tokens(details: object, key: str) -> int:
    if not isinstance(details, Mapping):
        return 0
    return _nonneg_int(details.get(key))


def response_id_from_event(event: Mapping[str, object]) -> str | None:
    """Return the protocol response id when Qwen provides a stable string."""

    response = event.get("response")
    if isinstance(response, Mapping):
        response_id = response.get("id")
        if isinstance(response_id, str) and response_id.strip():
            return response_id.strip()
    return None


@dataclass(slots=True)
class CallUsageTotals:
    input_audio_tokens: int = 0
    input_text_tokens: int = 0
    output_audio_tokens: int = 0
    output_text_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    response_count: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    def has_data(self) -> bool:
        return self.response_count > 0 or self.total_tokens > 0


def parse_response_usage(event: Mapping[str, object]) -> CallUsageTotals | None:
    """Read one Qwen/OpenAI-realtime `response.done` usage object."""

    payload: Mapping[str, object] = event
    response = event.get("response")
    if isinstance(response, Mapping):
        payload = response
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None

    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    input_audio = _detail_tokens(input_details, "audio_tokens")
    input_text = _detail_tokens(input_details, "text_tokens")
    output_audio = _detail_tokens(output_details, "audio_tokens")
    output_text = _detail_tokens(output_details, "text_tokens")
    input_tokens = _nonneg_int(usage.get("input_tokens"))
    output_tokens = _nonneg_int(usage.get("output_tokens"))
    total_tokens = _nonneg_int(usage.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    if (
        input_audio
        + input_text
        + output_audio
        + output_text
        + input_tokens
        + output_tokens
        + total_tokens
        == 0
    ):
        return None
    return CallUsageTotals(
        input_audio_tokens=input_audio,
        input_text_tokens=input_text,
        output_audio_tokens=output_audio,
        output_text_tokens=output_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        response_count=1,
    )


class CallUsageAccumulator:
    def __init__(self) -> None:
        self._totals = CallUsageTotals()
        self._seen_ids: set[str] = set()
        self._seen_order: deque[str] = deque()

    def add(self, event: Mapping[str, object]) -> None:
        parsed = parse_response_usage(event)
        if parsed is None:
            return
        response_id = response_id_from_event(event)
        if response_id is not None:
            if response_id in self._seen_ids:
                return
            self._seen_ids.add(response_id)
            self._seen_order.append(response_id)
            if len(self._seen_order) > _MAX_SEEN_RESPONSE_IDS:
                expired = self._seen_order.popleft()
                self._seen_ids.discard(expired)
        totals = self._totals
        totals.input_audio_tokens += parsed.input_audio_tokens
        totals.input_text_tokens += parsed.input_text_tokens
        totals.output_audio_tokens += parsed.output_audio_tokens
        totals.output_text_tokens += parsed.output_text_tokens
        totals.input_tokens += parsed.input_tokens
        totals.output_tokens += parsed.output_tokens
        totals.total_tokens += parsed.total_tokens
        totals.response_count += parsed.response_count

    def snapshot(self) -> CallUsageTotals:
        return CallUsageTotals(**self._totals.as_dict())
