from __future__ import annotations

from platform_core.providers.knowledge.base import KnowledgeChunk, KnowledgeProvider


class KnowledgeRuntime:
    """Formats retrieved chunks for Model context injection."""

    def __init__(self, provider: KnowledgeProvider) -> None:
        self._provider = provider

    async def retrieve_context(
        self,
        *,
        question: str,
        tenant_id: str,
        agent_id: str | None = None,
        top_k: int | None = None,
        max_chars: int = 4000,
    ) -> str:
        chunks = await self._provider.retrieve(
            question=question,
            tenant_id=tenant_id,
            agent_id=agent_id,
            top_k=top_k,
        )
        return self.format_context(chunks, max_chars=max_chars)

    @staticmethod
    def format_context(chunks: list[KnowledgeChunk], *, max_chars: int = 4000) -> str:
        if not chunks:
            return ""
        parts: list[str] = []
        used = 0
        for idx, chunk in enumerate(chunks, start=1):
            header = f"[{idx}] {chunk.document_name or 'document'} (score={chunk.score:.3f})"
            block = f"{header}\n{chunk.content.strip()}"
            if used and used + len(block) + 2 > max_chars:
                break
            parts.append(block)
            used += len(block) + 2
        return "\n\n".join(parts)
