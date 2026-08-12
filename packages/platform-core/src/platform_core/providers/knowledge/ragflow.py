from __future__ import annotations

import os
from typing import Any

import httpx

from platform_core.providers.knowledge.base import KnowledgeChunk
from platform_core.providers.knowledge.mapping import KnowledgeMappingConfig, load_mapping


class RagflowProvider:
    """HTTP KnowledgeProvider backed by RAGFlow POST /api/v1/retrieval."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        mapping: KnowledgeMappingConfig,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._mapping = mapping
        self._timeout = timeout_seconds
        self._client = client
        self._owns_client = client is None

    @classmethod
    def from_env(cls, *, client: httpx.AsyncClient | None = None) -> "RagflowProvider":
        base_url = os.getenv("RAGFLOW_BASE_URL", "").strip()
        api_key = os.getenv("RAGFLOW_API_KEY", "").strip()
        mapping_file = os.getenv("RAGFLOW_MAPPING_FILE", "").strip()
        timeout = float(os.getenv("RAGFLOW_TIMEOUT_SECONDS", "15"))
        missing = [n for n, v in {
            "RAGFLOW_BASE_URL": base_url,
            "RAGFLOW_API_KEY": api_key,
            "RAGFLOW_MAPPING_FILE": mapping_file,
        }.items() if not v]
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
        return cls(
            base_url=base_url,
            api_key=api_key,
            mapping=load_mapping(mapping_file),
            timeout_seconds=timeout,
            client=client,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def retrieve(
        self,
        *,
        question: str,
        tenant_id: str,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeChunk]:
        _ = agent_id
        mapped = self._mapping.for_tenant(tenant_id)
        if mapped is None or not mapped.dataset_ids:
            return []

        base_url = (mapped.base_url or self._base_url).rstrip("/")
        api_key = mapped.api_key or self._api_key
        k = top_k if top_k is not None else mapped.top_k
        payload: dict[str, Any] = {
            "question": question,
            "dataset_ids": mapped.dataset_ids,
            "top_k": k,
            "similarity_threshold": mapped.similarity_threshold,
        }
        client = await self._get_client()
        response = await client.post(
            f"{base_url}/api/v1/retrieval",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        raw_chunks = []
        if isinstance(data, dict):
            raw_chunks = data.get("chunks") or []
        elif isinstance(data, list):
            raw_chunks = data

        chunks: list[KnowledgeChunk] = []
        for item in raw_chunks:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("content_with_weight") or "")
            if not content:
                continue
            score_raw = item.get("similarity", item.get("score", 0.0))
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0
            chunks.append(
                KnowledgeChunk(
                    content=content,
                    score=score,
                    document_name=str(item.get("document_keyword") or item.get("document_name") or ""),
                    document_id=str(item.get("document_id") or ""),
                    dataset_id=str(item.get("kb_id") or item.get("dataset_id") or ""),
                    chunk_id=str(item.get("id") or item.get("chunk_id") or ""),
                )
            )
        return chunks[:k]
