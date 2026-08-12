"""Create MVP core tables.

Revision ID: 20260811_0001
Revises:
Create Date: 2026-08-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "home_region",
            sa.Text(),
            server_default=sa.text("'cn-mainland'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'active'"),
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
            "status IN ('active', 'disabled')",
            name="tenants_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "schema_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("package", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="agent_template_versions_version_check",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_key",
            "version",
            name="agent_template_versions_key_version_uidx",
        ),
    )

    op.create_table(
        "voice_agent_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "template_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("organization_name", sa.String(length=120), nullable=False),
        sa.Column("business_profile", sa.Text(), nullable=False),
        sa.Column("primary_language", sa.Text(), nullable=False),
        sa.Column("greeting", sa.String(length=300), nullable=False),
        sa.Column(
            "platform_prompt",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "tenant_prompt",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "voice_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "response_config",
            postgresql.JSONB(astext_type=sa.Text()),
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
            "version >= 1",
            name="voice_agent_instances_version_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="voice_agent_instances_tenant_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["agent_template_versions.id"],
            name="voice_agent_instances_template_version_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="voice_agent_instances_tenant_id_uidx",
        ),
    )

    op.create_table(
        "call_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("room_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "direction",
            sa.Text(),
            server_default=sa.text("'web'"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column(
            "recording_status",
            sa.Text(),
            server_default=sa.text("'none'"),
            nullable=False,
        ),
        sa.Column("recording_mime_type", sa.Text(), nullable=True),
        sa.Column("recording_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("recording_failure_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'interrupted', 'failed')",
            name="call_records_status_check",
        ),
        sa.CheckConstraint(
            "direction IN ('web', 'inbound', 'outbound')",
            name="call_records_direction_check",
        ),
        sa.CheckConstraint(
            "duration_sec BETWEEN 0 AND 86400",
            name="call_records_duration_sec_check",
        ),
        sa.CheckConstraint(
            "recording_status IN ('none', 'uploading', 'ready', 'failed')",
            name="call_records_recording_status_check",
        ),
        sa.CheckConstraint(
            "recording_size_bytes IS NULL OR recording_size_bytes >= 0",
            name="call_records_recording_size_bytes_check",
        ),
        sa.CheckConstraint(
            "ended_at >= started_at",
            name="call_records_ended_at_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="call_records_instance_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="call_records_tenant_id_uidx",
        ),
    )
    op.execute(
        "CREATE INDEX call_records_tenant_created_idx "
        "ON call_records (tenant_id, created_at DESC, id DESC)"
    )

    op.create_table(
        "call_messages",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="call_messages_role_check",
        ),
        sa.CheckConstraint(
            "sequence >= 0 AND sequence <= 1000000",
            name="call_messages_sequence_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "call_record_id"],
            ["call_records.tenant_id", "call_records.id"],
            name="call_messages_call_record_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "call_record_id",
            "sequence",
            name="call_messages_pkey",
        ),
    )


def downgrade() -> None:
    op.drop_table("call_messages")
    op.execute("DROP INDEX IF EXISTS call_records_tenant_created_idx")
    op.drop_table("call_records")
    op.drop_table("voice_agent_instances")
    op.drop_table("agent_template_versions")
    op.drop_table("tenants")
