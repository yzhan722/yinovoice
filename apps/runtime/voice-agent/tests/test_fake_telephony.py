from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from yino_voice_agent.runtime_config import RuntimeConfigurationError
from yino_voice_agent.telephony import (
    FakeDestinationResolver,
    FakeInboundProvider,
    InboundCallAdapter,
    PlatformDestinationResolver,
    ResolvedDestination,
)
from yino_voice_agent.telephony.resolver import PHONE_LOOKUP_HEADER

TENANT = UUID("00000000-0000-0000-0000-000000000001")
INSTANCE = UUID("00000000-0000-0000-0000-000000000101")
KNOWN = "+61400000099"
DISABLED = "+61400000098"
UNKNOWN = "+61400000097"
LOOKUP_TOKEN = "test-phone-lookup-token"


def _resolver() -> FakeDestinationResolver:
    return FakeDestinationResolver(
        {
            KNOWN: ResolvedDestination(
                tenant_id=TENANT,
                customer_service_id=INSTANCE,
                config_version=3,
                enabled=True,
            ),
            DISABLED: ResolvedDestination(
                tenant_id=TENANT,
                customer_service_id=INSTANCE,
                config_version=3,
                enabled=False,
            ),
        }
    )


@pytest.mark.asyncio
async def test_known_inbound_dispatches_runtime_metadata() -> None:
    adapter = InboundCallAdapter(
        provider=FakeInboundProvider(), resolver=_resolver()
    )
    metadata = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-1",
        callee_number=KNOWN,
        caller_number="+61400000001",
        room_name="sip-room-1",
    )
    assert metadata is not None
    assert metadata.channel == "sip"
    assert metadata.tenant_id == TENANT
    assert metadata.customer_service_id == INSTANCE
    assert metadata.config_version == 3
    assert metadata.caller_number == "+61400000001"
    assert metadata.callee_number == KNOWN
    assert metadata.provider_call_id == "prov-1"


@pytest.mark.asyncio
async def test_unknown_disabled_missing_caller_and_duplicate_are_safe() -> None:
    adapter = InboundCallAdapter(
        provider=FakeInboundProvider(), resolver=_resolver()
    )
    unknown = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-unknown",
        callee_number=UNKNOWN,
        caller_number="+61400000001",
    )
    disabled = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-disabled",
        callee_number=DISABLED,
        caller_number="+61400000001",
    )
    missing_caller = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-missing-caller",
        callee_number=KNOWN,
        caller_number=None,
    )
    first = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-dup",
        callee_number=KNOWN,
        caller_number="+61400000001",
    )
    duplicate = await adapter.dispatch(
        provider="fake-sip",
        provider_call_id="prov-dup",
        callee_number=KNOWN,
        caller_number="+61400000002",
    )

    assert unknown is None
    assert disabled is None
    assert missing_caller is not None
    assert missing_caller.caller_number is None
    assert first is not None
    assert duplicate is None


@pytest.mark.asyncio
async def test_platform_lookup_maps_and_rejects_incomplete_contract() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        number = request.url.params.get("number")
        if number == UNKNOWN:
            return httpx.Response(404)
        if number == KNOWN:
            return httpx.Response(
                200,
                json={
                    "tenant_id": str(TENANT),
                    "voice_agent_instance_id": str(INSTANCE),
                    "config_version": 4,
                    "enabled": True,
                },
            )
        return httpx.Response(200, json={"tenant_id": str(TENANT)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://platform.test"
    ) as http:
        resolver = PlatformDestinationResolver(http, lookup_token=LOOKUP_TOKEN)
        found = await resolver.resolve(KNOWN)
        missing = await resolver.resolve(UNKNOWN)
        with pytest.raises(RuntimeConfigurationError, match="missing fields"):
            await resolver.resolve(DISABLED)

    assert found is not None
    assert found.config_version == 4
    assert missing is None
    assert seen[0].url.path == "/api/v1/phone-numbers/lookup"
    assert seen[0].headers.get(PHONE_LOOKUP_HEADER) == LOOKUP_TOKEN


@pytest.mark.asyncio
async def test_platform_lookup_timeout_and_http_error_fail_closed() -> None:
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    def boom_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout_handler),
        base_url="http://platform.test",
    ) as http:
        with pytest.raises(
            RuntimeConfigurationError, match="destination lookup failed"
        ):
            await PlatformDestinationResolver(
                http, lookup_token=LOOKUP_TOKEN
            ).resolve(KNOWN)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(boom_handler),
        base_url="http://platform.test",
    ) as http:
        with pytest.raises(RuntimeConfigurationError, match="HTTP 500"):
            await PlatformDestinationResolver(
                http, lookup_token=LOOKUP_TOKEN
            ).resolve(KNOWN)


def test_normalized_inbound_is_not_raw_provider_json() -> None:
    provider = FakeInboundProvider()
    call = provider.ingest(
        provider="fake-sip",
        provider_call_id="prov-model",
        callee_number=KNOWN,
        caller_number="+61400000001",
        connected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert call is not None
    assert call.direction == "inbound"
    dumped = asdict(call)
    assert "payload" not in dumped
    assert set(dumped) == {
        "provider",
        "provider_call_id",
        "caller_number",
        "callee_number",
        "direction",
        "connected_at",
        "room_name",
        "trunk_id",
        "rule_id",
    }
