from __future__ import annotations

import asyncio
import base64
import json
from array import array
from collections.abc import Mapping

import pytest
from livekit import rtc
from livekit.agents import llm

from yino_voice_agent.qwen_realtime import QwenRealtimeModel, QwenRealtimeSession


class FakeQwenSocket:
    def __init__(self) -> None:
        self.server_events: asyncio.Queue[str | None] = asyncio.Queue()
        self.sent: list[Mapping[str, object]] = []
        self.close_calls = 0

    async def push(self, event: Mapping[str, object]) -> None:
        await self.server_events.put(json.dumps(event))

    async def receive_text(self) -> str | None:
        return await self.server_events.get()

    async def end(self) -> None:
        await self.server_events.put(None)

    async def send_json(self, event: Mapping[str, object]) -> None:
        self.sent.append(event)

    async def close(self) -> None:
        self.close_calls += 1
        if self.close_calls == 1:
            await self.server_events.put(None)

    def events(self, event_type: str) -> list[Mapping[str, object]]:
        return [event for event in self.sent if event.get("type") == event_type]

    async def wait_for_event_count(
        self, event_type: str, count: int, timeout: float = 0.2
    ) -> list[Mapping[str, object]]:
        async def find_events() -> list[Mapping[str, object]]:
            while len(events := self.events(event_type)) < count:
                await asyncio.sleep(0)
            return events

        return await asyncio.wait_for(find_events(), timeout)


class FakeQwenConnector:
    def __init__(self, socket: FakeQwenSocket) -> None:
        self.socket = socket
        self.connected = asyncio.Event()

    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> FakeQwenSocket:
        self.connected.set()
        return self.socket


async def connected_session(
    socket: FakeQwenSocket,
) -> tuple[QwenRealtimeModel, QwenRealtimeSession]:
    connector = FakeQwenConnector(socket)
    model = QwenRealtimeModel(
        api_key="",
        url="",
        model="qwen-audio-3.0-realtime-plus",
        voice="longanqian",
        instructions="使用标准普通话自然回答。",
        connector=connector,
    )
    session = model.session()
    await asyncio.wait_for(connector.connected.wait(), timeout=0.2)
    await socket.wait_for_event_count("session.update", 1)
    await socket.push({"type": "session.updated", "session": {}})

    async def _session_ready() -> None:
        while not session._session_accepts_audio:
            await asyncio.sleep(0)

    await asyncio.wait_for(_session_ready(), timeout=0.2)
    return model, session


async def wait_for_length(items: list[object], count: int) -> None:
    async def enough_items() -> None:
        while len(items) < count:
            await asyncio.sleep(0)

    await asyncio.wait_for(enough_items(), timeout=0.2)


def response_created(response_id: str) -> dict[str, object]:
    return {"type": "response.created", "response": {"id": response_id}}


def message_added(response_id: str, message_id: str) -> dict[str, object]:
    return {
        "type": "response.output_item.added",
        "response_id": response_id,
        "item": {"id": message_id, "type": "message"},
    }


def audio_delta(
    response_id: str, message_id: str, pcm: bytes
) -> dict[str, object]:
    return {
        "type": "response.audio.delta",
        "response_id": response_id,
        "item_id": message_id,
        "delta": base64.b64encode(pcm).decode("ascii"),
    }


async def active_message(
    socket: FakeQwenSocket, session: QwenRealtimeSession
) -> llm.MessageGeneration:
    generations: list[llm.GenerationCreatedEvent] = []
    session.on("generation_created", generations.append)
    await socket.push(response_created("resp-old"))
    await socket.push(message_added("resp-old", "msg-old"))
    await wait_for_length(generations, 1)
    return await asyncio.wait_for(
        anext(generations[0].message_stream), timeout=0.2
    )


@pytest.mark.asyncio
async def test_push_audio_resamples_stereo_to_16k_mono_40ms_chunks() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    stereo_pcm = array("h", [1000, 1000] * 1_920).tobytes()
    frame = rtc.AudioFrame(
        data=stereo_pcm,
        sample_rate=48_000,
        num_channels=2,
        samples_per_channel=1_920,
    )

    session.push_audio(frame)
    session.push_audio(frame)
    await socket.wait_for_event_count("input_audio_buffer.append", 1)
    await session.aclose()
    appends = socket.events("input_audio_buffer.append")

    assert len(appends) == 2
    for event in appends:
        pcm = base64.b64decode(event["audio"])
        assert len(pcm) == 1_280
        assert max(abs(sample) for sample in array("h", pcm)) >= 100
    assert not socket.events("input_audio_buffer.commit")
    assert not socket.events("response.create")

    await model.aclose()


