from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sip_fakes import (
    CALLEE_A,
    CALLEE_B,
    CALLER_A,
    LOOKUP_TOKEN,
    TENANT_A,
    TENANT_AGENT_A,
    TENANT_AGENT_B,
    TENANT_B,
    SipJobContext,
    lookup_payload,
    sip_attributes,
    sip_participant,
    web_kind,
)

from yino_voice_agent.runtime_config import DispatchMetadata, RuntimeConfigurationError
from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.telephony import (
    FrozenUtcClock,
    PlatformDestinationResolver,
    resolve_runtime_dispatch,
    resolve_sip_inbound_dispatch,
)
from yino_voice_agent.telephony.dispatch import (
    await_joining_participant,
    explicit_job_metadata,
)
from yino_voice_agent.telephony.livekit_sip import LIVEKIT_SIP_PARTICIPANT_KIND
from yino_voice_agent.telephony.resolver import PHONE_LOOKUP_HEADER


def _empty_job(room_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        room=SimpleNamespace(name=room_name),
        job=SimpleNamespace(metadata=""),
    )


def _http(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    )


@pytest.mark.asyncio
async def test_resolve_sip_inbound_known_number() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/phone-numbers/lookup"
        assert request.url.params.get("number") == CALLEE_A
        assert request.headers.get(PHONE_LOOKUP_HEADER) == LOOKUP_TOKEN
        return httpx.Response(200, json=lookup_payload(TENANT_AGENT_A))

    ctx = _empty_job("yino-sip-a")
    clock = FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC))
    trace = SessionTrace(session_id="yino-sip-a", clock=FakeClock())
    async with _http(handler) as http:
        metadata = await resolve_sip_inbound_dispatch(
            ctx,
            participant=sip_participant(),
            http=http,
            clock=clock,
            trace=trace,
            lookup_token=LOOKUP_TOKEN,
        )
    assert metadata.tenant_id == TENANT_A
    assert metadata.customer_service_id == TENANT_AGENT_A.instance_id
    assert metadata.channel == "sip"
    assert metadata.caller_number == CALLER_A
    assert metadata.callee_number == CALLEE_A
    assert metadata.provider_call_id == "provider-call-full-1"
    assert trace.timestamp("sip_normalized") is not None
    assert trace.timestamp("destination_resolved") is not None


@pytest.mark.asyncio
async def test_resolve_does_not_cross_tenant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        number = request.url.params.get("number")
        if number == CALLEE_B:
            return httpx.Response(200, json=lookup_payload(TENANT_AGENT_B))
        return httpx.Response(200, json=lookup_payload(TENANT_AGENT_A))

    ctx = _empty_job("yino-sip-b")
    async with _http(handler) as http:
        metadata = await resolve_sip_inbound_dispatch(
            ctx,
            participant=sip_participant(attributes=sip_attributes(callee=CALLEE_B)),
            http=http,
            clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
            lookup_token=LOOKUP_TOKEN,
        )
    assert metadata.tenant_id == TENANT_B
    assert metadata.tenant_id != TENANT_A
    assert metadata.customer_service_id == TENANT_AGENT_B.instance_id


@pytest.mark.asyncio
async def test_unknown_and_disabled_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        number = request.url.params.get("number")
        if number == CALLEE_A:
            return httpx.Response(404)
        return httpx.Response(200, json=lookup_payload(TENANT_AGENT_B, enabled=False))

    ctx = _empty_job("room")
    clock = FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC))
    async with _http(handler) as http:
        with pytest.raises(RuntimeConfigurationError, match="destination not found"):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=sip_participant(),
                http=http,
                clock=clock,
                lookup_token=LOOKUP_TOKEN,
            )
        with pytest.raises(RuntimeConfigurationError, match="disabled"):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=sip_participant(attributes=sip_attributes(callee=CALLEE_B)),
                http=http,
                clock=clock,
                lookup_token=LOOKUP_TOKEN,
            )


@pytest.mark.asyncio
async def test_lookup_timeout_and_500_fail_closed() -> None:
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    def boom_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "down"})

    ctx = _empty_job("room")
    participant = sip_participant()
    clock = FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC))
    async with _http(timeout_handler) as http:
        with pytest.raises(
            RuntimeConfigurationError, match="destination lookup failed"
        ) as caught:
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=participant,
                http=http,
                clock=clock,
                lookup_token=LOOKUP_TOKEN,
            )
    assert caught.value.__cause__ is None
    assert CALLEE_A not in str(caught.value)
    async with _http(boom_handler) as http:
        with pytest.raises(RuntimeConfigurationError, match="HTTP 500"):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=participant,
                http=http,
                clock=clock,
                lookup_token=LOOKUP_TOKEN,
            )


