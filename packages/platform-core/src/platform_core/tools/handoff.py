"""Human handoff / callback stub."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from platform_core.tools.base import ToolResult, ToolSpec


class HandoffTool:
    spec = ToolSpec(
        name="handoff",
        description="将来电转交人工或创建回拨任务。",
        requires_confirmation=False,
    )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        reason = str(arguments.get("reason") or "用户请求人工")
        task_id = f"cb-{uuid4().hex[:8]}"
        return ToolResult(
            ok=True,
            message=f"已创建转人工/回拨任务 {task_id}：{reason}",
            data={"callback_task_id": task_id, "reason": reason},
        )
