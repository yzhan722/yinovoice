from pathlib import Path
from typing import ClassVar

import pytest
from livekit import rtc
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectionError, stt

from yino_voice_agent.fun_asr import FunAsrSTT


class FakeResult:
    def get_sentence(self) -> dict[str, object]:
        return {"text": "我想预约明天下午洗牙。"}

    def get_request_id(self) -> str:
        return "request-123"


class EmptyResult(FakeResult):
    def get_sentence(self) -> dict[str, object]:
        return {"text": ""}


class FakeRecognition:
    paths: ClassVar[list[Path]] = []
    result_type: ClassVar[type[FakeResult]] = FakeResult

    def __init__(
        self,
        *,
        model: str,
        format: str,
        sample_rate: int,
        callback: object,
    ) -> None:
        assert model == "fun-asr-realtime"
        assert format == "wav"
        assert sample_rate == 16000
        assert callback is None

    def call(self, path: str) -> FakeResult:
        wav_path = Path(path)
        assert wav_path.exists()
        assert wav_path.read_bytes().startswith(b"RIFF")
        self.paths.append(wav_path)
        return self.result_type()


class EmptyRecognition(FakeRecognition):
    result_type = EmptyResult


def mono_frame() -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=bytes(3200),
        sample_rate=16000,
        num_channels=1,
        samples_per_channel=1600,
    )


def create_adapter(
    recognition_factory: type[FakeRecognition] = FakeRecognition,
) -> tuple[FunAsrSTT, list[tuple[str, str]]]:
    configuration_calls: list[tuple[str, str]] = []
    adapter = FunAsrSTT(
        api_key="test-key",
        websocket_url="wss://example.invalid/api-ws/v1/inference",
        recognition_factory=recognition_factory,
        sdk_configurer=lambda key, url: configuration_calls.append((key, url)),
    )
    return adapter, configuration_calls


@pytest.mark.asyncio
async def test_returns_livekit_final_transcript_and_cleans_up_wav() -> None:
    FakeRecognition.paths.clear()
    adapter, configuration_calls = create_adapter()

    event = await adapter._recognize_impl(
        mono_frame(),
        conn_options=DEFAULT_API_CONNECT_OPTIONS,
    )

    assert event.type is stt.SpeechEventType.FINAL_TRANSCRIPT
    assert event.request_id == "request-123"
    assert event.alternatives[0].text == "我想预约明天下午洗牙。"
    assert event.alternatives[0].language == "zh"
    assert configuration_calls == [
        ("test-key", "wss://example.invalid/api-ws/v1/inference")
    ]
    assert len(FakeRecognition.paths) == 1
    assert not FakeRecognition.paths[0].exists()


@pytest.mark.asyncio
async def test_empty_transcript_is_rejected() -> None:
    adapter, _ = create_adapter(EmptyRecognition)

    with pytest.raises(APIConnectionError, match="empty transcript"):
        await adapter._recognize_impl(
            mono_frame(),
            conn_options=DEFAULT_API_CONNECT_OPTIONS,
        )


@pytest.mark.asyncio
async def test_stereo_audio_is_rejected() -> None:
    frame = rtc.AudioFrame(
        data=bytes(6400),
        sample_rate=16000,
        num_channels=2,
        samples_per_channel=1600,
    )
    adapter, _ = create_adapter()

    with pytest.raises(ValueError, match="mono audio"):
        await adapter._recognize_impl(
            frame,
            conn_options=DEFAULT_API_CONNECT_OPTIONS,
        )
