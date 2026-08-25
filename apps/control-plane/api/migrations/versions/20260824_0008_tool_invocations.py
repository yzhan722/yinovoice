"""Add tool_invocations audit table.

Revision ID: 20260824_0008
Revises: 20260824_0007
Create Date: 2026-08-25

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_0008"
down_revision: str | Sequence[str] | None = "20260824_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("call_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column(
            "arguments_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "result_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="tool_invocations_pkey"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="tool_invocations_tenant_id_uidx",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="tool_invocations_tenant_idempotency_uidx",
        ),
        sa.CheckConstraint(
            "tool_name IN ('check_availability', 'create_appointment', 'create_callback')",
            name="tool_invocations_tool_name_check",
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'error', 'skipped')",
            name="tool_invocations_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="tool_invocations_instance_fkey",
        ),
    )
    op.create_index(
        "tool_invocations_tenant_session_idx",
        "tool_invocations",
        ["tenant_id", "session_id"],
    )
    op.create_index(
        "tool_invocations_tenant_call_record_idx",
        "tool_invocations",
        ["tenant_id", "call_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "tool_invocations_tenant_call_record_idx", table_name="tool_invocations"
    )
    op.drop_index("tool_invocations_tenant_session_idx", table_name="tool_invocations")
    op.drop_table("tool_invocations")
