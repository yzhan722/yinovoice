"""SQLAlchemy ORM models for the PostgreSQL MVP core tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
            "status IN ('completed', 'interrupted', 'failed')",
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
            "ended_at >= started_at",
            name="call_records_ended_at_check",
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
    ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    recording_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'none'")
    )
    recording_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recording_failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
