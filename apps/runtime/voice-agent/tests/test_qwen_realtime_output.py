from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Mapping

import pytest
from livekit.agents import llm

from yino_voice_agent.qwen_realtime import QwenRealtimeModel, QwenRealtimeSession


class FakeQwenSocket:
    def __init__(self) -> None:
        self.server_events: asyncio.Queue[str | None] = asyncio.Queue()
        self.received_server_event_types: list[str] = []
        self.sent: list[Mapping[str, object]] = []
        self.close_calls = 0

    async def push(self, event: Mapping[str, object]) -> None:
        event_type = event["type"]
        assert isinstance(event_type, str)
        self.received_server_event_types.append(event_type)
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

    async def wait_until_client_event(
        self, event_type: str, timeout: float = 0.2
    ) -> Mapping[str, object]:
        async def find_event() -> Mapping[str, object]:
            while True:
                for event in self.sent:
                    if event.get("type") == event_type:
                        return event
                await asyncio.sleep(0)

        return await asyncio.wait_for(find_event(), timeout)


class FakeQwenConnector:
    def __init__(self, socket: FakeQwenSocket) -> None:
        self.socket = socket
        self.connected = asyncio.Event()
        self.connected_url: str | None = None
        self.connected_headers: Mapping[str, str] | None = None

    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> FakeQwenSocket:
        self.connected_url = url
        self.connected_headers = headers
        self.connected.set()
        return self.socket


def response_created(response_id: str) -> dict[str, object]:
    return {"type": "response.created", "response": {"id": response_id}}


def message_added(response_id: str, message_id: str) -> dict[str, object]:
    return {
        "type": "response.output_item.added",
        "response_id": response_id,
        "item": {"id": message_id, "type": "message"},
    }


def audio_part_added(response_id: str, message_id: str) -> dict[str, object]:
    return {
        "type": "response.content_part.added",
        "response_id": response_id,
        "item_id": message_id,
        "part": {"type": "audio"},
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


async def next_generation(
    session: QwenRealtimeSession,
) -> llm.GenerationCreatedEvent:
    future: asyncio.Future[llm.GenerationCreatedEvent] = asyncio.Future()
    session.once("generation_created", future.set_result)
    return await future


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
    await socket.wait_until_client_event("session.update")
    await socket.push({"type": "session.updated", "session": {}})

    async def _session_ready() -> None:
        while not session._session_accepts_audio:
            await asyncio.sleep(0)

    await asyncio.wait_for(_session_ready(), timeout=0.2)
    return model, session


@pytest.mark.asyncio
async def test_audio_delta_is_streamed_before_response_done() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-1"))
    await socket.push(message_added("resp-1", "msg-1"))
    await socket.push(audio_part_added("resp-1", "msg-1"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)
    message = await asyncio.wait_for(anext(generation.message_stream), timeout=0.2)

    pcm = b"\x01\x00" * 240
    await socket.push(audio_delta("resp-1", "msg-1", pcm))
    frame = await asyncio.wait_for(anext(message.audio_stream), timeout=0.2)

    assert frame.sample_rate == 24_000
    assert frame.num_channels == 1
    assert frame.data.tobytes() == pcm
    assert await message.modalities == ["audio", "text"]
    assert "response.done" not in socket.received_server_event_types

    await session.aclose()
    await model.aclose()


def test_model_declares_realtime_capabilities_including_say() -> None:
    model = QwenRealtimeModel(
        api_key="",
        url="",
        model="qwen-audio-3.0-realtime-plus",
        voice="longanqian",
        instructions="",
        connector=FakeQwenConnector(FakeQwenSocket()),
    )

    assert model.model == "qwen-audio-3.0-realtime-plus"
    assert model.capabilities.turn_detection is True
    assert model.capabilities.user_transcription is True
    assert model.capabilities.audio_output is True
    assert model.capabilities.supports_say is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "expected_url"),
    [
        (
            "wss://example.invalid/realtime?trace=one%20two",
            "wss://example.invalid/realtime?trace=one+two&model=qwen+audio%2Fplus",
        ),
        (
            "wss://example.invalid/realtime?model=stale&trace=on&model=duplicate",
            "wss://example.invalid/realtime?trace=on&model=qwen+audio%2Fplus",
        ),
    ],
)
async def test_connection_uses_one_encoded_configured_model_query(
    url: str,
    expected_url: str,
) -> None:
    socket = FakeQwenSocket()
    connector = FakeQwenConnector(socket)
    model = QwenRealtimeModel(
        api_key="",
        url=url,
        model="qwen audio/plus",
        voice="longanqian",
        instructions="",
        connector=connector,
    )
    session = model.session()

    await asyncio.wait_for(connector.connected.wait(), timeout=0.2)
    assert connector.connected_url == expected_url

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_session_updates_instructions_and_rejects_unsupported_state() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    assert len(session.chat_ctx.items) == 0
    assert len(session.tools.flatten()) == 0
    await session.update_instructions("只回答必要信息。")
    update = await socket.wait_until_client_event("session.update")
    assert update["session"]["instructions"] in {
        "使用标准普通话自然回答。",
        "只回答必要信息。",
    }
    await asyncio.sleep(0)
    assert socket.sent[-1]["session"]["instructions"] == "只回答必要信息。"

    empty_ctx = llm.ChatContext.empty()
    await session.update_chat_ctx(empty_ctx)
    assert session.chat_ctx is not None
    await session.update_tools([])
    with pytest.raises(llm.RealtimeError, match="tools"):
        await session.update_tools([object()])  # type: ignore[list-item]
    with pytest.raises(llm.RealtimeError, match="video"):
        session.push_video(None)  # type: ignore[arg-type]
    with pytest.raises(llm.RealtimeError, match="truncation"):
        session.truncate(message_id="msg-1", modalities=["audio"], audio_end_ms=10)
    with pytest.raises(llm.RealtimeError, match="tool choice"):
        session.update_options(tool_choice="auto")

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_generate_reply_maps_next_response_created_to_its_future() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)

    generation_future = session.generate_reply()
    await socket.wait_until_client_event("response.create")
    await socket.push(response_created("resp-generated"))
    generation = await asyncio.wait_for(generation_future, timeout=0.2)

    assert generation.response_id == "resp-generated"
    assert generation.user_initiated is True

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_server_eof_fails_pending_and_future_generations_without_hang() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    pending = session.generate_reply()
    await socket.wait_until_client_event("response.create")

    await socket.end()

    try:
        with pytest.raises(llm.RealtimeError, match="closed"):
            await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
        rejected = session.generate_reply()
        with pytest.raises(llm.RealtimeError, match="closed"):
            await asyncio.wait_for(rejected, timeout=0.2)
    finally:
        await session.aclose()
        await model.aclose()


