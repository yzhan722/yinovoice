from __future__ import annotations

import asyncio

import pytest

from yino_voice_agent.recording import RecordingController


class _Sink:
    def __init__(self, *, fail: bool = False, hang: bool = False) -> None:
        self.fail = fail
        self.hang = hang
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.release = asyncio.Event()

    async def start(self, session_id: str) -> str | None:
        if self.hang:
            await self.release.wait()
        if self.fail:
            raise RuntimeError("egress down")
        self.started.append(session_id)
        return f"eg-{session_id}"

    async def stop(self, egress_id: str) -> None:
        self.stopped.append(egress_id)


@pytest.mark.asyncio
async def test_recording_disabled_is_noop() -> None:
    sink = _Sink()
    controller = RecordingController(enabled=False, sink=sink)
    controller.request_start("room-off")
    await controller.notify_session_ended()
    assert sink.started == []
    assert controller.egress_id is None


@pytest.mark.asyncio
async def test_recording_start_success_then_stop() -> None:
    sink = _Sink()
    controller = RecordingController(enabled=True, sink=sink)
    controller.request_start("room-on")
    await asyncio.sleep(0)
    await controller.notify_session_ended()
    assert sink.started == ["room-on"]
    assert sink.stopped == ["eg-room-on"]
    assert controller.failed is False


@pytest.mark.asyncio
async def test_recording_start_failure_does_not_raise() -> None:
    sink = _Sink(fail=True)
    controller = RecordingController(enabled=True, sink=sink)
    controller.request_start("room-fail")
    await asyncio.sleep(0)
    await controller.notify_session_ended()
    assert controller.failed is True
    assert controller.egress_id is None


@pytest.mark.asyncio
async def test_recording_failure_does_not_change_readiness() -> None:
    from yino_voice_agent.ops import WorkerRuntime

    worker = WorkerRuntime()
    worker.mark_ready()
    sink = _Sink(fail=True)
    controller = RecordingController(enabled=True, sink=sink)
    controller.request_start("room-ops")
    await asyncio.sleep(0)
    await controller.notify_session_ended()
    assert controller.failed is True
    assert worker.livez() == {"status": "ok"}
    assert worker.readyz()["ready"] is True


@pytest.mark.asyncio
async def test_session_ends_before_egress_starts() -> None:
    sink = _Sink(hang=True)
    controller = RecordingController(enabled=True, sink=sink)
    controller.request_start("room-pending")
    await asyncio.sleep(0)
    assert controller.pending is True
    ended = asyncio.create_task(controller.notify_session_ended())
    sink.release.set()
    await ended
    assert sink.stopped == ["eg-room-pending"]


@pytest.mark.asyncio
async def test_finish_while_egress_pending_still_stops() -> None:
    sink = _Sink(hang=True)
    controller = RecordingController(enabled=True, sink=sink)
    controller.request_start("room-race")
    await asyncio.sleep(0)
    finish = asyncio.create_task(controller.notify_session_ended())
    await asyncio.sleep(0)
    sink.release.set()
    await finish
    assert len(sink.stopped) == 1
