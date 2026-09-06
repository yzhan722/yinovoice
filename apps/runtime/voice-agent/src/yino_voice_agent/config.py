"""Environment-backed settings for the local voice agent."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast
from urllib.parse import urlsplit

from .llm_providers import PROVIDER_KEYS, PROVIDERS, LlmSelection
from .voice_ux_config import VoiceUxSettings

ProviderMode = Literal["qwen-realtime", "pipeline"]
DEFAULT_LIVEKIT_AGENT_NAME = "yino-customer-service"


class ConfigurationError(ValueError):
    """Raised when a required setting is absent or blank."""


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    """Validated provider and customer-service settings."""

    provider_mode: ProviderMode
    dashscope_api_key: str
    qwen_realtime_url: str | None
    qwen_realtime_model: str
    qwen_realtime_voice: str
    dashscope_websocket_url: str | None
    openai_api_key: str | None
    fun_asr_model: str | None
    llm_model: str | None
    llm: LlmSelection | None
    tts_model: str | None
    tts_voice: str | None
    language: str | None
    greeting: str
    platform_api_url: str
    allow_empty_dispatch_metadata_local_dev: bool
    phone_lookup_token: str | None
    ux: VoiceUxSettings = field(default_factory=VoiceUxSettings)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> VoiceSettings:
        values = os.environ if env is None else env

        def read(name: str, default: str | None = None) -> str:
            value = values.get(name, default)
            if value is None or not value.strip():
                raise ConfigurationError(f"{name} must not be blank")
            return value.strip()

        def read_bool(name: str, default: bool = False) -> bool:
            raw = values.get(name)
            if raw is None:
                return default
            normalized = raw.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
            raise ConfigurationError(f"{name} must be true or false")

        provider_mode_value = read("VOICE_PROVIDER_MODE", "qwen-realtime")
        if provider_mode_value not in {"qwen-realtime", "pipeline"}:
            raise ConfigurationError(
                "VOICE_PROVIDER_MODE must be qwen-realtime or pipeline"
            )
        provider_mode = cast(ProviderMode, provider_mode_value)

        def read_optional_value(name: str) -> str | None:
            raw = values.get(name)
            if raw is None or not raw.strip():
                return None
            return raw.strip()

        def read_override(name: str) -> str | None:
            """Absent means "use the default"; present but blank is a mistake."""
            if name not in values:
                return None
            raw = values[name]
            if raw is None or not raw.strip():
                raise ConfigurationError(f"{name} must not be blank")
            return raw.strip()

        def resolve_llm() -> LlmSelection:
            """Pick the pipeline LLM: explicit overrides win over provider defaults."""
            provider_key = (values.get("LLM_PROVIDER") or "openai").strip().lower()
            if provider_key not in PROVIDERS:
                raise ConfigurationError(
                    "LLM_PROVIDER must be one of: " + ", ".join(PROVIDER_KEYS)
                )
            provider = PROVIDERS[provider_key]
            base_url = read_override("LLM_BASE_URL") or provider.base_url
            model = read_override("LLM_MODEL") or provider.default_model
            api_key = read_override("LLM_API_KEY")
            if api_key is None:
                for env_name in provider.api_key_envs:
                    api_key = read_optional_value(env_name)
                    if api_key:
                        break
            if not model:
                raise ConfigurationError(
                    f"LLM_MODEL is required for LLM_PROVIDER={provider_key}"
                )
            if not api_key:
                raise ConfigurationError(
                    f"LLM_PROVIDER={provider_key} needs LLM_API_KEY or one of: "
                    + ", ".join(provider.api_key_envs)
                )
            if provider_key == "custom" and not base_url:
                raise ConfigurationError("LLM_PROVIDER=custom requires LLM_BASE_URL")
            if base_url is not None:
                parsed = urlsplit(base_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ConfigurationError("LLM_BASE_URL must be an http(s) URL")
            return LlmSelection(
                provider=provider_key,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )

        qwen_realtime_url: str | None = None
        dashscope_websocket_url: str | None = None
        openai_api_key: str | None = None
        fun_asr_model: str | None = None
        llm_model: str | None = None
        llm: LlmSelection | None = None
        tts_model: str | None = None
        tts_voice: str | None = None
        language: str | None = None
        if provider_mode == "qwen-realtime":
            qwen_realtime_url = read("QWEN_REALTIME_URL")
            try:
                parsed_realtime_url = urlsplit(qwen_realtime_url)
            except ValueError:
                raise ConfigurationError(
                    "QWEN_REALTIME_URL must be a valid wss:// URL"
                ) from None
            if parsed_realtime_url.scheme != "wss" or not parsed_realtime_url.netloc:
                raise ConfigurationError("QWEN_REALTIME_URL must be a valid wss:// URL")
        else:
            dashscope_websocket_url = read("DASHSCOPE_WEBSOCKET_URL")
            llm = resolve_llm()
            llm_model = llm.model
            # TTS still runs on OpenAI; the LLM may now live elsewhere.
            openai_api_key = read("OPENAI_API_KEY")
            fun_asr_model = read("FUN_ASR_MODEL", "fun-asr-realtime")
            tts_model = read("TTS_MODEL", "gpt-4o-mini-tts")
            tts_voice = read("TTS_VOICE", "ash")
            language = read("AGENT_LANGUAGE", "zh")

        read_optional = read_optional_value

        return cls(
            provider_mode=provider_mode,
            dashscope_api_key=read("DASHSCOPE_API_KEY"),
            qwen_realtime_url=qwen_realtime_url,
            qwen_realtime_model=read(
                "QWEN_REALTIME_MODEL", "qwen-audio-3.0-realtime-plus"
            ),
            qwen_realtime_voice=read("QWEN_REALTIME_VOICE", "longanqian"),
            dashscope_websocket_url=dashscope_websocket_url,
            openai_api_key=openai_api_key,
            fun_asr_model=fun_asr_model,
            llm_model=llm_model,
            llm=llm,
            tts_model=tts_model,
            tts_voice=tts_voice,
            language=language,
            greeting=read(
                "AGENT_GREETING",
                "您好，这里是演示机构客服，请问有什么可以帮您？",  # noqa: RUF001
            ),
            platform_api_url=read(
                "PLATFORM_API_URL",
                "http://localhost:8000",
            ),
            allow_empty_dispatch_metadata_local_dev=read_bool(
                "ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV",
            ),
            phone_lookup_token=read_optional("PHONE_LOOKUP_TOKEN"),
            ux=VoiceUxSettings.from_env(values),
        )
