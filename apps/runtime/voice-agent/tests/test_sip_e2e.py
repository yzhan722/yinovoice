from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from sip_fakes import (
    AGENT_A,
    CALLEE_A,
    CALLEE_B,
    TENANT_A,
    TENANT_AGENT_A,
    TENANT_AGENT_B,
    FakeTenantAgent,
    PlatformSipTransport,
    SipJobContext,
    closable_session,
    immediate_session,
    patched_voice_agent,
    sip_attributes,
    sip_participant,
    web_kind,
)
from test_server import _ClosableSession, runtime_customer_service

from yino_voice_agent.runtime_config import RuntimeConfigurationError
from yino_voice_agent.server import _ended_from_close, local_voice_agent
from yino_voice_agent.telephony.livekit_sip import LIVEKIT_SIP_PARTICIPANT_KIND
from yino_voice_agent.tool_protocol import encode_tool_marker


async def _wait_close_handler(
    session: _ClosableSession, task: asyncio.Task[None]
) -> None:
    for _ in range(100):
        if session._close_handler is not None or task.done():
            break
        await asyncio.sleep(0)
    assert session._close_handler is not None
    assert not task.done()


@pytest.mark.asyncio
async def test_case1_known_callee_uses_tenant_a() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-a",
        participant=sip_participant(),
    )
    session = immediate_session()
    with patched_voice_agent(
        transport=transport, session_factory=lambda: session
    ) as orgs:
        await local_voice_agent(ctx)
    assert orgs == ["Tenant A Clinic"]
    assert transport.lookup_numbers == [CALLEE_A]
    assert transport.snapshot_orgs == ["Tenant A Clinic"]
    assert transport.start_bodies[0]["customer_service_id"] == str(AGENT_A)
    session.start.assert_awaited_once()
    assert ctx.wait_kwargs.get("kind") == LIVEKIT_SIP_PARTICIPANT_KIND


@pytest.mark.asyncio
async def test_case2_other_callee_uses_tenant_b_never_a() -> None:
    transport = PlatformSipTransport(
        {CALLEE_A: TENANT_AGENT_A, CALLEE_B: TENANT_AGENT_B}
    )
    ctx = SipJobContext(
        room_name="yino-sip-b",
        participant=sip_participant(attributes=sip_attributes(callee=CALLEE_B)),
    )
    with patched_voice_agent(
        transport=transport, session_factory=immediate_session
    ) as orgs:
        await local_voice_agent(ctx)
    assert orgs == ["Tenant B Clinic"]
    assert "Tenant A Clinic" not in orgs
    assert transport.start_bodies[0]["customer_service_id"] == str(
        TENANT_AGENT_B.instance_id
    )


@pytest.mark.asyncio
async def test_case3_unknown_number_does_not_start_agent() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-unknown",
        participant=sip_participant(
            attributes=sip_attributes(callee="+61390000999")
        ),
    )
    factory = Mock(side_effect=immediate_session)
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        pytest.raises(RuntimeConfigurationError, match="destination not found"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    assert transport.start_bodies == []
    assert transport.snapshot_orgs == []


@pytest.mark.asyncio
async def test_case4_disabled_number_does_not_start_agent() -> None:
    disabled = FakeTenantAgent(
        tenant_id=TENANT_A,
        instance_id=AGENT_A,
        version=3,
        organization_name="Tenant A Clinic",
        callee=CALLEE_A,
        enabled=False,
    )
    transport = PlatformSipTransport({CALLEE_A: disabled})
    ctx = SipJobContext(room_name="yino-sip-disabled", participant=sip_participant())
    factory = Mock(side_effect=immediate_session)
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        pytest.raises(RuntimeConfigurationError, match="disabled"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    assert transport.start_bodies == []


@pytest.mark.asyncio
async def test_case5_missing_caller_still_routes_on_callee() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-anon",
        participant=sip_participant(attributes=sip_attributes(caller=None)),
    )
    with patched_voice_agent(
        transport=transport, session_factory=immediate_session
    ) as orgs:
        await local_voice_agent(ctx)
    assert orgs == ["Tenant A Clinic"]
    assert "caller_number" not in transport.start_bodies[0]
    assert transport.start_bodies[0]["callee_number"] == CALLEE_A


@pytest.mark.asyncio
async def test_case6_missing_callee_fails_closed() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-no-callee",
        participant=sip_participant(attributes=sip_attributes(callee=None)),
    )
    factory = Mock(side_effect=immediate_session)
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        pytest.raises(RuntimeConfigurationError, match="callee"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    assert transport.lookup_numbers == []


@pytest.mark.asyncio
async def test_case7_call_id_fallback() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-fallback",
        participant=sip_participant(
            attributes=sip_attributes(call_id_full=None, call_id="lk-only-7")
        ),
    )
    with patched_voice_agent(transport=transport, session_factory=immediate_session):
        await local_voice_agent(ctx)
    assert transport.start_bodies[0]["provider_call_id"] == "lk-only-7"


