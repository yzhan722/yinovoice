"""Cascade tenant changes down the instance-scoped foreign key graph.

Revision ID: 20260906_0014
Revises: 20260903_0013
Create Date: 2026-09-06

Every instance-scoped table keys on (tenant_id, <parent id>), so moving an
instance to another tenant previously meant rewriting thirteen tables in the
right order with NO ACTION foreign keys in the way. A child's tenant is by
definition its parent's tenant, so ON UPDATE CASCADE states the relationship
correctly and reduces the move to a single UPDATE.

The graph is two levels deep: instances -> call_records -> call_messages, and
instances -> service_offerings -> appointments. Both levels must cascade or
the first update is rejected by the second level's constraint. Foreign keys
that point at `tenants` are deliberately left alone: a tenant id never moves.

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0014"
down_revision: str | Sequence[str] | None = "20260903_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Recreating a constraint drops its other actions, so ON DELETE is restated
# here. Only call_messages cascades on delete today.
ON_DELETE: dict[str, str] = {"call_messages_call_record_fkey": "CASCADE"}

# (child table, constraint, child columns, parent table, parent columns)
TENANT_SCOPED_FKS: tuple[tuple[str, str, list[str], str, list[str]], ...] = (
    # level 1: children of voice_agent_instances
    (
        "call_records",
        "call_records_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "appointments",
        "appointments_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "callback_tasks",
        "callback_tasks_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "phone_numbers",
        "phone_numbers_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "service_offerings",
        "service_offerings_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "scheduling_profiles",
        "scheduling_profiles_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "business_hours",
        "business_hours_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "schedule_exceptions",
        "schedule_exceptions_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "tool_invocations",
        "tool_invocations_instance_fkey",
        ["tenant_id", "voice_agent_instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "instance_config_revisions",
        "instance_config_revisions_instance_fkey",
        ["tenant_id", "instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    (
        "knowledge_documents",
        "knowledge_documents_instance_fkey",
        ["tenant_id", "instance_id"],
        "voice_agent_instances",
        ["tenant_id", "id"],
    ),
    # level 2: children of those children
    (
        "call_messages",
        "call_messages_call_record_fkey",
        ["tenant_id", "call_record_id"],
        "call_records",
        ["tenant_id", "id"],
    ),
    (
        "appointments",
        "appointments_offering_fkey",
        ["tenant_id", "service_offering_id"],
        "service_offerings",
        ["tenant_id", "id"],
    ),
)


def _recreate(onupdate: str | None) -> None:
    for child, constraint, child_cols, parent, parent_cols in TENANT_SCOPED_FKS:
        op.drop_constraint(constraint, child, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            child,
            parent,
            child_cols,
            parent_cols,
            onupdate=onupdate,
            ondelete=ON_DELETE.get(constraint),
        )


def upgrade() -> None:
    _recreate("CASCADE")


def downgrade() -> None:
    _recreate(None)
