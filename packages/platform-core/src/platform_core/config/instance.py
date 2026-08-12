"""Instance / template config models for voice agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TemplateConfig:
    template_id: str
    version: str
    name: str
    protected_prompt: str
    default_tool_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InstanceConfig:
    instance_id: str
    tenant_id: str
    template_id: str
    template_version: str
    display_name: str
    organization_name: str
    fields: dict[str, str] = field(default_factory=dict)
    tenant_prompt: str = ""
    tool_ids: list[str] = field(default_factory=list)

    @property
    def agent_id(self) -> str:
        return self.instance_id
