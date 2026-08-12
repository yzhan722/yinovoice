from __future__ import annotations

import asyncio
import logging
import time
import weakref
from array import array
from collections import deque
from collections.abc import AsyncIterable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp
from livekit import rtc
from livekit.agents import llm, utils
from livekit.agents.types import NOT_GIVEN, NotGivenOr

logger = logging.getLogger("yino_voice_agent.qwen_realtime")

from .qwen_realtime_protocol import (
    QwenProtocolError,
    QwenSessionOptions,
    build_audio_append,
    build_audio_commit,
    build_instructions_update,
    build_response_cancel,
    build_response_create,
    build_session_update,
    build_user_text_item,
    decode_audio_delta,
    parse_server_event,
)

OUTPUT_SAMPLE_RATE = 24_000
NUM_CHANNELS = 1
INPUT_SAMPLE_RATE = 16_000
INPUT_SAMPLES_PER_CHUNK = 640
# Ignore near-silence so Qwen's input buffer is not filled with zeros between turns.
INPUT_MIN_PEAK = 600
# While the assistant is speaking, require louder mic energy before appending so
# speaker echo is less likely to trigger a false barge-in.
INPUT_BARGE_IN_PEAK = 5_000
COMMIT_RESPONSE_FALLBACK_S = 1.25
# If Qwen never emits speech_stopped (common when silence frames were dropped),
# force-commit after this much quiet / max speech duration.
# Backup only when server VAD never emits speech_stopped.
STUCK_SPEECH_SILENCE_S = 1.8
STUCK_SPEECH_MAX_S = 14.0
# Confirm barge-in briefly so short echo bursts do not cancel the reply.
BARGE_IN_CONFIRM_S = 0.55
BARGE_IN_MIN_MEANINGFUL_APPENDS = 5
# Qwen race errors that must not tear down the LiveKit AgentSession.
_RECOVERABLE_ERROR_SNIPPETS = (
    "no active response",
    "cannot create response while another response is in progress",
    "already has an active response",
)
SAY_MAX_CHARS = 4_096
WRITER_DRAIN_TIMEOUT = 1.0


class QwenSocket(Protocol):
    async def receive_text(self) -> str | None: ...

    async def send_json(self, event: Mapping[str, object]) -> None: ...

    async def close(self) -> None: ...


class QwenConnector(Protocol):
    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> QwenSocket: ...


class _AiohttpQwenSocket:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        socket: aiohttp.ClientWebSocketResponse,
    ) -> None:
        self._session = session
        self._socket = socket
        self._closed = False

    async def receive_text(self) -> str | None:
        message = await self._socket.receive()
        if message.type is aiohttp.WSMsgType.TEXT:
            return str(message.data)
        if message.type in {
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
        }:
            return None
        if message.type is aiohttp.WSMsgType.ERROR:
            raise llm.RealtimeError("Qwen realtime socket failed")
        return await self.receive_text()

    async def send_json(self, event: Mapping[str, object]) -> None:
        await self._socket.send_json(event)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._socket.close()
        await self._session.close()


class _AiohttpQwenConnector:
    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> QwenSocket:
        session = aiohttp.ClientSession()
        try:
            socket = await session.ws_connect(url, headers=headers)
        except Exception:
            await session.close()
            raise
        return _AiohttpQwenSocket(session, socket)


def _url_with_model(url: str, model: str) -> str:
    parsed = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "model"
    ]
    query.append(("model", model))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


@dataclass(slots=True)
class _MessageGeneration:
    text_ch: utils.aio.Chan[str]
    audio_ch: utils.aio.Chan[rtc.AudioFrame]
    modalities: asyncio.Future[list[Literal["text", "audio"]]]

    def close(self) -> None:
        if not self.text_ch.closed:
            self.text_ch.close()
        if not self.audio_ch.closed:
            self.audio_ch.close()
        if not self.modalities.done():
            self.modalities.set_result(["audio", "text"])


@dataclass(slots=True)
class _ResponseGeneration:
    message_ch: utils.aio.Chan[llm.MessageGeneration]
    function_ch: utils.aio.Chan[llm.FunctionCall]
    messages: dict[str, _MessageGeneration]

    def close(self) -> None:
        for message in self.messages.values():
            message.close()
        if not self.message_ch.closed:
            self.message_ch.close()
        if not self.function_ch.closed:
            self.function_ch.close()


@dataclass(slots=True)
class _WriterBarrier:
    done: asyncio.Future[None]


