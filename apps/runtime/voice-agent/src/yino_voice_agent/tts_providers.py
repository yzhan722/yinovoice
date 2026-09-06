"""TTS provider registry for pipeline mode (overseas parity with Vapi).

Ten of the thirteen legacy assistants speak through ElevenLabs, and the
LiveKit plugin takes the same model names, the same voice ids and the same
four tuning knobs (stability, similarity_boost, style, speed), so those voices
carry over unchanged. The three assistants on Vapi's own voices (Layla, Emma,
Nico) have no equivalent to copy and need a substitute voice chosen by ear.

Plugins are imported lazily; vendors come from the `overseas` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class TtsProvider:
    key: str
    label: str
    default_model: str
    default_voice: str
    api_key_envs: tuple[str, ...]
    plugin_extra: str = ""
    supports_tuning: bool = False
    notes: str = ""


PROVIDERS: Final[dict[str, TtsProvider]] = {
    "openai": TtsProvider(
        key="openai",
        label="OpenAI TTS",
        default_model="gpt-4o-mini-tts",
        default_voice="ash",
        api_key_envs=("OPENAI_API_KEY",),
        notes="Current pipeline default; instructions steer style.",
    ),
    "elevenlabs": TtsProvider(
        key="elevenlabs",
        label="ElevenLabs",
        default_model="eleven_turbo_v2_5",
        default_voice="",
        api_key_envs=("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
        plugin_extra="elevenlabs",
        supports_tuning=True,
        notes=(
            "Same vendor as the legacy assistants: reuse the Vapi voiceId and "
            "eleven_turbo_v2_5 / eleven_flash_v2_5 verbatim."
        ),
    ),
    "cartesia": TtsProvider(
        key="cartesia",
        label="Cartesia",
        default_model="sonic-2",
        default_voice="",
        api_key_envs=("CARTESIA_API_KEY",),
        plugin_extra="cartesia",
        notes="Low-latency substitute for the three Vapi built-in voices.",
    ),
    "dashscope": TtsProvider(
        key="dashscope",
        label="Alibaba CosyVoice (DashScope)",
        default_model="cosyvoice-v2",
        default_voice="longanqian",
        api_key_envs=("DASHSCOPE_API_KEY",),
        notes="Mainland Chinese voices; same ids the console already offers.",
    ),
}

PROVIDER_KEYS: Final[tuple[str, ...]] = tuple(PROVIDERS)


@dataclass(frozen=True, slots=True)
class TtsTuning:
    """ElevenLabs voice settings, named exactly as Vapi stores them."""

    stability: float | None = None
    similarity_boost: float | None = None
    style: float | None = None
    speed: float | None = None
    use_speaker_boost: bool | None = None

    def as_kwargs(self) -> dict[str, float | bool]:
        return {
            name: value
            for name, value in (
                ("stability", self.stability),
                ("similarity_boost", self.similarity_boost),
                ("style", self.style),
                ("speed", self.speed),
                ("use_speaker_boost", self.use_speaker_boost),
            )
            if value is not None
        }


@dataclass(frozen=True, slots=True)
class TtsSelection:
    provider: str
    model: str
    voice: str
    api_key: str
    tuning: TtsTuning = TtsTuning()

    @property
    def label(self) -> str:
        return PROVIDERS[self.provider].label
