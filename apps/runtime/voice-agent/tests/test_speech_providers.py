"""STT/TTS provider selection: can the legacy Vapi stack be reproduced exactly?

The parity claims asserted here come from the legacy console's stored Vapi
configs: Deepgram nova-2 / nova-3 / flux-general-en and OpenAI
gpt-4o-transcribe for recognition, ElevenLabs eleven_turbo_v2_5 /
eleven_flash_v2_5 with stability + similarityBoost for speech.
"""

from __future__ import annotations

from typing import Any

import pytest

from yino_voice_agent.config import ConfigurationError, VoiceSettings
from yino_voice_agent.providers import (
    UnsupportedProviderConfiguration,
    build_stt,
    build_tts,
)

BASE = {
    "VOICE_PROVIDER_MODE": "pipeline",
    "DASHSCOPE_API_KEY": "ds-key",
    "DASHSCOPE_WEBSOCKET_URL": "wss://dashscope.example/ws",
    "OPENAI_API_KEY": "openai-key",
    "PLATFORM_API_URL": "http://localhost:8000",
}


class Recorder:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeFunAsr(Recorder):
    pass


class FakeVoiceSettings(Recorder):
    pass


class FakeDeepgram:
    STT = type("DgSTT", (Recorder,), {})
    STTv2 = type("DgSTTv2", (Recorder,), {})


class FakeElevenLabs:
    TTS = type("ElTTS", (Recorder,), {})
    VoiceSettings = FakeVoiceSettings


class FakeCartesia:
    TTS = type("CaTTS", (Recorder,), {})


class FakeOpenAi:
    STT = type("OaSTT", (Recorder,), {})
    TTS = type("OaTTS", (Recorder,), {})


def settings_from(**overrides: str) -> VoiceSettings:
    return VoiceSettings.from_env({**BASE, **overrides})


FUN_ASR_KWARGS = {
    "api_key": "ds-key",
    "websocket_url": "wss://dashscope.example/ws",
    "model": "fun-asr-realtime",
    "language": "zh",
}


def make_stt(settings: VoiceSettings, plugins: Any | None = None) -> Any:
    return build_stt(
        settings,
        fun_asr_type=FakeFunAsr,
        fun_asr_kwargs=FUN_ASR_KWARGS,
        plugins=plugins,
    )


def make_tts(settings: VoiceSettings, plugins: Any | None = None) -> Any:
    return build_tts(
        settings,
        openai_plugin=FakeOpenAi,
        openai_kwargs={"api_key": "openai-key", "model": "gpt-4o-mini-tts"},
        plugins=plugins,
    )


# --- defaults stay exactly as before -----------------------------------------
def test_defaults_keep_fun_asr_and_openai_tts() -> None:
    settings = settings_from()
    assert settings.stt is not None and settings.stt.provider == "fun-asr"
    assert settings.tts is not None and settings.tts.provider == "openai"
    assert settings.tts.model == "gpt-4o-mini-tts"
    assert settings.tts.voice == "ash"
    assert isinstance(make_stt(settings), FakeFunAsr)
    assert isinstance(make_tts(settings), FakeOpenAi.TTS)


# --- STT parity ---------------------------------------------------------------
@pytest.mark.parametrize("model", ["nova-2", "nova-2-phonecall", "nova-3"])
def test_deepgram_nova_models_use_the_v1_client(model: str) -> None:
    settings = settings_from(
        STT_PROVIDER="deepgram",
        STT_MODEL=model,
        DEEPGRAM_API_KEY="dg-key",
        AGENT_LANGUAGE="en",
    )
    assert settings.stt is not None
    assert settings.stt.uses_deepgram_v2 is False
    client = make_stt(settings, plugins=FakeDeepgram)
    assert isinstance(client, FakeDeepgram.STT)
    assert client.kwargs == {"api_key": "dg-key", "model": model, "language": "en"}


def test_deepgram_flux_uses_the_v2_client_with_language_hint() -> None:
    settings = settings_from(
        STT_PROVIDER="deepgram",
        STT_MODEL="flux-general-en",
        DEEPGRAM_API_KEY="dg-key",
        AGENT_LANGUAGE="en",
    )
    assert settings.stt is not None and settings.stt.uses_deepgram_v2 is True
    client = make_stt(settings, plugins=FakeDeepgram)
    assert isinstance(client, FakeDeepgram.STTv2)
    assert client.kwargs == {
        "api_key": "dg-key",
        "model": "flux-general-en",
        "language_hint": "en",
    }


def test_openai_transcribe_matches_the_legacy_chinese_assistants() -> None:
    settings = settings_from(STT_PROVIDER="openai", AGENT_LANGUAGE="zh")
    assert settings.stt is not None
    assert settings.stt.model == "gpt-4o-transcribe"
    client = make_stt(settings, plugins=FakeOpenAi)
    assert isinstance(client, FakeOpenAi.STT)
    assert client.kwargs == {
        "api_key": "openai-key",
        "model": "gpt-4o-transcribe",
        "language": "zh",
    }


def test_stt_language_can_differ_from_the_agent_language() -> None:
    settings = settings_from(
        STT_PROVIDER="deepgram", DEEPGRAM_API_KEY="dg-key", STT_LANGUAGE="en-AU"
    )
    assert settings.stt is not None and settings.stt.language == "en-AU"


