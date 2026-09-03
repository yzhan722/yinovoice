"""Add console user accounts (multi-tenant login with roles).

Revision ID: 20260903_0013
Revises: 20260901_0012
Create Date: 2026-09-03

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0013"
down_revision: str | Sequence[str] | None = "20260901_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account", sa.String(length=80), nullable=False),
        sa.Column("nickname", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'tenant_operator'"),
        ),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="user_accounts_tenant_fk",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "role IN ('platform_admin', 'tenant_operator')",
            name="user_accounts_role_check",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="user_accounts_status_check",
        ),
    )
    op.create_index(
        "user_accounts_account_lower_uq",
        "user_accounts",
        [sa.text("lower(account)")],
        unique=True,
    )
    op.create_index("user_accounts_tenant_idx", "user_accounts", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("user_accounts_tenant_idx", table_name="user_accounts")
    op.drop_index("user_accounts_account_lower_uq", table_name="user_accounts")
    op.drop_table("user_accounts")
