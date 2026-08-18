"""PostgreSQL adapter for CallbackTaskRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import CallbackTaskRow
from ...domain.callback_task import CallbackTask


def _to_domain(row: CallbackTaskRow) -> CallbackTask:
    return CallbackTask(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        call_record_id=row.call_record_id,
        caller_phone=row.caller_phone,
        reason=row.reason,
        summary=row.summary,
        status=row.status,  # type: ignore[arg-type]
        source=row.source,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresCallbackTaskRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        include_cancelled: bool = False,
    ) -> tuple[list[CallbackTask], int]:
        async with self._sessions() as session:
            filters = [CallbackTaskRow.tenant_id == tenant_id]
            if status is not None:
                filters.append(CallbackTaskRow.status == status)
            elif not include_cancelled:
                filters.append(CallbackTaskRow.status != "cancelled")
            total = await session.scalar(
                select(func.count()).select_from(CallbackTaskRow).where(*filters)
            )
            rows = (
                await session.scalars(
                    select(CallbackTaskRow)
                    .where(*filters)
                    .order_by(
                        CallbackTaskRow.created_at.desc(),
                        CallbackTaskRow.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [_to_domain(row) for row in rows], int(total or 0)

    async def get(
        self, task_id: UUID, tenant_id: UUID
    ) -> CallbackTask | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallbackTaskRow).where(
                    CallbackTaskRow.tenant_id == tenant_id,
                    CallbackTaskRow.id == task_id,
                )
            )
            return _to_domain(row) if row is not None else None

    async def find_by_call_record_id(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> CallbackTask | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallbackTaskRow)
                .where(
                    CallbackTaskRow.tenant_id == tenant_id,
                    CallbackTaskRow.call_record_id == call_record_id,
                )
                .order_by(CallbackTaskRow.created_at.asc(), CallbackTaskRow.id.asc())
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def create(self, task: CallbackTask) -> CallbackTask:
        async with self._sessions() as session:
            session.add(
                CallbackTaskRow(
                    id=task.id,
                    tenant_id=task.tenant_id,
                    voice_agent_instance_id=task.voice_agent_instance_id,
                    call_record_id=task.call_record_id,
                    caller_phone=task.caller_phone,
                    reason=task.reason,
                    summary=task.summary,
                    status=task.status,
                    source=task.source,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
            )
            await session.commit()
            return task

    async def save(self, task: CallbackTask) -> CallbackTask:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallbackTaskRow).where(
                    CallbackTaskRow.tenant_id == task.tenant_id,
                    CallbackTaskRow.id == task.id,
                )
            )
            if row is None:
                return await self.create(task)
            row.caller_phone = task.caller_phone
            row.reason = task.reason
            row.summary = task.summary
            row.status = task.status
            row.voice_agent_instance_id = task.voice_agent_instance_id
            row.call_record_id = task.call_record_id
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)
