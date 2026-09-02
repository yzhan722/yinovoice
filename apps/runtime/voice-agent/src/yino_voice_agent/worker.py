"""In-process worker drain. Does not wrap undocumented LiveKit Agent APIs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .call_lifecycle import CallLifecycleClient
from .errors import WorkerNotAcceptingError
from .tool_orchestrator import ToolOrchestrator

FinishFn = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class RegisteredSession:
    session_id: str
    lifecycle: CallLifecycleClient
    orchestrator: ToolOrchestrator | None
    finish: FinishFn


class WorkerSessionRegistry:
    """Track active Runtime sessions and drain them on worker shutdown."""

    def __init__(self) -> None:
        self._accepting = True
        self._sessions: dict[str, RegisteredSession] = {}
        self._lock = asyncio.Lock()

    @property
    def accepting(self) -> bool:
        return self._accepting

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def stop_accepting(self) -> None:
        self._accepting = False

    def register(
        self,
        session_id: str,
        lifecycle: CallLifecycleClient,
        *,
        orchestrator: ToolOrchestrator | None = None,
        finish: FinishFn | None = None,
    ) -> None:
        if not self._accepting:
            raise WorkerNotAcceptingError("worker is draining")

        async def _default_finish() -> None:
            if orchestrator is not None:
                orchestrator.mark_closed()
            await lifecycle.finish(status="completed", ended_reason="completed")

        self._sessions[session_id] = RegisteredSession(
            session_id=session_id,
            lifecycle=lifecycle,
            orchestrator=orchestrator,
            finish=finish or _default_finish,
        )

    def unregister(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def drain(self) -> None:
        self._accepting = False
        async with self._lock:
            registered = list(self._sessions.values())
        if not registered:
            return
        await asyncio.gather(
            *(item.finish() for item in registered),
            return_exceptions=True,
        )
        for item in registered:
            orchestrator = item.orchestrator
            if orchestrator is not None:
                await orchestrator.wait_idle()
        self._sessions.clear()
