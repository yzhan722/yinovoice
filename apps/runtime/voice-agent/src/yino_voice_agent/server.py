"""LiveKit entrypoint for local and Platform-dispatched voice sessions."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, cli

from .call_lifecycle import CallLifecycleClient
from .config import DEFAULT_LIVEKIT_AGENT_NAME, VoiceSettings
from .customer_service import create_customer_service
from .providers import ProviderBundle, build_providers
from .runtime_config import (
    DispatchMetadata,
    PlatformConfigClient,
    RuntimeConfigurationError,
    RuntimeCustomerService,
)
from .session import create_session
from .session_trace import SessionTrace
from .telephony.dispatch import (
    await_joining_participant,
    explicit_job_metadata,
    resolve_sip_inbound_dispatch,
)
from .telephony.livekit_sip import is_sip_participant
from .tool_client import ToolInvocationClient
from .tool_orchestrator import ToolOrchestrator


@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    settings: VoiceSettings
    providers: ProviderBundle
    vad: Any | None
    customer_service: RuntimeCustomerService | None = None


def _load_pipeline_vad() -> Any:
    from livekit.plugins import silero

    return silero.VAD.load()


def create_console_runtime(
    settings_loader: Callable[[], VoiceSettings] = VoiceSettings.from_env,
    provider_factory: Callable[[VoiceSettings], ProviderBundle] | None = None,
    vad_loader: Callable[[], Any] | None = None,
) -> RuntimeDependencies:
    """Create runtime dependencies after configuration has been validated."""

    settings = settings_loader()
    providers = (provider_factory or build_providers)(settings)
    vad = None
    if providers.mode == "pipeline":
        vad = (vad_loader or _load_pipeline_vad)()
    return RuntimeDependencies(
        settings=settings,
        providers=providers,
        vad=vad,
    )


async def create_dispatched_runtime(
    raw_metadata: str | DispatchMetadata,
    *,
    settings: VoiceSettings,
    config_client: PlatformConfigClient,
    provider_factory: Callable[..., ProviderBundle] | None = None,
    vad_loader: Callable[[], Any] | None = None,
) -> RuntimeDependencies:
    """Create dependencies from one exact Platform-published snapshot."""

    metadata = (
        raw_metadata
        if isinstance(raw_metadata, DispatchMetadata)
        else DispatchMetadata.from_json(raw_metadata)
    )
    customer_service = await config_client.get(metadata)
    providers = (provider_factory or build_providers)(
        settings, runtime_config=customer_service
    )
    vad = None
    if providers.mode == "pipeline":
        vad = (vad_loader or _load_pipeline_vad)()
    return RuntimeDependencies(
        settings=settings,
        providers=providers,
        vad=vad,
        customer_service=customer_service,
    )


load_dotenv(".env.local")
server = AgentServer()

# Isolate parallel deployments (prod vs stage1) via LIVEKIT_AGENT_NAME.
# SIP inbound Dispatch Rules must use this same name and leave job metadata empty
# so callee lookup can select the tenant. Do not hard-code the name elsewhere.
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", DEFAULT_LIVEKIT_AGENT_NAME)


def _room_name(ctx: JobContext) -> str:
    name = getattr(ctx.room, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "unknown-room"


@server.rtc_session(agent_name=LIVEKIT_AGENT_NAME)
async def local_voice_agent(ctx: JobContext) -> None:
    """Run one local, Platform-dispatched, or LiveKit SIP inbound session."""

    settings = VoiceSettings.from_env()
    explicit = explicit_job_metadata(ctx)
    participant = None
    if explicit is None:
        participant = await await_joining_participant(
            ctx,
            sip_only=not settings.allow_empty_dispatch_metadata_local_dev,
        )

    if explicit is not None or is_sip_participant(participant):
        async with httpx.AsyncClient(
            base_url=settings.platform_api_url,
            timeout=5.0,
        ) as http_client:
            sip_trace = None
            if explicit is not None:
                metadata = explicit
            else:
                sip_trace = SessionTrace(session_id=_room_name(ctx))
                metadata = await resolve_sip_inbound_dispatch(
                    ctx,
                    participant=participant,
                    http=http_client,
                    trace=sip_trace,
                    lookup_token=settings.phone_lookup_token,
                )
            runtime = await create_dispatched_runtime(
                metadata,
                settings=settings,
                config_client=PlatformConfigClient(http_client),
            )
            await _speak_with_optional_lifecycle(
                ctx,
                runtime,
                metadata=metadata,
                http_client=http_client,
                trace=sip_trace,
            )
        return

    if not settings.allow_empty_dispatch_metadata_local_dev:
        raise RuntimeConfigurationError(
            "RTC jobs with empty dispatch metadata are disabled; "
            "explicit local development opt-in is required"
        )
    runtime = create_console_runtime(settings_loader=lambda: settings)
    await _speak_with_optional_lifecycle(ctx, runtime)


async def _speak_with_optional_lifecycle(
    ctx: JobContext,
    runtime: RuntimeDependencies,
    *,
    metadata: DispatchMetadata | None = None,
    http_client: httpx.AsyncClient | None = None,
    trace: SessionTrace | None = None,
) -> None:
    customer_service = runtime.customer_service
    if customer_service is None:
        agent = create_customer_service()
        greeting = runtime.settings.greeting
    else:
        agent = create_customer_service(
            customer_service.organization_name,
            platform_prompt=customer_service.platform_prompt,
            tenant_prompt=customer_service.tenant_prompt,
            brevity=customer_service.response.brevity,
            max_spoken_sentences=(
                customer_service.response.max_spoken_sentences
            ),
            ask_one_question_at_a_time=(
                customer_service.response.ask_one_question_at_a_time
            ),
        )
        greeting = customer_service.greeting

    lifecycle: CallLifecycleClient | None = None
    orchestrator: ToolOrchestrator | None = None
    if metadata is not None and http_client is not None:
        if trace is None:
            trace = SessionTrace(
                session_id=_room_name(ctx),
                call_id=metadata.provider_call_id,
            )
        elif not trace.call_id:
            trace.call_id = metadata.provider_call_id
        lifecycle = CallLifecycleClient(
            http_client, metadata.tenant_id, trace=trace
        )
        await lifecycle.start_from_dispatch(metadata, _room_name(ctx))
        orchestrator = ToolOrchestrator(
            tools=ToolInvocationClient(
                http_client, metadata.tenant_id, trace=trace
            ),
            lifecycle=lifecycle,
            session_id=_room_name(ctx),
            voice_agent_instance_id=metadata.customer_service_id,
            trace=trace,
        )

    session = create_session(runtime.providers, runtime.vad)
    if lifecycle is not None:
        attach_usage = getattr(runtime.providers.llm, "attach_usage_sink", None)
        if callable(attach_usage):
            attach_usage(lifecycle.record_usage)
    if orchestrator is not None:
        _bind_orchestrator(session, orchestrator)
    closed = asyncio.Event()
    close_events: list[object] = []
    finish_tasks: list[asyncio.Task[None]] = []

    async def request_finish(status: str, ended_reason: str) -> None:
        try:
            if orchestrator is not None:
                orchestrator.mark_closed()
            if lifecycle is not None:
                await lifecycle.finish(status=status, ended_reason=ended_reason)
        finally:
            closed.set()

    on = getattr(session, "on", None)
    if callable(on):

        def _on_close(event: object = None) -> None:
            close_events.append(event)
            status, ended_reason = _ended_from_close(event)
            finish_tasks.append(
                asyncio.create_task(request_finish(status, ended_reason))
            )

        on("close", _on_close)
    add_shutdown = getattr(ctx, "add_shutdown_callback", None)
    if callable(add_shutdown):

        async def _on_shutdown(_reason: str = "") -> None:
            event = close_events[0] if close_events else None
            status, ended_reason = _ended_from_close(event)
            await request_finish(status, ended_reason)

        add_shutdown(_on_shutdown)
    try:
        try:
            await session.start(
                room=ctx.room,
                agent=agent,
            )
            if trace is not None:
                trace.mark("runtime_ready")
            session.say(
                greeting,
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
        except Exception:
            await request_finish("failed", "agent_error")
            raise
        if callable(on) or callable(add_shutdown):
            await closed.wait()
        elif lifecycle is not None:
            await request_finish("completed", "completed")
    finally:
        if orchestrator is not None:
            orchestrator.mark_closed()
            await orchestrator.wait_idle()
        if finish_tasks:
            await asyncio.gather(*finish_tasks, return_exceptions=True)


def _ended_from_close(event: object | None) -> tuple[str, str]:
    """Map AgentSession CloseEvent.reason (CloseReason names).

    Inbound SIP BYE is DisconnectReason.CLIENT_INITIATED on the participant.
    RoomIO then closes the session with CloseReason.PARTICIPANT_DISCONNECTED.
    CLIENT_INITIATED is kept as a defensive alias if a close event ever carries
    the disconnect enum name.
    """
    if event is None:
        return ("completed", "completed")
    if getattr(event, "error", None) is not None:
        return ("failed", "agent_error")
    reason = getattr(event, "reason", None)
    name = getattr(reason, "name", None)
    if name in {
        "PARTICIPANT_DISCONNECTED",
        "USER_INITIATED",
        "CLIENT_INITIATED",
    }:
        return ("completed", "user_hangup")
    if name in {"ERROR", "SIP_TRUNK_FAILURE"}:
        return ("failed", "agent_error")
    return ("completed", "completed")


def _chat_text(item: object) -> str:
    text = getattr(item, "text_content", None)
    if isinstance(text, str) and text.strip():
        return text
    content = getattr(item, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return ""


def _bind_orchestrator(session: object, orchestrator: ToolOrchestrator) -> None:
    on = getattr(session, "on", None)
    if not callable(on):
        return

    def _on_user(event: object) -> None:
        if not getattr(event, "is_final", False):
            return
        transcript = getattr(event, "transcript", "")
        if isinstance(transcript, str) and transcript.strip():
            orchestrator.spawn(orchestrator.handle_user_final(transcript))

    def _on_item(event: object) -> None:
        item = getattr(event, "item", None)
        if getattr(item, "role", None) != "assistant":
            return
        text = _chat_text(item)
        if text.strip():
            orchestrator.spawn(orchestrator.handle_assistant_final(text))

    on("user_input_transcribed", _on_user)
    on("conversation_item_added", _on_item)


if __name__ == "__main__":
    cli.run_app(server)
