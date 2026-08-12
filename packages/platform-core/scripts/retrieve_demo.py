"""Dry-run retrieve against a live RAGFlow (requires env + mapping)."""

from __future__ import annotations

import asyncio
import os
import sys

from platform_core.providers.knowledge.ragflow import RagflowProvider
from platform_core.runtime.knowledge import KnowledgeRuntime


async def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or "诊所营业时间是什么？"
    tenant_id = os.getenv("RAGFLOW_DEMO_TENANT_ID", "demo-tenant")
    provider = RagflowProvider.from_env()
    runtime = KnowledgeRuntime(provider)
    try:
        text = await runtime.retrieve_context(question=question, tenant_id=tenant_id)
    finally:
        await provider.aclose()
    print(text or "(no chunks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
