"""PostgreSQL adapter for CallRecordRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ...db.models import CallMessageRow, CallRecordRow
from ...domain.call_record import CallRecord, TranscriptMessage


def _to_domain(row: CallRecordRow) -> CallRecord:
    messages = sorted(row.messages, key=lambda item: item.sequence)
    return CallRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        customer_service_id=row.voice_agent_instance_id,
        room_name=row.room_name,
        status=row.status,  # type: ignore[arg-type]
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_sec=row.duration_sec,
        direction=row.direction,  # type: ignore[arg-type]
        caller_number=row.caller_number,
        callee_number=row.callee_number,
        provider_call_id=row.provider_call_id,
        connected_at=row.connected_at,
        ended_reason=row.ended_reason,  # type: ignore[arg-type]
        messages=[
            TranscriptMessage(
                role=message.role,  # type: ignore[arg-type]
                text=message.text,
                sequence=message.sequence,
            )
            for message in messages
        ],
        created_at=row.created_at,
        recording_status=row.recording_status,  # type: ignore[arg-type]
        recording_mime_type=row.recording_mime_type,
        recording_size_bytes=row.recording_size_bytes,
        recording_failure_code=row.recording_failure_code,
        recording_egress_id=row.recording_egress_id,
        recording_object_key=row.recording_object_key,
        deleted_at=row.deleted_at,
    )


class PostgresCallRecordRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, record: CallRecord) -> CallRecord:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == record.tenant_id,
                    CallRecordRow.id == record.id,
                )
                .options(selectinload(CallRecordRow.messages))
            )
            if row is None:
                row = CallRecordRow(
                    id=record.id,
                    tenant_id=record.tenant_id,
                    voice_agent_instance_id=record.customer_service_id,
                    room_name=record.room_name,
                    status=record.status,
                    direction=record.direction,
                    started_at=record.started_at,
                    ended_at=record.ended_at,
                    duration_sec=record.duration_sec,
                    caller_number=record.caller_number,
                    callee_number=record.callee_number,
                    provider_call_id=record.provider_call_id,
                    connected_at=record.connected_at,
                    ended_reason=record.ended_reason,
                    created_at=record.created_at,
                    recording_status=record.recording_status,
                    recording_mime_type=record.recording_mime_type,
                    recording_size_bytes=record.recording_size_bytes,
                    recording_failure_code=record.recording_failure_code,
                    recording_egress_id=record.recording_egress_id,
                    recording_object_key=record.recording_object_key,
                    deleted_at=record.deleted_at,
                )
                session.add(row)
            else:
                row.voice_agent_instance_id = record.customer_service_id
                row.room_name = record.room_name
                row.status = record.status
                row.direction = record.direction
                row.started_at = record.started_at
                row.ended_at = record.ended_at
                row.duration_sec = record.duration_sec
                row.caller_number = record.caller_number
                row.callee_number = record.callee_number
                row.provider_call_id = record.provider_call_id
                row.connected_at = record.connected_at
                row.ended_reason = record.ended_reason
                row.recording_status = record.recording_status
                row.recording_mime_type = record.recording_mime_type
                row.recording_size_bytes = record.recording_size_bytes
                row.recording_failure_code = record.recording_failure_code
                row.recording_egress_id = record.recording_egress_id
                row.recording_object_key = record.recording_object_key
                row.deleted_at = record.deleted_at

            await session.execute(
                delete(CallMessageRow).where(
                    CallMessageRow.tenant_id == record.tenant_id,
                    CallMessageRow.call_record_id == record.id,
                )
            )
            for message in record.messages:
                session.add(
                    CallMessageRow(
                        tenant_id=record.tenant_id,
                        call_record_id=record.id,
                        sequence=message.sequence,
                        role=message.role,
                        text=message.text,
                    )
                )

            await session.commit()

            loaded = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == record.tenant_id,
                    CallRecordRow.id == record.id,
                )
                .options(selectinload(CallRecordRow.messages))
            )
            assert loaded is not None
            return _to_domain(loaded)

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        include_deleted: bool = False,
    ) -> tuple[list[CallRecord], int]:
        filters = [CallRecordRow.tenant_id == tenant_id]
        if not include_deleted:
            filters.append(CallRecordRow.deleted_at.is_(None))

        async with self._sessions() as session:
            total = await session.scalar(
                select(func.count())
                .select_from(CallRecordRow)
                .where(*filters)
            )
            rows = (
                await session.scalars(
                    select(CallRecordRow)
                    .where(*filters)
                    .options(selectinload(CallRecordRow.messages))
                    .order_by(
                        CallRecordRow.created_at.desc(),
                        CallRecordRow.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [_to_domain(row) for row in rows], int(total or 0)

    async def get(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.id == record_id,
                )
                .options(selectinload(CallRecordRow.messages))
            )
            if row is None:
                return None
            return _to_domain(row)

    async def soft_delete(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.id == record_id,
                )
                .options(selectinload(CallRecordRow.messages))
            )
            if row is None:
                return None
            if row.deleted_at is None:
                row.deleted_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(row, attribute_names=["messages"])
            return _to_domain(row)

    async def restore(
        self, record_id: UUID, tenant_id: UUID
    ) -> CallRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.id == record_id,
                )
                .options(selectinload(CallRecordRow.messages))
            )
            if row is None:
                return None
            if row.deleted_at is not None:
                row.deleted_at = None
                await session.commit()
                await session.refresh(row, attribute_names=["messages"])
            return _to_domain(row)

    async def exists_for_customer_service(
        self,
        tenant_id: UUID,
        customer_service_id: UUID,
    ) -> bool:
        async with self._sessions() as session:
            found = await session.scalar(
                select(CallRecordRow.id)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.voice_agent_instance_id == customer_service_id,
                )
                .limit(1)
            )
            return found is not None

    async def find_by_provider_call_id(
        self,
        tenant_id: UUID,
        provider_call_id: str,
    ) -> CallRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.provider_call_id == provider_call_id,
                    CallRecordRow.deleted_at.is_(None),
                )
                .options(selectinload(CallRecordRow.messages))
                .order_by(CallRecordRow.created_at.desc())
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def find_in_progress_by_room_name(
        self,
        tenant_id: UUID,
        room_name: str,
    ) -> CallRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CallRecordRow)
                .where(
                    CallRecordRow.tenant_id == tenant_id,
                    CallRecordRow.room_name == room_name,
                    CallRecordRow.status == "in_progress",
                    CallRecordRow.deleted_at.is_(None),
                )
                .options(selectinload(CallRecordRow.messages))
            )
            return _to_domain(row) if row is not None else None
