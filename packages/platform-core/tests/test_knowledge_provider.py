from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from platform_core.providers.knowledge.base import KnowledgeChunk
from platform_core.providers.knowledge.fake import FakeKnowledgeProvider
from platform_core.providers.knowledge.mapping import load_mapping
from platform_core.providers.knowledge.ragflow import RagflowProvider
from platform_core.runtime.knowledge import KnowledgeRuntime


def test_load_mapping(tmp_path: Path) -> None:
    path = tmp_path / "mapping.yaml"
    path.write_text(
        """
default_tenant_id: demo-tenant
tenants:
  demo-tenant:
    dataset_ids: ["ds-1"]
    top_k: 3
    similarity_threshold: 0.1
""",
        encoding="utf-8",
    )
    cfg = load_mapping(path)
    mapped = cfg.for_tenant("unknown")
    assert mapped is not None
    assert mapped.dataset_ids == ["ds-1"]
    assert mapped.top_k == 3


@pytest.mark.asyncio
async def test_fake_provider_and_runtime() -> None:
    provider = FakeKnowledgeProvider(
        {
            "demo-tenant": [
                KnowledgeChunk(content="Clinic opens at 9am.", score=0.9, document_name="faq.txt"),
                KnowledgeChunk(content="Parking is free.", score=0.8, document_name="faq.txt"),
            ]
        }
    )
    runtime = KnowledgeRuntime(provider)
    text = await runtime.retrieve_context(question="hours", tenant_id="demo-tenant", top_k=1)
    assert "Clinic opens at 9am." in text
    assert "Parking" not in text


@pytest.mark.asyncio
async def test_ragflow_provider_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/v1/retrieval")
        assert request.headers.get("Authorization") == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "content": "RAGFlow retrieves grounded chunks.",
                            "similarity": 0.77,
                            "document_keyword": "intro.md",
                            "document_id": "doc-1",
                            "kb_id": "ds-1",
                            "id": "c-1",
                        }
                    ]
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        from platform_core.providers.knowledge.mapping import (
            KnowledgeMappingConfig,
            TenantKnowledgeMapping,
        )

        provider = RagflowProvider(
            base_url="http://ragflow.test",
            api_key="test-key",
            mapping=KnowledgeMappingConfig(
                default_tenant_id="demo-tenant",
                tenants={
                    "demo-tenant": TenantKnowledgeMapping(dataset_ids=["ds-1"], top_k=5),
                },
            ),
            client=client,
        )
        chunks = await provider.retrieve(question="what is ragflow", tenant_id="demo-tenant")
        assert len(chunks) == 1
        assert chunks[0].content.startswith("RAGFlow")
        assert chunks[0].score == pytest.approx(0.77)


@pytest.mark.asyncio
async def test_ragflow_provider_unknown_tenant_returns_empty() -> None:
    from platform_core.providers.knowledge.mapping import KnowledgeMappingConfig

    provider = RagflowProvider(
        base_url="http://ragflow.test",
        api_key="test-key",
        mapping=KnowledgeMappingConfig(default_tenant_id=None, tenants={}),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
    )
    chunks = await provider.retrieve(question="x", tenant_id="no-such")
    assert chunks == []
    await provider._client.aclose()
