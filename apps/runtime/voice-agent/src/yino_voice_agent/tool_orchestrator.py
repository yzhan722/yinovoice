from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from .call_lifecycle import CallLifecycleClient
from .session_trace import SessionTrace
from .tool_client import ToolInvocationClient
from .tool_protocol import SpokenTurn, split_assistant_final


class ToolOrchestrator:
    """Strip hidden tool markers from assistant finals and invoke Control Plane."""

    def __init__(
        self,
        *,
        tools: ToolInvocationClient | None,
        lifecycle: CallLifecycleClient | None,
        session_id: str,
        voice_agent_instance_id: UUID | None,
        trace: SessionTrace | None = None,
    ) -> None:
        self._tools = tools
        self._lifecycle = lifecycle
        self._session_id = session_id
        self._instance_id = voice_agent_instance_id
        self._trace = trace
        self._sequence = 0
        self._seen_markers: set[str] = set()
        self._closed = False
        self._tasks: set[asyncio.Task[Any]] = set()

    def mark_closed(self) -> None:
        self._closed = True
        if self._trace is not None:
            self._trace.mark("session_close")

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def wait_idle(self) -> None:
        pending = list(self._tasks)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def prepare_assistant_final(self, text: str) -> SpokenTurn:
        return split_assistant_final(text)

    async def handle_user_final(self, text: str) -> None:
        spoken = (text or "").strip()
        if not spoken or self._lifecycle is None or self._closed:
            return
        if self._trace is not None:
            self._trace.mark("first_user_transcript")
        self._sequence += 1
        await self._lifecycle.append_final("user", spoken, self._sequence)

    async def handle_assistant_final(self, text: str) -> SpokenTurn:
        turn = split_assistant_final(text)
        if self._closed:
            return turn
        if self._lifecycle is not None and turn.spoken:
            if self._trace is not None:
                self._trace.mark("assistant_response_start")
            self._sequence += 1
            await self._lifecycle.append_final(
                "assistant", turn.spoken, self._sequence
            )
        if (
            turn.marker is not None
            and self._tools is not None
            and turn.marker.raw not in self._seen_markers
        ):
            self._seen_markers.add(turn.marker.raw)
            arguments = dict(turn.marker.arguments)
            call_record_id = (
                self._lifecycle.record_id if self._lifecycle is not None else None
            )
            await self._tools.invoke(
                session_id=self._session_id,
                tool_name=turn.marker.tool_name,
                arguments=arguments,
                voice_agent_instance_id=self._instance_id,
                call_record_id=call_record_id,
                idempotency_key=f"{self._session_id}:{turn.marker.raw}",
            )
        return turn
