import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import pytest

from yino_voice_agent.config import VoiceSettings
from yino_voice_agent.providers import ProviderBundle
from yino_voice_agent.runtime_config import (
    DispatchMetadata,
    PlatformConfigClient,
    RuntimeConfigurationError,
    RuntimeCustomerService,
)
from yino_voice_agent.server import (
    create_console_runtime,
    create_dispatched_runtime,
    local_voice_agent,
)


def runtime_customer_service() -> RuntimeCustomerService:
    return RuntimeCustomerService.from_mapping(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "version": 7,
            "display_name": "Yino AI 语音客服",
            "organization_name": "Yino 演示机构",
            "greeting": "您好，这里是 Yino 演示机构客服。",
            "platform_prompt": "平台对话规则。",
            "tenant_prompt": "只回答本机构业务相关问题。",
            "voice": {
                "preset_id": "mandarin-standard",
                "locale": "zh-CN",
                "speaking_rate": 1.1,
                "volume": 1.0,
                "pitch": 0.0,
                "style": "professional-friendly",
                "emotion": "neutral",
                "pause_profile": "receptionist",
                "tts_voice": "longanxiaoxin",
            },
            "response": {
                "brevity": "concise",
                "max_spoken_sentences": 2,
                "ask_one_question_at_a_time": True,
            },
            "business_profile": "generic-receptionist",
            "primary_language": "zh-CN",
        }
    )


def realtime_settings() -> VoiceSettings:
    return VoiceSettings.from_env(
        {
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
        }
    )


def test_console_runtime_uses_injected_factories() -> None:
    settings = VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "pipeline",
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "DASHSCOPE_WEBSOCKET_URL": (
                "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
            ),
            "OPENAI_API_KEY": "openai-test-key",
        }
    )
    providers = ProviderBundle(
        mode="pipeline", stt=object(), llm=object(), tts=object()
    )
    settings_loader = Mock(return_value=settings)
    provider_factory = Mock(return_value=providers)
    vad = object()
    vad_loader = Mock(return_value=vad)

    runtime = create_console_runtime(settings_loader, provider_factory, vad_loader)

    assert runtime.settings is settings
    assert runtime.providers is providers
    assert runtime.vad is vad
    provider_factory.assert_called_once_with(settings)
    vad_loader.assert_called_once_with()


def test_realtime_console_runtime_does_not_load_vad() -> None:
    settings = realtime_settings()
    providers = ProviderBundle(mode="qwen-realtime", llm=object())
    settings_loader = Mock(return_value=settings)
    provider_factory = Mock(return_value=providers)
    vad_loader = Mock()

    runtime = create_console_runtime(settings_loader, provider_factory, vad_loader)

    assert runtime.providers is providers
    assert runtime.vad is None
    vad_loader.assert_not_called()


@pytest.mark.asyncio
async def test_realtime_dispatched_runtime_does_not_load_vad() -> None:
    settings = realtime_settings()
    customer_service = runtime_customer_service()
    providers = ProviderBundle(mode="qwen-realtime", llm=object())
    config_client = SimpleNamespace(
        get=AsyncMock(return_value=customer_service)
    )
    metadata = json.dumps(
        {
            "customer_service_id": str(customer_service.id),
            "tenant_id": str(customer_service.tenant_id),
            "config_version": customer_service.version,
        }
    )

    provider_factory = Mock(return_value=providers)
    vad_loader = Mock()

    runtime = await create_dispatched_runtime(
        metadata,
        settings=settings,
        config_client=config_client,
        provider_factory=provider_factory,
        vad_loader=vad_loader,
    )

    assert runtime.providers is providers
    assert runtime.vad is None
    provider_factory.assert_called_once_with(
        settings,
        runtime_config=customer_service,
    )
    vad_loader.assert_not_called()


def test_settings_default_to_local_platform_api() -> None:
    settings = realtime_settings()

    assert settings.platform_api_url == "http://localhost:8000"


@pytest.mark.asyncio
async def test_entrypoint_starts_session_and_speaks_configured_greeting() -> None:
    settings = SimpleNamespace(
        greeting="您好，这里是测试机构客服。",
        allow_empty_dispatch_metadata_local_dev=True,
    )
    runtime = SimpleNamespace(
        settings=settings,
        providers=object(),
        vad=object(),
        customer_service=None,
    )
    lifecycle: list[str] = []
    session = SimpleNamespace(
        start=AsyncMock(side_effect=lambda **_: lifecycle.append("start")),
        say=Mock(side_effect=lambda *_args, **_kwargs: lifecycle.append("say")),
    )
    customer_service = object()
    context = SimpleNamespace(
        room=object(),
        job=SimpleNamespace(metadata=""),
    )

    with (
        patch.object(VoiceSettings, "from_env", return_value=settings),
        patch(
            "yino_voice_agent.server.create_console_runtime",
            return_value=runtime,
        ),
        patch(
            "yino_voice_agent.server.create_session",
            return_value=session,
        ) as session_factory,
        patch(
            "yino_voice_agent.server.create_customer_service",
            return_value=customer_service,
        ),
    ):
        await local_voice_agent(context)

    session_factory.assert_called_once_with(runtime.providers, runtime.vad)
    session.start.assert_awaited_once_with(
        room=context.room,
        agent=customer_service,
    )
    session.say.assert_called_once_with(
        "您好，这里是测试机构客服。",
        allow_interruptions=True,
        add_to_chat_ctx=False,
    )
    assert lifecycle == ["start", "say"]


