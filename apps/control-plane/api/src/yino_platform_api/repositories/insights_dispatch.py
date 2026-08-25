from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ..domain.insights_dispatch import InsightsDispatchJob


class InsightsDispatchRepository(Protocol):
    async def enqueue(self, job: InsightsDispatchJob) -> InsightsDispatchJob: ...

    async def claim_due(self, now: datetime) -> InsightsDispatchJob | None: ...

    async def mark_sent(self, job_id: UUID) -> None: ...

    async def mark_retry(
        self,
        job_id: UUID,
        error: str,
        next_attempt_at: datetime,
    ) -> None: ...

    async def mark_failed(self, job_id: UUID, error: str) -> None: ...


class InMemoryInsightsDispatchRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, InsightsDispatchJob] = {}
        self._by_call: dict[UUID, UUID] = {}
        self._order: list[UUID] = []

    def all(self) -> list[InsightsDispatchJob]:
        return [self._jobs[job_id] for job_id in self._order]

    async def enqueue(self, job: InsightsDispatchJob) -> InsightsDispatchJob:
        existing_id = self._by_call.get(job.call_id)
        if existing_id is not None:
            return self._jobs[existing_id]
        stored = job.model_copy(deep=True)
        self._jobs[stored.id] = stored
        self._by_call[stored.call_id] = stored.id
        self._order.append(stored.id)
        return stored

    async def claim_due(self, now: datetime) -> InsightsDispatchJob | None:
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status != "pending":
                continue
            if job.next_attempt_at is not None and job.next_attempt_at > now:
                continue
            return job.model_copy(deep=True)
        return None

    async def mark_sent(self, job_id: UUID) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        self._jobs[job_id] = job.model_copy(
            update={"status": "sent", "last_error": ""}
        )

    async def mark_retry(
        self,
        job_id: UUID,
        error: str,
        next_attempt_at: datetime,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        self._jobs[job_id] = job.model_copy(
            update={
                "status": "pending",
                "attempts": job.attempts + 1,
                "next_attempt_at": next_attempt_at,
                "last_error": error,
            }
        )

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        self._jobs[job_id] = job.model_copy(
            update={
                "status": "failed",
                "attempts": job.attempts + 1,
                "last_error": error,
            }
        )