class QwenRealtimeModel(llm.RealtimeModel):
    def __init__(
        self,
        *,
        api_key: str,
        url: str,
        model: str,
        voice: str,
        instructions: str,
        connector: QwenConnector | None = None,
    ) -> None:
        super().__init__(
            capabilities=llm.RealtimeCapabilities(
                message_truncation=False,
                turn_detection=True,
                can_disable_turn_detection=True,
                user_transcription=True,
                auto_tool_reply_generation=False,
                audio_output=True,
                manual_function_calls=False,
                mutable_chat_context=False,
                mutable_instructions=True,
                mutable_tools=False,
                per_response_tool_choice=False,
                supports_say=True,
            )
        )
        self._api_key = api_key
        self._url = url
        self._model = model
        self._initial_session_options = QwenSessionOptions(
            instructions=instructions,
            voice=voice,
        )
        self._connector = connector or _AiohttpQwenConnector()
        self._sessions: weakref.WeakSet[QwenRealtimeSession] = weakref.WeakSet()

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "qwen"

    def session(self, *args: object, **kwargs: object) -> QwenRealtimeSession:
        # livekit-agents>=1.6 may pass turn_detection_disabled=...
        _ = args
        turn_detection_disabled = bool(kwargs.get("turn_detection_disabled", False))
        session = QwenRealtimeSession(
            self, turn_detection_disabled=turn_detection_disabled
        )
        self._sessions.add(session)
        return session

    async def _connect(self) -> QwenSocket:
        return await self._connector.connect(
            _url_with_model(self._url, self._model),
            {"Authorization": f"Bearer {self._api_key}"},
        )

    async def aclose(self) -> None:
        await asyncio.gather(
            *(session.aclose() for session in tuple(self._sessions)),
            return_exceptions=True,
        )


