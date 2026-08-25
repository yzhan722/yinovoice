"""Add insights_profile and insights dispatch queue.

Revision ID: 20260825_0010
Revises: 20260824_0009
Create Date: 2026-08-25

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0010"
down_revision: str | Sequence[str] | None = "20260824_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "voice_agent_instances",
        sa.Column("insights_profile", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "insights_dispatch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_error",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="insights_dispatch_jobs_pkey"),
        sa.UniqueConstraint("call_id", name="insights_dispatch_jobs_call_id_uidx"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="insights_dispatch_jobs_status_check",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="insights_dispatch_jobs_attempts_check",
        ),
    )
    op.create_index(
        "insights_dispatch_jobs_due_idx",
        "insights_dispatch_jobs",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "insights_dispatch_jobs_due_idx",
        table_name="insights_dispatch_jobs",
    )
    op.drop_table("insights_dispatch_jobs")
    op.drop_column("voice_agent_instances", "insights_profile")
