from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

KNOWLEDGE_START = "<!-- yino-knowledge-start -->"
KNOWLEDGE_END = "<!-- yino-knowledge-end -->"

_BLOCK_PATTERN = re.compile(
    re.escape(KNOWLEDGE_START) + r".*?" + re.escape(KNOWLEDGE_END),
    re.DOTALL,
)


def compile_knowledge_block(documents: Sequence[Any]) -> str:
    parts: list[str] = []
    for item in documents:
        title, body = _title_body(item)
        parts.append(f"## {title}\n{body}")
    inner = "\n\n".join(parts).strip()
    if not inner:
        return f"{KNOWLEDGE_START}\n{KNOWLEDGE_END}"
    return f"{KNOWLEDGE_START}\n{inner}\n{KNOWLEDGE_END}"


def apply_knowledge_block(tenant_prompt: str, block: str) -> str:
    if _BLOCK_PATTERN.search(tenant_prompt):
        return _BLOCK_PATTERN.sub(block, tenant_prompt, count=1)
    stripped = tenant_prompt.rstrip()
    if not stripped:
        return block
    return stripped + "\n\n" + block


def _title_body(item: Any) -> tuple[str, str]:
    if isinstance(item, Mapping):
        return str(item["title"]).strip(), str(item["body"]).strip()
    return str(item.title).strip(), str(item.body).strip()
