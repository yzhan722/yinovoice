"""Deterministic LiveKit SIP fakes for inbound runtime tests. No PSTN."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import httpx
from test_server import _ClosableSession

from yino_voice_agent.config import VoiceSettings
from yino_voice_agent.providers import ProviderBundle

_RealAsyncClient = httpx.AsyncClient

CALLER_A = "+61411111111"
CALLEE_A = "+61390000001"
CALLEE_B = "+61390000002"
TENANT_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
TENANT_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
AGENT_A = UUID("aaaaaaaa-0000-4000-8000-0000000000aa")
AGENT_B = UUID("bbbbbbbb-0000-4000-8000-0000000000bb")
LOOKUP_TOKEN = "test-phone-lookup-token"
LOOKUP_HEADER = "X-Phone-Lookup-Token"


@dataclass(frozen=True, slots=True)
class FakeTenantAgent:
    tenant_id: UUID
    instance_id: UUID
    version: int
    organization_name: str
    callee: str
    enabled: bool = True


TENANT_AGENT_A = FakeTenantAgent(
    tenant_id=TENANT_A,
    instance_id=AGENT_A,
    version=3,
    organization_name="Tenant A Clinic",
    callee=CALLEE_A,
)
TENANT_AGENT_B = FakeTenantAgent(
    tenant_id=TENANT_B,
    instance_id=AGENT_B,
    version=5,
    organization_name="Tenant B Clinic",
    callee=CALLEE_B,
)


def sip_kind() -> SimpleNamespace:
    return SimpleNamespace(name="PARTICIPANT_KIND_SIP", value=3)


def web_kind() -> SimpleNamespace:
    return SimpleNamespace(name="PARTICIPANT_KIND_STANDARD", value=0)


def sip_attributes(
    *,
    callee: str | None = CALLEE_A,
    caller: str | None = CALLER_A,
    call_id_full: str | None = "provider-call-full-1",
    call_id: str | None = "lk-sip-call-1",
    trunk_id: str | None = "ST_PLACEHOLDER",
    rule_id: str | None = "SDR_PLACEHOLDER",
) -> dict[str, str]:
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
    return attributes


def sip_participant(
    *,
    kind: object | None = None,
    attributes: dict[str, str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        kind=kind if kind is not None else sip_kind(),
        attributes=attributes if attributes is not None else sip_attributes(),
    )


class SipJobContext:
    def __init__(
        self,
        *,
        room_name: str,
        participant: object,
        metadata: str = "",
        capture_shutdown: bool = False,
    ) -> None:
        self.room = SimpleNamespace(name=room_name)
        self.job = SimpleNamespace(metadata=metadata)
        self.shutdown_callbacks: list[object] = []
        self._participant = participant
        self.wait_calls = 0
        self.wait_kwargs: dict[str, object] = {}
        if capture_shutdown:
            self.add_shutdown_callback = self._add_shutdown_callback

    async def wait_for_participant(self, *args: object, **kwargs: object) -> object:
        self.wait_calls += 1
        self.wait_kwargs = dict(kwargs)
        requested = kwargs.get("kind")
        if requested is not None:
            wanted = requested if isinstance(requested, list | tuple) else (requested,)
            kind = getattr(self._participant, "kind", None)
            value = getattr(kind, "value", kind)
            if value not in wanted:
                raise TimeoutError("no matching participant")
        return self._participant

    def _add_shutdown_callback(self, handler: object) -> None:
        self.shutdown_callbacks.append(handler)


def pipeline_settings() -> VoiceSettings:
    return VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "pipeline",
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "DASHSCOPE_WEBSOCKET_URL": (
                "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
            ),
            "OPENAI_API_KEY": "openai-test-key",
            "PHONE_LOOKUP_TOKEN": LOOKUP_TOKEN,
        }
    )


def snapshot_payload(agent: FakeTenantAgent) -> dict[str, object]:
    return {
        "id": str(agent.instance_id),
        "tenant_id": str(agent.tenant_id),
        "version": agent.version,
        "display_name": agent.organization_name,
        "organization_name": agent.organization_name,
        "greeting": f"您好，这里是 {agent.organization_name} 客服。",
        "platform_prompt": "平台对话规则。",
        "tenant_prompt": f"只回答 {agent.organization_name} 业务相关问题。",
        "voice": {
            "preset_id": "mandarin-standard",
            "locale": "zh-CN",
            "speaking_rate": 1.0,
            "volume": 1.0,
            "pitch": 0.0,
            "style": "professional-friendly",
            "emotion": "neutral",
            "pause_profile": "receptionist",
            "tts_voice": "longanqian",
        },
        "response": {
            "brevity": "concise",
            "max_spoken_sentences": 2,
            "ask_one_question_at_a_time": True,
        },
        "business_profile": "generic-receptionist",
        "primary_language": "zh-CN",
    }


def lookup_payload(
    agent: FakeTenantAgent, *, enabled: bool | None = None
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "tenant_id": str(agent.tenant_id),
        "voice_agent_instance_id": str(agent.instance_id),
        "e164_number": agent.callee,
        "provider": "livekit_sip",
        "inbound_trunk_id": "ST_PLACEHOLDER",
        "dispatch_rule_id": "SDR_PLACEHOLDER",
        "enabled": agent.enabled if enabled is None else enabled,
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "config_version": agent.version,
    }


def _json_object(content: bytes) -> dict[str, object]:
    payload = json.loads(content)
    return payload if isinstance(payload, dict) else {}


class PlatformSipTransport(httpx.AsyncBaseTransport):
    """In-memory Platform: lookup, snapshot, lifecycle, tools."""

    def __init__(
        self,
        agents: dict[str, FakeTenantAgent],
        *,
        lookup_mode: str = "ok",
        snapshot_status: int = 200,
        tool_timeout: bool = False,
    ) -> None:
        self.agents = agents
        self.lookup_mode = lookup_mode
        self.snapshot_status = snapshot_status
        self.lookup_numbers: list[str | None] = []
        self.start_bodies: list[dict[str, object]] = []
        self.finish_bodies: list[dict[str, object]] = []
        self.tool_bodies: list[dict[str, object]] = []
        self.snapshot_orgs: list[str] = []
        self.slow_started = asyncio.Event()
        self.release_slow = asyncio.Event()
        self.tool_started = asyncio.Event()
        self.release_tool = asyncio.Event()
        if not tool_timeout:
            self.release_tool.set()
        self._records: dict[str, UUID] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/phone-numbers/lookup"):
            return await self._lookup(request)
        if "/customer-services/" in path and request.method == "GET":
            return self._snapshot(request, path)
        if path.endswith("/start"):
            body = _json_object(request.content)
            self.start_bodies.append(body)
            record_id = uuid4()
            self._records[str(body.get("room_name", ""))] = record_id
            return httpx.Response(201, json={"id": str(record_id)})
        if path.endswith("/finish"):
            body = _json_object(request.content)
            self.finish_bodies.append(body)
            return httpx.Response(200, json={"id": str(uuid4()), **body})
        if path.endswith("/tool-invocations"):
            self.tool_started.set()
            await self.release_tool.wait()
            body = _json_object(request.content)
            self.tool_bodies.append(body)
            return httpx.Response(
                200,
                json={
                    "invocation_id": str(uuid4()),
                    "status": "ok",
                    "session_id": body.get("session_id"),
                    "tool_name": body.get("tool_name"),
                },
            )
        if path.endswith("/messages"):
            return httpx.Response(200, json={"id": str(uuid4())})
        return httpx.Response(404)

    async def _lookup(self, request: httpx.Request) -> httpx.Response:
        given = request.headers.get(LOOKUP_HEADER)
        if given != LOOKUP_TOKEN:
            return httpx.Response(401, json={"detail": "Unauthorized"})
        number = request.url.params.get("number")
        self.lookup_numbers.append(number)
        if self.lookup_mode == "timeout":
            raise httpx.ConnectTimeout("destination lookup timed out")
        if self.lookup_mode == "http_500":
            return httpx.Response(500, json={"detail": "down"})
        if self.lookup_mode == "slow":
            self.slow_started.set()
            await self.release_slow.wait()
        agent = self.agents.get(number or "")
        if agent is None:
            return httpx.Response(404, json={"detail": "Phone number not found"})
        return httpx.Response(200, json=lookup_payload(agent, enabled=agent.enabled))

    def _snapshot(self, request: httpx.Request, path: str) -> httpx.Response:
        if self.snapshot_status >= 400:
            return httpx.Response(self.snapshot_status, json={"detail": "down"})
        instance_id = path.rsplit("/", 1)[-1]
        tenant_header = request.headers.get("x-tenant-id")
        for agent in self.agents.values():
            if str(agent.instance_id) != instance_id:
                continue
            if str(agent.tenant_id) != tenant_header:
                return httpx.Response(404)
            self.snapshot_orgs.append(agent.organization_name)
            return httpx.Response(200, json=snapshot_payload(agent))
        return httpx.Response(404)


@contextmanager
def patched_voice_agent(
    *,
    transport: PlatformSipTransport,
    session_factory: Callable[[], object],
) -> Iterator[list[str]]:
    settings = pipeline_settings()
    providers = ProviderBundle(
        mode="pipeline", stt=object(), llm=object(), tts=object()
    )
    orgs: list[str] = []

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return _RealAsyncClient(*args, **kwargs)

    def customer_factory(organization_name: str, **_kwargs: object) -> object:
        orgs.append(organization_name)
        return object()

    with (
        patch.object(VoiceSettings, "from_env", return_value=settings),
        patch("yino_voice_agent.server.httpx.AsyncClient", side_effect=client_factory),
        patch(
            "yino_voice_agent.server.build_providers",
            Mock(return_value=providers),
        ),
        patch("yino_voice_agent.server._load_pipeline_vad", return_value=object()),
        patch(
            "yino_voice_agent.server.create_session",
            side_effect=lambda *_a, **_k: session_factory(),
        ),
        patch(
            "yino_voice_agent.server.create_customer_service",
            side_effect=customer_factory,
        ),
    ):
        yield orgs


def immediate_session() -> SimpleNamespace:
    return SimpleNamespace(start=AsyncMock(), say=Mock())


def closable_session() -> _ClosableSession:
    return _ClosableSession()
