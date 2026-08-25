"""Allow in-progress call records and SIP session fields.

Revision ID: 20260824_0006
Revises: 20260824_0005
Create Date: 2026-08-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0006"
down_revision: str | Sequence[str] | None = "20260824_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("call_records_status_check", "call_records", type_="check")
    op.create_check_constraint(
        "call_records_status_check",
        "call_records",
        "status IN ('in_progress', 'completed', 'interrupted', 'failed')",
    )
    op.drop_constraint("call_records_ended_at_check", "call_records", type_="check")
    op.alter_column("call_records", "ended_at", existing_nullable=False, nullable=True)
    op.alter_column(
        "call_records",
        "duration_sec",
        existing_nullable=False,
        nullable=True,
    )
    op.create_check_constraint(
        "call_records_ended_at_check",
        "call_records",
        "("
        "status = 'in_progress' AND ended_at IS NULL AND duration_sec IS NULL"
        ") OR ("
        "status <> 'in_progress' AND ended_at IS NOT NULL "
        "AND duration_sec IS NOT NULL AND ended_at >= started_at"
        ")",
    )
    op.add_column("call_records", sa.Column("caller_number", sa.Text(), nullable=True))
    op.add_column("call_records", sa.Column("callee_number", sa.Text(), nullable=True))
    op.add_column(
        "call_records",
        sa.Column("provider_call_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "call_records",
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("call_records", sa.Column("ended_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "call_records_ended_reason_check",
        "call_records",
        "ended_reason IS NULL OR ended_reason IN "
        "('completed', 'user_hangup', 'agent_error')",
    )
    op.create_index(
        "call_records_tenant_provider_call_uidx",
        "call_records",
        ["tenant_id", "provider_call_id"],
        unique=True,
        postgresql_where=sa.text(
            "provider_call_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "call_records_tenant_room_in_progress_uidx",
        "call_records",
        ["tenant_id", "room_name"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "call_records_tenant_room_in_progress_uidx",
        table_name="call_records",
    )
    op.drop_index(
        "call_records_tenant_provider_call_uidx",
        table_name="call_records",
    )
    op.drop_constraint(
        "call_records_ended_reason_check",
        "call_records",
        type_="check",
    )
    op.drop_column("call_records", "ended_reason")
    op.drop_column("call_records", "connected_at")
    op.drop_column("call_records", "provider_call_id")
    op.drop_column("call_records", "callee_number")
    op.drop_column("call_records", "caller_number")
    op.drop_constraint("call_records_ended_at_check", "call_records", type_="check")
    op.alter_column(
        "call_records",
        "duration_sec",
        existing_nullable=True,
        nullable=False,
    )
    op.alter_column("call_records", "ended_at", existing_nullable=True, nullable=False)
    op.create_check_constraint(
        "call_records_ended_at_check",
        "call_records",
        "ended_at >= started_at",
    )
    op.drop_constraint("call_records_status_check", "call_records", type_="check")
    op.create_check_constraint(
        "call_records_status_check",
        "call_records",
        "status IN ('completed', 'interrupted', 'failed')",
    )
