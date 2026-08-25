"""SQLAlchemy ORM models for the PostgreSQL MVP core tables."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="tenants_status_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    home_region: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'cn-mainland'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instances: Mapped[list[VoiceAgentInstance]] = relationship(
        back_populates="tenant"
    )


class AgentTemplateVersion(Base):
    __tablename__ = "agent_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_key",
            "version",
            name="agent_template_versions_key_version_uidx",
        ),
        CheckConstraint("version >= 1", name="agent_template_versions_version_check"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    template_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    package: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    instances: Mapped[list[VoiceAgentInstance]] = relationship(
        back_populates="template_version"
    )


class VoiceAgentInstance(Base):
    __tablename__ = "voice_agent_instances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="voice_agent_instances_tenant_id_uidx",
        ),
        CheckConstraint("version >= 1", name="voice_agent_instances_version_check"),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="voice_agent_instances_tenant_id_fkey",
        ),
        ForeignKeyConstraint(
            ["template_version_id"],
            ["agent_template_versions.id"],
            name="voice_agent_instances_template_version_id_fkey",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    template_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(120), nullable=False)
    business_profile: Mapped[str] = mapped_column(Text, nullable=False)
    primary_language: Mapped[str] = mapped_column(Text, nullable=False)
    greeting: Mapped[str] = mapped_column(String(300), nullable=False)
    platform_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    tenant_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    voice_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    insights_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship(back_populates="instances")
    template_version: Mapped[AgentTemplateVersion] = relationship(
        back_populates="instances"
    )
    call_records: Mapped[list[CallRecordRow]] = relationship(
        back_populates="voice_agent_instance"
    )


class CallRecordRow(Base):
    __tablename__ = "call_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="call_records_tenant_id_uidx"),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'interrupted', 'failed')",
            name="call_records_status_check",
        ),
        CheckConstraint(
            "direction IN ('web', 'inbound', 'outbound')",
            name="call_records_direction_check",
        ),
        CheckConstraint(
            "duration_sec BETWEEN 0 AND 86400",
            name="call_records_duration_sec_check",
        ),
        CheckConstraint(
            "recording_status IN ('none', 'uploading', 'ready', 'failed')",
            name="call_records_recording_status_check",
        ),
        CheckConstraint(
            "recording_size_bytes IS NULL OR recording_size_bytes >= 0",
            name="call_records_recording_size_bytes_check",
        ),
        CheckConstraint(
            "("
            "status = 'in_progress' AND ended_at IS NULL AND duration_sec IS NULL"
            ") OR ("
            "status <> 'in_progress' AND ended_at IS NOT NULL "
            "AND duration_sec IS NOT NULL AND ended_at >= started_at"
            ")",
            name="call_records_ended_at_check",
        ),
        CheckConstraint(
            "ended_reason IS NULL OR ended_reason IN "
            "('completed', 'user_hangup', 'agent_error')",
            name="call_records_ended_reason_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="call_records_instance_fkey",
        ),
        Index(
            "call_records_tenant_created_idx",
            "tenant_id",
            "created_at",
            "id",
        ),
        Index(
            "call_records_tenant_provider_call_uidx",
            "tenant_id",
            "provider_call_id",
            unique=True,
            postgresql_where=text(
                "provider_call_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index(
            "call_records_tenant_room_in_progress_uidx",
            "tenant_id",
            "room_name",
            unique=True,
            postgresql_where=text(
                "status = 'in_progress' AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    room_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'web'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caller_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    callee_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'none'")
    )
    recording_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recording_failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_egress_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    voice_agent_instance: Mapped[VoiceAgentInstance] = relationship(
        back_populates="call_records"
    )
    messages: Mapped[list[CallMessageRow]] = relationship(
        back_populates="call_record",
        cascade="all, delete-orphan",
    )


class CallMessageRow(Base):
    __tablename__ = "call_messages"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "call_record_id",
            "sequence",
            name="call_messages_pkey",
        ),
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="call_messages_role_check",
        ),
        CheckConstraint(
            "sequence >= 0 AND sequence <= 1000000",
            name="call_messages_sequence_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "call_record_id"],
            ["call_records.tenant_id", "call_records.id"],
            name="call_messages_call_record_fkey",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    call_record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    call_record: Mapped[CallRecordRow] = relationship(back_populates="messages")


class AppointmentRow(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="appointments_tenant_id_uidx"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled')",
            name="appointments_status_check",
        ),
        CheckConstraint(
            "source IN ('manual', 'voice_tool', 'import')",
            name="appointments_source_check",
        ),
        CheckConstraint(
            "slot_end >= slot_start",
            name="appointments_slot_order_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="appointments_instance_fkey",
        ),
        Index("appointments_tenant_slot_idx", "tenant_id", "slot_start"),
        Index("appointments_tenant_status_idx", "tenant_id", "status"),
        ForeignKeyConstraint(
            ["tenant_id", "service_offering_id"],
            ["service_offerings.tenant_id", "service_offerings.id"],
            name="appointments_offering_fkey",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    call_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    service_offering_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    patient_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    slot_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    slot_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'manual'")
    )
    notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CallbackTaskRow(Base):
    __tablename__ = "callback_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="callback_tasks_tenant_id_uidx"),
        CheckConstraint(
            "status IN ('open', 'done', 'cancelled')",
            name="callback_tasks_status_check",
        ),
        CheckConstraint(
            "source IN ('manual', 'voice_tool', 'from_call')",
            name="callback_tasks_source_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="callback_tasks_instance_fkey",
        ),
        Index(
            "callback_tasks_tenant_status_created_idx",
            "tenant_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    call_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    caller_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'manual'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PhoneNumberRow(Base):
    __tablename__ = "phone_numbers"
    __table_args__ = (
        UniqueConstraint("e164_number", name="phone_numbers_e164_uidx"),
        UniqueConstraint("tenant_id", "id", name="phone_numbers_tenant_id_uidx"),
        CheckConstraint(
            "provider = 'livekit_sip'",
            name="phone_numbers_provider_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="phone_numbers_instance_fkey",
        ),
        Index("phone_numbers_tenant_created_idx", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    e164_number: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'livekit_sip'")
    )
    inbound_trunk_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_rule_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ServiceOfferingRow(Base):
    __tablename__ = "service_offerings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="service_offerings_tenant_id_uidx"),
        CheckConstraint(
            "duration_minutes BETWEEN 5 AND 480",
            name="service_offerings_duration_check",
        ),
        CheckConstraint(
            "buffer_minutes BETWEEN 0 AND 120",
            name="service_offerings_buffer_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="service_offerings_instance_fkey",
        ),
        Index(
            "service_offerings_tenant_instance_idx",
            "tenant_id",
            "voice_agent_instance_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SchedulingProfileRow(Base):
    __tablename__ = "scheduling_profiles"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "voice_agent_instance_id",
            name="scheduling_profiles_pkey",
        ),
        CheckConstraint(
            "slot_interval_minutes BETWEEN 5 AND 60",
            name="scheduling_profiles_interval_check",
        ),
        CheckConstraint(
            "minimum_notice_minutes BETWEEN 0 AND 10080",
            name="scheduling_profiles_notice_check",
        ),
        CheckConstraint(
            "booking_horizon_days BETWEEN 1 AND 365",
            name="scheduling_profiles_horizon_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="scheduling_profiles_instance_fkey",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    slot_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("15")
    )
    minimum_notice_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    booking_horizon_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BusinessHoursRow(Base):
    __tablename__ = "business_hours"
    __table_args__ = (
        CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="business_hours_weekday_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="business_hours_instance_fkey",
        ),
        Index(
            "business_hours_tenant_instance_idx",
            "tenant_id",
            "voice_agent_instance_id",
            "weekday",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_local: Mapped[str] = mapped_column(String(5), nullable=False)
    end_local: Mapped[str] = mapped_column(String(5), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class ScheduleExceptionRow(Base):
    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "id", name="schedule_exceptions_tenant_id_uidx"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="schedule_exceptions_instance_fkey",
        ),
        Index(
            "schedule_exceptions_tenant_instance_date_idx",
            "tenant_id",
            "voice_agent_instance_id",
            "date_local",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    voice_agent_instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    date_local: Mapped[date] = mapped_column(Date, nullable=False)
    closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    start_local: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_local: Mapped[str | None] = mapped_column(String(5), nullable=True)
    reason: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default=text("''")
    )


class ToolInvocationRow(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="tool_invocations_tenant_id_uidx"),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="tool_invocations_tenant_idempotency_uidx",
        ),
        CheckConstraint(
            "tool_name IN ('check_availability', 'create_appointment', 'create_callback')",
            name="tool_invocations_tool_name_check",
        ),
        CheckConstraint(
            "status IN ('ok', 'error', 'skipped')",
            name="tool_invocations_status_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "voice_agent_instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="tool_invocations_instance_fkey",
        ),
        Index(
            "tool_invocations_tenant_session_idx",
            "tenant_id",
            "session_id",
        ),
        Index(
            "tool_invocations_tenant_call_record_idx",
            "tenant_id",
            "call_record_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    call_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    voice_agent_instance_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NotificationSettingsRow(Base):
    __tablename__ = "notification_settings"

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default=text("''")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NotificationEventRow(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('sent', 'failed')",
            name="notification_events_status_check",
        ),
        Index(
            "notification_events_tenant_created_idx",
            "tenant_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InsightsDispatchJobRow(Base):
    __tablename__ = "insights_dispatch_jobs"
    __table_args__ = (
        UniqueConstraint("call_id", name="insights_dispatch_jobs_call_id_uidx"),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="insights_dispatch_jobs_status_check",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="insights_dispatch_jobs_attempts_check",
        ),
        Index(
            "insights_dispatch_jobs_due_idx",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    call_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    profile: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InstanceConfigRevisionRow(Base):
    __tablename__ = "instance_config_revisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "instance_id",
            "revision",
            name="instance_config_revisions_revision_uidx",
        ),
        CheckConstraint(
            "revision >= 1",
            name="instance_config_revisions_revision_check",
        ),
        CheckConstraint(
            "source IN ('create', 'publish', 'rollback')",
            name="instance_config_revisions_source_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="instance_config_revisions_instance_fkey",
        ),
        Index(
            "instance_config_revisions_instance_idx",
            "tenant_id",
            "instance_id",
            "revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    instance_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeDocumentRow(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="knowledge_documents_tenant_id_uidx",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "instance_id"],
            ["voice_agent_instances.tenant_id", "voice_agent_instances.id"],
            name="knowledge_documents_instance_fkey",
        ),
        Index(
            "knowledge_documents_instance_idx",
            "tenant_id",
            "instance_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    instance_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
