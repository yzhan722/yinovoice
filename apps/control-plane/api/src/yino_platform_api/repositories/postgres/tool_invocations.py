"""PostgreSQL adapter for ToolInvocationRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import ToolInvocationRow
from ...domain.tool_invocation import ToolInvocation


def _to_domain(row: ToolInvocationRow) -> ToolInvocation:
    return ToolInvocation(
        id=row.id,
        tenant_id=row.tenant_id,
        session_id=row.session_id,
        call_record_id=row.call_record_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        tool_name=row.tool_name,  # type: ignore[arg-type]
        arguments=dict(row.arguments_json or {}),
        status=row.status,  # type: ignore[arg-type]
        result=dict(row.result_json or {}),
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
    )


class PostgresToolInvocationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(
        self, invocation_id: UUID, tenant_id: UUID
    ) -> ToolInvocation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ToolInvocationRow).where(
                    ToolInvocationRow.tenant_id == tenant_id,
                    ToolInvocationRow.id == invocation_id,
                )
            )
            return _to_domain(row) if row is not None else None

    async def find_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> ToolInvocation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ToolInvocationRow).where(
                    ToolInvocationRow.tenant_id == tenant_id,
                    ToolInvocationRow.idempotency_key == idempotency_key,
                )
            )
            return _to_domain(row) if row is not None else None

    async def list_for_session(
        self, tenant_id: UUID, session_id: str
    ) -> list[ToolInvocation]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ToolInvocationRow)
                    .where(
                        ToolInvocationRow.tenant_id == tenant_id,
                        ToolInvocationRow.session_id == session_id,
                    )
                    .order_by(
                        ToolInvocationRow.created_at.asc(),
                        ToolInvocationRow.id.asc(),
                    )
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def list_for_call_record(
        self, tenant_id: UUID, call_record_id: UUID
    ) -> list[ToolInvocation]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ToolInvocationRow)
                    .where(
                        ToolInvocationRow.tenant_id == tenant_id,
                        ToolInvocationRow.call_record_id == call_record_id,
                    )
                    .order_by(
                        ToolInvocationRow.created_at.asc(),
                        ToolInvocationRow.id.asc(),
                    )
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def create(self, item: ToolInvocation) -> ToolInvocation:
        async with self._sessions() as session:
            session.add(
                ToolInvocationRow(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    session_id=item.session_id,
                    call_record_id=item.call_record_id,
                    voice_agent_instance_id=item.voice_agent_instance_id,
                    tool_name=item.tool_name,
                    arguments_json=item.arguments,
                    status=item.status,
                    result_json=item.result,
                    idempotency_key=item.idempotency_key,
                    created_at=item.created_at,
                )
            )
            await session.commit()
            return item

    async def save(self, item: ToolInvocation) -> ToolInvocation:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ToolInvocationRow).where(
                    ToolInvocationRow.tenant_id == item.tenant_id,
                    ToolInvocationRow.id == item.id,
                )
            )
            if row is None:
                return await self.create(item)
            row.session_id = item.session_id
            row.call_record_id = item.call_record_id
            row.voice_agent_instance_id = item.voice_agent_instance_id
            row.tool_name = item.tool_name
            row.arguments_json = item.arguments
            row.status = item.status
            row.result_json = item.result
            row.idempotency_key = item.idempotency_key
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)

    async def bind_call_record(
        self, tenant_id: UUID, session_id: str, call_record_id: UUID
    ) -> int:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ToolInvocationRow).where(
                        ToolInvocationRow.tenant_id == tenant_id,
                        ToolInvocationRow.session_id == session_id,
                        ToolInvocationRow.call_record_id.is_(None),
                    )
                )
            ).all()
            for row in rows:
                row.call_record_id = call_record_id
            await session.commit()
            return len(rows)
