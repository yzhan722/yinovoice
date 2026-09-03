from __future__ import annotations

from yino_voice_agent.customer_safe import customer_safe_message, looks_technical
from yino_voice_agent.transcript_filter import FinalTranscriptGate


def test_empty_and_noise_transcripts_are_dropped() -> None:
    gate = FinalTranscriptGate()
    assert not gate.accept("")
    assert not gate.accept("   ")
    assert not gate.accept("...")
    assert not gate.accept("，，")
    assert gate.accept("嗯")
    assert gate.accept("预约下午三点")


def test_duplicate_item_id_is_dropped_but_repeat_text_is_kept() -> None:
    gate = FinalTranscriptGate()
    assert gate.accept("hello", "item-1")
    assert not gate.accept("hello", "item-1")
    assert gate.accept("hello", "item-2")


def test_customer_safe_strips_http_json_and_traces() -> None:
    assert looks_technical("HTTP status code 503")
    assert "HTTP" not in customer_safe_message("HTTP 503")
    assert "JSON" not in customer_safe_message('{"status":500}')
    assert customer_safe_message("档期已满") == "档期已满"
