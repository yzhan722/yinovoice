from unittest.mock import patch

from yino_voice_agent.providers import ProviderBundle
from yino_voice_agent.session import create_session


def test_pipeline_session_receives_provider_bundle_and_vad() -> None:
    providers = ProviderBundle(
        mode="pipeline", stt=object(), llm=object(), tts=object()
    )
    vad = object()

    with patch("yino_voice_agent.session.AgentSession") as session_type:
        session = create_session(providers, vad)

    session_type.assert_called_once_with(
        stt=providers.stt,
        llm=providers.llm,
        tts=providers.tts,
        vad=vad,
    )
    assert session is session_type.return_value


def test_realtime_session_uses_only_llm_and_model_turn_detection() -> None:
    providers = ProviderBundle(mode="qwen-realtime", llm=object())

    with patch("yino_voice_agent.session.AgentSession") as session_type:
        session = create_session(providers, vad=None)

    session_type.assert_called_once_with(
        llm=providers.llm,
        turn_detection="realtime_llm",
    )
    assert session is session_type.return_value