@pytest.mark.asyncio
async def test_user_transcript_combines_text_and_stash_then_finalizes() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    transcripts: list[llm.InputTranscriptionCompleted] = []
    session.on("input_audio_transcription_completed", transcripts.append)

    await socket.push(
        {
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "user-1",
            "content_index": 0,
            "text": "我想预约",
            "stash": "洗",
        }
    )
    await socket.push(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "user-1",
            "content_index": 0,
            "transcript": "我想预约洗牙",
        }
    )
    await wait_for_length(transcripts, 2)

    assert [
        (item.item_id, item.transcript, item.is_final) for item in transcripts
    ] == [
        ("user-1", "我想预约洗", False),
        ("user-1", "我想预约洗牙", True),
    ]

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_speech_started_cancels_once_and_discards_late_old_output() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    message = await active_message(socket, session)
    starts: list[llm.InputSpeechStartedEvent] = []
    session.on("input_speech_started", starts.append)

    await socket.push({"type": "input_audio_buffer.speech_started"})
    await wait_for_length(starts, 1)
    await socket.push({"type": "input_audio_buffer.speech_started"})
    # Wait until speech_started has reset the counter, then inject sustained
    # energy so barge-in debounce can confirm against the captured baseline.
    session._meaningful_appends_since_speech_start = 5
    await asyncio.sleep(0.65)
    await socket.wait_for_event_count("response.cancel", 1)
    await wait_for_length(starts, 1)
    await socket.push(audio_delta("resp-old", "msg-old", b"\x02\x00" * 240))
    await socket.push(
        {
            "type": "response.audio_transcript.delta",
            "response_id": "resp-old",
            "item_id": "msg-old",
            "delta": "late text",
        }
    )
    await asyncio.sleep(0)

    assert len(socket.events("response.cancel")) == 1
    assert len(starts) == 1
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(message.audio_stream), timeout=0.05)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(message.text_stream), timeout=0.05)

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_speech_started_cancels_response_created_after_pending_greeting() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    greeting = session.say("欢迎致电。")
    await socket.wait_for_event_count("response.create", 1)

    await socket.push({"type": "input_audio_buffer.speech_started"})
    await socket.push(response_created("resp-late-greeting"))
    await socket.wait_for_event_count("response.cancel", 1)
    generation = await asyncio.wait_for(greeting, timeout=0.2)

    assert generation.response_id == "resp-late-greeting"
    await socket.push(
        {"type": "response.done", "response": {"id": "resp-late-greeting"}}
    )
    await socket.wait_for_event_count("session.update", 3)
    await asyncio.sleep(0)
    assert "resp-late-greeting" not in session._suppressed_response_ids

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_stuck_speech_watchdog_force_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "yino_voice_agent.qwen_realtime.STUCK_SPEECH_SILENCE_S", 0.2
    )
    monkeypatch.setattr(
        "yino_voice_agent.qwen_realtime.STUCK_SPEECH_MAX_S", 1.0
    )
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    stops: list[llm.InputSpeechStoppedEvent] = []
    session.on("input_speech_stopped", stops.append)

    await socket.push({"type": "session.updated", "session": {}})
    await socket.push({"type": "input_audio_buffer.speech_started"})
    session._audio_append_events = 4
    session._meaningful_appends_since_commit = 4
    session._last_meaningful_audio_at = 0.0

    await socket.wait_for_event_count("input_audio_buffer.commit", 1, timeout=1.0)
    await wait_for_length(stops, 1)
    assert session._input_speech_active is False

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_speech_stopped_ignores_turn_invalid_and_emits_valid_stop() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    stops: list[llm.InputSpeechStoppedEvent] = []
    session.on("input_speech_stopped", stops.append)

    await socket.push(
        {"type": "input_audio_buffer.speech_stopped", "reason": "turn_invalid"}
    )
    await socket.push(
        {"type": "input_audio_buffer.speech_stopped", "reason": "natural"}
    )
    await wait_for_length(stops, 1)
    await asyncio.sleep(0)

    assert len(stops) == 1
    assert stops[0].user_transcription_enabled is True

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_ambient_transcript_is_ignored() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    transcripts: list[llm.InputTranscriptionCompleted] = []
    session.on("input_audio_transcription_completed", transcripts.append)

    await socket.push(
        {
            "type": "conversation.item.ambient_audio_transcription.delta",
            "item_id": "ambient-1",
            "text": "空调声",
            "stash": "",
        }
    )
    await socket.push(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "user-1",
            "transcript": "您好",
        }
    )
    await wait_for_length(transcripts, 1)
    await asyncio.sleep(0)

    assert [(item.item_id, item.transcript) for item in transcripts] == [
        ("user-1", "您好")
    ]

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_say_reads_exact_text_then_restores_normal_instructions() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    generation_future = session.say("欢迎致电颐诺口腔。")
    updates = await socket.wait_for_event_count("session.update", 2)
    items = await socket.wait_for_event_count("conversation.item.create", 1)
    await socket.wait_for_event_count("response.create", 1)
    temporary = updates[-1]["session"]
    assert isinstance(temporary, Mapping)
    assert "欢迎致电颐诺口腔。" in temporary["instructions"]
    assert set(temporary) == {"instructions"}
    item = items[-1]["item"]
    assert isinstance(item, Mapping)
    assert item["role"] == "user"
    sent_types = [event["type"] for event in socket.sent]
    assert sent_types.index("conversation.item.create") < sent_types.index(
        "response.create"
    )

    await socket.push(response_created("resp-say"))
    generation = await asyncio.wait_for(generation_future, timeout=0.2)
    assert generation.response_id == "resp-say"
    await socket.push({"type": "response.done", "response": {"id": "resp-say"}})
    updates = await socket.wait_for_event_count("session.update", 3)
    restored = updates[-1]["session"]
    assert isinstance(restored, Mapping)
    assert restored["instructions"] == "使用标准普通话自然回答。"
    assert set(restored) == {"instructions"}

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_say_rejects_overlap_and_eof_fails_pending_future() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    pending = session.say("第一句")
    with pytest.raises(llm.RealtimeError, match="generation"):
        session.say("第二句")
    await socket.end()

    with pytest.raises(llm.RealtimeError, match="closed"):
        await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_say_rejects_active_smart_turn_until_response_done() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    await active_message(socket, session)
    rejected: asyncio.Future[llm.GenerationCreatedEvent] | None = None

    try:
        stops: list[llm.InputSpeechStoppedEvent] = []
        session.on("input_speech_stopped", stops.append)
        await socket.push({"type": "input_audio_buffer.speech_started"})
        await socket.push(
            {"type": "input_audio_buffer.speech_stopped", "reason": "natural"}
        )
        await wait_for_length(stops, 1)
        await socket.push(
            {"type": "response.done", "response": {"id": "resp-old"}}
        )
        await asyncio.sleep(0)

        try:
            rejected = session.say("轮次尚未结束")
        except llm.RealtimeError as error:
            assert "turn" in str(error)
        else:
            pytest.fail("say accepted while a smart-turn response was pending")
        assert not socket.events("response.create")

        await socket.push(response_created("resp-auto"))
        await socket.push(
            {"type": "response.done", "response": {"id": "resp-auto"}}
        )
        await asyncio.sleep(0)
        allowed = session.say("轮次已经结束")
        await socket.wait_for_event_count("response.create", 1)
        await socket.push(response_created("resp-after-turn"))
        await asyncio.wait_for(allowed, timeout=0.2)
        await socket.push(
            {"type": "response.done", "response": {"id": "resp-after-turn"}}
        )
        await socket.wait_for_event_count("session.update", 3)
    finally:
        await session.aclose()
        if rejected is not None:
            with pytest.raises(llm.RealtimeError):
                await rejected
        await model.aclose()


