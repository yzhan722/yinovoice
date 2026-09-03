from __future__ import annotations

import pytest

from yino_voice_agent.errors import WorkerNotAcceptingError
from yino_voice_agent.ops import WorkerRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 10, 50])
async def test_drain_matrix_active_goes_to_zero(count: int) -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    for index in range(count):
        worker.accept_session(f"d-{index}")
    worker.begin_drain()
    assert worker.readyz()["ready"] is False
    with pytest.raises(WorkerNotAcceptingError):
        worker.accept_session("late")
    await worker.drain_sessions()
    assert worker.metrics.active_sessions == 0
    assert worker.registry.active_count == 0


@pytest.mark.asyncio
async def test_fifty_session_drain_repeats_three_times() -> None:
    for _ in range(3):
        worker = WorkerRuntime()
        worker.mark_ready()
        for index in range(50):
            worker.accept_session(f"r-{index}")
        await worker.drain_sessions()
        with pytest.raises(WorkerNotAcceptingError):
            worker.accept_session("after")
        assert worker.metrics.active_sessions == 0


@pytest.mark.asyncio
async def test_shutdown_and_hangup_unregister_once() -> None:
    worker = WorkerRuntime()
    worker.accept_session("race")
    worker.release_session("race", status="completed", ended_reason="user_hangup")
    worker.begin_drain()
    await worker.drain_sessions()
    assert worker.registry.unregister("race") is False
    assert worker.metrics.sessions_started == 1
    assert worker.metrics.user_hangups == 1


@pytest.mark.asyncio
async def test_shutdown_and_qwen_disconnect_metrics() -> None:
    worker = WorkerRuntime()
    worker.mark_ready()
    worker.accept_session("q")
    worker.note_qwen_disconnect()
    worker.release_session("q", status="failed", ended_reason="agent_error")
    await worker.drain_sessions()
    assert worker.metrics.qwen_disconnects == 1
    assert worker.metrics.sessions_failed == 1
    assert worker.livez()["status"] == "ok"
