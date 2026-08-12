from __future__ import annotations

from platform_core.providers.knowledge.base import KnowledgeChunk


class FakeKnowledgeProvider:
    """Deterministic provider for unit tests and local dry-runs."""

    def __init__(self, chunks_by_tenant: dict[str, list[KnowledgeChunk]] | None = None) -> None:
        self._chunks_by_tenant = chunks_by_tenant or {}

    async def retrieve(
        self,
        *,
        question: str,
        tenant_id: str,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeChunk]:
        _ = question, agent_id
        chunks = list(self._chunks_by_tenant.get(tenant_id, []))
        if top_k is not None:
            return chunks[:top_k]
        return chunks
