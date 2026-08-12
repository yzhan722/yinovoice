"""LiveKit STT adapter for Alibaba Cloud Model Studio Fun-ASR."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dashscope
from dashscope.audio.asr import Recognition
from livekit import rtc
from livekit.agents import (
    NOT_GIVEN,
    APIConnectionError,
    APIConnectOptions,
    NotGivenOr,
    stt,
)
from livekit.agents.utils import AudioBuffer


def configure_dashscope(api_key: str, websocket_url: str) -> None:
    """Configure the DashScope SDK without exposing credentials in logs."""

    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = websocket_url


class FunAsrSTT(stt.STT):
    """Return one final transcript for each VAD-delimited utterance."""

    def __init__(
        self,
        *,
        api_key: str,
        websocket_url: str,
        model: str = "fun-asr-realtime",
        language: str = "zh",
        recognition_factory: Callable[..., Any] = Recognition,
        sdk_configurer: Callable[[str, str], None] = configure_dashscope,
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )
        self._api_key = api_key
        self._websocket_url = websocket_url
        self._model = model
        self._language = language
        self._recognition_factory = recognition_factory
        self._sdk_configurer = sdk_configurer

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "Alibaba Cloud Model Studio"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        del language, conn_options
        frame = rtc.combine_audio_frames(buffer)
        if frame.num_channels != 1:
            raise ValueError("Fun-ASR Stage 1 adapter requires mono audio")

        frames = [frame]
        if frame.sample_rate != 16000:
            resampler = rtc.AudioResampler(
                input_rate=frame.sample_rate,
                output_rate=16000,
                num_channels=1,
                quality=rtc.AudioResamplerQuality.HIGH,
            )
            frames = [*resampler.push(frame), *resampler.flush()]

        wav_bytes = rtc.combine_audio_frames(frames).to_wav_bytes()
        text, request_id = await asyncio.to_thread(
            self._recognize_wav,
            wav_bytes,
        )
        if not text:
            raise APIConnectionError("Fun-ASR returned an empty transcript")

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            request_id=request_id,
            alternatives=[
                stt.SpeechData(
                    language=self._language,
                    text=text,
                    confidence=1.0,
                )
            ],
        )

    def _recognize_wav(self, wav_bytes: bytes) -> tuple[str, str]:
        self._sdk_configurer(self._api_key, self._websocket_url)
        descriptor, file_name = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        path = Path(file_name)
        try:
            path.write_bytes(wav_bytes)
            recognition = self._recognition_factory(
                model=self._model,
                format="wav",
                sample_rate=16000,
                callback=None,
            )
            result = recognition.call(str(path))
            sentence = result.get_sentence() or {}
            return (
                str(sentence.get("text", "")).strip(),
                str(result.get_request_id()),
            )
        except APIConnectionError:
            raise
        except Exception as error:
            raise APIConnectionError("Fun-ASR recognition failed") from error
        finally:
            path.unlink(missing_ok=True)
