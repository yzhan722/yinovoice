from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..domain.knowledge import KnowledgeDocument, KnowledgeDocumentCreate


class KnowledgeRepository(Protocol):
    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[KnowledgeDocument]: ...

    async def get(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> KnowledgeDocument | None: ...

    async def create(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        payload: KnowledgeDocumentCreate,
    ) -> KnowledgeDocument: ...

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument: ...

    async def delete(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> bool: ...


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], KnowledgeDocument] = {}

    async def list_for_instance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> list[KnowledgeDocument]:
        items = [
            item
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.instance_id == instance_id
        ]
        items.sort(key=lambda item: (item.created_at, item.id))
        return items

    async def get(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> KnowledgeDocument | None:
        document = self._items.get((tenant_id, document_id))
        if document is None or document.instance_id != instance_id:
            return None
        return document

    async def create(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        payload: KnowledgeDocumentCreate,
    ) -> KnowledgeDocument:
        now = datetime.now(UTC)
        document = KnowledgeDocument(
            id=uuid4(),
            tenant_id=tenant_id,
            instance_id=instance_id,
            title=payload.title,
            body=payload.body,
            created_at=now,
            updated_at=now,
        )
        self._items[(tenant_id, document.id)] = document
        return document

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        stored = document.model_copy(update={"updated_at": datetime.now(UTC)})
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored

    async def delete(
        self,
        document_id: UUID,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> bool:
        existing = await self.get(document_id, tenant_id, instance_id)
        if existing is None:
            return False
        self._items.pop((tenant_id, document_id), None)
        return True
