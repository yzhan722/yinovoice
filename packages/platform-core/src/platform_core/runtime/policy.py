"""Platform policy gates for tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from platform_core.runtime.turn import ToolCallRequest


Decision = Literal["execute", "require_confirmation", "block"]


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    requires_confirmation: bool = False
    allow_without_confirm_on_emergency: bool = False


DEFAULT_TOOL_POLICIES: dict[str, ToolPolicy] = {
    "booking": ToolPolicy(name="booking", requires_confirmation=True),
    "handoff": ToolPolicy(
        name="handoff",
        requires_confirmation=False,
        allow_without_confirm_on_emergency=True,
    ),
}

_EMERGENCY_HINTS = ("转人工", "人工", "急救", "出血不止", "呼吸困难", "胸痛")


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str


class PlatformPolicy:
    def __init__(self, policies: dict[str, ToolPolicy] | None = None) -> None:
        self._policies = policies or DEFAULT_TOOL_POLICIES

    def decide(
        self,
        call: ToolCallRequest,
        *,
        user_text: str,
        confirmed_ids: set[str] | None = None,
    ) -> PolicyDecision:
        confirmed_ids = confirmed_ids or set()
        policy = self._policies.get(call.name)
        if policy is None:
            return PolicyDecision("block", f"unknown tool: {call.name}")
        if call.id in confirmed_ids:
            return PolicyDecision("execute", "user confirmed")
        if policy.requires_confirmation:
            if policy.allow_without_confirm_on_emergency and self._looks_emergency(user_text):
                return PolicyDecision("execute", "emergency bypass")
            return PolicyDecision("require_confirmation", "write tool needs confirmation")
        return PolicyDecision("execute", "allowed")

    @staticmethod
    def _looks_emergency(user_text: str) -> bool:
        text = user_text or ""
        return any(h in text for h in _EMERGENCY_HINTS)
