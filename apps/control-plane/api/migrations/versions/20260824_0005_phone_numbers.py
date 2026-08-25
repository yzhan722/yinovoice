"""Add phone_numbers for inbound SIP mapping.

Revision ID: 20260824_0005
Revises: 20260817_0004
Create Date: 2026-08-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_0005"
down_revision: str | Sequence[str] | None = "20260817_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("e164_number", sa.String(length=16), nullable=False),
        sa.Column(
            "provider",
            sa.Text(),
            server_default=sa.text("'livekit_sip'"),
            nullable=False,
        ),
        sa.Column("inbound_trunk_id", sa.Text(), nullable=True),
        sa.Column("dispatch_rule_id", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            "provider = 'livekit_sip'",
            name="phone_numbers_provider_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="phone_numbers_instance_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("e164_number", name="phone_numbers_e164_uidx"),
        sa.UniqueConstraint("tenant_id", "id", name="phone_numbers_tenant_id_uidx"),
    )
    op.create_index(
        "phone_numbers_tenant_created_idx",
        "phone_numbers",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("phone_numbers_tenant_created_idx", table_name="phone_numbers")
    op.drop_table("phone_numbers")
