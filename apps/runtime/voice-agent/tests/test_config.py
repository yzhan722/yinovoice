import pytest

from yino_voice_agent.config import (
    DEFAULT_LIVEKIT_AGENT_NAME,
    ConfigurationError,
    VoiceSettings,
)


def valid_env() -> dict[str, str]:
    return {
        "VOICE_PROVIDER_MODE": "pipeline",
        "DASHSCOPE_API_KEY": "dashscope-test-key",
        "DASHSCOPE_WEBSOCKET_URL": (
            "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
        ),
        "OPENAI_API_KEY": "openai-test-key",
    }


def realtime_env() -> dict[str, str]:
    return {
        "DASHSCOPE_API_KEY": "dashscope-test-key",
        "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
    }


def test_qwen_realtime_is_the_default_without_pipeline_credentials() -> None:
    settings = VoiceSettings.from_env(realtime_env())

    assert settings.provider_mode == "qwen-realtime"
    assert settings.openai_api_key is None
    assert settings.dashscope_websocket_url is None


def test_qwen_realtime_uses_the_documented_model_and_voice_defaults() -> None:
    settings = VoiceSettings.from_env(realtime_env())

    assert settings.qwen_realtime_model == "qwen-audio-3.0-realtime-plus"
    assert settings.qwen_realtime_voice == "longanqian"


def test_qwen_realtime_ignores_blank_legacy_pipeline_values() -> None:
    settings = VoiceSettings.from_env(
        realtime_env()
        | {
            "DASHSCOPE_WEBSOCKET_URL": "   ",
            "OPENAI_API_KEY": "   ",
            "FUN_ASR_MODEL": "   ",
            "LLM_MODEL": "   ",
            "TTS_MODEL": "   ",
            "TTS_VOICE": "   ",
            "AGENT_LANGUAGE": "   ",
        }
    )

    assert settings.dashscope_websocket_url is None
    assert settings.openai_api_key is None
    assert settings.fun_asr_model is None
    assert settings.llm_model is None
    assert settings.tts_model is None
    assert settings.tts_voice is None
    assert settings.language is None


@pytest.mark.parametrize(
    ("override", "expected_name", "sensitive_value"),
    [
        ({"DASHSCOPE_API_KEY": "   "}, "DASHSCOPE_API_KEY", None),
        (
            {
                "QWEN_REALTIME_URL": (
                    "https://workspace.example/realtime?token=sensitive-query-value"
                )
            },
            "QWEN_REALTIME_URL",
            "sensitive-query-value",
        ),
        (
            {"QWEN_REALTIME_URL": "wss://["},
            "QWEN_REALTIME_URL",
            None,
        ),
    ],
)
def test_qwen_realtime_rejects_invalid_required_values_safely(
    override: dict[str, str],
    expected_name: str,
    sensitive_value: str | None,
) -> None:
    with pytest.raises(ConfigurationError, match=expected_name) as error:
        VoiceSettings.from_env(realtime_env() | override)

    if sensitive_value is not None:
        assert sensitive_value not in str(error.value)


@pytest.mark.parametrize(
    "name",
    ["QWEN_REALTIME_MODEL", "QWEN_REALTIME_VOICE"],
)
def test_qwen_realtime_rejects_blank_optional_overrides(name: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        VoiceSettings.from_env(realtime_env() | {name: "   "})


def test_unknown_provider_mode_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="VOICE_PROVIDER_MODE"):
        VoiceSettings.from_env(realtime_env() | {"VOICE_PROVIDER_MODE": "unknown"})


def test_pipeline_loads_defaults_with_required_credentials() -> None:
    settings = VoiceSettings.from_env(valid_env())

    assert settings.provider_mode == "pipeline"
    assert settings.fun_asr_model == "fun-asr-realtime"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.tts_model == "gpt-4o-mini-tts"
    assert settings.tts_voice == "ash"
    assert settings.language == "zh"
    assert settings.allow_empty_dispatch_metadata_local_dev is False


def test_empty_dispatch_metadata_requires_explicit_local_dev_opt_in() -> None:
    settings = VoiceSettings.from_env(
        valid_env() | {"ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV": "true"}
    )

    assert settings.allow_empty_dispatch_metadata_local_dev is True


def test_invalid_local_dev_boolean_is_rejected() -> None:
    with pytest.raises(
        ConfigurationError,
        match="ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV",
    ):
        VoiceSettings.from_env(
            valid_env() | {"ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV": "sometimes"}
        )


def test_blank_phone_lookup_token_is_optional() -> None:
    settings = VoiceSettings.from_env(valid_env() | {"PHONE_LOOKUP_TOKEN": "   "})
    assert settings.phone_lookup_token is None
    settings = VoiceSettings.from_env(
        valid_env() | {"PHONE_LOOKUP_TOKEN": "runtime-lookup-token"}
    )
    assert settings.phone_lookup_token == "runtime-lookup-token"


def test_default_greeting_uses_customer_service_language() -> None:
    settings = VoiceSettings.from_env(valid_env())

    assert settings.greeting == "您好，这里是演示机构客服，请问有什么可以帮您？"
    assert "助手" not in settings.greeting


@pytest.mark.parametrize(
    "missing_name",
    ["DASHSCOPE_API_KEY", "DASHSCOPE_WEBSOCKET_URL", "OPENAI_API_KEY"],
)
def test_missing_required_value_is_rejected(missing_name: str) -> None:
    env = valid_env()
    env.pop(missing_name)

    with pytest.raises(ConfigurationError, match=missing_name):
        VoiceSettings.from_env(env)


@pytest.mark.parametrize(
    "name",
    [
        "DASHSCOPE_WEBSOCKET_URL",
        "OPENAI_API_KEY",
        "FUN_ASR_MODEL",
        "LLM_MODEL",
        "TTS_MODEL",
        "TTS_VOICE",
        "AGENT_LANGUAGE",
    ],
)
def test_blank_pipeline_value_is_rejected(name: str) -> None:
    env = valid_env() | {name: "   "}

    with pytest.raises(ConfigurationError, match=name):
        VoiceSettings.from_env(env)


def test_default_livekit_agent_name_is_stable() -> None:
    assert DEFAULT_LIVEKIT_AGENT_NAME == "yino-customer-service"
