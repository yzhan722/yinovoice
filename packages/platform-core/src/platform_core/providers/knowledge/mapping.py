from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TenantKnowledgeMapping:
    dataset_ids: list[str]
    base_url: str | None = None
    api_key: str | None = None
    top_k: int = 5
    similarity_threshold: float = 0.2


@dataclass(frozen=True)
class KnowledgeMappingConfig:
    default_tenant_id: str | None
    tenants: dict[str, TenantKnowledgeMapping]

    def for_tenant(self, tenant_id: str) -> TenantKnowledgeMapping | None:
        if tenant_id in self.tenants:
            return self.tenants[tenant_id]
        if self.default_tenant_id and self.default_tenant_id in self.tenants:
            return self.tenants[self.default_tenant_id]
        return None


def load_mapping(path: str | Path) -> KnowledgeMappingConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    tenants_raw = data.get("tenants") or {}
    tenants: dict[str, TenantKnowledgeMapping] = {}
    for tenant_id, raw in tenants_raw.items():
        tenants[str(tenant_id)] = TenantKnowledgeMapping(
            dataset_ids=[str(x) for x in (raw.get("dataset_ids") or [])],
            base_url=raw.get("base_url"),
            api_key=raw.get("api_key"),
            top_k=int(raw.get("top_k", 5)),
            similarity_threshold=float(raw.get("similarity_threshold", 0.2)),
        )
    return KnowledgeMappingConfig(
        default_tenant_id=data.get("default_tenant_id"),
        tenants=tenants,
    )
