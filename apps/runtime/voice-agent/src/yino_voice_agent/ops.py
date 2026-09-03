"""Worker operational state, bounded metrics, and loopback ops HTTP."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from enum import StrEnum
from typing import Any

from aiohttp import web

from .errors import WorkerNotAcceptingError
from .latency import summarize
from .worker import WorkerSessionRegistry

_MAX_LATENCY_SAMPLES = 1024
_LATENCY_KEYS = (
    "startup",
    "speech_end_to_first_audio",
    "tool_rtt",
    "barge_in_stop",
    "close_to_finish",
)

_worker: WorkerRuntime | None = None


class WorkerState(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"


class RuntimeMetrics:
    """Process-lifetime counters. No tenant/call/phone labels."""

    def __init__(self) -> None:
        self.sessions_started = 0
        self.sessions_completed = 0
        self.sessions_failed = 0
        self.active_sessions = 0
        self.peak_active_sessions = 0
        self.user_hangups = 0
        self.agent_errors = 0
        self.qwen_disconnects = 0
        self.qwen_errors = 0
        self.tool_requests = 0
        self.tool_errors = 0
        self.tool_timeouts = 0
        self.interruptions = 0
        self.finish_attempts = 0
        self.finish_failures = 0
        self._latency: dict[str, deque[float]] = {
            name: deque(maxlen=_MAX_LATENCY_SAMPLES) for name in _LATENCY_KEYS
        }

    def note_session_start(self) -> None:
        self.sessions_started += 1
        self.active_sessions += 1
        if self.active_sessions > self.peak_active_sessions:
            self.peak_active_sessions = self.active_sessions

    def note_session_end(self, status: str, ended_reason: str) -> None:
        if self.active_sessions > 0:
            self.active_sessions -= 1
        if status == "failed" or ended_reason == "agent_error":
            self.sessions_failed += 1
        else:
            self.sessions_completed += 1
        if ended_reason == "user_hangup":
            self.user_hangups += 1
        if ended_reason == "agent_error":
            self.agent_errors += 1

    def note_qwen_disconnect(self) -> None:
        self.qwen_disconnects += 1

    def note_qwen_error(self) -> None:
        self.qwen_errors += 1

    def note_interruption(self) -> None:
        self.interruptions += 1

    def note_tool_request(self) -> None:
        self.tool_requests += 1

    def note_tool_error(self) -> None:
        self.tool_errors += 1

    def note_tool_timeout(self) -> None:
        self.tool_timeouts += 1

    def note_finish_attempt(self) -> None:
        self.finish_attempts += 1

    def note_finish_failure(self) -> None:
        self.finish_failures += 1

    def observe_latency(self, name: str, value: float) -> None:
        samples = self._latency.get(name)
        if samples is None:
            return
        samples.append(value)

    def observe_trace(self, derived: dict[str, float]) -> None:
        for name in _LATENCY_KEYS:
            value = derived.get(name)
            if value is None and name == "barge_in_stop":
                value = derived.get("barge_in_stop_latency")
            if isinstance(value, (int, float)):
                self.observe_latency(name, float(value))

    def latency_snapshot(self) -> dict[str, dict[str, float | int]]:
        out: dict[str, dict[str, float | int]] = {}
        for name, samples in self._latency.items():
            if not samples:
                out[name] = {"count": 0}
                continue
            summary = summarize(list(samples))
            out[name] = {
                "count": summary.count,
                "p50": summary.p50,
                "p95": summary.p95,
                "p99": summary.p99,
            }
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "sessions_started": self.sessions_started,
            "sessions_completed": self.sessions_completed,
            "sessions_failed": self.sessions_failed,
            "active_sessions": self.active_sessions,
            "peak_active_sessions": self.peak_active_sessions,
            "user_hangups": self.user_hangups,
            "agent_errors": self.agent_errors,
            "qwen_disconnects": self.qwen_disconnects,
            "qwen_errors": self.qwen_errors,
            "tool_requests": self.tool_requests,
            "tool_errors": self.tool_errors,
            "tool_timeouts": self.tool_timeouts,
            "interruptions": self.interruptions,
            "finish_attempts": self.finish_attempts,
            "finish_failures": self.finish_failures,
            "latency": self.latency_snapshot(),
        }


class WorkerRuntime:
    """In-process worker ops. Process-lifetime; a new instance is a restart."""

    def __init__(self, *, drain_timeout_s: float = 30.0) -> None:
        self.registry = WorkerSessionRegistry()
        self.metrics = RuntimeMetrics()
        self.state = WorkerState.STARTING
        self.started_at = time.monotonic()
        self.last_runtime_error_type: str | None = None
        self.drain_timeout_s = drain_timeout_s
        self._ops_runner: web.AppRunner | None = None
        self._ops_site: web.TCPSite | None = None
        self._ops_task: asyncio.Task[int] | None = None

    @property
    def draining(self) -> bool:
        return self.registry.draining or self.state is WorkerState.DRAINING

    @property
    def uptime_s(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def mark_ready(self) -> None:
        if self.state in {WorkerState.DRAINING, WorkerState.STOPPED}:
            return
        if self.state is WorkerState.DEGRADED:
            return
        self.state = WorkerState.READY

    def mark_degraded(self, error_type: str) -> None:
        self.last_runtime_error_type = error_type
        if self.state is WorkerState.READY:
            self.state = WorkerState.DEGRADED

    def begin_drain(self) -> None:
        self.registry.begin_drain()
        if self.state is not WorkerState.STOPPED:
            self.state = WorkerState.DRAINING

    def mark_stopped(self) -> None:
        self.registry.begin_drain()
        self.state = WorkerState.STOPPED

    def accept_session(self, session_id: str) -> None:
        try:
            self.registry.register(session_id)
        except WorkerNotAcceptingError:
            raise
        self.metrics.note_session_start()

    def release_session(
        self,
        session_id: str,
        *,
        status: str,
        ended_reason: str,
        derived: dict[str, float] | None = None,
    ) -> None:
        if self.registry.unregister(session_id):
            self.metrics.note_session_end(status, ended_reason)
            if derived:
                self.metrics.observe_trace(derived)

    def livez(self) -> dict[str, str]:
        return {"status": "ok"}

    def readyz(self) -> dict[str, object]:
        ready = (
            self.state in {WorkerState.READY, WorkerState.DEGRADED}
            and not self.draining
        )
        return {"ready": ready, "state": self.state.value}

    def status(self) -> dict[str, object]:
        return {
            "worker_state": self.state.value,
            "uptime_s": round(self.uptime_s, 3),
            "draining": self.draining,
            "active_sessions": self.metrics.active_sessions,
            "sessions_started": self.metrics.sessions_started,
            "sessions_completed": self.metrics.sessions_completed,
            "sessions_failed": self.metrics.sessions_failed,
            "last_runtime_error_type": self.last_runtime_error_type,
            "metrics": self.metrics.as_dict(),
        }

    def note_qwen_disconnect(self) -> None:
        self.metrics.note_qwen_disconnect()
        self.mark_degraded("qwen_disconnect")

    def note_qwen_error(self) -> None:
        self.metrics.note_qwen_error()
        self.mark_degraded("qwen_error")

    def note_interruption(self) -> None:
        self.metrics.note_interruption()

    def note_tool_request(self) -> None:
        self.metrics.note_tool_request()

    def note_tool_error(self) -> None:
        self.metrics.note_tool_error()

    def note_tool_timeout(self) -> None:
        self.metrics.note_tool_timeout()

    def note_finish_attempt(self) -> None:
        self.metrics.note_finish_attempt()

    def note_finish_failure(self) -> None:
        self.metrics.note_finish_failure()

    def build_ops_app(self) -> web.Application:
        app = web.Application()

        async def livez(_: web.Request) -> web.Response:
            return web.json_response(self.livez())

        async def readyz(_: web.Request) -> web.Response:
            body = self.readyz()
            return web.json_response(body, status=200 if body["ready"] else 503)

        async def status(_: web.Request) -> web.Response:
            return web.json_response(self.status())

        app.router.add_get("/livez", livez)
        app.router.add_get("/readyz", readyz)
        app.router.add_get("/status", status)
        return app

    def spawn_ops(self, *, host: str = "127.0.0.1", port: int = 8091) -> None:
        if self._ops_task is not None and not self._ops_task.done():
            return
        self._ops_task = asyncio.create_task(
            self.start_ops(host=host, port=port),
            name="voice-ops-http",
        )

    async def start_ops(self, *, host: str = "127.0.0.1", port: int = 8091) -> int:
        if host.strip() == "0.0.0.0":
            host = "127.0.0.1"
        runner = web.AppRunner(self.build_ops_app())
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        self._ops_runner = runner
        self._ops_site = site
        bound = port
        server = getattr(site, "_server", None)
        sockets = getattr(server, "sockets", None) if server is not None else None
        if sockets:
            bound = int(sockets[0].getsockname()[1])
        return bound

    async def aclose_ops(self) -> None:
        task = self._ops_task
        self._ops_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._ops_runner is not None:
            await self._ops_runner.cleanup()
            self._ops_runner = None
            self._ops_site = None

    async def drain_sessions(self) -> None:
        self.begin_drain()
        remaining = self.registry.snapshot_ids()
        await self.registry.drain(timeout_s=self.drain_timeout_s)
        for _session_id in remaining:
            if self.metrics.active_sessions > 0:
                self.metrics.note_session_end("completed", "completed")


def get_worker() -> WorkerRuntime:
    global _worker
    if _worker is None:
        _worker = WorkerRuntime()
    return _worker


def set_worker(worker: WorkerRuntime | None) -> None:
    global _worker
    _worker = worker