@pytest.mark.asyncio
async def test_transcript_and_item_done_close_message_streams() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-1"))
    await socket.push(message_added("resp-1", "msg-1"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)
    message = await asyncio.wait_for(anext(generation.message_stream), timeout=0.2)

    await socket.push(
        {
            "type": "response.audio_transcript.delta",
            "response_id": "resp-1",
            "item_id": "msg-1",
            "delta": "您好",
        }
    )
    assert await asyncio.wait_for(anext(message.text_stream), timeout=0.2) == "您好"

    await socket.push(
        {
            "type": "response.output_item.done",
            "response_id": "resp-1",
            "item": {"id": "msg-1", "type": "message"},
        }
    )
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(message.text_stream), timeout=0.2)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(message.audio_stream), timeout=0.2)

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_interrupt_discards_late_audio_and_text_for_cancelled_response() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-old"))
    await socket.push(message_added("resp-old", "msg-old"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)
    message = await asyncio.wait_for(anext(generation.message_stream), timeout=0.2)

    session.interrupt()
    await socket.wait_until_client_event("response.cancel")
    await socket.push(audio_delta("resp-old", "msg-old", b"\x02\x00" * 240))
    await socket.push(
        {
            "type": "response.audio_transcript.delta",
            "response_id": "resp-old",
            "item_id": "msg-old",
            "delta": "late text",
        }
    )

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(message.audio_stream), timeout=0.05)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(message.text_stream), timeout=0.05)

    await socket.push({"type": "response.done", "response": {"id": "resp-old"}})
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_response_done_closes_remaining_generation_channels() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-1"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)

    await socket.push({"type": "response.done", "response": {"id": "resp-1"}})
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(generation.message_stream), timeout=0.2)

    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_smart_turn_commit_clear_are_noops_and_close_is_idempotent() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    initial_events = list(socket.sent)

    session.commit_audio()
    session.clear_audio()
    await asyncio.sleep(0)
    assert socket.sent == initial_events

    await session.aclose()
    await session.aclose()
    assert socket.close_calls == 1
    await model.aclose()