@pytest.mark.asyncio
async def test_case8_platform_timeout_does_not_fallback() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A}, lookup_mode="timeout")
    ctx = SipJobContext(room_name="yino-sip-timeout", participant=sip_participant())
    factory = Mock(side_effect=immediate_session)
    console = Mock()
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        patch("yino_voice_agent.server.create_console_runtime", console),
        pytest.raises(RuntimeConfigurationError, match="destination lookup failed"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    console.assert_not_called()


@pytest.mark.asyncio
async def test_case9_platform_500_does_not_fallback() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A}, lookup_mode="http_500")
    ctx = SipJobContext(room_name="yino-sip-500", participant=sip_participant())
    factory = Mock(side_effect=immediate_session)
    console = Mock()
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        patch("yino_voice_agent.server.create_console_runtime", console),
        pytest.raises(RuntimeConfigurationError, match="HTTP 500"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    console.assert_not_called()


@pytest.mark.asyncio
async def test_case10_web_participant_empty_metadata_rejected() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="web-room",
        participant=sip_participant(kind=web_kind()),
    )
    factory = Mock(side_effect=immediate_session)
    console = Mock()
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        patch("yino_voice_agent.server.create_console_runtime", console),
        pytest.raises(RuntimeConfigurationError, match="SIP participant did not join"),
    ):
        await local_voice_agent(ctx)
    assert ctx.wait_calls == 1
    assert ctx.wait_kwargs.get("kind") == LIVEKIT_SIP_PARTICIPANT_KIND
    factory.assert_not_called()
    console.assert_not_called()
    assert transport.lookup_numbers == []


@pytest.mark.asyncio
async def test_case11_explicit_job_metadata_skips_sip_wait() -> None:
    runtime = runtime_customer_service()
    matching = FakeTenantAgent(
        tenant_id=runtime.tenant_id,
        instance_id=runtime.id,
        version=runtime.version,
        organization_name=runtime.organization_name,
        callee=CALLEE_A,
    )
    transport = PlatformSipTransport({CALLEE_A: matching})
    ctx = SipJobContext(
        room_name="web-dispatch",
        participant=sip_participant(),
        metadata=json.dumps(
            {
                "customer_service_id": str(runtime.id),
                "tenant_id": str(runtime.tenant_id),
                "config_version": runtime.version,
            }
        ),
    )
    with patched_voice_agent(
        transport=transport, session_factory=immediate_session
    ) as orgs:
        await local_voice_agent(ctx)
    assert ctx.wait_calls == 0
    assert transport.lookup_numbers == []
    assert orgs == [runtime.organization_name]


@pytest.mark.asyncio
async def test_sip_user_hangup_finish_once() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(room_name="yino-sip-hangup", participant=sip_participant())
    session = closable_session()
    with patched_voice_agent(transport=transport, session_factory=lambda: session):
        task = asyncio.create_task(local_voice_agent(ctx))
        await _wait_close_handler(session, task)
        session.emit_close(reason_name="PARTICIPANT_DISCONNECTED")
        await asyncio.wait_for(task, timeout=2)
    assert len(transport.finish_bodies) == 1
    assert transport.finish_bodies[0]["status"] == "completed"
    assert transport.finish_bodies[0]["ended_reason"] == "user_hangup"


@pytest.mark.asyncio
async def test_sip_agent_exception_finish_once_failed() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(room_name="yino-sip-error", participant=sip_participant())
    session = closable_session()
    session.start = _async_fail()
    with (
        patched_voice_agent(transport=transport, session_factory=lambda: session),
        pytest.raises(RuntimeError, match="agent exploded"),
    ):
        await local_voice_agent(ctx)
    assert len(transport.finish_bodies) == 1
    assert transport.finish_bodies[0]["status"] == "failed"
    assert transport.finish_bodies[0]["ended_reason"] == "agent_error"


