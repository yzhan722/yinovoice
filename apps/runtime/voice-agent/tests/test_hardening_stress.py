from __future__ import annotations

import asyncio
import random
from uuid import UUID

import httpx
import pytest
from hardening_support import (
    FailureScenario,
    FakePlatform,
    make_spec,
    run_multi_turn_session,
    runtime_tasks,
)

TENANT_POOL = [
    UUID("aaaaaaaa-0000-4000-8000-00000000000a"),
    UUID("bbbbbbbb-0000-4000-8000-00000000000b"),
    UUID("cccccccc-0000-4000-8000-00000000000c"),
    UUID("dddddddd-0000-4000-8000-00000000000d"),
    UUID("eeeeeeee-0000-4000-8000-00000000000e"),
]
SERVICE_POOL = [
    UUID("aaaaaaaa-0000-4000-8000-0000000000a1"),
    UUID("bbbbbbbb-0000-4000-8000-0000000000b1"),
    UUID("cccccccc-0000-4000-8000-0000000000c1"),
    UUID("dddddddd-0000-4000-8000-0000000000d1"),
    UUID("eeeeeeee-0000-4000-8000-0000000000e1"),
]


async def _matrix(calls: int, turns: int, seed: int = 42) -> None:
    rng = random.Random(seed)
    platform = FakePlatform()
    specs = []
    for index in range(calls):
        bucket = index % 5
        specs.append(
            make_spec(
                index,
                tenant_id=TENANT_POOL[bucket],
                customer_service_id=SERVICE_POOL[bucket],
                session_id=f"load-{calls}-{index}",
                room_name=f"load-{calls}-{index}",
                transcript=f"load-hello-{index}",
                greeting=f"load-greet-{index}",
                use_tool=rng.random() < 0.10,
                interrupt=rng.random() < 0.10,
                qwen_error=rng.random() < 0.05,
                early_hangup=rng.random() < 0.05,
            )
        )
    before = runtime_tasks()
    unhandled: list[BaseException] = []

    async def _one(spec: object) -> None:
        try:
            await run_multi_turn_session(http, spec, turns=turns)  # type: ignore[arg-type]
        except Exception as error:
            unhandled.append(error)

    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        await asyncio.gather(*[_one(spec) for spec in specs])
    leftover = runtime_tasks() - before
    assert leftover == set()
    assert unhandled == []
    assert platform.finish_count() == calls
    for record_id, count in platform.finish_by_record.items():
        assert count == 1, record_id
    sessions = {spec.session_id for spec in specs}
    for session_id in platform.tools_by_session:
        assert session_id in sessions
    tenants = {platform.tenant_by_session[spec.session_id] for spec in specs}
    assert len(tenants) == min(5, calls)


@pytest.mark.asyncio
async def test_load_matrix_repeatable() -> None:
    for _ in range(3):
        await _matrix(10, 20)
        await _matrix(25, 20)
        await _matrix(50, 10)


@pytest.mark.asyncio
async def test_failure_injection_delay_still_finishes_once() -> None:
    platform = FakePlatform(FailureScenario(platform_delay_s=0.002))
    spec = make_spec(0, session_id="delay-1", room_name="delay-1")
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        await run_multi_turn_session(http, spec, turns=3)
    assert platform.finish_count() == 1
