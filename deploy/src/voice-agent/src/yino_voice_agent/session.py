"""LiveKit AgentSession composition."""

from __future__ import annotations

from typing import Any

from livekit.agents import AgentSession

from .providers import ProviderBundle


def create_session(providers: ProviderBundle, vad: Any | None) -> AgentSession:
    """Compose the audio pipeline while preserving provider boundaries."""

    if providers.mode == "qwen-realtime":
        return AgentSession(
            llm=providers.llm,
            turn_detection="realtime_llm",
        )

    return AgentSession(
        stt=providers.stt,
        llm=providers.llm,
        tts=providers.tts,
        vad=vad,
    )
