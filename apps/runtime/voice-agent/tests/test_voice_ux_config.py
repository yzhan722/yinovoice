from __future__ import annotations

import pytest

from yino_voice_agent.config import ConfigurationError, VoiceSettings
from yino_voice_agent.voice_ux_config import (
    CONTEXT_POLICY,
    ENDPOINT_AUTHORITY,
    PROVIDER_DISCONNECT_POLICY,
    VoiceUxSettings,
)


def realtime_env() -> dict[str, str]:
    return {
        "DASHSCOPE_API_KEY": "dashscope-test-key",
        "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
    }


def test_voice_ux_defaults_are_telephone_safe() -> None:
    ux = VoiceUxSettings.from_env({})
    assert ux.initial_silence_s == 8.0
    assert ux.followup_silence_s == 12.0
    assert ux.max_silence_prompts == 2
    assert ux.max_idle_s == 180.0
    assert ux.max_session_s == 1800.0
    assert ux.endpoint_silence_ms == 450
    assert ux.endpoint_threshold == 0.35
    assert ux.provider_disconnect_policy == PROVIDER_DISCONNECT_POLICY
    assert ux.context_policy == CONTEXT_POLICY
    assert ux.endpoint_authority == ENDPOINT_AUTHORITY
    assert ux.max_session_s >= ux.max_idle_s


def test_voice_ux_loads_from_env_and_rejects_invalid() -> None:
    ux = VoiceUxSettings.from_env({"VOICE_UX_INITIAL_SILENCE_S": "10"})
    assert ux.initial_silence_s == 10.0
    with pytest.raises(ConfigurationError, match="VOICE_UX_INITIAL_SILENCE_S"):
        VoiceUxSettings.from_env({"VOICE_UX_INITIAL_SILENCE_S": "nope"})
    with pytest.raises(ConfigurationError, match="VOICE_UX_MAX_SILENCE_PROMPTS"):
        VoiceUxSettings.from_env({"VOICE_UX_MAX_SILENCE_PROMPTS": "0"})


def test_voice_settings_includes_ux() -> None:
    settings = VoiceSettings.from_env(realtime_env())
    assert settings.ux.endpoint_silence_ms == 450
