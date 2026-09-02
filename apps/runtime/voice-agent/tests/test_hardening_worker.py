from __future__ import annotations

import asyncio

import httpx
import pytest
from hardening_support import FakePlatform, make_spec, metadata_for, runtime_tasks

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.errors import WorkerNotAcceptingError
from yino_voice_agent.worker import WorkerSessionRegistry


async def _lifecycle(http: httpx.AsyncClient, index: int) -> CallLifecycleClient:
    spec = make_spec(index, session_id=f"drain-{index}", room_name=f"drain-{index}")
    lifecycle = CallLifecycleClient(http, spec.tenant_id)
    await lifecycle.start_from_dispatch(metadata_for(spec), spec.room_name)
    return lifecycle


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 10, 50])
async def test_worker_drain_finishes_each_session_once(count: int) -> None:
    platform = FakePlatform()
    registry = WorkerSessionRegistry()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        for index in range(count):
            lifecycle = await _lifecycle(http, index)
            registry.register(f"drain-{index}", lifecycle)
        before = runtime_tasks()
        await registry.drain()
        leftover = runtime_tasks() - before
        assert leftover == set()
        assert platform.finish_count() == count
        assert registry.active_count == 0
        with pytest.raises(WorkerNotAcceptingError):
            late = await _lifecycle(http, 99)
            registry.register("late", late)


@pytest.mark.asyncio
async def test_drain_does_not_double_finish() -> None:
    platform = FakePlatform()
    registry = WorkerSessionRegistry()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        lifecycle = await _lifecycle(http, 0)
        registry.register("drain-0", lifecycle)
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        await registry.drain()
    assert platform.finish_count() == 1


@pytest.mark.asyncio
async def test_register_rejected_while_draining() -> None:
    registry = WorkerSessionRegistry()
    registry.begin_drain()
    with pytest.raises(WorkerNotAcceptingError):
        registry.register("late")


@pytest.mark.asyncio
async def test_duplicate_register_and_unregister_once() -> None:
    registry = WorkerSessionRegistry()
    registry.register("once")
    with pytest.raises(RuntimeError, match="already registered"):
        registry.register("once")
    assert registry.unregister("once") is True
    assert registry.unregister("once") is False
    assert registry.total_started == 1
    assert registry.active_count == 0


@pytest.mark.asyncio
async def test_drain_timeout_clears_hung_session() -> None:
    registry = WorkerSessionRegistry()
    stuck = asyncio.Event()

    async def hang() -> None:
        await stuck.wait()

    registry.register("hung", finish=hang)
    await registry.drain(timeout_s=0.05)
    assert registry.active_count == 0
    stuck.set()
