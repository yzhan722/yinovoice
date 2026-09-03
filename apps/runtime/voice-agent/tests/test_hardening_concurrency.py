from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
import pytest
from hardening_support import (
    TENANT_A,
    TENANT_B,
    FailureScenario,
    FakePlatform,
    make_spec,
    run_synthetic_session,
)

TENANTS = [
    UUID("aaaaaaaa-0000-4000-8000-00000000000a"),
    UUID("bbbbbbbb-0000-4000-8000-00000000000b"),
    UUID("cccccccc-0000-4000-8000-00000000000c"),
    UUID("dddddddd-0000-4000-8000-00000000000d"),
    UUID("eeeeeeee-0000-4000-8000-00000000000e"),
]
SERVICES = [
    UUID("aaaaaaaa-0000-4000-8000-0000000000a1"),
    UUID("bbbbbbbb-0000-4000-8000-0000000000b1"),
    UUID("cccccccc-0000-4000-8000-0000000000c1"),
    UUID("dddddddd-0000-4000-8000-0000000000d1"),
    UUID("eeeeeeee-0000-4000-8000-0000000000e1"),
]


async def _run_many(count: int) -> None:
    platform = FakePlatform()
    specs = [
        make_spec(
            index,
            tenant_id=TENANTS[index % 5],
            customer_service_id=SERVICES[index % 5],
            session_id=f"iso-room-{index}",
            room_name=f"iso-room-{index}",
            call_id=f"iso-call-{index}",
            provider_call_id=f"iso-provider-{index}",
            transcript=f"hello-{index}",
            greeting=f"greet-{index}",
        )
        for index in range(count)
    ]
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        results = await asyncio.gather(
            *[run_synthetic_session(http, spec) for spec in specs]
        )
    assert len(results) == count
    assert platform.finish_count() == count
    session_ids = [item.session_id for item in results]
    assert len(set(session_ids)) == count
    for spec in specs:
        tools = platform.tools_by_session.get(spec.session_id, [])
        assert len(tools) == 1
        assert tools[0]["session_id"] == spec.session_id
        messages = platform.messages_by_session.get(spec.session_id, [])
        spoken = [item["text"] for item in messages if item.get("role") == "user"]
        assert spec.transcript in spoken
        assert platform.finishes_for(spec.session_id) == 1
        assert platform.tenant_by_session[spec.session_id] == str(spec.tenant_id)
    tenants_seen = {platform.tenant_by_session[spec.session_id] for spec in specs}
    assert len(tenants_seen) == min(5, count)


@pytest.mark.asyncio
async def test_ten_concurrent_calls_are_isolated() -> None:
    await _run_many(10)


@pytest.mark.asyncio
async def test_twenty_five_concurrent_calls_are_isolated() -> None:
    await _run_many(25)


@pytest.mark.asyncio
async def test_fifty_concurrent_calls_are_isolated() -> None:
    await _run_many(50)


@pytest.mark.asyncio
async def test_five_tenants_do_not_cross_contaminate() -> None:
    platform = FakePlatform()
    specs = [
        make_spec(
            index,
            tenant_id=TENANTS[index],
            customer_service_id=SERVICES[index],
            session_id=f"tenant-room-{index}",
            room_name=f"tenant-room-{index}",
            transcript=f"tenant-hello-{index}",
            greeting=f"tenant-greet-{index}",
        )
        for index in range(5)
    ]
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        await asyncio.gather(*[run_synthetic_session(http, spec) for spec in specs])
    for spec in specs:
        tools = platform.tools_by_session[spec.session_id]
        assert tools[0]["session_id"] == spec.session_id
        assert platform.tenant_by_session[spec.session_id] == str(spec.tenant_id)
        for other in specs:
            if other.session_id == spec.session_id:
                continue
            texts = [
                item.get("text")
                for item in platform.messages_by_session[spec.session_id]
            ]
            assert other.transcript not in texts
            assert other.greeting not in "".join(str(item) for item in texts)


@pytest.mark.asyncio
async def test_platform_delay_does_not_mix_tenants() -> None:
    platform = FakePlatform(FailureScenario(platform_delay_s=0.01))
    specs = [
        make_spec(0, tenant_id=TENANT_A, session_id="delay-a", room_name="delay-a"),
        make_spec(1, tenant_id=TENANT_B, session_id="delay-b", room_name="delay-b"),
    ]
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        await asyncio.gather(*[run_synthetic_session(http, spec) for spec in specs])
    assert platform.tenant_by_session["delay-a"] == str(TENANT_A)
    assert platform.tenant_by_session["delay-b"] == str(TENANT_B)
