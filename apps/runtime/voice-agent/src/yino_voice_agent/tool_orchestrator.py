from __future__ import annotations

from uuid import UUID

from .call_lifecycle import CallLifecycleClient
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
    ) -> None:
        self._tools = tools
        self._lifecycle = lifecycle
        self._session_id = session_id
        self._instance_id = voice_agent_instance_id
        self._sequence = 0
        self._seen_markers: set[str] = set()

    def prepare_assistant_final(self, text: str) -> SpokenTurn:
        return split_assistant_final(text)

    async def handle_user_final(self, text: str) -> None:
        spoken = (text or "").strip()
        if not spoken or self._lifecycle is None:
            return
        self._sequence += 1
        await self._lifecycle.append_final("user", spoken, self._sequence)

    async def handle_assistant_final(self, text: str) -> SpokenTurn:
        turn = split_assistant_final(text)
        if self._lifecycle is not None and turn.spoken:
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
            )
        return turn
