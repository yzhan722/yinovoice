"""Resolve Job metadata or a LiveKit SIP participant into DispatchMetadata."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..runtime_config import DispatchMetadata, RuntimeConfigurationError
from ..session_trace import SessionTrace, redact_phone_numbers
from .inbound import RuntimeDispatch
from .livekit_sip import (
    LIVEKIT_SIP_PARTICIPANT_KIND,
    UtcClock,
    is_sip_participant,
    normalize_livekit_sip_participant,
)
from .resolver import PlatformDestinationResolver

logger = logging.getLogger(__name__)


def redact_room(room_name: str) -> str:
    return redact_phone_numbers(room_name)


def _room_name(ctx: object) -> str:
    room = getattr(ctx, "room", None)
    name = getattr(room, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "unknown-room"


def explicit_job_metadata(ctx: object) -> DispatchMetadata | None:
    job = getattr(ctx, "job", None)
    raw = getattr(job, "metadata", "") or ""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return DispatchMetadata.from_json(raw)


async def resolve_sip_inbound_dispatch(
    ctx: object,
    *,
    participant: object,
    http: httpx.AsyncClient,
    clock: UtcClock | None = None,
    trace: SessionTrace | None = None,
    lookup_token: str | None = None,
) -> DispatchMetadata:
    room_name = _room_name(ctx)
    call = normalize_livekit_sip_participant(
        participant, room_name=room_name, clock=clock
    )
    if trace is not None:
        if not trace.call_id:
            trace.call_id = call.provider_call_id
        trace.mark("sip_normalized")
    destination = await PlatformDestinationResolver(
        http, lookup_token=lookup_token
    ).resolve(call.callee_number)
    if destination is None:
        raise RuntimeConfigurationError("destination not found")
    if not destination.enabled:
        raise RuntimeConfigurationError("destination is disabled")
    if trace is not None:
        trace.mark("destination_resolved")
    metadata = RuntimeDispatch.to_metadata(call, destination)
    logger.info(
        "sip destination resolved call_id=%s room=%s tenant_id=%s instance_id=%s",
        redact_phone_numbers(call.provider_call_id),
        redact_room(room_name),
        metadata.tenant_id,
        metadata.customer_service_id,
    )
    return metadata


async def await_joining_participant(
    ctx: object, *, sip_only: bool = True
) -> object | None:
    waiter = getattr(ctx, "wait_for_participant", None)
    if not callable(waiter):
        return None
    try:
        if sip_only:
            return await waiter(kind=LIVEKIT_SIP_PARTICIPANT_KIND)
        return await waiter()
    except TimeoutError:
        raise RuntimeConfigurationError("SIP participant did not join") from None


async def resolve_runtime_dispatch(
    ctx: object,
    *,
    http: httpx.AsyncClient,
    clock: UtcClock | None = None,
    trace: SessionTrace | None = None,
    participant: Any | None = None,
    lookup_token: str | None = None,
) -> DispatchMetadata | None:
    """Return explicit job metadata, SIP-resolved metadata, or None for web/local."""

    explicit = explicit_job_metadata(ctx)
    if explicit is not None:
        return explicit
    joined = participant
    if joined is None:
        joined = await await_joining_participant(ctx)
    if not is_sip_participant(joined):
        return None
    return await resolve_sip_inbound_dispatch(
        ctx,
        participant=joined,
        http=http,
        clock=clock,
        trace=trace,
        lookup_token=lookup_token,
    )
