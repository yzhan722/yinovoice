from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KnowledgeChunk:
    content: str
    score: float
    document_name: str = ""
    document_id: str = ""
    dataset_id: str = ""
    chunk_id: str = ""


class KnowledgeProvider(Protocol):
    async def retrieve(
        self,
        *,
        question: str,
        tenant_id: str,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeChunk]: ...
