"""PostgreSQL adapter for notification settings and events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import NotificationEventRow, NotificationSettingsRow
from ...services.notifications import NotificationEvent, NotificationSettings


class PostgresNotificationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_settings(self, tenant_id: UUID) -> NotificationSettings | None:
        async with self._sessions() as session:
            row = await session.get(NotificationSettingsRow, tenant_id)
            if row is None:
                return None
            return NotificationSettings(
                tenant_id=row.tenant_id,
                email=row.email,
                enabled=row.enabled,
                updated_at=row.updated_at,
            )

    async def upsert_settings(
        self, settings: NotificationSettings
    ) -> NotificationSettings:
        stamp = datetime.now(UTC)
        async with self._sessions() as session:
            row = await session.get(NotificationSettingsRow, settings.tenant_id)
            if row is None:
                row = NotificationSettingsRow(
                    tenant_id=settings.tenant_id,
                    email=settings.email,
                    enabled=settings.enabled,
                    updated_at=stamp,
                )
                session.add(row)
            else:
                row.email = settings.email
                row.enabled = settings.enabled
                row.updated_at = stamp
            await session.commit()
            await session.refresh(row)
            return NotificationSettings(
                tenant_id=row.tenant_id,
                email=row.email,
                enabled=row.enabled,
                updated_at=row.updated_at,
            )

    async def add_event(self, event: NotificationEvent) -> NotificationEvent:
        async with self._sessions() as session:
            session.add(
                NotificationEventRow(
                    id=event.id,
                    tenant_id=event.tenant_id,
                    kind=event.kind,
                    target=event.target,
                    status=event.status,
                    detail=event.detail,
                    created_at=event.created_at,
                )
            )
            await session.commit()
            return event
