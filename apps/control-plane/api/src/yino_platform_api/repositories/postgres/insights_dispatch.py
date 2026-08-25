"""PostgreSQL adapter for InsightsDispatchRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import InsightsDispatchJobRow
from ...domain.insights_dispatch import InsightsDispatchJob


def _to_domain(row: InsightsDispatchJobRow) -> InsightsDispatchJob:
    return InsightsDispatchJob(
        id=row.id,
        tenant_id=row.tenant_id,
        call_id=row.call_id,
        profile=row.profile,
        event_id=row.event_id,
        body=dict(row.body),
        status=row.status,  # type: ignore[arg-type]
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        last_error=row.last_error,
    )


class PostgresInsightsDispatchRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def enqueue(self, job: InsightsDispatchJob) -> InsightsDispatchJob:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(InsightsDispatchJobRow).where(
                    InsightsDispatchJobRow.call_id == job.call_id
                )
            )
            if existing is not None:
                return _to_domain(existing)
            session.add(
                InsightsDispatchJobRow(
                    id=job.id,
                    tenant_id=job.tenant_id,
                    call_id=job.call_id,
                    profile=job.profile,
                    event_id=job.event_id,
                    body=job.body,
                    status=job.status,
                    attempts=job.attempts,
                    next_attempt_at=job.next_attempt_at,
                    last_error=job.last_error,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raced = await session.scalar(
                    select(InsightsDispatchJobRow).where(
                        InsightsDispatchJobRow.call_id == job.call_id
                    )
                )
                assert raced is not None
                return _to_domain(raced)
            return job

    async def claim_due(self, now: datetime) -> InsightsDispatchJob | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InsightsDispatchJobRow)
                .where(
                    InsightsDispatchJobRow.status == "pending",
                    or_(
                        InsightsDispatchJobRow.next_attempt_at.is_(None),
                        InsightsDispatchJobRow.next_attempt_at <= now,
                    ),
                )
                .order_by(
                    InsightsDispatchJobRow.created_at,
                    InsightsDispatchJobRow.id,
                )
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def mark_sent(self, job_id: UUID) -> None:
        async with self._sessions() as session:
            await session.execute(
                update(InsightsDispatchJobRow)
                .where(InsightsDispatchJobRow.id == job_id)
                .values(
                    status="sent",
                    last_error="",
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def mark_retry(
        self,
        job_id: UUID,
        error: str,
        next_attempt_at: datetime,
    ) -> None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InsightsDispatchJobRow).where(
                    InsightsDispatchJobRow.id == job_id
                )
            )
            if row is None:
                return
            row.status = "pending"
            row.attempts = row.attempts + 1
            row.next_attempt_at = next_attempt_at
            row.last_error = error
            row.updated_at = datetime.now(UTC)
            await session.commit()

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InsightsDispatchJobRow).where(
                    InsightsDispatchJobRow.id == job_id
                )
            )
            if row is None:
                return
            row.status = "failed"
            row.attempts = row.attempts + 1
            row.last_error = error
            row.updated_at = datetime.now(UTC)
            await session.commit()
