from __future__ import annotations

import pytest

from yino_voice_agent.latency import percentile, summarize
from yino_voice_agent.session_trace import FakeClock, SessionTrace


def test_percentile_summary_is_deterministic() -> None:
    samples = [float(value) for value in range(1, 101)]
    summary = summarize(samples)
    assert summary.count == 100
    assert summary.min == 1.0
    assert summary.max == 100.0
    assert summary.p50 == percentile(samples, 50)
    assert summary.p95 == percentile(samples, 95)
    assert summary.p99 == percentile(samples, 99)
    block = summary.format_block("speech_end_to_first_audio")
    assert "count: 100" in block
    assert "p50:" in block
    assert "p95:" in block
    assert "p99:" in block


def test_session_trace_derived_metrics_on_fake_clock() -> None:
    clock = FakeClock()
    trace = SessionTrace(session_id="lat-1", clock=clock)
    trace.mark("session_start")
    clock.advance(0.12)
    trace.mark("runtime_ready")
    clock.advance(0.04)
    trace.mark("first_user_audio")
    clock.advance(0.20)
    trace.mark("user_speech_end")
    clock.advance(0.08)
    trace.mark("final_user_transcript")
    clock.advance(0.03)
    trace.mark("model_request_start")
    clock.advance(0.15)
    trace.mark("first_assistant_audio")
    clock.advance(0.02)
    trace.mark("tool_request")
    clock.advance(0.05)
    trace.mark("tool_response")
    clock.advance(0.01)
    trace.mark("interrupt_start")
    clock.advance(0.025)
    trace.mark("interrupt_complete")
    clock.advance(0.04)
    trace.mark("session_close")
    clock.advance(0.03)
    trace.mark("finish_start")
    clock.advance(0.01)
    trace.mark("finish_complete")
    derived = trace.derived()
    assert derived["startup_latency"] == pytest.approx(0.12)
    assert derived["speech_end_to_transcript"] == pytest.approx(0.08)
    assert derived["transcript_to_model"] == pytest.approx(0.03)
    assert derived["model_to_first_audio"] == pytest.approx(0.15)
    assert derived["speech_end_to_first_audio"] == pytest.approx(0.26)
    assert derived["tool_rtt"] == pytest.approx(0.05)
    assert derived["barge_in_stop"] == pytest.approx(0.025)
    assert derived["close_to_finish"] == pytest.approx(0.04)


def test_synthetic_latency_percentiles_from_trace_runs() -> None:
    samples: list[float] = []
    for index in range(40):
        clock = FakeClock()
        trace = SessionTrace(session_id=f"p-{index}", clock=clock)
        trace.mark("user_speech_end")
        clock.advance(0.2 + index * 0.001)
        trace.mark("first_assistant_audio")
        value = trace.derived()["speech_end_to_first_audio"]
        samples.append(value)
    summary = summarize(samples)
    assert summary.count == 40
    assert summary.p50 <= summary.p95 <= summary.p99 <= summary.max
