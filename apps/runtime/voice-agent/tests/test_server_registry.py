from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from yino_voice_agent.errors import WorkerNotAcceptingError
from yino_voice_agent.ops import WorkerRuntime, get_worker
from yino_voice_agent.runtime_config import RuntimeConfigurationError
from yino_voice_agent.server import install_worker_lifecycle, local_voice_agent
from yino_voice_agent.startup import WorkerStartupSettings


@pytest.mark.asyncio
async def test_draining_worker_rejects_new_runtime_session() -> None:
    worker = get_worker()
    worker.begin_drain()
    context = SimpleNamespace(
        room=SimpleNamespace(name="drain-reject"),
        job=SimpleNamespace(metadata=""),
    )
    with pytest.raises(WorkerNotAcceptingError):
        await local_voice_agent(context)
    assert worker.metrics.sessions_started == 0
    assert worker.registry.active_count == 0


@pytest.mark.asyncio
async def test_empty_metadata_failure_unregisters() -> None:
    worker = get_worker()
    settings = SimpleNamespace(
        greeting="hi",
        allow_empty_dispatch_metadata_local_dev=False,
    )
    context = SimpleNamespace(
        room=SimpleNamespace(name="fail-room"),
        job=SimpleNamespace(metadata=""),
    )
    with (
        patch("yino_voice_agent.server.VoiceSettings.from_env", return_value=settings),
        pytest.raises(RuntimeConfigurationError, match="empty dispatch metadata"),
    ):
        await local_voice_agent(context)
    assert worker.registry.active_count == 0
    assert worker.metrics.sessions_started == 1
    assert worker.metrics.sessions_failed == 1


@pytest.mark.asyncio
async def test_install_lifecycle_marks_draining_then_stopped() -> None:
    class FakeServer:
        def __init__(self) -> None:
            self.handlers: dict[str, object] = {}

        def on(self, name: str):
            def decorator(fn):
                self.handlers[name] = fn
                return fn

            return decorator

        async def drain(self, timeout: object = None) -> None:
            _ = timeout

    server = FakeServer()
    worker = WorkerRuntime()
    startup = WorkerStartupSettings.from_env({}, mode="synthetic-test")
    install_worker_lifecycle(server, worker, startup)  # type: ignore[arg-type]
    started = server.handlers["worker_started"]
    assert callable(started)
    started()
    assert worker.readyz()["ready"] is True
    await server.drain()
    assert worker.draining is True
    assert worker.state.value == "STOPPED"
    assert worker.readyz()["ready"] is False
