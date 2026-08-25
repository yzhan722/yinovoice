"""PostgreSQL adapter for ConfigRevisionRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import InstanceConfigRevisionRow
from ...domain.config_revision import InstanceConfigRevision


def _to_domain(row: InstanceConfigRevisionRow) -> InstanceConfigRevision:
    return InstanceConfigRevision(
        id=row.id,
        tenant_id=row.tenant_id,
        instance_id=row.instance_id,
        revision=row.revision,
        source=row.source,  # type: ignore[arg-type]
        snapshot=dict(row.snapshot),
        created_at=row.created_at,
    )


class PostgresConfigRevisionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[InstanceConfigRevision]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(InstanceConfigRevisionRow)
                    .where(
                        InstanceConfigRevisionRow.tenant_id == tenant_id,
                        InstanceConfigRevisionRow.instance_id == instance_id,
                    )
                    .order_by(InstanceConfigRevisionRow.revision.desc())
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def get_by_revision(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        revision: int,
    ) -> InstanceConfigRevision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InstanceConfigRevisionRow).where(
                    InstanceConfigRevisionRow.tenant_id == tenant_id,
                    InstanceConfigRevisionRow.instance_id == instance_id,
                    InstanceConfigRevisionRow.revision == revision,
                )
            )
            return _to_domain(row) if row is not None else None

    async def latest(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> InstanceConfigRevision | None:
        items = await self.list_for_instance(tenant_id, instance_id)
        return items[0] if items else None

    async def add(
        self, revision: InstanceConfigRevision
    ) -> InstanceConfigRevision:
        async with self._sessions() as session:
            row = InstanceConfigRevisionRow(
                id=revision.id,
                tenant_id=revision.tenant_id,
                instance_id=revision.instance_id,
                revision=revision.revision,
                source=revision.source,
                snapshot=revision.snapshot,
                created_at=revision.created_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)
