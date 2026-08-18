"""Add soft-delete column to voice_agent_instances.

Revision ID: 20260817_0003
Revises: 20260813_0002
Create Date: 2026-08-17

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0003"
down_revision: Union[str, Sequence[str], None] = "20260813_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "voice_agent_instances",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "voice_agent_instances_tenant_deleted_idx",
        "voice_agent_instances",
        ["tenant_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "voice_agent_instances_tenant_deleted_idx",
        table_name="voice_agent_instances",
    )
    op.drop_column("voice_agent_instances", "deleted_at")
