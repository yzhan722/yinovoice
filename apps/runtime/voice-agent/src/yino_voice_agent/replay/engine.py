"""Drive lifecycle / tools / SIP / usage from a sanitized fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import httpx

from ..call_lifecycle import CallLifecycleClient
from ..conversation import (
    ConversationDirector,
    ConversationEvent,
)
from ..runtime_config import DispatchMetadata, RuntimeConfigurationError
from ..session_trace import FakeClock, SessionTrace
from ..telephony.dispatch import resolve_sip_inbound_dispatch
from ..telephony.livekit_sip import LIVEKIT_SIP_PARTICIPANT_KIND
from ..tool_client import ToolInvocationClient
from ..tool_orchestrator import ToolOrchestrator
from ..tool_protocol import ALLOWED_TOOL_NAMES, ToolName, encode_tool_marker
from ..usage import CallUsageTotals
from ..voice_ux_config import VoiceUxSettings
from .schema import ReplayEvent, ReplayFixture


@dataclass(slots=True)
class ReplayResult:
    finish_count: int
    finish_outcome: tuple[str, str] | None
    tool_names: list[str]
    usage: CallUsageTotals
    trace_order: list[str]
    errors: list[str] = field(default_factory=list)
    sip_provider_call_id: str | None = None
    tenant_id: str | None = None
    greeting_count: int = 0
    silence_prompt_count: int = 0
    phase: str = ""
    ux_actions: list[str] = field(default_factory=list)


class ReplayEngine:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        tenant_id: UUID,
        session_id: str,
        customer_service_id: UUID,
        lookup_token: str | None = None,
        clock: FakeClock | None = None,
    ) -> None:
        self._http = http
        self._tenant_id = tenant_id
        self._session_id = session_id
        self._customer_service_id = customer_service_id
        self._lookup_token = lookup_token
        self._clock = clock or FakeClock()
        self._trace = SessionTrace(session_id=session_id, clock=self._clock)
        self._lifecycle = CallLifecycleClient(http, tenant_id, trace=self._trace)
        self._director = ConversationDirector(
            VoiceUxSettings(),
            clock=self._clock,
            trace=self._trace,
        )
        self._orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(http, tenant_id, trace=self._trace),
            lifecycle=self._lifecycle,
            session_id=session_id,
            voice_agent_instance_id=customer_service_id,
            trace=self._trace,
            conversation=self._director,
        )
        self._started = False
        self._errors: list[str] = []
        self._sip_call_id: str | None = None
        self._tool_names: list[str] = []
        self._ux_kinds: list[str] = []

    async def run(self, fixture: ReplayFixture) -> ReplayResult:
        previous_ms = 0
        for event in fixture.events:
            delta_s = (event.at_ms - previous_ms) / 1000.0
            if delta_s > 0:
                self._clock.advance(delta_s)
            previous_ms = event.at_ms
            await self._apply(event)
            due = self._director.expire_due()
            self._ux_kinds.extend(action.kind.value for action in due)
        if self._started and not self._lifecycle.finish_committed:
            self._orchestrator.mark_closed()
            await self._lifecycle.finish(status="completed", ended_reason="completed")
            await self._orchestrator.wait_idle()
        elif self._started:
            await self._orchestrator.wait_idle()
        return self._snapshot()

    async def _apply(self, event: ReplayEvent) -> None:
        data = event.data
        if event.type in {"session_start", "start"}:
            await self._ensure_started(data)
            return
        if event.type == "user_final":
            await self._ensure_started(data)
            text = data.get("text")
            item_id = data.get("item_id")
            if isinstance(text, str):
                self._note(
                    self._director.handle(
                        ConversationEvent.TRANSCRIPT_FINAL,
                        accepted=True,
                    )
                )
                await self._orchestrator.handle_user_final(
                    text,
                    item_id=item_id if isinstance(item_id, str) else None,
                )
            return
        if event.type in {
            "speech_start",
            "speech_end",
            "audio_output_start",
            "audio_output_cancel",
            "qwen_disconnect",
            "provider_error",
        }:
            await self._ensure_started(data)
            mapped = {
                "speech_start": ConversationEvent.USER_SPEECH_START,
                "speech_end": ConversationEvent.USER_SPEECH_END,
                "audio_output_start": ConversationEvent.ASSISTANT_AUDIO_START,
                "audio_output_cancel": ConversationEvent.INTERRUPT,
                "qwen_disconnect": ConversationEvent.PROVIDER_DISCONNECT,
                "provider_error": ConversationEvent.PROVIDER_ERROR,
            }[event.type]
            self._note(self._director.handle(mapped))
            if event.type in {"qwen_disconnect", "provider_error"}:
                self._errors.append("qwen_error")
            return
        if event.type == "assistant_final":
            await self._ensure_started(data)
            spoken = data.get("spoken")
            tool_name = data.get("tool_name")
            text = spoken if isinstance(spoken, str) else "ok"
            if isinstance(tool_name, str) and tool_name in ALLOWED_TOOL_NAMES:
                marker = encode_tool_marker(
                    cast(ToolName, tool_name),
                    {"reason": "replay"},
                )
                text = f"{text}\n{marker}"
                self._tool_names.append(tool_name)
            await self._orchestrator.handle_assistant_final(text)
            return
        if event.source == "qwen" and event.type == "response.done":
            usage = data.get("usage")
            response_id = data.get("response_id")
            response: dict[str, Any] = {
                "id": response_id if isinstance(response_id, str) else "resp-replay",
            }
            if isinstance(usage, dict):
                response["usage"] = usage
            self._lifecycle.record_usage(
                {"type": "response.done", "response": response}
            )
            return
        if event.type == "participant_joined":
            await self._join_sip(data)
            return
        if event.type in {"participant_disconnected", "hangup"}:
            self._orchestrator.mark_closed()
            await self._lifecycle.finish(status="completed", ended_reason="user_hangup")
            return
        if event.type == "agent_error":
            self._orchestrator.mark_closed()
            await self._lifecycle.finish(status="failed", ended_reason="agent_error")
            return
        if event.type == "shutdown":
            self._orchestrator.mark_closed()
            await self._lifecycle.finish(status="completed", ended_reason="completed")
            return
        if event.source == "qwen" and event.type == "error":
            self._errors.append("qwen_error")

    async def _ensure_started(self, data: dict[str, Any]) -> None:
        if self._started:
            return
        metadata = DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": str(self._customer_service_id),
                    "tenant_id": str(self._tenant_id),
                    "config_version": 1,
                    "provider_call_id": str(
                        data.get("provider_call_id") or self._session_id
                    ),
                }
            )
        )
        await self._lifecycle.start_from_dispatch(metadata, self._session_id)
        self._trace.mark("runtime_ready")
        self._started = True
        self._note(self._director.handle(ConversationEvent.SESSION_READY))
        self._note(self._director.handle(ConversationEvent.GREETING_FINISHED))

    async def _join_sip(self, data: dict[str, Any]) -> None:
        attributes = data.get("attributes")
        if not isinstance(attributes, dict):
            self._errors.append("sip_missing_attributes")
            return
        participant = SimpleNamespace(
            kind=SimpleNamespace(
                name="PARTICIPANT_KIND_SIP",
                value=LIVEKIT_SIP_PARTICIPANT_KIND,
            ),
            attributes={
                key: value
                for key, value in attributes.items()
                if isinstance(value, str)
            },
        )
        ctx = SimpleNamespace(
            room=SimpleNamespace(name=self._session_id),
            job=SimpleNamespace(metadata=""),
        )
        try:
            metadata = await resolve_sip_inbound_dispatch(
                ctx,
                participant=participant,
                http=self._http,
                lookup_token=self._lookup_token,
                trace=self._trace,
            )
        except RuntimeConfigurationError:
            self._errors.append("sip_dispatch_failed")
            return
        self._tenant_id = metadata.tenant_id
        self._customer_service_id = metadata.customer_service_id
        self._lifecycle = CallLifecycleClient(
            self._http, metadata.tenant_id, trace=self._trace
        )
        self._orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(
                self._http, metadata.tenant_id, trace=self._trace
            ),
            lifecycle=self._lifecycle,
            session_id=self._session_id,
            voice_agent_instance_id=metadata.customer_service_id,
            trace=self._trace,
            conversation=self._director,
        )
        await self._lifecycle.start_from_dispatch(metadata, self._session_id)
        self._trace.mark("runtime_ready")
        self._started = True
        self._sip_call_id = metadata.provider_call_id
        self._note(self._director.handle(ConversationEvent.SESSION_READY))
        self._note(self._director.handle(ConversationEvent.GREETING_FINISHED))

    def _snapshot(self) -> ReplayResult:
        return ReplayResult(
            finish_count=1 if self._lifecycle.finish_committed else 0,
            finish_outcome=self._lifecycle.finish_selected,
            tool_names=list(self._tool_names),
            usage=self._lifecycle.usage.snapshot(),
            trace_order=list(self._trace.order),
            errors=list(self._errors),
            sip_provider_call_id=self._sip_call_id,
            tenant_id=str(self._tenant_id),
            greeting_count=self._director.greeting_count,
            silence_prompt_count=self._director.silence_prompt_count,
            phase=self._director.phase.value,
            ux_actions=list(self._ux_kinds),
        )

    def _note(self, actions: tuple[Any, ...]) -> None:
        self._ux_kinds.extend(action.kind.value for action in actions)
