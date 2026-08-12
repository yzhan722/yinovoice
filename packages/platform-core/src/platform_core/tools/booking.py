"""Demo booking tool — never silently succeeds without confirmation (policy)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from platform_core.tools.base import ToolResult, ToolSpec


class BookingTool:
    spec = ToolSpec(
        name="booking",
        description="为来电者创建或确认预约意向（演示空档）。",
        requires_confirmation=True,
    )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        slot = str(arguments.get("slot") or arguments.get("preferred_time") or "待定时段")
        patient = str(arguments.get("patient_name") or "来电者")
        booking_id = f"bk-{uuid4().hex[:8]}"
        return ToolResult(
            ok=True,
            message=f"已为{patient}登记预约意向 {slot}，编号 {booking_id}。工作人员会再确认。",
            data={"booking_id": booking_id, "slot": slot, "patient_name": patient},
        )