@pytest.mark.asyncio
async def test_empty_rtc_metadata_fails_closed_without_local_dev_opt_in() -> None:
    settings = SimpleNamespace(
        greeting="您好。",
        allow_empty_dispatch_metadata_local_dev=False,
    )
    console_runtime_factory = Mock()
    session_factory = Mock()
    context = SimpleNamespace(room=object(), job=SimpleNamespace(metadata=""))

    with (
        patch.object(VoiceSettings, "from_env", return_value=settings),
        patch(
            "yino_voice_agent.server.create_console_runtime",
            console_runtime_factory,
        ),
        patch("yino_voice_agent.server.create_session", session_factory),
        pytest.raises(RuntimeConfigurationError, match="empty dispatch metadata"),
    ):
        await local_voice_agent(context)

    console_runtime_factory.assert_not_called()
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_dispatched_entrypoint_uses_exact_platform_snapshot() -> None:
    settings = VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "pipeline",
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "DASHSCOPE_WEBSOCKET_URL": (
                "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
            ),
            "OPENAI_API_KEY": "openai-test-key",
        }
    )
    runtime = runtime_customer_service()
    providers = ProviderBundle(
        mode="pipeline", stt=object(), llm=object(), tts=object()
    )
    provider_factory = Mock(return_value=providers)
    config_get = AsyncMock(return_value=runtime)
    http_client_factory = MagicMock()
    vad = object()
    session = SimpleNamespace(start=AsyncMock(), say=Mock())
    customer_service = object()
    customer_service_factory = Mock(return_value=customer_service)
    context = SimpleNamespace(
        room=object(),
        job=SimpleNamespace(
            metadata=json.dumps(
                {
                    "customer_service_id": str(runtime.id),
                    "tenant_id": str(runtime.tenant_id),
                    "config_version": runtime.version,
                }
            )
        ),
    )

    with (
        patch.object(VoiceSettings, "from_env", return_value=settings),
        patch(
            "yino_voice_agent.server.httpx.AsyncClient",
            http_client_factory,
        ),
        patch.object(PlatformConfigClient, "get", config_get),
        patch("yino_voice_agent.server.build_providers", provider_factory),
        patch("yino_voice_agent.server._load_pipeline_vad", return_value=vad),
        patch(
            "yino_voice_agent.server.create_session",
            return_value=session,
        ) as session_factory,
        patch(
            "yino_voice_agent.server.create_customer_service",
            customer_service_factory,
        ),
    ):
        await local_voice_agent(context)

    metadata = DispatchMetadata.from_json(context.job.metadata)
    http_client_factory.assert_called_once_with(
        base_url=settings.platform_api_url,
        timeout=5.0,
    )
    http_client_factory.return_value.__aexit__.assert_awaited_once()
    config_get.assert_awaited_once_with(metadata)
    assert metadata.customer_service_id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    provider_factory.assert_called_once_with(settings, runtime_config=runtime)
    customer_service_factory.assert_called_once_with(
        runtime.organization_name,
        platform_prompt=runtime.platform_prompt,
        tenant_prompt=runtime.tenant_prompt,
        brevity=runtime.response.brevity,
        max_spoken_sentences=runtime.response.max_spoken_sentences,
        ask_one_question_at_a_time=(
            runtime.response.ask_one_question_at_a_time
        ),
    )
    session_factory.assert_called_once_with(providers, vad)
    session.start.assert_awaited_once_with(
        room=context.room,
        agent=customer_service,
    )
    session.say.assert_called_once_with(
        runtime.greeting,
        allow_interruptions=True,
        add_to_chat_ctx=False,
    )


@pytest.mark.asyncio
async def test_malformed_nonempty_dispatch_metadata_fails_before_providers() -> None:
    settings = VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "pipeline",
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "DASHSCOPE_WEBSOCKET_URL": (
                "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
            ),
            "OPENAI_API_KEY": "openai-test-key",
        }
    )
    provider_factory = Mock()
    http_client_factory = MagicMock()
    session_factory = Mock(
        return_value=SimpleNamespace(
            start=AsyncMock(),
            say=Mock(),
        )
    )
    context = SimpleNamespace(
        room=object(),
        job=SimpleNamespace(metadata='{"tenant_id": "missing-fields"}'),
    )

    with (
        patch.object(VoiceSettings, "from_env", return_value=settings),
        patch(
            "yino_voice_agent.server.httpx.AsyncClient",
            http_client_factory,
        ),
        patch("yino_voice_agent.server.build_providers", provider_factory),
        patch("yino_voice_agent.server.create_session", session_factory),
        pytest.raises(RuntimeConfigurationError),
    ):
        await local_voice_agent(context)

    http_client_factory.assert_not_called()
    provider_factory.assert_not_called()
    session_factory.assert_not_called()