@pytest.mark.asyncio
async def test_recoverable_response_race_errors_keep_session_alive() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    await socket.push(response_created("resp-live"))
    await asyncio.sleep(0)

    await socket.push(
        {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_value",
                "message": "Cannot create response while another response is in progress.",
                "param": "response.create",
            },
        }
    )
    await socket.push(
        {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_value",
                "message": "Conversation has no active response.",
                "param": "response.cancel",
            },
        }
    )
    await asyncio.sleep(0.05)

    assert session._closed is False
    assert socket.close_calls == 0
    assert session._active_response_id == "resp-live"

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_server_error_fails_pending_say_without_waiting_for_eof() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    pending = session.say("不会完成")
    await socket.wait_for_event_count("response.create", 1)

    await socket.push(
        {
            "type": "error",
            "error": {
                "message": "secret payload https://workspace.invalid key-123",
            },
        }
    )

    with pytest.raises(llm.RealtimeError) as caught:
        await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
    assert "secret payload" not in str(caught.value)
    assert "workspace.invalid" not in str(caught.value)
    assert "key-123" not in str(caught.value)
    while socket.close_calls == 0:
        await asyncio.sleep(0)
    assert socket.close_calls == 1

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_say_accepts_async_text_stream_and_restores_instructions() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    async def text_stream():
        yield "欢迎致电"
        await asyncio.sleep(0)
        yield "颐诺口腔。"

    try:
        pending = session.say(text_stream())
        updates = await socket.wait_for_event_count("session.update", 2)
        await socket.wait_for_event_count("response.create", 1)
        temporary = updates[-1]["session"]
        assert isinstance(temporary, Mapping)
        assert "欢迎致电颐诺口腔。" in temporary["instructions"]

        await socket.push(response_created("resp-stream"))
        generation = await asyncio.wait_for(pending, timeout=0.2)
        assert generation.response_id == "resp-stream"
        await socket.push(
            {"type": "response.done", "response": {"id": "resp-stream"}}
        )
        updates = await socket.wait_for_event_count("session.update", 3)
        restored = updates[-1]["session"]
        assert isinstance(restored, Mapping)
        assert restored["instructions"] == "使用标准普通话自然回答。"
    finally:
        await session.aclose()
        await model.aclose()


