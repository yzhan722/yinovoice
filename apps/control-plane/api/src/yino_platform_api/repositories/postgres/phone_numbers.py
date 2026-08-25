"""PostgreSQL adapter for PhoneNumberRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import PhoneNumberRow
from ...domain.phone_number import PhoneNumber, PhoneNumberCreate
from ..phone_numbers import PhoneNumberConflict


def _to_domain(row: PhoneNumberRow) -> PhoneNumber:
    return PhoneNumber(
        id=row.id,
        tenant_id=row.tenant_id,
        voice_agent_instance_id=row.voice_agent_instance_id,
        e164_number=row.e164_number,
        provider=row.provider,  # type: ignore[arg-type]
        inbound_trunk_id=row.inbound_trunk_id,
        dispatch_rule_id=row.dispatch_rule_id,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresPhoneNumberRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_for_tenant(self, tenant_id: UUID) -> list[PhoneNumber]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(PhoneNumberRow)
                    .where(PhoneNumberRow.tenant_id == tenant_id)
                    .order_by(PhoneNumberRow.created_at.asc(), PhoneNumberRow.id.asc())
                )
            ).all()
            return [_to_domain(row) for row in rows]

    async def get(
        self, phone_number_id: UUID, tenant_id: UUID
    ) -> PhoneNumber | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(PhoneNumberRow).where(
                    PhoneNumberRow.tenant_id == tenant_id,
                    PhoneNumberRow.id == phone_number_id,
                )
            )
            return _to_domain(row) if row is not None else None

    async def get_by_e164(self, e164_number: str) -> PhoneNumber | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(PhoneNumberRow).where(PhoneNumberRow.e164_number == e164_number)
            )
            return _to_domain(row) if row is not None else None

    async def create(
        self, tenant_id: UUID, payload: PhoneNumberCreate
    ) -> PhoneNumber:
        now = datetime.now(UTC)
        row = PhoneNumberRow(
            id=uuid4(),
            tenant_id=tenant_id,
            voice_agent_instance_id=payload.voice_agent_instance_id,
            e164_number=payload.e164_number,
            provider=payload.provider,
            inbound_trunk_id=payload.inbound_trunk_id,
            dispatch_rule_id=payload.dispatch_rule_id,
            enabled=payload.enabled,
            created_at=now,
            updated_at=now,
        )
        async with self._sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise PhoneNumberConflict() from error
            await session.refresh(row)
            return _to_domain(row)

    async def save(self, number: PhoneNumber) -> PhoneNumber:
        async with self._sessions() as session:
            row = await session.scalar(
                select(PhoneNumberRow).where(
                    PhoneNumberRow.tenant_id == number.tenant_id,
                    PhoneNumberRow.id == number.id,
                )
            )
            if row is None:
                raise PhoneNumberConflict()
            row.voice_agent_instance_id = number.voice_agent_instance_id
            row.e164_number = number.e164_number
            row.inbound_trunk_id = number.inbound_trunk_id
            row.dispatch_rule_id = number.dispatch_rule_id
            row.enabled = number.enabled
            row.updated_at = datetime.now(UTC)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise PhoneNumberConflict() from error
            await session.refresh(row)
            return _to_domain(row)

    async def delete(self, phone_number_id: UUID, tenant_id: UUID) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(PhoneNumberRow).where(
                    PhoneNumberRow.tenant_id == tenant_id,
                    PhoneNumberRow.id == phone_number_id,
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
