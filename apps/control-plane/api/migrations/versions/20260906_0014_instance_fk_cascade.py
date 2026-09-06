"""Cascade tenant changes from voice_agent_instances to its child rows.

Revision ID: 20260906_0014
Revises: 20260903_0013
Create Date: 2026-09-06

Every instance-scoped table keys on (tenant_id, voice_agent_instance_id), so
moving an instance to another tenant previously meant rewriting eleven tables
in the right order with NO ACTION foreign keys in the way. A child's tenant is
by definition the parent's tenant, so ON UPDATE CASCADE expresses the
relationship correctly and reduces the move to a single UPDATE.

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0014"
down_revision: str | Sequence[str] | None = "20260903_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, constraint, instance column)
INSTANCE_FKS: tuple[tuple[str, str, str], ...] = (
    ("call_records", "call_records_instance_fkey", "voice_agent_instance_id"),
    ("appointments", "appointments_instance_fkey", "voice_agent_instance_id"),
    ("callback_tasks", "callback_tasks_instance_fkey", "voice_agent_instance_id"),
    ("phone_numbers", "phone_numbers_instance_fkey", "voice_agent_instance_id"),
    ("service_offerings", "service_offerings_instance_fkey", "voice_agent_instance_id"),
    (
        "scheduling_profiles",
        "scheduling_profiles_instance_fkey",
        "voice_agent_instance_id",
    ),
    ("business_hours", "business_hours_instance_fkey", "voice_agent_instance_id"),
    (
        "schedule_exceptions",
        "schedule_exceptions_instance_fkey",
        "voice_agent_instance_id",
    ),
    ("tool_invocations", "tool_invocations_instance_fkey", "voice_agent_instance_id"),
    (
        "instance_config_revisions",
        "instance_config_revisions_instance_fkey",
        "instance_id",
    ),
    ("knowledge_documents", "knowledge_documents_instance_fkey", "instance_id"),
)


def _recreate(onupdate: str | None) -> None:
    for table, constraint, instance_column in INSTANCE_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            "voice_agent_instances",
            ["tenant_id", instance_column],
            ["tenant_id", "id"],
            onupdate=onupdate,
        )


def upgrade() -> None:
    _recreate("CASCADE")


def downgrade() -> None:
    _recreate(None)
