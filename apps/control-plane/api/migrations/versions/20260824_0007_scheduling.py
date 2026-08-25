"""Add built-in scheduling tables and optional appointment offering.

Revision ID: 20260824_0007
Revises: 20260824_0006
Create Date: 2026-08-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_0007"
down_revision: str | Sequence[str] | None = "20260824_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_offerings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "description",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "buffer_minutes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="service_offerings_pkey"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="service_offerings_tenant_id_uidx",
        ),
        sa.CheckConstraint(
            "duration_minutes BETWEEN 5 AND 480",
            name="service_offerings_duration_check",
        ),
        sa.CheckConstraint(
            "buffer_minutes BETWEEN 0 AND 120",
            name="service_offerings_buffer_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="service_offerings_instance_fkey",
        ),
    )
    op.create_index(
        "service_offerings_tenant_instance_idx",
        "service_offerings",
        ["tenant_id", "voice_agent_instance_id"],
    )

    op.create_table(
        "scheduling_profiles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column(
            "slot_interval_minutes",
            sa.Integer(),
            server_default=sa.text("15"),
            nullable=False,
        ),
        sa.Column(
            "minimum_notice_minutes",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column(
            "booking_horizon_days",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "voice_agent_instance_id",
            name="scheduling_profiles_pkey",
        ),
        sa.CheckConstraint(
            "slot_interval_minutes BETWEEN 5 AND 60",
            name="scheduling_profiles_interval_check",
        ),
        sa.CheckConstraint(
            "minimum_notice_minutes BETWEEN 0 AND 10080",
            name="scheduling_profiles_notice_check",
        ),
        sa.CheckConstraint(
            "booking_horizon_days BETWEEN 1 AND 365",
            name="scheduling_profiles_horizon_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="scheduling_profiles_instance_fkey",
        ),
    )

    op.create_table(
        "business_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_local", sa.String(length=5), nullable=False),
        sa.Column("end_local", sa.String(length=5), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="business_hours_pkey"),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="business_hours_weekday_check",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="business_hours_instance_fkey",
        ),
    )
    op.create_index(
        "business_hours_tenant_instance_idx",
        "business_hours",
        ["tenant_id", "voice_agent_instance_id", "weekday"],
    )

    op.create_table(
        "schedule_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_agent_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("date_local", sa.Date(), nullable=False),
        sa.Column(
            "closed",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("start_local", sa.String(length=5), nullable=True),
        sa.Column("end_local", sa.String(length=5), nullable=True),
        sa.Column(
            "reason",
            sa.String(length=200),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="schedule_exceptions_pkey"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="schedule_exceptions_tenant_id_uidx",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="schedule_exceptions_instance_fkey",
        ),
    )
    op.create_index(
        "schedule_exceptions_tenant_instance_date_idx",
        "schedule_exceptions",
        ["tenant_id", "voice_agent_instance_id", "date_local"],
    )

    op.add_column(
        "appointments",
        sa.Column("service_offering_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "appointments_offering_fkey",
        "appointments",
        "service_offerings",
        ["tenant_id", "service_offering_id"],
        ["tenant_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "appointments_offering_fkey", "appointments", type_="foreignkey"
    )
    op.drop_column("appointments", "service_offering_id")
    op.drop_index(
        "schedule_exceptions_tenant_instance_date_idx",
        table_name="schedule_exceptions",
    )
    op.drop_table("schedule_exceptions")
    op.drop_index("business_hours_tenant_instance_idx", table_name="business_hours")
    op.drop_table("business_hours")
    op.drop_table("scheduling_profiles")
    op.drop_index(
        "service_offerings_tenant_instance_idx", table_name="service_offerings"
    )
    op.drop_table("service_offerings")
