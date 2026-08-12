"""LiveKit entrypoint for local and Platform-dispatched voice sessions."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, cli

from .config import VoiceSettings
from .customer_service import create_customer_service
from .providers import ProviderBundle, build_providers
from .runtime_config import (
    DispatchMetadata,
    PlatformConfigClient,
    RuntimeConfigurationError,
    RuntimeCustomerService,
)
from .session import create_session


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
    raw_metadata: str,
    *,
    settings: VoiceSettings,
    config_client: PlatformConfigClient,
    provider_factory: Callable[..., ProviderBundle] | None = None,
    vad_loader: Callable[[], Any] | None = None,
) -> RuntimeDependencies:
    """Create dependencies from one exact Platform-published snapshot."""

    metadata = DispatchMetadata.from_json(raw_metadata)
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
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "yino-customer-service")


@server.rtc_session(agent_name=LIVEKIT_AGENT_NAME)
async def local_voice_agent(ctx: JobContext) -> None:
    """Run one local or RTC-backed voice-agent session."""

    raw_metadata = ctx.job.metadata
    if raw_metadata.strip():
        DispatchMetadata.from_json(raw_metadata)
        settings = VoiceSettings.from_env()
        async with httpx.AsyncClient(
            base_url=settings.platform_api_url,
            timeout=5.0,
        ) as http_client:
            runtime = await create_dispatched_runtime(
                raw_metadata,
                settings=settings,
                config_client=PlatformConfigClient(http_client),
            )
    else:
        settings = VoiceSettings.from_env()
        if not settings.allow_empty_dispatch_metadata_local_dev:
            raise RuntimeConfigurationError(
                "RTC jobs with empty dispatch metadata are disabled; "
                "explicit local development opt-in is required"
            )
        runtime = create_console_runtime(settings_loader=lambda: settings)

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

    session = create_session(runtime.providers, runtime.vad)
    await session.start(
        room=ctx.room,
        agent=agent,
    )
    session.say(
        greeting,
        allow_interruptions=True,
        add_to_chat_ctx=False,
    )


if __name__ == "__main__":
    cli.run_app(server)