# --- TTS parity ---------------------------------------------------------------
def test_elevenlabs_carries_voice_id_model_and_tuning_verbatim() -> None:
    settings = settings_from(
        TTS_PROVIDER="elevenlabs",
        TTS_MODEL="eleven_turbo_v2_5",
        TTS_VOICE="uYXf8XasLslADfZ2MB4u",
        ELEVENLABS_API_KEY="el-key",
        TTS_STABILITY="0.5",
        TTS_SIMILARITY_BOOST="0.75",
    )
    selection = settings.tts
    assert selection is not None
    assert selection.model == "eleven_turbo_v2_5"
    assert selection.voice == "uYXf8XasLslADfZ2MB4u"
    assert selection.tuning.as_kwargs() == {"stability": 0.5, "similarity_boost": 0.75}

    client = make_tts(settings, plugins=FakeElevenLabs)
    assert isinstance(client, FakeElevenLabs.TTS)
    assert client.kwargs["api_key"] == "el-key"
    assert client.kwargs["model"] == "eleven_turbo_v2_5"
    assert client.kwargs["voice_id"] == "uYXf8XasLslADfZ2MB4u"
    assert client.kwargs["voice_settings"].kwargs == {
        "stability": 0.5,
        "similarity_boost": 0.75,
    }


def test_elevenlabs_flash_model_and_style_speed_are_accepted() -> None:
    settings = settings_from(
        TTS_PROVIDER="elevenlabs",
        TTS_MODEL="eleven_flash_v2_5",
        TTS_VOICE="bhJUNIXWQQ94l8eI2VUf",
        ELEVENLABS_API_KEY="el-key",
        TTS_STYLE="0.5",
        TTS_SPEED="1.0",
    )
    assert settings.tts is not None
    assert settings.tts.tuning.as_kwargs() == {"style": 0.5, "speed": 1.0}


def test_elevenlabs_without_tuning_omits_voice_settings() -> None:
    settings = settings_from(
        TTS_PROVIDER="elevenlabs", TTS_VOICE="voice-1", ELEVENLABS_API_KEY="el-key"
    )
    client = make_tts(settings, plugins=FakeElevenLabs)
    assert "voice_settings" not in client.kwargs


def test_cartesia_substitutes_for_the_vapi_built_in_voices() -> None:
    settings = settings_from(
        TTS_PROVIDER="cartesia", TTS_VOICE="voice-uuid", CARTESIA_API_KEY="ca-key"
    )
    assert settings.tts is not None and settings.tts.model == "sonic-2"
    client = make_tts(settings, plugins=FakeCartesia)
    assert isinstance(client, FakeCartesia.TTS)
    assert client.kwargs == {
        "api_key": "ca-key",
        "model": "sonic-2",
        "voice": "voice-uuid",
    }


# --- guard rails --------------------------------------------------------------
def test_tuning_on_a_provider_that_cannot_apply_it_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="not supported"):
        settings_from(TTS_PROVIDER="openai", TTS_STABILITY="0.5")


def test_elevenlabs_requires_a_voice_id() -> None:
    with pytest.raises(ConfigurationError, match="TTS_VOICE"):
        settings_from(TTS_PROVIDER="elevenlabs", ELEVENLABS_API_KEY="el-key")


def test_missing_vendor_key_names_the_accepted_env_vars() -> None:
    with pytest.raises(ConfigurationError, match="DEEPGRAM_API_KEY"):
        settings_from(STT_PROVIDER="deepgram")
    with pytest.raises(ConfigurationError, match="ELEVENLABS_API_KEY"):
        settings_from(TTS_PROVIDER="elevenlabs", TTS_VOICE="v")


def test_unknown_providers_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="STT_PROVIDER must be one of"):
        settings_from(STT_PROVIDER="nope")
    with pytest.raises(ConfigurationError, match="TTS_PROVIDER must be one of"):
        settings_from(TTS_PROVIDER="nope")


def test_non_numeric_tuning_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="TTS_STABILITY must be a number"):
        settings_from(
            TTS_PROVIDER="elevenlabs",
            TTS_VOICE="v",
            ELEVENLABS_API_KEY="el-key",
            TTS_STABILITY="high",
        )


def test_dashscope_tts_points_the_operator_at_realtime_mode() -> None:
    settings = settings_from(TTS_PROVIDER="dashscope")
    with pytest.raises(UnsupportedProviderConfiguration, match="qwen-realtime"):
        make_tts(settings)


def test_missing_plugin_names_the_extra_to_install() -> None:
    settings = settings_from(STT_PROVIDER="deepgram", DEEPGRAM_API_KEY="dg-key")
    with pytest.raises(UnsupportedProviderConfiguration, match="overseas"):
        build_stt(
            settings,
            fun_asr_type=FakeFunAsr,
            fun_asr_kwargs=FUN_ASR_KWARGS,
            plugins=None,
        )


def test_realtime_mode_needs_no_speech_provider_settings() -> None:
    settings = VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "qwen-realtime",
            "DASHSCOPE_API_KEY": "ds-key",
            "QWEN_REALTIME_URL": "wss://dashscope.example/realtime",
            "PLATFORM_API_URL": "http://localhost:8000",
        }
    )
    assert settings.stt is None
    assert settings.tts is None
