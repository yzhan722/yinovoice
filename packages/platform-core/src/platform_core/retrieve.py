"""CLI: python -m platform_core.retrieve --tenant demo --q \"诊所营业时间是什么？\"

Requires env: RAGFLOW_BASE_URL, RAGFLOW_API_KEY, RAGFLOW_MAPPING_FILE.
Unknown / unmapped tenants fail soft (empty context), never raise for missing mapping.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from platform_core.providers.knowledge.ragflow import RagflowProvider
from platform_core.runtime.knowledge import KnowledgeRuntime


async def _run(question: str, tenant_id: str) -> int:
    provider = RagflowProvider.from_env()
    runtime = KnowledgeRuntime(provider)
    try:
        text = await runtime.retrieve_context(question=question, tenant_id=tenant_id)
    finally:
        await provider.aclose()
    sys.stdout.write((text or "(no chunks)") + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve knowledge context via RagflowProvider")
    parser.add_argument("--tenant", default=os.getenv("RAGFLOW_DEMO_TENANT_ID", "demo"))
    parser.add_argument("--q", "--question", dest="question", required=True, help="User question")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.question, args.tenant))


if __name__ == "__main__":
    raise SystemExit(main())
