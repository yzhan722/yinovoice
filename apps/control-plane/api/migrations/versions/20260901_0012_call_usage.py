"""Store per-call Qwen response.done token usage on call_records.

Revision ID: 20260901_0012
Revises: 20260825_0011
Create Date: 2026-09-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0012"
down_revision: str | Sequence[str] | None = "20260825_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column(
            "usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("call_records", "usage")
