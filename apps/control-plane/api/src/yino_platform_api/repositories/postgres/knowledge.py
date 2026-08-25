"""PostgreSQL adapter for KnowledgeRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import KnowledgeDocumentRow
from ...domain.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentCreate,
)


def _to_domain(row: KnowledgeDocumentRow) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=row.id,
        tenant_id=row.tenant_id,
        instance_id=row.instance_id,
        title=row.title,
        body=row.body,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresKnowledgeRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[KnowledgeDocument]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(KnowledgeDocumentRow)
                    .where(
                        KnowledgeDocumentRow.tenant_id == tenant_id,
                        KnowledgeDocumentRow.instance_id == instance_id,
                    )
                    .order_by(
                        KnowledgeDocumentRow.created_at.asc(),
                        KnowledgeDocumentRow.id.asc(),
                    )
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def get(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> KnowledgeDocument | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(KnowledgeDocumentRow).where(
                    KnowledgeDocumentRow.tenant_id == tenant_id,
                    KnowledgeDocumentRow.id == document_id,
                    KnowledgeDocumentRow.instance_id == instance_id,
                )
            )
            return _to_domain(row) if row is not None else None

    async def create(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        payload: KnowledgeDocumentCreate,
    ) -> KnowledgeDocument:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            row = KnowledgeDocumentRow(
                id=uuid4(),
                tenant_id=tenant_id,
                instance_id=instance_id,
                title=payload.title,
                body=payload.body,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        async with self._sessions() as session:
            row = await session.scalar(
                select(KnowledgeDocumentRow).where(
                    KnowledgeDocumentRow.tenant_id == document.tenant_id,
                    KnowledgeDocumentRow.id == document.id,
                    KnowledgeDocumentRow.instance_id == document.instance_id,
                )
            )
            if row is None:
                raise LookupError("knowledge document not found")
            row.title = document.title
            row.body = document.body
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)

    async def delete(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(KnowledgeDocumentRow).where(
                    KnowledgeDocumentRow.tenant_id == tenant_id,
                    KnowledgeDocumentRow.id == document_id,
                    KnowledgeDocumentRow.instance_id == instance_id,
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
