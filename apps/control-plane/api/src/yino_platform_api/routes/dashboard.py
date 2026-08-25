from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from ..dependencies import TenantId
from ..repositories.appointments import AppointmentRepository
from ..repositories.call_records import CallRecordRepository
from ..repositories.callback_tasks import CallbackTaskRepository


def create_router(
    appointments: AppointmentRepository,
    callbacks: CallbackTaskRepository,
    call_records: CallRecordRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/dashboard")

    @router.get("/summary")
    async def summary(tenant_id: TenantId) -> dict[str, object]:
        now = datetime.now(UTC)
        today = now.date()
        apt_items, _ = await appointments.list_for_tenant(
            tenant_id, limit=100, offset=0, include_cancelled=True
        )
        cb_items, _ = await callbacks.list_for_tenant(
            tenant_id, limit=100, offset=0, include_cancelled=True
        )
        calls, _ = await call_records.list_for_tenant(
            tenant_id, limit=100, offset=0
        )
        today_apts = [
            item
            for item in apt_items
            if item.status != "cancelled" and item.slot_start.date() == today
        ]
        pending = [item for item in apt_items if item.status == "pending"]
        open_cb = [item for item in cb_items if item.status == "open"]
        today_calls = [item for item in calls if item.started_at.date() == today]
        connected = [
            item
            for item in today_calls
            if item.status in {"completed", "interrupted", "in_progress"}
        ]
        trend = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = sum(1 for item in calls if item.started_at.date() == day)
            minutes = sum(
                (item.duration_sec or 0)
                for item in calls
                if item.started_at.date() == day
            )
            trend.append(
                {
                    "date": day.isoformat(),
                    "count": count,
                    "minutes": round(minutes / 60, 1),
                }
            )
        return {
            "callbacks": {"open": len(open_cb), "delta": 0},
            "appointments": {
                "today": len(today_apts),
                "week": len(
                    [
                        item
                        for item in apt_items
                        if item.status != "cancelled"
                        and item.slot_start.date() >= today - timedelta(days=7)
                    ]
                ),
                "pendingConfirm": len(pending),
            },
            "followUps": {
                "todo": len(open_cb),
                "doing": 0,
                "done": sum(1 for item in cb_items if item.status == "done"),
            },
            "callStats": {
                "todayCount": len(today_calls),
                "connectedToday": len(connected),
                "effectiveToday": len(
                    [item for item in today_calls if item.status == "completed"]
                ),
                "todayMinutes": round(
                    sum((item.duration_sec or 0) for item in today_calls) / 60, 1
                ),
                "trend": trend,
            },
        }

    return router
