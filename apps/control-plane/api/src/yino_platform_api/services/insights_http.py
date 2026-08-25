from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Literal

import httpx

from ..repositories.insights_dispatch import InsightsDispatchRepository

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {408, 429}


def retry_delay_seconds(attempts: int) -> int:
    exponent = max(attempts - 1, 0)
    return min(10 * (4**exponent), 900)


async def post_ended_call(
    *,
    base_url: str,
    token: str,
    profile: str,
    body: dict[str, object],
    transport: httpx.AsyncClient | None = None,
) -> Literal["ok", "retry", "fail"]:
    url = f"{base_url.rstrip('/')}/v1/ingest/{profile}"
    headers = {"Authorization": f"Bearer {token}"}
    own_client = transport is None
    client = transport or httpx.AsyncClient(timeout=10.0)
    try:
        response = await client.post(url, json=body, headers=headers, timeout=10.0)
    except httpx.RequestError:
        logger.warning("insights ingest network error", exc_info=True)
        return "retry"
    finally:
        if own_client:
            await client.aclose()

    if response.status_code in {200, 202}:
        return "ok"
    if response.status_code in _RETRY_STATUSES or response.status_code >= 500:
        return "retry"
    return "fail"


async def drain_once(
    repo: InsightsDispatchRepository,
    *,
    now: datetime,
    base_url: str,
    token: str,
    transport: httpx.AsyncClient | None = None,
) -> Literal["ok", "retry", "fail"] | None:
    job = await repo.claim_due(now)
    if job is None:
        return None
    result = await post_ended_call(
        base_url=base_url,
        token=token,
        profile=job.profile,
        body=job.body,
        transport=transport,
    )
    if result == "ok":
        await repo.mark_sent(job.id)
        return result
    error = f"insights ingest {result}"
    if result == "retry":
        delay = retry_delay_seconds(job.attempts + 1)
        await repo.mark_retry(
            job.id,
            error,
            now + timedelta(seconds=delay),
        )
        return result
    await repo.mark_failed(job.id, error)
    return result
