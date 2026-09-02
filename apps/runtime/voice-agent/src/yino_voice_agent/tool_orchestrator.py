from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from .call_lifecycle import CallLifecycleClient
from .conversation import ConversationDirector, ConversationEvent, ConversationPhase
from .session_trace import SessionTrace
from .tool_client import ToolInvocationClient
from .tool_protocol import SpokenTurn, split_assistant_final
from .transcript_filter import FinalTranscriptGate


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
        conversation: ConversationDirector | None = None,
    ) -> None:
        self._tools = tools
        self._lifecycle = lifecycle
        self._session_id = session_id
        self._instance_id = voice_agent_instance_id
        self._trace = trace
        self._conversation = conversation
        self._sequence = 0
        self._seen_markers: set[str] = set()
        self._closed = False
        self._tasks: set[asyncio.Task[Any]] = set()
        self._transcripts = FinalTranscriptGate()

    def mark_closed(self) -> None:
        self._closed = True
        if self._trace is not None:
            self._trace.mark("session_close")
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

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

    async def handle_user_final(self, text: str, *, item_id: str | None = None) -> None:
        spoken = (text or "").strip()
        if not self._transcripts.accept(spoken, item_id):
            return
        if self._lifecycle is None or self._closed:
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
            await self._lifecycle.append_final("assistant", turn.spoken, self._sequence)
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
            if self._closed or (
                self._conversation is not None
                and self._conversation.phase
                in {ConversationPhase.CLOSING, ConversationPhase.CLOSED}
            ):
                return turn
            if self._conversation is not None:
                self._conversation.handle(ConversationEvent.TOOL_REQUEST)
            invoke_task = self.spawn(
                self._tools.invoke(
                    session_id=self._session_id,
                    tool_name=turn.marker.tool_name,
                    arguments=arguments,
                    voice_agent_instance_id=self._instance_id,
                    call_record_id=call_record_id,
                    idempotency_key=f"{self._session_id}:{turn.marker.raw}",
                )
            )
            try:
                result = await invoke_task
            except asyncio.CancelledError:
                if self._closed:
                    return turn
                raise
            if self._conversation is not None:
                self._conversation.handle(
                    ConversationEvent.TOOL_RESULT,
                    success=_tool_invocation_succeeded(result),
                )
            return turn
        return turn


def _tool_invocation_succeeded(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    if status == "error" or result.get("code") in {
        "retryable_transport",
        "platform_error",
        "unknown_tool",
        "invalid_arguments",
    }:
        return False
    return status in {"ok", "success"}