def _async_fail() -> Callable[..., object]:
    async def _start(**_kwargs: object) -> None:
        raise RuntimeError("agent exploded")

    return _start


@pytest.mark.asyncio
async def test_sip_close_and_shutdown_one_finish() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="yino-sip-race",
        participant=sip_participant(),
        capture_shutdown=True,
    )
    session = closable_session()
    with patched_voice_agent(transport=transport, session_factory=lambda: session):
        task = asyncio.create_task(local_voice_agent(ctx))
        await _wait_close_handler(session, task)
        session.emit_close(reason_name="PARTICIPANT_DISCONNECTED")
        await asyncio.gather(*(callback("") for callback in ctx.shutdown_callbacks))
        await asyncio.wait_for(task, timeout=2)
    assert len(transport.finish_bodies) == 1
    assert transport.finish_bodies[0]["ended_reason"] == "user_hangup"


@pytest.mark.asyncio
async def test_sip_close_storm_one_finish() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(room_name="yino-sip-storm", participant=sip_participant())
    session = closable_session()
    with patched_voice_agent(transport=transport, session_factory=lambda: session):
        task = asyncio.create_task(local_voice_agent(ctx))
        await _wait_close_handler(session, task)
        session.emit_close(reason_name="PARTICIPANT_DISCONNECTED")
        session.emit_close(reason_name="USER_INITIATED")
        session.emit_close(reason_name="TASK_COMPLETED")
        await asyncio.wait_for(task, timeout=2)
    assert len(transport.finish_bodies) == 1


class _ToolSession(_ClosableSession):
    def __init__(self) -> None:
        super().__init__()
        self._item = None
        self.start = self._start_with_tool

    def on(self, event: str, handler: object) -> None:
        if event == "close":
            self._close_handler = handler
        elif event == "conversation_item_added":
            self._item = handler

    async def _start_with_tool(self, **_kwargs: object) -> None:
        marker = encode_tool_marker(
            "create_callback", {"phone": "13800138000", "reason": "sip"}
        )
        assert callable(self._item)
        self._item(
            SimpleNamespace(
                item=SimpleNamespace(
                    role="assistant",
                    text_content=f"ack\n{marker}",
                )
            )
        )


@pytest.mark.asyncio
async def test_tool_in_flight_hangup_one_finish_no_orphan() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A}, tool_timeout=True)
    ctx = SipJobContext(room_name="yino-sip-tool", participant=sip_participant())
    session = _ToolSession()
    before = {id(task) for task in asyncio.all_tasks()}
    with patched_voice_agent(transport=transport, session_factory=lambda: session):
        task = asyncio.create_task(local_voice_agent(ctx))
        await transport.tool_started.wait()
        await _wait_close_handler(session, task)
        session.emit_close(reason_name="PARTICIPANT_DISCONNECTED")
        transport.release_tool.set()
        await asyncio.wait_for(task, timeout=2)
    assert len(transport.finish_bodies) == 1
    pending = [
        item
        for item in asyncio.all_tasks()
        if id(item) not in before and not item.done()
    ]
    assert pending == []


@pytest.mark.asyncio
async def test_five_concurrent_sip_calls_are_isolated() -> None:
    await _assert_n_sip_calls(5, round_id=0)


@pytest.mark.asyncio
async def test_ten_sip_sessions_isolated_three_repeats() -> None:
    for round_id in range(3):
        await _assert_n_sip_calls(10, round_id=round_id)


