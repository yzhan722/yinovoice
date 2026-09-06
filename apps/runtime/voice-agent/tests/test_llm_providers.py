"""LLM provider selection for pipeline mode."""

from __future__ import annotations

from typing import Any

import pytest

from yino_voice_agent.config import ConfigurationError, VoiceSettings
from yino_voice_agent.llm_providers import PROVIDER_KEYS, PROVIDERS
from yino_voice_agent.providers import build_llm

BASE_PIPELINE_ENV = {
    "VOICE_PROVIDER_MODE": "pipeline",
    "DASHSCOPE_API_KEY": "ds-key",
    "DASHSCOPE_WEBSOCKET_URL": "wss://dashscope.example/ws",
    "OPENAI_API_KEY": "openai-key",
    "PLATFORM_API_URL": "http://localhost:8000",
}


class FakeResponsesLLM:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeChatLLM:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakePlugin:
    LLM = FakeChatLLM

    class responses:  # noqa: N801 - mirrors the plugin's module layout
        LLM = FakeResponsesLLM


def settings_from(**overrides: str) -> VoiceSettings:
    return VoiceSettings.from_env({**BASE_PIPELINE_ENV, **overrides})


def test_default_provider_is_openai_and_keeps_the_responses_client() -> None:
    settings = settings_from()
    assert settings.llm is not None
    assert settings.llm.provider == "openai"
    assert settings.llm.model == "gpt-4o-mini"
    assert settings.llm.base_url is None
    assert settings.llm.api_key == "openai-key"

    client = build_llm(settings, plugin=FakePlugin)
    assert isinstance(client, FakeResponsesLLM)
    assert client.kwargs == {"api_key": "openai-key", "model": "gpt-4o-mini"}


def test_legacy_llm_model_override_still_applies() -> None:
    settings = settings_from(LLM_MODEL="gpt-4o")
    assert settings.llm is not None
    assert settings.llm.model == "gpt-4o"
    assert settings.llm_model == "gpt-4o"


@pytest.mark.parametrize(
    ("provider", "key_env", "expected_host", "expected_model"),
    [
        ("deepseek", "DEEPSEEK_API_KEY", "api.deepseek.com", "deepseek-chat"),
        ("dashscope", "DASHSCOPE_API_KEY", "dashscope.aliyuncs.com", "qwen-plus"),
        ("zhipu", "ZHIPU_API_KEY", "open.bigmodel.cn", "glm-4-plus"),
        ("moonshot", "MOONSHOT_API_KEY", "api.moonshot.cn", "moonshot-v1-8k"),
        ("minimax", "MINIMAX_API_KEY", "api.minimax.chat", "abab6.5s-chat"),
        ("openrouter", "OPENROUTER_API_KEY", "openrouter.ai", "openai/gpt-4o-mini"),
    ],
)
def test_each_provider_resolves_endpoint_model_and_key(
    provider: str, key_env: str, expected_host: str, expected_model: str
) -> None:
    settings = settings_from(LLM_PROVIDER=provider, **{key_env: f"{provider}-key"})
    selection = settings.llm
    assert selection is not None
    assert selection.provider == provider
    assert selection.model == expected_model
    assert expected_host in (selection.base_url or "")
    assert selection.api_key == f"{provider}-key"

    client = build_llm(settings, plugin=FakePlugin)
    assert isinstance(client, FakeChatLLM)
    assert client.kwargs["base_url"] == selection.base_url
    assert client.kwargs["model"] == expected_model
    assert client.kwargs["api_key"] == f"{provider}-key"


def test_provider_key_falls_back_to_openai_key_so_one_key_can_be_shared() -> None:
    settings = settings_from(LLM_PROVIDER="deepseek")
    assert settings.llm is not None
    assert settings.llm.api_key == "openai-key"


def test_explicit_overrides_beat_provider_defaults() -> None:
    settings = settings_from(
        LLM_PROVIDER="deepseek",
        LLM_BASE_URL="https://gateway.internal/v1",
        LLM_MODEL="deepseek-reasoner",
        LLM_API_KEY="explicit-key",
    )
    selection = settings.llm
    assert selection is not None
    assert selection.base_url == "https://gateway.internal/v1"
    assert selection.model == "deepseek-reasoner"
    assert selection.api_key == "explicit-key"


def test_custom_provider_requires_base_url_and_model() -> None:
    with pytest.raises(ConfigurationError, match="LLM_BASE_URL"):
        settings_from(LLM_PROVIDER="custom", LLM_MODEL="local-model")
    with pytest.raises(ConfigurationError, match="LLM_MODEL"):
        settings_from(LLM_PROVIDER="custom", LLM_BASE_URL="http://127.0.0.1:8001/v1")
    settings = settings_from(
        LLM_PROVIDER="custom",
        LLM_BASE_URL="http://127.0.0.1:8001/v1",
        LLM_MODEL="Qwen2.5-7B",
    )
    assert settings.llm is not None
    assert settings.llm.model == "Qwen2.5-7B"


@pytest.mark.parametrize("name", ["LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"])
def test_blank_override_is_rejected_rather_than_silently_defaulted(name: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        settings_from(LLM_PROVIDER="deepseek", **{name: "   "})


def test_unknown_provider_and_bad_base_url_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER must be one of"):
        settings_from(LLM_PROVIDER="not-a-vendor")
    with pytest.raises(ConfigurationError, match="LLM_BASE_URL must be an http"):
        settings_from(LLM_PROVIDER="deepseek", LLM_BASE_URL="ftp://nope")


def test_missing_key_names_the_accepted_env_vars() -> None:
    env = {k: v for k, v in BASE_PIPELINE_ENV.items() if k != "OPENAI_API_KEY"}
    with pytest.raises(ConfigurationError, match="MOONSHOT_API_KEY"):
        VoiceSettings.from_env({**env, "LLM_PROVIDER": "moonshot"})


def test_realtime_mode_does_not_require_llm_settings() -> None:
    settings = VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "qwen-realtime",
            "DASHSCOPE_API_KEY": "ds-key",
            "QWEN_REALTIME_URL": "wss://dashscope.example/realtime",
            "PLATFORM_API_URL": "http://localhost:8000",
        }
    )
    assert settings.llm is None


def test_registry_is_self_consistent() -> None:
    for key, provider in PROVIDERS.items():
        assert provider.key == key
        assert provider.label
        assert provider.api_key_envs
        if key not in {"openai", "custom"}:
            assert provider.base_url and provider.base_url.startswith("https://")
            assert provider.default_model
    assert "openai" in PROVIDER_KEYS
