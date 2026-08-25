from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ConfigRevisionSource = Literal["create", "publish", "rollback"]


class InstanceConfigRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    instance_id: UUID
    revision: int = Field(ge=1)
    source: ConfigRevisionSource
    snapshot: dict[str, Any]
    created_at: datetime
