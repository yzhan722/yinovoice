from __future__ import annotations

from yino_voice_agent.endpointing import (
    SpeechSpan,
    endpoint_authority,
    gap_ms,
    is_turn_end,
    utterance_complete_at,
)
from yino_voice_agent.voice_ux_config import ENDPOINT_AUTHORITY


def test_qwen_server_vad_is_authoritative() -> None:
    assert endpoint_authority() == ENDPOINT_AUTHORITY
    assert endpoint_authority() == "qwen_server_vad"


def test_short_hesitation_is_not_turn_end() -> None:
    spans = (SpeechSpan(0, 1000), SpeechSpan(1200, 2200))
    assert gap_ms(1000, 1200) == 200
    assert not is_turn_end(200, 450)
    assert not utterance_complete_at(spans, now_ms=1200, silence_duration_ms=450)
    assert not utterance_complete_at(spans, now_ms=1350, silence_duration_ms=450)


def test_normal_sentence_end_after_configured_silence() -> None:
    spans = (SpeechSpan(0, 1000),)
    assert not utterance_complete_at(spans, now_ms=1300, silence_duration_ms=450)
    assert utterance_complete_at(spans, now_ms=1450, silence_duration_ms=450)


def test_long_pause_is_turn_end() -> None:
    assert is_turn_end(800, 450)


def test_consecutive_short_clauses_keep_one_utterance() -> None:
    spans = (
        SpeechSpan(0, 400),
        SpeechSpan(550, 900),
        SpeechSpan(1050, 1600),
    )
    assert not utterance_complete_at(spans, now_ms=1050, silence_duration_ms=450)
    assert utterance_complete_at(spans, now_ms=2050, silence_duration_ms=450)
