"""Add SIP recording keys, notification settings and events.

Revision ID: 20260824_0009
Revises: 20260824_0008
Create Date: 2026-08-25

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_0009"
down_revision: str | Sequence[str] | None = "20260824_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column("recording_egress_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "call_records",
        sa.Column("recording_object_key", sa.Text(), nullable=True),
    )
    op.create_table(
        "notification_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "email",
            sa.String(length=200),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="notification_settings_pkey"),
    )
    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "detail",
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
        sa.PrimaryKeyConstraint("id", name="notification_events_pkey"),
        sa.CheckConstraint(
            "status IN ('sent', 'failed')",
            name="notification_events_status_check",
        ),
    )
    op.create_index(
        "notification_events_tenant_created_idx",
        "notification_events",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "notification_events_tenant_created_idx",
        table_name="notification_events",
    )
    op.drop_table("notification_events")
    op.drop_table("notification_settings")
    op.drop_column("call_records", "recording_object_key")
    op.drop_column("call_records", "recording_egress_id")
