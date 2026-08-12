"""Construction boundary for replaceable speech and language providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ProviderMode, VoiceSettings
from .customer_service import build_customer_service_instructions
from .qwen_realtime import QwenRealtimeModel
from .runtime_config import RuntimeCustomerService


class UnsupportedProviderConfiguration(ValueError):  # noqa: N818
    """Raised when a published voice provider is unavailable in this runtime."""


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    mode: ProviderMode
    llm: Any
    stt: Any | None = None
    tts: Any | None = None


def _pipeline_value(value: str | None, name: str) -> str:
    if value is None:
        raise UnsupportedProviderConfiguration(
            f"{name} is required in pipeline mode"
        )
    return value


def build_providers(
    settings: VoiceSettings,
    runtime_config: RuntimeCustomerService | None = None,
    stt_type: Any | None = None,
    plugin: Any | None = None,
    realtime_type: Any = QwenRealtimeModel,
) -> ProviderBundle:
    """Build provider objects without coupling them to the session runtime."""

    if settings.provider_mode == "qwen-realtime":
        if runtime_config is None:
            realtime_instructions = ""
            realtime_voice = settings.qwen_realtime_voice
        else:
            realtime_instructions = build_customer_service_instructions(
                organization_name=runtime_config.organization_name,
                platform_prompt=runtime_config.platform_prompt,
                tenant_prompt=runtime_config.tenant_prompt,
                brevity=runtime_config.response.brevity,
                max_spoken_sentences=(
                    runtime_config.response.max_spoken_sentences
                ),
                ask_one_question_at_a_time=(
                    runtime_config.response.ask_one_question_at_a_time
                ),
            )
            realtime_voice = (
                runtime_config.voice.tts_voice or settings.qwen_realtime_voice
            )
            # Guard against stale CosyVoice IDs that would kill the session.
            from .runtime_config import _TTS_VOICES

            if realtime_voice not in _TTS_VOICES:
                realtime_voice = settings.qwen_realtime_voice or "longanqian"
        return ProviderBundle(
            mode="qwen-realtime",
            llm=realtime_type(
                api_key=settings.dashscope_api_key,
                url=settings.qwen_realtime_url,
                model=settings.qwen_realtime_model,
                voice=realtime_voice,
                instructions=realtime_instructions,
            ),
        )

    dashscope_websocket_url = _pipeline_value(
        settings.dashscope_websocket_url, "DASHSCOPE_WEBSOCKET_URL"
    )
    openai_api_key = _pipeline_value(
        settings.openai_api_key, "OPENAI_API_KEY"
    )
    fun_asr_model = _pipeline_value(settings.fun_asr_model, "FUN_ASR_MODEL")
    llm_model = _pipeline_value(settings.llm_model, "LLM_MODEL")
    tts_model = _pipeline_value(settings.tts_model, "TTS_MODEL")
    tts_voice = _pipeline_value(settings.tts_voice, "TTS_VOICE")
    language = _pipeline_value(settings.language, "AGENT_LANGUAGE")

    if stt_type is None:
        from .fun_asr import FunAsrSTT

        stt_type = FunAsrSTT
    if plugin is None:
        from livekit.plugins import openai

        plugin = openai

    tts_options = {
        "api_key": openai_api_key,
        "model": tts_model,
        "voice": tts_voice,
        "instructions": "使用自然、清晰、友好的标准普通话朗读。",
    }
    if runtime_config is not None:
        voice = runtime_config.voice
        if voice.preset_id != "mandarin-standard":
            raise UnsupportedProviderConfiguration(
                "Runtime voice preset is unsupported"
            )
        tts_options.update(
            model=tts_model,
            voice=tts_voice,
            speed=voice.speaking_rate,
            instructions=(
                "使用自然、清晰的语音朗读。"
                f"Style: {voice.style}. Emotion: {voice.emotion}. "
                f"Locale: {voice.locale}. Pause profile: {voice.pause_profile}."
            ),
        )

    return ProviderBundle(
        mode="pipeline",
        stt=stt_type(
            api_key=settings.dashscope_api_key,
            websocket_url=dashscope_websocket_url,
            model=fun_asr_model,
            language=language,
        ),
        llm=plugin.responses.LLM(
            api_key=openai_api_key,
            model=llm_model,
        ),
        tts=plugin.TTS(**tts_options),
    )
