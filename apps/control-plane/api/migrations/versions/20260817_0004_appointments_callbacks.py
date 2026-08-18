"""Add appointments and callback_tasks tables.

Revision ID: 20260817_0004
Revises: 20260817_0003
Create Date: 2026-08-17

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0004"
down_revision: Union[str, Sequence[str], None] = "20260817_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("call_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("patient_name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Text(),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column(
            "notes",
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
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled')",
            name="appointments_status_check",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'voice_tool', 'import')",
            name="appointments_source_check",
        ),
        sa.CheckConstraint(
            "slot_end >= slot_start",
            name="appointments_slot_order_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="appointments_instance_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="appointments_tenant_id_uidx",
        ),
    )
    op.create_index(
        "appointments_tenant_slot_idx",
        "appointments",
        ["tenant_id", "slot_start"],
    )
    op.create_index(
        "appointments_tenant_status_idx",
        "appointments",
        ["tenant_id", "status"],
    )

    op.create_table(
        "callback_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("call_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("caller_phone", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column(
            "summary",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Text(),
            server_default=sa.text("'manual'"),
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
        sa.CheckConstraint(
            "status IN ('open', 'done', 'cancelled')",
            name="callback_tasks_status_check",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'voice_tool', 'from_call')",
            name="callback_tasks_source_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="callback_tasks_instance_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="callback_tasks_tenant_id_uidx",
        ),
    )
    op.create_index(
        "callback_tasks_tenant_status_created_idx",
        "callback_tasks",
        ["tenant_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "callback_tasks_tenant_status_created_idx",
        table_name="callback_tasks",
    )
    op.drop_table("callback_tasks")
    op.drop_index("appointments_tenant_status_idx", table_name="appointments")
    op.drop_index("appointments_tenant_slot_idx", table_name="appointments")
    op.drop_table("appointments")