async def _assert_n_sip_calls(count: int, *, round_id: int) -> None:
    agents: dict[str, FakeTenantAgent] = {}
    contexts: list[SipJobContext] = []
    for index in range(count):
        callee = f"+61391{round_id:02d}{index:04d}"
        agent = FakeTenantAgent(
            tenant_id=UUID(f"aaaaaaaa-0000-4000-8000-{round_id:04d}{index:08d}"),
            instance_id=UUID(f"bbbbbbbb-0000-4000-8000-{round_id:04d}{index:08d}"),
            version=1,
            organization_name=f"Tenant R{round_id} N{index}",
            callee=callee,
        )
        agents[callee] = agent
        contexts.append(
            SipJobContext(
                room_name=f"yino-sip-r{round_id}-n{index}",
                participant=sip_participant(
                    attributes=sip_attributes(
                        callee=callee,
                        caller=None,
                        call_id_full=f"full-r{round_id}-n{index}",
                        call_id=f"id-r{round_id}-n{index}",
                    )
                ),
            )
        )
    transport = PlatformSipTransport(agents)
    sessions: list[_ClosableSession] = []

    def factory() -> _ClosableSession:
        session = closable_session()
        sessions.append(session)
        return session

    with patched_voice_agent(transport=transport, session_factory=factory) as orgs:
        tasks = [asyncio.create_task(local_voice_agent(ctx)) for ctx in contexts]
        for _ in range(200):
            if len(sessions) == count and all(
                item._close_handler is not None for item in sessions
            ):
                break
            failed = [item for item in tasks if item.done() and item.exception()]
            if failed:
                await failed[0]
            await asyncio.sleep(0)
        assert len(sessions) == count
        for session in sessions:
            session.emit_close(reason_name="PARTICIPANT_DISCONNECTED")
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
    assert len(set(orgs)) == count
    rooms = [str(body["room_name"]) for body in transport.start_bodies]
    tenants = [str(body["customer_service_id"]) for body in transport.start_bodies]
    assert len(set(rooms)) == count
    assert len(set(tenants)) == count
    assert len(transport.finish_bodies) == count
    assert all(
        body["ended_reason"] == "user_hangup" for body in transport.finish_bodies
    )


@pytest.mark.asyncio
async def test_slow_lookup_does_not_block_other_session() -> None:
    slow = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A}, lookup_mode="slow")
    fast = PlatformSipTransport({CALLEE_B: TENANT_AGENT_B})
    slow_ctx = SipJobContext(
        room_name="slow-room",
        participant=sip_participant(),
    )
    fast_ctx = SipJobContext(
        room_name="fast-room",
        participant=sip_participant(attributes=sip_attributes(callee=CALLEE_B)),
    )
    fast_done = asyncio.Event()

    async def run_fast() -> None:
        with patched_voice_agent(
            transport=fast, session_factory=immediate_session
        ):
            await local_voice_agent(fast_ctx)
        fast_done.set()

    async def run_slow() -> None:
        with patched_voice_agent(
            transport=slow, session_factory=immediate_session
        ):
            await local_voice_agent(slow_ctx)

    slow_task = asyncio.create_task(run_slow())
    await slow.slow_started.wait()
    await run_fast()
    assert fast_done.is_set()
    assert not slow_task.done()
    slow.release_slow.set()
    await slow_task
    assert fast.start_bodies[0]["callee_number"] == CALLEE_B
    assert slow.start_bodies[0]["callee_number"] == CALLEE_A


@pytest.mark.asyncio
async def test_malformed_sip_does_not_start_or_lookup() -> None:
    transport = PlatformSipTransport({CALLEE_A: TENANT_AGENT_A})
    ctx = SipJobContext(
        room_name="malformed",
        participant=sip_participant(
            attributes=sip_attributes(call_id_full=None, call_id=None)
        ),
    )
    factory = Mock(side_effect=immediate_session)
    with (
        patched_voice_agent(transport=transport, session_factory=factory),
        pytest.raises(RuntimeConfigurationError, match=r"sip\.callID"),
    ):
        await local_voice_agent(ctx)
    factory.assert_not_called()
    assert transport.lookup_numbers == []


def test_ended_from_close_maps_documented_reasons() -> None:
    disconnected = SimpleNamespace(
        reason=SimpleNamespace(name="PARTICIPANT_DISCONNECTED"), error=None
    )
    assert _ended_from_close(disconnected) == ("completed", "user_hangup")
    user_initiated = SimpleNamespace(
        reason=SimpleNamespace(name="USER_INITIATED"), error=None
    )
    assert _ended_from_close(user_initiated) == ("completed", "user_hangup")
    disconnect_alias = SimpleNamespace(
        reason=SimpleNamespace(name="CLIENT_INITIATED"),
        error=None,
    )
    assert _ended_from_close(disconnect_alias) == ("completed", "user_hangup")
    unclear = SimpleNamespace(reason=SimpleNamespace(name="ROOM_DELETED"), error=None)
    assert _ended_from_close(unclear) == ("completed", "completed")
    trunk_alias = SimpleNamespace(
        reason=SimpleNamespace(name="SIP_TRUNK_FAILURE"), error=None
    )
    assert _ended_from_close(trunk_alias) == ("failed", "agent_error")
    error = SimpleNamespace(reason=SimpleNamespace(name="ERROR"), error=object())
    assert _ended_from_close(error) == ("failed", "agent_error")