@pytest.mark.asyncio
async def test_say_rejects_oversized_async_text_without_sending_partial_text() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    async def oversized_stream():
        yield "private-prefix"
        yield "x" * 100_000

    try:
        pending = session.say(oversized_stream())
        with pytest.raises(llm.RealtimeError) as caught:
            await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
        assert "private-prefix" not in str(caught.value)
        assert not socket.events("response.create")
        assert len(socket.events("session.update")) == 1
    finally:
        await session.aclose()
        await model.aclose()


@pytest.mark.asyncio
async def test_say_sanitizes_async_generator_failure() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    async def failing_stream():
        yield "partial-private-text"
        raise RuntimeError("secret generator payload")

    try:
        pending = session.say(failing_stream())
        with pytest.raises(llm.RealtimeError) as caught:
            await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
        assert "partial-private-text" not in str(caught.value)
        assert "secret generator payload" not in str(caught.value)
        assert not socket.events("response.create")
    finally:
        await session.aclose()
        await model.aclose()


@pytest.mark.asyncio
async def test_close_cancels_async_say_collection_without_hanging() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    waiting = asyncio.Event()
    finalized = asyncio.Event()

    async def slow_stream():
        try:
            yield "partial-private-text"
            waiting.set()
            await asyncio.Event().wait()
        finally:
            finalized.set()

    try:
        pending = session.say(slow_stream())
        await asyncio.wait_for(waiting.wait(), timeout=0.2)
        await asyncio.wait_for(session.aclose(), timeout=0.2)
        with pytest.raises(llm.RealtimeError, match="closed"):
            await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
        await asyncio.wait_for(finalized.wait(), timeout=0.2)
        assert not socket.events("response.create")
    finally:
        await session.aclose()
        await model.aclose()


@pytest.mark.asyncio
async def test_three_say_rounds_each_restore_normal_instructions() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    first = session.say("第一句")
    await socket.wait_for_event_count("response.create", 1)
    await socket.push(response_created("resp-first"))
    await asyncio.wait_for(first, timeout=0.2)
    await socket.push({"type": "response.done", "response": {"id": "resp-first"}})
    await socket.wait_for_event_count("session.update", 3)

    second = session.say("第二句")
    await socket.wait_for_event_count("response.create", 2)
    await socket.push(response_created("resp-second"))
    await asyncio.wait_for(second, timeout=0.2)
    await socket.push(
        {"type": "response.done", "response": {"id": "resp-second"}}
    )
    await socket.wait_for_event_count("session.update", 5)

    third = session.say("第三句")
    await socket.wait_for_event_count("response.create", 3)
    await socket.push(response_created("resp-third"))
    await asyncio.wait_for(third, timeout=0.2)
    await socket.push({"type": "response.done", "response": {"id": "resp-third"}})
    updates = await socket.wait_for_event_count("session.update", 7)

    assert [
        event["session"]["instructions"]
        for event in (updates[2], updates[4], updates[6])
    ] == [
        "使用标准普通话自然回答。",
        "使用标准普通话自然回答。",
        "使用标准普通话自然回答。",
    ]

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_cancelled_say_future_still_restores_session_lifecycle() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    cancelled = session.say("用户不再等待这句")
    cancelled.cancel()
    await socket.push(response_created("resp-cancelled-future"))
    await socket.push(
        {
            "type": "response.done",
            "response": {"id": "resp-cancelled-future"},
        }
    )
    updates = await socket.wait_for_event_count("session.update", 3)

    restored = updates[-1]["session"]
    assert isinstance(restored, Mapping)
    assert restored["instructions"] == "使用标准普通话自然回答。"
    replacement = session.say("下一句")
    await socket.end()
    with pytest.raises(llm.RealtimeError, match="closed"):
        await asyncio.wait_for(asyncio.shield(replacement), timeout=0.2)

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_close_discards_partial_input_and_fails_pending_say() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    short_frame = rtc.AudioFrame(
        data=b"\x01\x00" * 160,
        sample_rate=16_000,
        num_channels=1,
        samples_per_channel=160,
    )
    session.push_audio(short_frame)
    pending = session.say("尚未生成")

    await session.aclose()

    assert not socket.events("input_audio_buffer.append")
    assert socket.close_calls == 1
    with pytest.raises(llm.RealtimeError, match="closed"):
        await asyncio.wait_for(pending, timeout=0.2)
    await model.aclose()
