from __future__ import annotations

import asyncio

import httpx
import pytest

from yino_voice_agent.errors import WorkerNotAcceptingError
from yino_voice_agent.ops import WorkerRuntime, WorkerState
from yino_voice_agent.session_trace import FakeClock, SessionTrace


@pytest.mark.asyncio
async def test_livez_stays_ok_when_degraded() -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    worker.note_qwen_disconnect()
    assert worker.state is WorkerState.DEGRADED
    assert worker.livez() == {"status": "ok"}
    assert worker.readyz()["ready"] is True


@pytest.mark.asyncio
async def test_readyz_false_while_draining_or_starting() -> None:
    worker = WorkerRuntime()
    assert worker.readyz()["ready"] is False
    worker.mark_ready()
    assert worker.readyz()["ready"] is True
    worker.begin_drain()
    assert worker.readyz()["ready"] is False
    assert worker.readyz()["state"] == "DRAINING"


@pytest.mark.asyncio
async def test_status_has_no_pii_or_secrets() -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    worker.accept_session("room-a")
    body = worker.status()
    blob = str(body)
    assert "DASHSCOPE" not in blob
    assert "phone" not in blob
    assert "transcript" not in blob
    assert body["active_sessions"] == 1
    worker.release_session("room-a", status="completed", ended_reason="user_hangup")
    assert worker.metrics.user_hangups == 1
    assert worker.metrics.sessions_completed == 1
    assert worker.metrics.sessions_failed == 0


@pytest.mark.asyncio
async def test_agent_error_is_not_completed() -> None:
    worker = WorkerRuntime()
    worker.accept_session("room-b")
    worker.release_session("room-b", status="failed", ended_reason="agent_error")
    assert worker.metrics.sessions_failed == 1
    assert worker.metrics.sessions_completed == 0
    assert worker.metrics.agent_errors == 1


@pytest.mark.asyncio
async def test_ops_http_binds_loopback_and_serves_json() -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    port = await worker.start_ops(host="127.0.0.1", port=0)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            live = await http.get("/livez")
            ready = await http.get("/readyz")
            status = await http.get("/status")
        assert live.json() == {"status": "ok"}
        assert ready.json()["ready"] is True
        assert "metrics" in status.json()
        assert "environment" not in status.json()
    finally:
        await worker.aclose_ops()


@pytest.mark.asyncio
async def test_zero_zero_zero_zero_is_coerced_to_loopback() -> None:
    worker = WorkerRuntime()
    port = await worker.start_ops(host="0.0.0.0", port=0)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            live = await http.get("/livez")
        assert live.status_code == 200
    finally:
        await worker.aclose_ops()


@pytest.mark.asyncio
async def test_drain_rejects_new_sessions_and_clears_active() -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    for index in range(10):
        worker.accept_session(f"s-{index}")
    worker.begin_drain()
    with pytest.raises(WorkerNotAcceptingError):
        worker.accept_session("late")
    await worker.drain_sessions()
    assert worker.metrics.active_sessions == 0
    assert worker.readyz()["ready"] is False


@pytest.mark.asyncio
async def test_fifty_sessions_metrics_are_isolated() -> None:
    worker = WorkerRuntime()

    async def one(index: int) -> None:
        worker.accept_session(f"c-{index}")
        worker.release_session(
            f"c-{index}", status="completed", ended_reason="completed"
        )

    await asyncio.gather(*[one(index) for index in range(50)])
    assert worker.metrics.sessions_started == 50
    assert worker.metrics.active_sessions == 0
    assert worker.metrics.peak_active_sessions >= 1
    assert worker.metrics.sessions_completed == 50


@pytest.mark.asyncio
async def test_restart_has_fresh_state() -> None:
    first = WorkerRuntime()
    first.accept_session("old")
    first.metrics.note_qwen_error()
    second = WorkerRuntime()
    assert second.metrics.active_sessions == 0
    assert second.metrics.qwen_errors == 0
    assert second.registry.active_count == 0


def test_latency_samples_are_bounded() -> None:
    worker = WorkerRuntime()
    clock = FakeClock()
    for index in range(2000):
        trace = SessionTrace(session_id=f"lat-{index}", clock=clock)
        trace.mark("user_speech_end")
        clock.advance(0.2)
        trace.mark("first_assistant_audio")
        worker.metrics.observe_trace(trace.derived())
    snapshot = worker.metrics.latency_snapshot()["speech_end_to_first_audio"]
    assert snapshot["count"] == 1024
    assert snapshot["p50"] == pytest.approx(0.2)