@pytest.mark.asyncio
async def test_explicit_metadata_skips_sip() -> None:
    raw = json.dumps(
        {
            "customer_service_id": str(TENANT_AGENT_A.instance_id),
            "tenant_id": str(TENANT_A),
            "config_version": 3,
        }
    )
    ctx = SimpleNamespace(
        room=SimpleNamespace(name="web-room"),
        job=SimpleNamespace(metadata=raw),
        wait_for_participant=lambda: (_ for _ in ()).throw(AssertionError("waited")),
    )
    assert explicit_job_metadata(ctx) == DispatchMetadata.from_json(raw)

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("lookup must not run for explicit metadata")

    async with _http(handler) as http:
        metadata = await resolve_runtime_dispatch(ctx, http=http)
    assert metadata is not None
    assert metadata.channel == "web"


@pytest.mark.asyncio
async def test_web_participant_returns_none_for_local_fail_closed() -> None:
    ctx = SimpleNamespace(
        room=SimpleNamespace(name="web-room"),
        job=SimpleNamespace(metadata=""),
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("web participant must not lookup")

    async with _http(handler) as http:
        metadata = await resolve_runtime_dispatch(
            ctx,
            http=http,
            participant=sip_participant(kind=web_kind()),
        )
    assert metadata is None


@pytest.mark.asyncio
async def test_platform_view_extra_fields_are_accepted() -> None:
    resolver_calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        resolver_calls.append(request.url.params.get("number"))
        return httpx.Response(200, json=lookup_payload(TENANT_AGENT_A))

    async with _http(handler) as http:
        found = await PlatformDestinationResolver(
            http, lookup_token=LOOKUP_TOKEN
        ).resolve(CALLEE_A)
    assert found is not None
    assert found.tenant_id == TENANT_A
    assert resolver_calls == [CALLEE_A]


@pytest.mark.asyncio
async def test_enabled_must_be_boolean() -> None:
    payload = lookup_payload(TENANT_AGENT_A)
    payload["enabled"] = "false"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with _http(handler) as http:
        with pytest.raises(
            RuntimeConfigurationError, match="enabled must be a boolean"
        ):
            await PlatformDestinationResolver(http, lookup_token=LOOKUP_TOKEN).resolve(
                CALLEE_A
            )


@pytest.mark.asyncio
async def test_missing_lookup_token_fails_closed_without_http() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("lookup must not run without a token")

    async with _http(handler) as http:
        with pytest.raises(
            RuntimeConfigurationError, match="lookup token is not configured"
        ):
            await PlatformDestinationResolver(http).resolve(CALLEE_A)


@pytest.mark.asyncio
async def test_lookup_401_fails_closed() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Unauthorized"})

    async with _http(handler) as http:
        with pytest.raises(RuntimeConfigurationError, match="HTTP 401"):
            await PlatformDestinationResolver(http, lookup_token=LOOKUP_TOKEN).resolve(
                CALLEE_A
            )


@pytest.mark.asyncio
async def test_await_joining_participant_requests_sip_kind() -> None:
    participant = sip_participant()
    ctx = SipJobContext(room_name="yino-sip-wait", participant=participant)
    joined = await await_joining_participant(ctx)
    assert joined is participant
    assert ctx.wait_kwargs == {"kind": LIVEKIT_SIP_PARTICIPANT_KIND}


@pytest.mark.asyncio
async def test_await_joining_participant_rejects_web_when_sip_only() -> None:
    ctx = SipJobContext(
        room_name="web-room",
        participant=sip_participant(kind=web_kind()),
    )
    with pytest.raises(RuntimeConfigurationError, match="SIP participant did not join"):
        await await_joining_participant(ctx)


@pytest.mark.asyncio
async def test_await_joining_participant_allows_web_when_not_sip_only() -> None:
    participant = sip_participant(kind=web_kind())
    ctx = SipJobContext(room_name="web-room", participant=participant)
    joined = await await_joining_participant(ctx, sip_only=False)
    assert joined is participant
    assert ctx.wait_kwargs == {}
