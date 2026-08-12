"""Model provider protocol for text turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from platform_core.runtime.turn import Message, ToolCallRequest
from platform_core.tools.base import ToolSpec


@dataclass
class ModelRequest:
    system_prompt: str
    messages: list[Message]
    tools: list[ToolSpec] = field(default_factory=list)
    user_text: str = ""
    knowledge_block: str = ""
    confirm_tool_call_id: str | None = None


@dataclass
class ModelResponse:
    reply_text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)


class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
