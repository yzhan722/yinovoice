"""Shared failure-injection and synthetic session helpers for Runtime tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx

from yino_voice_agent.call_lifecycle import CallLifecycleClient
from yino_voice_agent.runtime_config import DispatchMetadata
from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.tool_client import ToolInvocationClient
from yino_voice_agent.tool_orchestrator import ToolOrchestrator
from yino_voice_agent.tool_protocol import encode_tool_marker

TENANT_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
TENANT_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
SERVICE_A = UUID("aaaaaaaa-0000-4000-8000-0000000000aa")
SERVICE_B = UUID("bbbbbbbb-0000-4000-8000-0000000000bb")


@dataclass(slots=True)
class FailureScenario:
    platform_delay_s: float = 0.0
    qwen_disconnect: bool = False
    participant_disconnect: bool = False
    tool_status: int | None = None
    tool_timeout: bool = False
    tool_empty_body: bool = False
    tool_malformed: bool = False
    tool_exception: str | None = None
    start_status: int = 201
    finish_status: int = 200
    lookup_status: int | None = None
    lookup_delay_s: float = 0.0
    lookup_enabled: bool = True
    message_delay_s: float = 0.0


@dataclass(slots=True)
class SessionSpec:
    index: int
    tenant_id: UUID
    customer_service_id: UUID
    session_id: str
    call_id: str
    room_name: str
    provider_call_id: str
    transcript: str
    greeting: str = "hello"
    use_tool: bool = True
    hangup: bool = True
    agent_error: bool = False
    early_hangup: bool = False
    qwen_error: bool = False
    interrupt: bool = False
    usage_tokens: int = 10


@dataclass(slots=True)
class SessionResult:
    spec: SessionSpec
    finish_count: int
    finish_reason: str | None
    tool_count: int
    tenant_id: str
    session_id: str
    usage_total: int
    trace_session: str
    messages: list[dict[str, object]] = field(default_factory=list)


class FakePlatform(httpx.AsyncBaseTransport):
    """One shared fake Control Plane. Isolates records by session/tenant."""

    def __init__(self, scenario: FailureScenario | None = None) -> None:
        self.scenario = scenario or FailureScenario()
        self.requests: list[httpx.Request] = []
        self.finish_by_record: dict[str, int] = {}
        self.tools_by_session: dict[str, list[dict[str, object]]] = {}
        self.messages_by_session: dict[str, list[dict[str, object]]] = {}
        self.tenant_by_session: dict[str, str] = {}
        self.record_to_session: dict[str, str] = {}
        self.lookup_calls = 0
        self.tool_started = asyncio.Event()

    def finish_count(self) -> int:
        return sum(self.finish_by_record.values())

    def finishes_for(self, session_id: str) -> int:
        record_ids = [
            record_id
            for record_id, mapped in self.record_to_session.items()
            if mapped == session_id
        ]
        return sum(self.finish_by_record.get(record_id, 0) for record_id in record_ids)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        scenario = self.scenario
        path = request.url.path
        tenant = request.headers.get("x-tenant-id", "")
        if scenario.platform_delay_s > 0:
            await asyncio.sleep(scenario.platform_delay_s)
        if scenario.tool_exception == "connect" and path.endswith("/tool-invocations"):
            raise httpx.ConnectError("connection refused")
        if scenario.tool_exception == "dns" and path.endswith("/tool-invocations"):
            raise httpx.ConnectError("Name or service not known")
        if path.endswith("/phone-numbers/lookup"):
            return await self._lookup(request)
        if path.endswith("/start"):
            return self._start(request, tenant)
        if path.endswith("/tool-invocations"):
            return await self._tool(request, tenant)
        if path.endswith("/finish"):
            return self._finish(request)
        if "/messages" in path:
            return await self._message(request)
        return httpx.Response(200, json={"ok": True})

    async def _lookup(self, request: httpx.Request) -> httpx.Response:
        self.lookup_calls += 1
        if self.scenario.lookup_delay_s > 0:
            await asyncio.sleep(self.scenario.lookup_delay_s)
        status = self.scenario.lookup_status
        if status is None:
            status = 200
        if status != 200:
            return httpx.Response(status, json={"detail": "lookup"})
        number = request.url.params.get("number", "")
        tenant_id = str(TENANT_A)
        instance_id = str(SERVICE_A)
        if number.endswith("2"):
            tenant_id = str(TENANT_B)
            instance_id = str(SERVICE_B)
        return httpx.Response(
            200,
            json={
                "tenant_id": tenant_id,
                "voice_agent_instance_id": instance_id,
                "config_version": 1,
                "enabled": self.scenario.lookup_enabled,
            },
        )

    def _start(self, request: httpx.Request, tenant: str) -> httpx.Response:
        if self.scenario.start_status >= 400:
            return httpx.Response(self.scenario.start_status, json={"detail": "start"})
        body = json.loads(request.content)
        record_id = str(uuid4())
        session_id = str(body.get("room_name") or record_id)
        self.record_to_session[record_id] = session_id
        self.tenant_by_session[session_id] = tenant
        return httpx.Response(self.scenario.start_status, json={"id": record_id})

    async def _tool(self, request: httpx.Request, tenant: str) -> httpx.Response:
        body = json.loads(request.content)
        session_id = str(body.get("session_id") or "")
        self.tools_by_session.setdefault(session_id, []).append(body)
        self.tool_started.set()
        if self.scenario.tool_timeout:
            await asyncio.Event().wait()
        if tenant and session_id:
            mapped = self.tenant_by_session.get(session_id)
            if mapped and mapped != tenant:
                raise AssertionError("cross-tenant tool invocation")
        if self.scenario.tool_empty_body:
            return httpx.Response(200, content=b"")
        if self.scenario.tool_malformed:
            return httpx.Response(200, content=b"not-json")
        status = self.scenario.tool_status or 200
        if status >= 400:
            return httpx.Response(status, json={"detail": "tool-error"})
        return httpx.Response(
            200,
            json={
                "invocation_id": str(uuid4()),
                "status": "ok",
                "session_id": session_id,
                "tool_name": body.get("tool_name"),
                "tenant_id": tenant,
            },
        )

    def _finish(self, request: httpx.Request) -> httpx.Response:
        record_id = request.url.path.rstrip("/").split("/")[-2]
        self.finish_by_record[record_id] = self.finish_by_record.get(record_id, 0) + 1
        body = json.loads(request.content)
        if self.scenario.finish_status >= 400:
            return httpx.Response(
                self.scenario.finish_status, json={"detail": "finish"}
            )
        return httpx.Response(200, json={"id": record_id, **body})

    async def _message(self, request: httpx.Request) -> httpx.Response:
        if self.scenario.message_delay_s > 0:
            await asyncio.sleep(self.scenario.message_delay_s)
        record_id = request.url.path.rstrip("/").split("/")[-2]
        session_id = self.record_to_session.get(record_id, record_id)
        body = json.loads(request.content)
        self.messages_by_session.setdefault(session_id, []).append(body)
        return httpx.Response(200, json={"id": record_id})


def make_spec(
    index: int,
    *,
    tenant_id: UUID | None = None,
    customer_service_id: UUID | None = None,
    **overrides: object,
) -> SessionSpec:
    tenant = tenant_id or TENANT_A
    service = customer_service_id or SERVICE_A
    payload = {
        "index": index,
        "tenant_id": tenant,
        "customer_service_id": service,
        "session_id": f"room-{index}",
        "call_id": f"call-{index}",
        "room_name": f"room-{index}",
        "provider_call_id": f"provider-{index}",
        "transcript": f"turn-{index}",
        "greeting": f"greet-{index}",
    }
    payload.update(overrides)
    return SessionSpec(**payload)  # type: ignore[arg-type]


def metadata_for(spec: SessionSpec) -> DispatchMetadata:
    return DispatchMetadata.from_json(
        json.dumps(
            {
                "customer_service_id": str(spec.customer_service_id),
                "tenant_id": str(spec.tenant_id),
                "config_version": 1,
                "provider_call_id": spec.provider_call_id,
            }
        )
    )


async def run_synthetic_session(
    http: httpx.AsyncClient,
    spec: SessionSpec,
    *,
    scenario: FailureScenario | None = None,
    clock: FakeClock | None = None,
) -> SessionResult:
    _ = scenario
    trace = SessionTrace(
        session_id=spec.session_id,
        call_id=spec.call_id,
        clock=clock or FakeClock(),
    )
    lifecycle = CallLifecycleClient(http, spec.tenant_id, trace=trace)
    orchestrator = ToolOrchestrator(
        tools=ToolInvocationClient(http, spec.tenant_id, timeout_s=0.2, trace=trace),
        lifecycle=lifecycle,
        session_id=spec.session_id,
        voice_agent_instance_id=spec.customer_service_id,
        trace=trace,
    )
    await lifecycle.start_from_dispatch(metadata_for(spec), spec.room_name)
    trace.mark("runtime_ready")
    await orchestrator.handle_user_final(spec.transcript)
    spoken = f"{spec.greeting}-reply"
    if spec.use_tool:
        marker = encode_tool_marker("check_availability", {"day": "2026-09-02"})
        spoken = f"{spoken}\n{marker}"
    if spec.early_hangup:
        task = orchestrator.spawn(orchestrator.handle_assistant_final(spoken))
        orchestrator.mark_closed()
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        await asyncio.gather(task, return_exceptions=True)
    elif spec.agent_error:
        await orchestrator.handle_assistant_final(spoken)
        orchestrator.mark_closed()
        await lifecycle.finish(status="failed", ended_reason="agent_error")
    else:
        await orchestrator.handle_assistant_final(spoken)
        if spec.qwen_error:
            lifecycle.record_usage(
                {
                    "type": "response.done",
                    "response": {
                        "id": f"resp-{spec.index}",
                        "usage": {"total_tokens": spec.usage_tokens},
                    },
                }
            )
        else:
            lifecycle.record_usage(
                {
                    "type": "response.done",
                    "response": {
                        "id": f"resp-{spec.index}",
                        "usage": {
                            "total_tokens": spec.usage_tokens,
                            "input_tokens": spec.usage_tokens,
                            "output_tokens": 0,
                        },
                    },
                }
            )
        if spec.interrupt:
            trace.mark("interrupt_start")
            trace.mark("interrupt_complete")
        if spec.hangup:
            orchestrator.mark_closed()
            await lifecycle.finish(status="completed", ended_reason="user_hangup")
        else:
            orchestrator.mark_closed()
            await lifecycle.finish(status="completed", ended_reason="completed")
    await orchestrator.wait_idle()
    return SessionResult(
        spec=spec,
        finish_count=1 if lifecycle.finish_committed else 0,
        finish_reason=(
            lifecycle.finish_selected[1] if lifecycle.finish_selected else None
        ),
        tool_count=0,
        tenant_id=str(spec.tenant_id),
        session_id=spec.session_id,
        usage_total=lifecycle.usage.snapshot().total_tokens,
        trace_session=trace.session_id,
    )


async def run_multi_turn_session(
    http: httpx.AsyncClient,
    spec: SessionSpec,
    *,
    turns: int,
    clock: FakeClock | None = None,
) -> SessionResult:
    trace = SessionTrace(
        session_id=spec.session_id,
        call_id=spec.call_id,
        clock=clock or FakeClock(),
    )
    lifecycle = CallLifecycleClient(http, spec.tenant_id, trace=trace)
    orchestrator = ToolOrchestrator(
        tools=ToolInvocationClient(http, spec.tenant_id, timeout_s=0.2, trace=trace),
        lifecycle=lifecycle,
        session_id=spec.session_id,
        voice_agent_instance_id=spec.customer_service_id,
        trace=trace,
    )
    await lifecycle.start_from_dispatch(metadata_for(spec), spec.room_name)
    trace.mark("runtime_ready")
    if spec.early_hangup:
        orchestrator.mark_closed()
        await lifecycle.finish(status="completed", ended_reason="user_hangup")
        await orchestrator.wait_idle()
        return SessionResult(
            spec=spec,
            finish_count=1 if lifecycle.finish_committed else 0,
            finish_reason=(
                lifecycle.finish_selected[1] if lifecycle.finish_selected else None
            ),
            tool_count=0,
            tenant_id=str(spec.tenant_id),
            session_id=spec.session_id,
            usage_total=lifecycle.usage.snapshot().total_tokens,
            trace_session=trace.session_id,
        )
    for turn in range(turns):
        await orchestrator.handle_user_final(f"{spec.transcript}-{turn}")
        spoken = f"{spec.greeting}-{turn}"
        if spec.use_tool and turn == 0:
            marker = encode_tool_marker("check_availability", {"day": "2026-09-02"})
            spoken = f"{spoken}\n{marker}"
        await orchestrator.handle_assistant_final(spoken)
        if spec.interrupt and turn == 0:
            trace.mark("interrupt_start")
            trace.mark("interrupt_complete")
        if spec.agent_error and turn == 0:
            orchestrator.mark_closed()
            await lifecycle.finish(status="failed", ended_reason="agent_error")
            await orchestrator.wait_idle()
            return SessionResult(
                spec=spec,
                finish_count=1 if lifecycle.finish_committed else 0,
                finish_reason="agent_error",
                tool_count=0,
                tenant_id=str(spec.tenant_id),
                session_id=spec.session_id,
                usage_total=lifecycle.usage.snapshot().total_tokens,
                trace_session=trace.session_id,
            )
        lifecycle.record_usage(
            {
                "type": "response.done",
                "response": {
                    "id": f"resp-{spec.index}-{turn}",
                    "usage": {
                        "total_tokens": spec.usage_tokens,
                        "input_tokens": spec.usage_tokens,
                        "output_tokens": 0,
                    },
                },
            }
        )
    orchestrator.mark_closed()
    reason = "user_hangup" if spec.hangup else "completed"
    await lifecycle.finish(status="completed", ended_reason=reason)
    await orchestrator.wait_idle()
    return SessionResult(
        spec=spec,
        finish_count=1 if lifecycle.finish_committed else 0,
        finish_reason=(
            lifecycle.finish_selected[1] if lifecycle.finish_selected else None
        ),
        tool_count=0,
        tenant_id=str(spec.tenant_id),
        session_id=spec.session_id,
        usage_total=lifecycle.usage.snapshot().total_tokens,
        trace_session=trace.session_id,
    )


def sip_participant(
    *,
    caller: str | None = "+61400000001",
    callee: str | None = "+61390000001",
    call_id_full: str | None = "full-call-1",
    call_id: str | None = "short-call-1",
    trunk_id: str | None = "ST_TEST",
    rule_id: str | None = "SDR_TEST",
    kind_sip: bool = True,
) -> SimpleNamespace:
    attributes: dict[str, str] = {"sip.callStatus": "active"}
    if call_id_full is not None:
        attributes["sip.callIDFull"] = call_id_full
    if call_id is not None:
        attributes["sip.callID"] = call_id
    if caller is not None:
        attributes["sip.phoneNumber"] = caller
    if callee is not None:
        attributes["sip.trunkPhoneNumber"] = callee
    if trunk_id is not None:
        attributes["sip.trunkID"] = trunk_id
    if rule_id is not None:
        attributes["sip.ruleID"] = rule_id
    kind = SimpleNamespace(
        name="PARTICIPANT_KIND_SIP" if kind_sip else "PARTICIPANT_KIND_STANDARD",
        value=3 if kind_sip else 0,
    )
    return SimpleNamespace(kind=kind, attributes=attributes)


def runtime_tasks() -> set[asyncio.Task[object]]:
    current = asyncio.current_task()
    owned: set[asyncio.Task[object]] = set()
    for task in asyncio.all_tasks():
        if task is current or task.done():
            continue
        name = task.get_name()
        if name.startswith("QwenRealtime") or name.startswith("RecordingController"):
            owned.add(task)
    return owned
