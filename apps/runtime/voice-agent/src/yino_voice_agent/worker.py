"""In-process worker drain. Does not wrap undocumented LiveKit Agent APIs."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .call_lifecycle import CallLifecycleClient
from .errors import WorkerNotAcceptingError
from .tool_orchestrator import ToolOrchestrator

FinishFn = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class RegisteredSession:
    session_id: str
    lifecycle: CallLifecycleClient | None
    orchestrator: ToolOrchestrator | None
    finish: FinishFn


class WorkerSessionRegistry:
    """Track active Runtime sessions and drain them on worker shutdown."""

    def __init__(self) -> None:
        self._accepting = True
        self._sessions: dict[str, RegisteredSession] = {}
        self._lock = asyncio.Lock()
        self._total_started = 0

    @property
    def accepting(self) -> bool:
        return self._accepting

    @property
    def draining(self) -> bool:
        return not self._accepting

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    @property
    def total_started(self) -> int:
        return self._total_started

    def stop_accepting(self) -> None:
        self._accepting = False

    def begin_drain(self) -> None:
        self.stop_accepting()

    def register(
        self,
        session_id: str,
        lifecycle: CallLifecycleClient | None = None,
        *,
        orchestrator: ToolOrchestrator | None = None,
        finish: FinishFn | None = None,
    ) -> None:
        if not self._accepting:
            raise WorkerNotAcceptingError("worker is draining")
        if session_id in self._sessions:
            raise RuntimeError("session already registered")

        async def _default_finish() -> None:
            if orchestrator is not None:
                orchestrator.mark_closed()
            if lifecycle is not None:
                await lifecycle.finish(status="completed", ended_reason="completed")

        self._sessions[session_id] = RegisteredSession(
            session_id=session_id,
            lifecycle=lifecycle,
            orchestrator=orchestrator,
            finish=finish or _default_finish,
        )
        self._total_started += 1

    def snapshot_ids(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    def unregister(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    async def drain(self, *, timeout_s: float | None = None) -> None:
        self.begin_drain()
        async with self._lock:
            registered = list(self._sessions.values())
        if not registered:
            return
        finisher = asyncio.gather(
            *(item.finish() for item in registered),
            return_exceptions=True,
        )
        if timeout_s is None:
            await finisher
        else:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(finisher, timeout=timeout_s)
        for item in registered:
            orchestrator = item.orchestrator
            if orchestrator is not None:
                await orchestrator.wait_idle()
        self._sessions.clear()
