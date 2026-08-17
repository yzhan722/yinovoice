"""Add soft-delete column to call_records.

Revision ID: 20260813_0002
Revises: 20260811_0001
Create Date: 2026-08-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0002"
down_revision: Union[str, Sequence[str], None] = "20260811_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "call_records_tenant_deleted_created_idx",
        "call_records",
        ["tenant_id", "deleted_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "call_records_tenant_deleted_created_idx",
        table_name="call_records",
    )
    op.drop_column("call_records", "deleted_at")
