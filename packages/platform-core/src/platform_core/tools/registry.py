"""Tool registry keyed by tool name."""

from __future__ import annotations

from platform_core.tools.base import Tool, ToolSpec
from platform_core.tools.booking import BookingTool
from platform_core.tools.handoff import HandoffTool


def default_tools() -> dict[str, Tool]:
    booking = BookingTool()
    handoff = HandoffTool()
    return {booking.spec.name: booking, handoff.spec.name: handoff}


class ToolRegistry:
    def __init__(self, tools: dict[str, Tool] | None = None) -> None:
        self._tools = tools or default_tools()

    def resolve(self, names: list[str]) -> list[Tool]:
        out: list[Tool] = []
        for name in names:
            tool = self._tools.get(name)
            if tool is not None:
                out.append(tool)
        return out

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs_for(self, names: list[str]) -> list[ToolSpec]:
        return [t.spec for t in self.resolve(names)]
