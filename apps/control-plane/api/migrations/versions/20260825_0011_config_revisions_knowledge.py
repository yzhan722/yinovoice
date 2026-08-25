"""Add instance config revisions and knowledge documents.

Revision ID: 20260825_0011
Revises: 20260825_0010
Create Date: 2026-08-25

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0011"
down_revision: str | Sequence[str] | None = "20260825_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instance_config_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="instance_config_revisions_pkey"),
        sa.UniqueConstraint(
            "tenant_id",
            "instance_id",
            "revision",
            name="instance_config_revisions_revision_uidx",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="instance_config_revisions_revision_check",
        ),
        sa.CheckConstraint(
            "source IN ('create', 'publish', 'rollback')",
            name="instance_config_revisions_source_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="instance_config_revisions_instance_fkey",
        ),
    )
    op.create_index(
        "instance_config_revisions_instance_idx",
        "instance_config_revisions",
        ["tenant_id", "instance_id", "revision"],
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="knowledge_documents_pkey"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="knowledge_documents_tenant_id_uidx",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="knowledge_documents_instance_fkey",
        ),
    )
    op.create_index(
        "knowledge_documents_instance_idx",
        "knowledge_documents",
        ["tenant_id", "instance_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "knowledge_documents_instance_idx",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
    op.drop_index(
        "instance_config_revisions_instance_idx",
        table_name="instance_config_revisions",
    )
    op.drop_table("instance_config_revisions")
