"""Load voice-agent instance and template YAML from integrations/platform-core."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from platform_core.config.instance import InstanceConfig, TemplateConfig


def find_platform_core_integrations_root() -> Path | None:
    override = os.getenv("PLATFORM_CORE_INTEGRATIONS", "").strip()
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "integrations" / "platform-core"
        if cand.is_dir():
            return cand
        cand2 = parent / "yinoai" / "integrations" / "platform-core"
        if cand2.is_dir():
            return cand2
    return None


def _as_str_map(raw: dict[str, Any] | None) -> dict[str, str]:
    if not raw:
        return {}
    return {str(k): "" if v is None else str(v) for k, v in raw.items()}


def load_template(path: str | Path) -> TemplateConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return TemplateConfig(
        template_id=str(data["template_id"]),
        version=str(data.get("version") or "1.0.0"),
        name=str(data.get("name") or data["template_id"]),
        protected_prompt=str(data.get("protected_prompt") or "").strip(),
        default_tool_ids=[str(x) for x in (data.get("default_tool_ids") or [])],
    )


def load_instance(path: str | Path) -> InstanceConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return InstanceConfig(
        instance_id=str(data["instance_id"]),
        tenant_id=str(data["tenant_id"]),
        template_id=str(data["template_id"]),
        template_version=str(data.get("template_version") or "1.0.0"),
        display_name=str(data.get("display_name") or ""),
        organization_name=str(data.get("organization_name") or ""),
        fields=_as_str_map(data.get("fields")),
        tenant_prompt=str(data.get("tenant_prompt") or "").strip(),
        tool_ids=[str(x) for x in (data.get("tool_ids") or [])],
    )


class InstanceRepository:
    """Filesystem-backed instance lookup by instance_id (e.g. \"1001\")."""

    def __init__(self, root: str | Path | None = None) -> None:
        base = Path(root) if root else find_platform_core_integrations_root()
        if base is None:
            raise FileNotFoundError(
                "integrations/platform-core not found; set PLATFORM_CORE_INTEGRATIONS"
            )
        self.root = base
        self.instances_dir = base / "instances"
        self.templates_dir = base / "templates"

    def get_instance(self, instance_id: str) -> InstanceConfig:
        # Prefer exact demo-1001.yaml style, else scan.
        preferred = self.instances_dir / f"demo-{instance_id}.yaml"
        if preferred.is_file():
            return load_instance(preferred)
        matches = list(self.instances_dir.glob("*.yaml"))
        for path in matches:
            inst = load_instance(path)
            if inst.instance_id == str(instance_id):
                return inst
        raise KeyError(f"instance not found: {instance_id}")

    def get_template(self, template_id: str, version: str) -> TemplateConfig:
        preferred = self.templates_dir / f"{template_id}-{version}.yaml"
        if preferred.is_file():
            return load_template(preferred)
        for path in self.templates_dir.glob(f"{template_id}*.yaml"):
            tpl = load_template(path)
            if tpl.template_id == template_id and tpl.version == version:
                return tpl
        raise KeyError(f"template not found: {template_id}@{version}")
