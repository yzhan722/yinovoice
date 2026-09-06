"""STT provider registry for pipeline mode (overseas parity with Vapi).

The legacy Vapi assistants use Deepgram (nova-2 / nova-3 / flux-general-en) for
English and OpenAI gpt-4o-transcribe for Chinese. Both are available as LiveKit
plugins with the same model names, so an imported assistant can keep the exact
recogniser it had. Fun-ASR stays the default for mainland Chinese traffic.

Plugins are imported lazily: the default install only carries openai + silero,
and vendors come from the `overseas` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SttProvider:
    key: str
    label: str
    default_model: str
    api_key_envs: tuple[str, ...]
    # Deepgram's Flux models run on a different client class than nova-*.
    plugin_extra: str = ""
    notes: str = ""


PROVIDERS: Final[dict[str, SttProvider]] = {
    "fun-asr": SttProvider(
        key="fun-asr",
        label="Alibaba Fun-ASR (DashScope)",
        default_model="fun-asr-realtime",
        api_key_envs=("DASHSCOPE_API_KEY",),
        notes="Mainland Chinese default; already bundled with the runtime.",
    ),
    "deepgram": SttProvider(
        key="deepgram",
        label="Deepgram",
        default_model="nova-3",
        api_key_envs=("DEEPGRAM_API_KEY",),
        plugin_extra="deepgram",
        notes=(
            "English/multilingual. nova-2-phonecall and nova-2-conversationalai "
            "are tuned for telephony; flux-general-en uses the v2 client."
        ),
    ),
    "openai": SttProvider(
        key="openai",
        label="OpenAI transcribe",
        default_model="gpt-4o-transcribe",
        api_key_envs=("OPENAI_API_KEY",),
        notes="What the legacy Chinese assistants used on Vapi.",
    ),
}

PROVIDER_KEYS: Final[tuple[str, ...]] = tuple(PROVIDERS)

# Deepgram exposes Flux through STTv2 rather than STT.
DEEPGRAM_V2_MODELS: Final[frozenset[str]] = frozenset(
    {"flux-general-en", "flux-general-multi"}
)


@dataclass(frozen=True, slots=True)
class SttSelection:
    provider: str
    model: str
    language: str
    api_key: str
    base_url: str | None = None

    @property
    def label(self) -> str:
        return PROVIDERS[self.provider].label

    @property
    def uses_deepgram_v2(self) -> bool:
        return self.provider == "deepgram" and self.model in DEEPGRAM_V2_MODELS