class QwenRealtimeSession(llm.RealtimeSession):
    def __init__(
        self,
        realtime_model: QwenRealtimeModel,
        *,
        turn_detection_disabled: bool = False,
    ) -> None:
        super().__init__(realtime_model)
        self._model = realtime_model
        self._chat_ctx = llm.ChatContext.empty()
        self._tools = llm.ToolContext.empty()
        session_options = realtime_model._initial_session_options
        self._instructions = session_options.instructions
        self._voice = session_options.voice
        self._turn_detection_disabled = turn_detection_disabled
        self._send_ch = utils.aio.Chan[Mapping[str, object] | _WriterBarrier]()
        self._socket_ready = asyncio.Event()
        self._socket: QwenSocket | None = None
        self._closed = False
        self._close_lock = asyncio.Lock()
        self._responses: dict[str, _ResponseGeneration] = {}
        self._active_response_id: str | None = None
        self._suppressed_response_ids: set[str] = set()
        self._cancel_pending_response = False
        self._input_resampler: rtc.AudioResampler | None = None
        self._input_resampler_rate: int | None = None
        self._input_audio_stream = utils.audio.AudioByteStream(
            INPUT_SAMPLE_RATE,
            NUM_CHANNELS,
            samples_per_channel=INPUT_SAMPLES_PER_CHUNK,
        )
        self._input_speech_active = False
        self._smart_turn_active = False
        self._smart_turn_response_id: str | None = None
        self._pending_generations: deque[
            asyncio.Future[llm.GenerationCreatedEvent]
        ] = deque()
        self._say_future: asyncio.Future[llm.GenerationCreatedEvent] | None = None
        self._say_response_id: str | None = None
        self._say_collection_task: asyncio.Task[None] | None = None
        self._audio_frames = 0
        self._audio_peak = 0
        self._audio_level_log_at = 0.0
        self._audio_append_events = 0
        self._manual_response_requested = False
        self._commit_fallback_task: asyncio.Task[None] | None = None
        self._stuck_speech_task: asyncio.Task[None] | None = None
        self._barge_in_task: asyncio.Task[None] | None = None
        self._speech_started_at = 0.0
        self._last_meaningful_audio_at = 0.0
        self._meaningful_appends_since_speech_start = 0
        # Drop uplink PCM until Qwen acknowledges the initial session.update.
        # Appending before that races the greeting and leaves garbage in the buffer.
        self._session_accepts_audio = False
        self._meaningful_appends_since_commit = 0

        self._send_ch.send_nowait(self._session_update_event())
        self._reader_task = asyncio.create_task(
            self._connection_reader(), name="QwenRealtimeSession.connection_reader"
        )
        self._writer_task = asyncio.create_task(
            self._serial_writer(), name="QwenRealtimeSession.serial_writer"
        )

    @property
    def chat_ctx(self) -> llm.ChatContext:
        return self._chat_ctx

    @property
    def tools(self) -> llm.ToolContext:
        return self._tools

    async def update_instructions(self, instructions: str) -> None:
        self._instructions = instructions
        if not self._say_in_progress:
            self._queue_event(
                build_instructions_update(
                    instructions,
                    turn_detection_disabled=self._turn_detection_disabled,
                )
            )

    async def update_chat_ctx(self, chat_ctx: llm.ChatContext) -> None:
        # livekit-agents may push chat_ctx on say()/start; Qwen realtime keeps
        # conversation state server-side, so accept and keep a local mirror only.
        self._chat_ctx = chat_ctx.copy() if hasattr(chat_ctx, "copy") else chat_ctx

    async def update_tools(self, tools: list[llm.Tool]) -> None:
        if tools:
            raise llm.RealtimeError("Qwen tools are not supported")

    def update_options(
        self,
        *,
        tool_choice: NotGivenOr[llm.ToolChoice | None] = NOT_GIVEN,
    ) -> None:
        if utils.is_given(tool_choice):
            raise llm.RealtimeError("Qwen per-response tool choice is not supported")

    def push_audio(self, frame: rtc.AudioFrame) -> None:
        if self._closed:
            raise llm.RealtimeError("Qwen realtime session is closed")
        mono_frame = self._to_mono(frame)
        self._observe_input_audio(mono_frame)
        if not self._session_accepts_audio:
            return
        # While the greeting (say) is in progress, do not feed the realtime
        # buffer — LiveKit already discards for uninterruptible speech; this
        # keeps Qwen's input buffer clean for the first real user turn.
        if self._say_in_progress:
            return
        if mono_frame.sample_rate == INPUT_SAMPLE_RATE:
            self._flush_resampler_to_input_stream()
            self._queue_input_frame(mono_frame)
            return

        if self._input_resampler_rate != mono_frame.sample_rate:
            self._flush_resampler_to_input_stream()
            self._input_resampler = rtc.AudioResampler(
                input_rate=mono_frame.sample_rate,
                output_rate=INPUT_SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
            )
            self._input_resampler_rate = mono_frame.sample_rate
        assert self._input_resampler is not None
        for resampled in self._input_resampler.push(mono_frame):
            self._queue_input_frame(resampled)

    def push_video(self, frame: rtc.VideoFrame) -> None:
        raise llm.RealtimeError("Qwen video input is not supported")

    def generate_reply(
        self,
        *,
        instructions: NotGivenOr[str] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        tools: NotGivenOr[list[llm.Tool]] = NOT_GIVEN,
    ) -> asyncio.Future[llm.GenerationCreatedEvent]:
        if any(utils.is_given(value) for value in (instructions, tool_choice, tools)):
            raise llm.RealtimeError("Qwen per-response options are not supported")
        future: asyncio.Future[llm.GenerationCreatedEvent] = (
            asyncio.get_running_loop().create_future()
        )
        if self._closed:
            future.set_exception(llm.RealtimeError("Qwen realtime session is closed"))
            return future

        # Manual (client VAD) mode: commit_audio already requested a reply.
        # Attach to that in-flight response instead of creating a duplicate.
        if self._turn_detection_disabled and self._manual_response_requested:
            if self._active_response_id is not None:
                future.set_exception(
                    llm.RealtimeError("Qwen response already started from commit")
                )
                return future
            self._pending_generations.append(future)
            logger.info("qwen generate_reply attached to commit response")
            return future

        self._pending_generations.append(future)
        self._queue_event(build_response_create())
        logger.info("qwen generate_reply sent response.create")
        return future

    def say(
        self, text: str | AsyncIterable[str]
    ) -> asyncio.Future[llm.GenerationCreatedEvent]:
        if isinstance(text, str) and not text:
            raise llm.RealtimeError("Qwen say requires non-empty text")
        if not isinstance(text, (str, AsyncIterable)):
            raise llm.RealtimeError("Qwen say requires text")
        if isinstance(text, str) and len(text) > SAY_MAX_CHARS:
            raise llm.RealtimeError("Qwen say text exceeds the safe limit")
        if (
            self._active_response_id is not None
            or self._pending_generations
            or self._say_in_progress
            or self._smart_turn_active
        ):
            raise llm.RealtimeError("Qwen generation or smart turn is already active")

        future: asyncio.Future[llm.GenerationCreatedEvent] = (
            asyncio.get_running_loop().create_future()
        )
        if self._closed:
            future.set_exception(llm.RealtimeError("Qwen realtime session is closed"))
            return future

        self._say_future = future
        if not isinstance(text, str):
            self._say_collection_task = asyncio.create_task(
                self._collect_say_text(text, future),
                name="QwenRealtimeSession.collect_say_text",
            )
            return future

        self._start_say_request(text, future)
        return future

    def _start_say_request(
        self,
        text: str,
        future: asyncio.Future[llm.GenerationCreatedEvent],
    ) -> None:
        self._pending_generations.append(future)
        temporary_instructions = (
            "Read only the specified text verbatim. Do not add, remove, explain, "
            f"or rewrite it.\nSpecified text: {text}"
        )
        self._queue_event(
            build_instructions_update(
                temporary_instructions,
                turn_detection_disabled=self._turn_detection_disabled,
            )
        )
        self._queue_event(
            build_user_text_item(
                "请立即执行当前会话指令,并且只输出指定内容。"
            )
        )
        self._queue_event(build_response_create())

    async def _collect_say_text(
        self,
        text: AsyncIterable[str],
        future: asyncio.Future[llm.GenerationCreatedEvent],
    ) -> None:
        completed = False
        parts: list[str] = []
        char_count = 0
        try:
            async for part in text:
                if future.cancelled():
                    return
                if not isinstance(part, str):
                    self._fail_say_future(future, "Qwen say text stream is invalid")
                    return
                char_count += len(part)
                if char_count > SAY_MAX_CHARS:
                    self._fail_say_future(
                        future, "Qwen say text exceeds the safe limit"
                    )
                    return
                parts.append(part)

            if future.cancelled():
                return
            collected = "".join(parts)
            if not collected:
                self._fail_say_future(future, "Qwen say requires non-empty text")
                return
            if self._closed:
                self._fail_say_future(future, "Qwen realtime session is closed")
                return
            if (
                self._active_response_id is not None
                or self._pending_generations
                or self._smart_turn_active
            ):
                self._fail_say_future(
                    future, "Qwen generation or smart turn is already active"
                )
                return
            self._start_say_request(collected, future)
            completed = True
        except asyncio.CancelledError:
            if not future.done():
                future.set_exception(
                    llm.RealtimeError("Qwen realtime session is closed")
                )
            raise
        except Exception:
            self._fail_say_future(future, "Qwen say text stream failed")
        finally:
            if self._say_collection_task is asyncio.current_task():
                self._say_collection_task = None
            if not completed and self._say_future is future:
                self._say_future = None

    @staticmethod
    def _fail_say_future(
        future: asyncio.Future[llm.GenerationCreatedEvent], message: str
    ) -> None:
        if not future.done():
            future.set_exception(llm.RealtimeError(message))

    def commit_audio(self) -> None:
        if self._closed:
            return
        self._release_input_audio(send_complete_chunks=True)
        if (
            self._turn_detection_disabled
            and self._meaningful_appends_since_commit <= 0
        ):
            logger.info(
                "qwen skip commit: no meaningful audio since last turn "
                "appends=%s",
                self._audio_append_events,
            )
            return
        self._queue_event(build_audio_commit())
        logger.info(
            "qwen input audio commit appends=%s meaningful=%s speech_active=%s",
            self._audio_append_events,
            self._meaningful_appends_since_commit,
            self._input_speech_active,
        )
        self._meaningful_appends_since_commit = 0
        # Push-to-talk: wait for input_audio_buffer.committed before response.create.
        # Sending both back-to-back can leave Qwen without a committed item.
        if (
            self._turn_detection_disabled
            and not self._say_in_progress
            and self._active_response_id is None
        ):
            self._manual_response_requested = True
            logger.info("qwen waiting for buffer committed before response.create")
            self._arm_commit_response_fallback()

    def _arm_commit_response_fallback(self) -> None:
        if self._commit_fallback_task is not None and not self._commit_fallback_task.done():
            self._commit_fallback_task.cancel()

        async def _fallback() -> None:
            try:
                await asyncio.sleep(COMMIT_RESPONSE_FALLBACK_S)
            except asyncio.CancelledError:
                return
            if (
                self._closed
                or not self._manual_response_requested
                or self._active_response_id is not None
                or self._say_in_progress
            ):
                return
            logger.warning(
                "qwen buffer committed timed out; sending response.create fallback"
            )
            self._queue_event(build_response_create())

        self._commit_fallback_task = asyncio.create_task(
            _fallback(), name="QwenRealtimeSession.commit_fallback"
        )

    def _cancel_commit_response_fallback(self) -> None:
        task = self._commit_fallback_task
        self._commit_fallback_task = None
        if task is not None and not task.done():
            task.cancel()

    def _cancel_stuck_speech_watchdog(self) -> None:
        task = self._stuck_speech_task
        self._stuck_speech_task = None
        if task is not None and not task.done():
            task.cancel()

    def _cancel_barge_in_confirm(self) -> None:
        task = self._barge_in_task
        self._barge_in_task = None
        if task is not None and not task.done():
            task.cancel()

    def _arm_stuck_speech_watchdog(self) -> None:
        self._cancel_stuck_speech_watchdog()

        async def _watch() -> None:
            try:
                while not self._closed and self._input_speech_active:
                    await asyncio.sleep(0.25)
                    now = time.monotonic()
                    idle = now - self._last_meaningful_audio_at
                    total = now - self._speech_started_at
                    if idle < STUCK_SPEECH_SILENCE_S and total < STUCK_SPEECH_MAX_S:
                        continue
                    logger.warning(
                        "qwen stuck speech watchdog forcing commit "
                        "idle=%.2fs total=%.2fs appends=%s meaningful=%s",
                        idle,
                        total,
                        self._audio_append_events,
                        self._meaningful_appends_since_commit,
                    )
                    self._force_end_speech_turn()
                    return
            except asyncio.CancelledError:
                return

        self._stuck_speech_task = asyncio.create_task(
            _watch(), name="QwenRealtimeSession.stuck_speech"
        )

    def _arm_barge_in_confirm(self) -> None:
        self._cancel_barge_in_confirm()
        started_at = self._speech_started_at
        baseline = self._meaningful_appends_since_speech_start

        async def _confirm() -> None:
            try:
                await asyncio.sleep(BARGE_IN_CONFIRM_S)
            except asyncio.CancelledError:
                return
            if (
                self._closed
                or not self._input_speech_active
                or self._speech_started_at != started_at
            ):
                return
            gained = self._meaningful_appends_since_speech_start - baseline
            if gained < BARGE_IN_MIN_MEANINGFUL_APPENDS:
                logger.info(
                    "qwen barge-in ignored (likely echo) gained=%s",
                    gained,
                )
                return
            logger.info("qwen barge-in confirmed gained=%s", gained)
            self.interrupt()

        self._barge_in_task = asyncio.create_task(
            _confirm(), name="QwenRealtimeSession.barge_in_confirm"
        )

    def _force_end_speech_turn(self) -> None:
        if self._closed or not self._input_speech_active:
            return
        self._cancel_stuck_speech_watchdog()
        self._cancel_barge_in_confirm()
        self._input_speech_active = False
        self.emit(
            "input_speech_stopped",
            llm.InputSpeechStoppedEvent(user_transcription_enabled=True),
        )
        if self._meaningful_appends_since_commit <= 0 and self._audio_append_events <= 0:
            self._smart_turn_active = False
            self._smart_turn_response_id = None
            return
        self._release_input_audio(send_complete_chunks=True)
        self._queue_event(build_audio_commit())
        logger.info(
            "qwen forced input audio commit appends=%s meaningful=%s",
            self._audio_append_events,
            self._meaningful_appends_since_commit,
        )
        self._meaningful_appends_since_commit = 0
        # server_vad auto-creates a response after commit; a second response.create
        # races and kills the session with "another response is in progress".
        if (
            self._turn_detection_disabled
            and self._active_response_id is None
            and not self._say_in_progress
            and not self._manual_response_requested
        ):
            self._manual_response_requested = True
            self._arm_commit_response_fallback()

    def clear_audio(self) -> None:
        if self._closed:
            return
        # Keep local buffers empty. Do not send input_audio_buffer.clear — some
        # Qwen gateways reject that event and would tear down the session.
        self._release_input_audio(send_complete_chunks=False)

    def interrupt(self) -> None:
        response_id = self._active_response_id
        if response_id is None:
            # Client-VAD commit has already requested a reply; do not mark it for
            # cancellation while overlapping mic noise retriggers interrupt().
            if self._manual_response_requested:
                return
            if any(not future.done() for future in self._pending_generations):
                self._cancel_pending_response = True
            return
        if response_id in self._suppressed_response_ids:
            return
        # Response may already be finishing; cancel is best-effort and must not
        # become a fatal "no active response" teardown.
        self._suppressed_response_ids.add(response_id)
        self._queue_event(build_response_cancel())

    def truncate(
        self,
        *,
        message_id: str,
        modalities: list[Literal["text", "audio"]],
        audio_end_ms: int,
        audio_transcript: NotGivenOr[str] = NOT_GIVEN,
    ) -> None:
        raise llm.RealtimeError("Qwen message truncation is not supported")

    async def aclose(self) -> None:
        async with self._close_lock:
            say_collection_task = self._say_collection_task
            self._cancel_commit_response_fallback()
            self._cancel_stuck_speech_watchdog()
            self._cancel_barge_in_confirm()
            if not self._closed:
                self._release_input_audio(send_complete_chunks=True)
                await self._drain_writer()
            self._terminate(
                "Qwen realtime session closed", release_input_audio=False
            )
            tasks = [self._reader_task, self._writer_task]
            if say_collection_task is not None:
                tasks.append(say_collection_task)
            await asyncio.gather(*tasks, return_exceptions=True)
            if self._socket is not None:
                await self._socket.close()
                self._socket = None

    def _session_update_event(self) -> dict[str, object]:
        return build_session_update(
            QwenSessionOptions(
                instructions=self._instructions,
                voice=self._voice,
                turn_detection_disabled=self._turn_detection_disabled,
            )
        )

    @property
    def _say_in_progress(self) -> bool:
        return self._say_future is not None or self._say_response_id is not None

    @staticmethod
    def _to_mono(frame: rtc.AudioFrame) -> rtc.AudioFrame:
        if frame.num_channels == NUM_CHANNELS:
            return frame
        samples = frame.data
        mono = array("h")
        for offset in range(0, len(samples), frame.num_channels):
            total = sum(samples[offset : offset + frame.num_channels])
            mono.append(int(total / frame.num_channels))
        return rtc.AudioFrame(
            data=mono.tobytes(),
            sample_rate=frame.sample_rate,
            num_channels=NUM_CHANNELS,
            samples_per_channel=frame.samples_per_channel,
        )

    def _observe_input_audio(self, frame: rtc.AudioFrame) -> None:
        samples = frame.data
        if not samples:
            return
        peak = 0
        for sample in samples:
            value = sample if sample >= 0 else -sample
            if value > peak:
                peak = value
        self._audio_frames += 1
        if peak > self._audio_peak:
            self._audio_peak = peak
        now = time.monotonic()
        if now - self._audio_level_log_at < 1.0:
            return
        self._audio_level_log_at = now
        logger.info(
            "qwen input audio level frames=%s peak=%s appends=%s speech_active=%s",
            self._audio_frames,
            self._audio_peak,
            self._audio_append_events,
            self._input_speech_active,
        )
        self._audio_frames = 0
        self._audio_peak = 0

    def _frame_peak(self, frame: rtc.AudioFrame) -> int:
        peak = 0
        for sample in frame.data:
            value = sample if sample >= 0 else -sample
            if value > peak:
                peak = value
        return peak

    @staticmethod
    def _pcm_peak(pcm: bytes) -> int:
        if len(pcm) < 2:
            return 0
        samples = memoryview(pcm).cast("h")
        peak = 0
        for sample in samples:
            value = sample if sample >= 0 else -sample
            if value > peak:
                peak = value
        return peak

    def _input_min_peak(self) -> int:
        # After speech starts, always forward frames (including near-silence) so
        # server VAD can observe end-of-utterance. Filtering silence here was
        # leaving speech_active=True forever with no commit/reply.
        if self._input_speech_active:
            return 0
        if self._active_response_id is not None or self._say_in_progress:
            return INPUT_BARGE_IN_PEAK
        return INPUT_MIN_PEAK

    def _queue_input_frame(self, frame: rtc.AudioFrame) -> None:
        peak = self._frame_peak(frame)
        if peak < self._input_min_peak():
            return
        meaningful = peak >= INPUT_MIN_PEAK
        for chunk in self._input_audio_stream.write(frame.data.tobytes()):
            self._audio_append_events += 1
            if meaningful:
                self._meaningful_appends_since_commit += 1
                self._meaningful_appends_since_speech_start += 1
                self._last_meaningful_audio_at = time.monotonic()
            self._queue_event(build_audio_append(chunk.data.tobytes()))

    def _flush_resampler_to_input_stream(self) -> None:
        if self._input_resampler is None:
            return
        for frame in self._input_resampler.flush():
            self._queue_input_frame(frame)
        self._input_resampler = None
        self._input_resampler_rate = None

    def _release_input_audio(self, *, send_complete_chunks: bool) -> None:
        if self._input_resampler is not None:
            flushed = self._input_resampler.flush()
            if send_complete_chunks:
                for frame in flushed:
                    self._queue_input_frame(frame)
            self._input_resampler = None
            self._input_resampler_rate = None
        remainder = self._input_audio_stream.flush()
        if send_complete_chunks:
            min_peak = self._input_min_peak()
            for frame in remainder:
                pcm = frame.data.tobytes()
                peak = self._pcm_peak(pcm)
                if peak < min_peak:
                    continue
                self._audio_append_events += 1
                if peak >= INPUT_MIN_PEAK:
                    self._meaningful_appends_since_commit += 1
                    self._meaningful_appends_since_speech_start += 1
                    self._last_meaningful_audio_at = time.monotonic()
                self._queue_event(build_audio_append(pcm))
        self._input_audio_stream = utils.audio.AudioByteStream(
            INPUT_SAMPLE_RATE,
            NUM_CHANNELS,
            samples_per_channel=INPUT_SAMPLES_PER_CHUNK,
        )

    async def _drain_writer(self) -> None:
        if self._writer_task.done():
            return
        barrier = asyncio.get_running_loop().create_future()
        self._send_ch.send_nowait(_WriterBarrier(done=barrier))
        done, _ = await asyncio.wait(
            (barrier, self._writer_task),
            timeout=WRITER_DRAIN_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if barrier not in done and not barrier.done():
            barrier.cancel()

    def _queue_event(self, event: Mapping[str, object]) -> None:
        if self._closed:
            raise llm.RealtimeError("Qwen realtime session is closed")
        self._send_ch.send_nowait(event)

    async def _connection_reader(self) -> None:
        try:
            self._socket = await self._model._connect()
            self._socket_ready.set()
            while not self._closed:
                raw = await self._socket.receive_text()
                if raw is None:
                    return
                try:
                    event = parse_server_event(raw)
                    self._handle_server_event(event)
                except QwenProtocolError:
                    self._emit_model_error("invalid Qwen realtime server event")
        except asyncio.CancelledError:
            raise
        except Exception:
            self._emit_model_error("Qwen realtime connection failed")
        finally:
            self._socket_ready.set()
            self._terminate("Qwen realtime connection closed")
            if self._socket is not None:
                await self._socket.close()
                self._socket = None

    async def _serial_writer(self) -> None:
        try:
            await self._socket_ready.wait()
            if self._socket is None:
                return
            async for event in self._send_ch:
                if isinstance(event, _WriterBarrier):
                    if not event.done.done():
                        event.done.set_result(None)
                    continue
                event_type = event.get("type")
                if event_type and event_type != "input_audio_buffer.append":
                    logger.info("qwen outbound event type=%s", event_type)
                await self._socket.send_json(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._emit_model_error("Qwen realtime writer failed")
            self._terminate("Qwen realtime writer closed")

    def _emit_model_error(self, message: str) -> None:
        self.emit(
            "error",
            llm.RealtimeModelError(
                timestamp=time.time(),
                label=self._model.label,
                error=llm.RealtimeError(message),
                recoverable=False,
            ),
        )

    def _handle_server_event(self, event: Mapping[str, object]) -> None:
        event_type = event["type"]
        if event_type == "response.created":
            self._handle_response_created(event)
        elif event_type == "response.output_item.added":
            self._handle_output_item_added(event)
        elif event_type == "response.content_part.added":
            self._handle_content_part_added(event)
        elif event_type == "response.audio_transcript.delta":
            self._handle_audio_transcript_delta(event)
        elif event_type == "response.audio.delta":
            self._handle_audio_delta(event)
        elif event_type == "response.output_item.done":
            self._handle_output_item_done(event)
        elif event_type == "response.done":
            self._handle_response_done(event)
        elif event_type == "input_audio_buffer.speech_started":
            self._handle_input_speech_started()
        elif event_type == "input_audio_buffer.speech_stopped":
            self._handle_input_speech_stopped(event)
        elif event_type == "input_audio_buffer.committed":
            logger.info("qwen input audio buffer committed")
            self._cancel_commit_response_fallback()
            if (
                self._turn_detection_disabled
                and self._manual_response_requested
                and self._active_response_id is None
                and not self._say_in_progress
            ):
                self._queue_event(build_response_create())
                logger.info("qwen response.create after buffer committed")
        elif event_type == "conversation.item.input_audio_transcription.delta":
            self._handle_input_transcription_delta(event)
        elif event_type == "conversation.item.input_audio_transcription.completed":
            self._handle_input_transcription_completed(event)
        elif event_type == "error":
            self._handle_server_error(event)
        elif event_type == "session.updated":
            if not self._session_accepts_audio:
                self._session_accepts_audio = True
                logger.info("qwen session ready; accepting input audio")
        else:
            logger.debug("qwen realtime unhandled event type=%s", event_type)

    @staticmethod
    def _error_message(error: object) -> str:
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str):
                return message
        return ""

    def _is_recoverable_server_error(self, error: object) -> bool:
        message = self._error_message(error).lower()
        if not message:
            return False
        return any(snippet in message for snippet in _RECOVERABLE_ERROR_SNIPPETS)

    def _handle_server_error(self, event: Mapping[str, object]) -> None:
        error = event.get("error")
        if self._is_recoverable_server_error(error):
            message = self._error_message(error)
            logger.warning(
                "qwen recoverable realtime error (session kept alive) message=%s",
                message,
            )
            lowered = message.lower()
            if "no active response" in lowered:
                self._cancel_pending_response = False
            if "another response is in progress" in lowered or "already has an active response" in lowered:
                self._manual_response_requested = False
                self._cancel_commit_response_fallback()
            return
        logger.error("qwen realtime server error event=%s", dict(event))
        self._emit_model_error("Qwen realtime server error")
        self._terminate("Qwen realtime server error")

    def _handle_input_speech_started(self) -> None:
        if self._input_speech_active:
            return
        logger.info("qwen input speech started")
        self._input_speech_active = True
        self._smart_turn_active = True
        self._smart_turn_response_id = None
        now = time.monotonic()
        self._speech_started_at = now
        self._last_meaningful_audio_at = now
        self._meaningful_appends_since_speech_start = 0
        self._arm_stuck_speech_watchdog()
        # Debounce cancel while assistant audio is playing — speaker echo often
        # fires speech_started and would otherwise cancel mid-reply.
        if self._active_response_id is not None:
            self._arm_barge_in_confirm()
        else:
            self.interrupt()
        self.emit("input_speech_started", llm.InputSpeechStartedEvent())

    def _handle_input_speech_stopped(self, event: Mapping[str, object]) -> None:
        self._cancel_stuck_speech_watchdog()
        self._cancel_barge_in_confirm()
        self._input_speech_active = False
        if event.get("reason") == "turn_invalid":
            self._smart_turn_active = False
            self._smart_turn_response_id = None
            return
        self.emit(
            "input_speech_stopped",
            llm.InputSpeechStoppedEvent(user_transcription_enabled=True),
        )

    def _handle_input_transcription_delta(
        self, event: Mapping[str, object]
    ) -> None:
        item_id = event.get("item_id")
        if not isinstance(item_id, str):
            return
        text = event.get("text")
        stash = event.get("stash")
        transcript = (text if isinstance(text, str) else "") + (
            stash if isinstance(stash, str) else ""
        )
        if not transcript:
            return
        self.emit(
            "input_audio_transcription_completed",
            llm.InputTranscriptionCompleted(
                item_id=item_id,
                transcript=transcript,
                is_final=False,
            ),
        )

    def _handle_input_transcription_completed(
        self, event: Mapping[str, object]
    ) -> None:
        item_id = event.get("item_id")
        transcript = event.get("transcript")
        if not isinstance(item_id, str) or not isinstance(transcript, str):
            return
        self.emit(
            "input_audio_transcription_completed",
            llm.InputTranscriptionCompleted(
                item_id=item_id,
                transcript=transcript,
                is_final=True,
            ),
        )
        logger.info("qwen user transcript final chars=%s", len(transcript))

    def _handle_response_created(self, event: Mapping[str, object]) -> None:
        response = event.get("response")
        if not isinstance(response, Mapping):
            raise QwenProtocolError("invalid Qwen response.created event")
        response_id = response.get("id")
        if not isinstance(response_id, str):
            raise QwenProtocolError("invalid Qwen response.created event")

        self._manual_response_requested = False
        generation = _ResponseGeneration(
            message_ch=utils.aio.Chan(),
            function_ch=utils.aio.Chan(),
            messages={},
        )
        previous = self._responses.pop(response_id, None)
        if previous is not None:
            previous.close()
        self._responses[response_id] = generation
        self._active_response_id = response_id
        if self._cancel_pending_response:
            self._cancel_pending_response = False
            self._suppressed_response_ids.add(response_id)
            self._queue_event(build_response_cancel())
        created = llm.GenerationCreatedEvent(
            message_stream=generation.message_ch,
            function_stream=generation.function_ch,
            user_initiated=False,
            response_id=response_id,
        )
        while self._pending_generations:
            future = self._pending_generations.popleft()
            if future.done():
                if future is self._say_future:
                    self._say_response_id = response_id
                    created.user_initiated = True
                    break
                continue
            created.user_initiated = True
            future.set_result(created)
            if future is self._say_future:
                self._say_response_id = response_id
            break
        if (
            self._smart_turn_active
            and not created.user_initiated
            and response_id not in self._suppressed_response_ids
        ):
            self._smart_turn_response_id = response_id
        logger.info(
            "qwen response.created id=%s user_initiated=%s",
            response_id,
            created.user_initiated,
        )
        self.emit("generation_created", created)

    def _handle_output_item_added(self, event: Mapping[str, object]) -> None:
        generation = self._generation_for(event)
        item = event.get("item")
        if generation is None or not isinstance(item, Mapping):
            return
        message_id = item.get("id")
        if item.get("type") != "message" or not isinstance(message_id, str):
            return
        message = _MessageGeneration(
            text_ch=utils.aio.Chan(),
            audio_ch=utils.aio.Chan(),
            modalities=asyncio.get_running_loop().create_future(),
        )
        generation.messages[message_id] = message
        generation.message_ch.send_nowait(
            llm.MessageGeneration(
                message_id=message_id,
                text_stream=message.text_ch,
                audio_stream=message.audio_ch,
                modalities=message.modalities,
            )
        )

    def _handle_content_part_added(self, event: Mapping[str, object]) -> None:
        message = self._message_for(event)
        part = event.get("part")
        if (
            message is None
            or not isinstance(part, Mapping)
            or message.modalities.done()
        ):
            return
        if part.get("type") == "audio":
            message.modalities.set_result(["audio", "text"])
        elif part.get("type") == "text":
            message.modalities.set_result(["text"])

    def _handle_audio_transcript_delta(self, event: Mapping[str, object]) -> None:
        if self._is_response_suppressed(event):
            return
        message = self._message_for(event)
        delta = event.get("delta")
        if message is None or not isinstance(delta, str):
            return
        message.text_ch.send_nowait(delta)

    def _handle_audio_delta(self, event: Mapping[str, object]) -> None:
        if self._is_response_suppressed(event):
            return
        message = self._message_for(event)
        if message is None:
            return
        pcm = decode_audio_delta(event)
        if not message.modalities.done():
            message.modalities.set_result(["audio", "text"])
        message.audio_ch.send_nowait(
            rtc.AudioFrame(
                data=pcm,
                sample_rate=OUTPUT_SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=len(pcm) // 2,
            )
        )

    def _handle_output_item_done(self, event: Mapping[str, object]) -> None:
        generation = self._generation_for(event)
        item = event.get("item")
        if generation is None or not isinstance(item, Mapping):
            return
        message_id = item.get("id")
        if item.get("type") == "message" and isinstance(message_id, str):
            message = generation.messages.get(message_id)
            if message is not None:
                message.close()

    def _handle_response_done(self, event: Mapping[str, object]) -> None:
        response = event.get("response")
        response_id = response.get("id") if isinstance(response, Mapping) else None
        if not isinstance(response_id, str):
            response_id = self._active_response_id
        if response_id is None:
            return
        generation = self._responses.pop(response_id, None)
        if generation is not None:
            generation.close()
        if self._active_response_id == response_id:
            self._active_response_id = None
        is_say_response = self._say_response_id == response_id
        if is_say_response:
            self._say_response_id = None
            self._say_future = None
            self.clear_audio()
            self._audio_append_events = 0
            self._meaningful_appends_since_commit = 0
            self._queue_event(
                build_instructions_update(
                    self._instructions,
                    turn_detection_disabled=self._turn_detection_disabled,
                )
            )
            logger.info("qwen greeting finished; audio buffer cleared")
        elif self._smart_turn_response_id == response_id:
            self._smart_turn_active = False
            self._smart_turn_response_id = None
        self._suppressed_response_ids.discard(response_id)

    def _generation_for(
        self, event: Mapping[str, object]
    ) -> _ResponseGeneration | None:
        response_id = event.get("response_id")
        if not isinstance(response_id, str):
            response_id = self._active_response_id
        return self._responses.get(response_id) if response_id is not None else None

    def _message_for(self, event: Mapping[str, object]) -> _MessageGeneration | None:
        generation = self._generation_for(event)
        message_id = event.get("item_id")
        if generation is None or not isinstance(message_id, str):
            return None
        return generation.messages.get(message_id)

    def _is_response_suppressed(self, event: Mapping[str, object]) -> bool:
        response_id = event.get("response_id")
        return (
            isinstance(response_id, str)
            and response_id in self._suppressed_response_ids
        )

    def _terminate(
        self, reason: str, *, release_input_audio: bool = True
    ) -> None:
        if self._closed:
            return
        if release_input_audio:
            self._release_input_audio(send_complete_chunks=False)
        self._closed = True
        self._cancel_stuck_speech_watchdog()
        self._cancel_barge_in_confirm()
        self._close_generations(reason)
        self._send_ch.close()
        current_task = asyncio.current_task()
        for task in (
            self._reader_task,
            self._writer_task,
            self._say_collection_task,
        ):
            if task is None:
                continue
            if task is not current_task:
                task.cancel()

    def _close_generations(self, reason: str) -> None:
        for generation in self._responses.values():
            generation.close()
        self._responses.clear()
        self._active_response_id = None
        self._input_speech_active = False
        self._smart_turn_active = False
        self._smart_turn_response_id = None
        self._cancel_pending_response = False
        self._suppressed_response_ids.clear()
        self._meaningful_appends_since_speech_start = 0
        while self._pending_generations:
            future = self._pending_generations.popleft()
            if not future.done():
                future.set_exception(llm.RealtimeError(reason))
        if self._say_future is not None and not self._say_future.done():
            self._say_future.set_exception(llm.RealtimeError(reason))
        self._say_future = None
        self._say_response_id = None
        self._manual_response_requested = False
