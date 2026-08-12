"""Turn I/O types for VoiceAgentOrchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingConfirmation:
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str = "requires_confirmation"


@dataclass
class TurnAction:
    type: str
    status: Literal["executed", "pending_confirmation", "blocked", "failed"]
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnInput:
    instance_id: str
    user_text: str
    conversation: list[Message] = field(default_factory=list)
    confirm_tool_call_id: str | None = None


@dataclass
class TurnOutput:
    reply_text: str
    knowledge_used: str = ""
    actions: list[TurnAction] = field(default_factory=list)
    pending_confirmations: list[PendingConfirmation] = field(default_factory=list)
    system_prompt: str = ""
