from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from hardening_support import FailureScenario, FakePlatform, sip_participant

from yino_voice_agent.errors import (
    DestinationResolutionError,
    TelephonyNormalizationError,
)
from yino_voice_agent.replay import (
    ReplayEngine,
    ReplayEvent,
    ReplayFixture,
    load_fixture,
    sanitize_event_data,
)
from yino_voice_agent.runtime_config import RuntimeConfigurationError
from yino_voice_agent.telephony.dispatch import resolve_sip_inbound_dispatch
from yino_voice_agent.telephony.livekit_sip import normalize_livekit_sip_participant

TENANT = UUID("aaaaaaaa-0000-4000-8000-000000000001")
SERVICE = UUID("aaaaaaaa-0000-4000-8000-0000000000aa")
LOOKUP = "test-phone-lookup-token"


def test_sanitize_drops_secrets_and_phones() -> None:
    cleaned = sanitize_event_data(
        {
            "audio": "AAAA",
            "transcript": "hello",
            "token": "secret",
            "ok": "room-1",
            "caller_number": "+61400000001",
        }
    )
    assert "audio" not in cleaned
    assert "transcript" not in cleaned
    assert "token" not in cleaned
    assert "caller_number" not in cleaned
    assert cleaned["ok"] == "room-1"


def test_load_fixture_rejects_bad_source() -> None:
    with pytest.raises(ValueError):
        load_fixture(
            json.dumps(
                {
                    "schema_version": 1,
                    "events": [
                        {"at_ms": 0, "source": "s3", "type": "upload", "data": {}}
                    ],
                }
            )
        )


def _voice_fixture() -> ReplayFixture:
    return ReplayFixture(
        schema_version=1,
        events=(
            ReplayEvent(0, "runtime", "session_start", {"provider_call_id": "p1"}),
            ReplayEvent(10, "runtime", "user_final", {"text": "hello-user"}),
            ReplayEvent(
                20,
                "qwen",
                "assistant_final",
                {"spoken": "hello-back", "tool_name": "check_availability"},
            ),
            ReplayEvent(
                30,
                "qwen",
                "response.done",
                {
                    "response_id": "resp-1",
                    "usage": {
                        "total_tokens": 9,
                        "input_tokens": 6,
                        "output_tokens": 3,
                    },
                },
            ),
            ReplayEvent(40, "livekit", "hangup", {}),
        ),
    )


@pytest.mark.asyncio
async def test_replay_is_deterministic_across_three_runs() -> None:
    platform = FakePlatform()
    fixture = _voice_fixture()
    results = []
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        for _ in range(3):
            engine = ReplayEngine(
                http=http,
                tenant_id=TENANT,
                session_id="replay-room",
                customer_service_id=SERVICE,
            )
            results.append(await engine.run(fixture))
    first = results[0]
    for item in results[1:]:
        assert item.finish_outcome == first.finish_outcome
        assert item.tool_names == first.tool_names
        assert item.usage.as_dict() == first.usage.as_dict()
        assert item.trace_order == first.trace_order
        assert item.finish_count == 1
    assert first.tool_names == ["check_availability"]
    assert first.usage.total_tokens == 9


def _sip_event(attributes: dict[str, str]) -> ReplayFixture:
    return ReplayFixture(
        schema_version=1,
        events=(
            ReplayEvent(
                0,
                "livekit",
                "participant_joined",
                {"attributes": attributes},
            ),
            ReplayEvent(5, "runtime", "user_final", {"text": "sip-hello"}),
            ReplayEvent(10, "runtime", "hangup", {}),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,attributes,lookup_status,expect_error",
    [
        (
            "normal",
            {
                "sip.callIDFull": "full-1",
                "sip.callID": "short-1",
                "sip.phoneNumber": "+61400000001",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.trunkID": "ST_TEST",
                "sip.ruleID": "SDR_TEST",
                "sip.callStatus": "active",
            },
            200,
            False,
        ),
        (
            "hidden_caller",
            {
                "sip.callIDFull": "full-2",
                "sip.callID": "short-2",
                "sip.phoneNumber": "anonymous",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            200,
            False,
        ),
        (
            "missing_caller",
            {
                "sip.callIDFull": "full-3",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            200,
            False,
        ),
        (
            "fallback_call_id",
            {
                "sip.callID": "short-only",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            200,
            False,
        ),
        (
            "missing_callee",
            {"sip.callIDFull": "full-x", "sip.callStatus": "active"},
            200,
            True,
        ),
        (
            "missing_call_id",
            {"sip.trunkPhoneNumber": "+61390000001", "sip.callStatus": "active"},
            200,
            True,
        ),
        (
            "lookup_401",
            {
                "sip.callIDFull": "full-401",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            401,
            True,
        ),
        (
            "lookup_404",
            {
                "sip.callIDFull": "full-404",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            404,
            True,
        ),
        (
            "lookup_500",
            {
                "sip.callIDFull": "full-500",
                "sip.trunkPhoneNumber": "+61390000001",
                "sip.callStatus": "active",
            },
            500,
            True,
        ),
    ],
)
async def test_sip_synthetic_replay_matrix(
    label: str,
    attributes: dict[str, str],
    lookup_status: int,
    expect_error: bool,
) -> None:
    _ = label
    platform = FakePlatform(FailureScenario(lookup_status=lookup_status))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        engine = ReplayEngine(
            http=http,
            tenant_id=TENANT,
            session_id=f"sip-{label}",
            customer_service_id=SERVICE,
            lookup_token=LOOKUP,
        )
        result = await engine.run(_sip_event(attributes))
    if expect_error:
        assert "sip_dispatch_failed" in result.errors or result.errors
    else:
        assert result.errors == []
        assert result.sip_provider_call_id
        assert result.finish_count == 1


@pytest.mark.asyncio
async def test_unknown_and_disabled_destination_fail_closed() -> None:
    ctx = SimpleNamespace(
        room=SimpleNamespace(name="sip-unknown"),
        job=SimpleNamespace(metadata=""),
    )
    platform = FakePlatform(FailureScenario(lookup_status=404))
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        with pytest.raises(RuntimeConfigurationError):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=sip_participant(),
                http=http,
                lookup_token=LOOKUP,
            )
    disabled = FakePlatform(FailureScenario(lookup_enabled=False))
    async with httpx.AsyncClient(
        transport=disabled, base_url="http://platform.test"
    ) as http:
        with pytest.raises(RuntimeConfigurationError, match="disabled"):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=sip_participant(),
                http=http,
                lookup_token=LOOKUP,
            )


def test_normalize_rejects_missing_callee() -> None:
    participant = sip_participant(callee=None)
    participant.attributes.pop("sip.trunkPhoneNumber", None)
    with pytest.raises(TelephonyNormalizationError):
        normalize_livekit_sip_participant(participant, room_name="r")


@pytest.mark.asyncio
async def test_lookup_timeout_is_destination_error() -> None:
    class _Timeout(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("lookup timeout")

    async with httpx.AsyncClient(
        transport=_Timeout(), base_url="http://platform.test"
    ) as http:
        ctx = SimpleNamespace(
            room=SimpleNamespace(name="sip-timeout"),
            job=SimpleNamespace(metadata=""),
        )
        with pytest.raises(DestinationResolutionError):
            await resolve_sip_inbound_dispatch(
                ctx,
                participant=sip_participant(),
                http=http,
                lookup_token=LOOKUP,
            )
