from __future__ import annotations

import asyncio
import logging

import pytest
from test_qwen_realtime_output import (
    FakeQwenSocket,
    audio_delta,
    audio_part_added,
    connected_session,
    message_added,
    next_generation,
    response_created,
)

from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.usage import CallUsageAccumulator


@pytest.mark.asyncio
async def test_unknown_qwen_event_does_not_close_session() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    await socket.push({"type": "session.created", "session": {"id": "sess-1"}})
    await socket.push({"type": "future.vendor.event", "payload": {"x": 1}})
    await socket.push({"type": "input_audio_buffer.cleared"})
    await socket.push({"type": "conversation.item.created", "item": {"id": "i1"}})
    await asyncio.sleep(0)
    assert session._closed is False
    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-ok"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)
    assert generation.response_id == "resp-ok"
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_malformed_qwen_events_do_not_kill_session_or_usage() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    acc = CallUsageAccumulator()
    model.attach_usage_sink(acc.add)
    await socket.server_events.put("not-json{")
    await socket.server_events.put("{}")
    await socket.server_events.put('{"type": 1}')
    await socket.push({"type": "response.created", "response": {"id": 123}})
    await socket.push(
        {
            "type": "response.done",
            "response": {
                "id": "resp-bad-usage",
                "usage": {
                    "total_tokens": "90",
                    "input_tokens": -5,
                    "output_tokens": True,
                },
            },
        }
    )
    await socket.push(
        {
            "type": "response.done",
            "response": {
                "id": "resp-good",
                "usage": {"total_tokens": 7, "input_tokens": 7, "output_tokens": 0},
            },
        }
    )
    await asyncio.sleep(0.02)
    assert session._closed is False
    snapshot = acc.snapshot()
    assert snapshot.total_tokens == 7
    assert snapshot.response_count == 1
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_partial_and_zero_usage_do_not_pollute_totals() -> None:
    acc = CallUsageAccumulator()
    acc.add({"type": "response.done", "response": {"id": "a"}})
    acc.add(
        {
            "type": "response.done",
            "response": {"id": "b", "usage": {"total_tokens": 0}},
        }
    )
    acc.add(
        {
            "type": "response.done",
            "response": {
                "id": "c",
                "usage": {"input_tokens": 4, "output_tokens": 1, "total_tokens": 5},
            },
        }
    )
    acc.add(
        {
            "type": "response.done",
            "response": {
                "id": "c",
                "usage": {"input_tokens": 4, "output_tokens": 1, "total_tokens": 5},
            },
        }
    )
    assert acc.snapshot().total_tokens == 5
    assert acc.snapshot().response_count == 1


@pytest.mark.asyncio
async def test_interrupt_then_hangup_and_response_done() -> None:
    socket = FakeQwenSocket()
    clock = FakeClock()
    trace = SessionTrace(session_id="barge", clock=clock)
    model, session = await connected_session(socket)
    model.attach_trace(trace)
    generation_task = asyncio.create_task(next_generation(session))
    await socket.push(response_created("resp-long"))
    await socket.push(message_added("resp-long", "msg-1"))
    await socket.push(audio_part_added("resp-long", "msg-1"))
    generation = await asyncio.wait_for(generation_task, timeout=0.2)
    message = await asyncio.wait_for(anext(generation.message_stream), timeout=0.2)
    pcm = b"\x01\x00" * 240
    await socket.push(audio_delta("resp-long", "msg-1", pcm))
    await asyncio.wait_for(anext(message.audio_stream), timeout=0.2)
    session.interrupt()
    await socket.wait_until_client_event("response.cancel")
    await socket.push(
        {
            "type": "response.done",
            "response": {"id": "resp-long", "status": "cancelled"},
        }
    )
    await socket.push(
        {
            "type": "error",
            "error": {"message": "Conversation has no active response."},
        }
    )
    await asyncio.sleep(0)
    assert session._closed is False
    assert trace.timestamp("interrupt_start") is not None
    assert trace.timestamp("first_assistant_audio") is not None
    late = []

    async def collect() -> None:
        async for _frame in message.audio_stream:
            late.append(_frame)

    collector = asyncio.create_task(collect())
    await socket.push(audio_delta("resp-long", "msg-1", pcm))
    await asyncio.sleep(0.01)
    collector.cancel()
    await asyncio.gather(collector, return_exceptions=True)
    assert late == []
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_double_interrupt_does_not_emit_two_cancels() -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    await socket.push(response_created("resp-1"))
    await asyncio.sleep(0)
    session.interrupt()
    session.interrupt()
    await socket.wait_until_client_event("response.cancel")
    cancels = [event for event in socket.sent if event.get("type") == "response.cancel"]
    assert len(cancels) == 1
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_fatal_qwen_error_does_not_log_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    socket = FakeQwenSocket()
    model, session = await connected_session(socket)
    with caplog.at_level(logging.ERROR):
        await socket.push(
            {
                "type": "error",
                "error": {
                    "message": "secret transcript +61411111111",
                    "type": "server_error",
                },
            }
        )
        await asyncio.sleep(0.02)
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "+61411111111" not in joined
    assert "secret transcript" not in joined
    await session.aclose()
    await model.aclose()


@pytest.mark.asyncio
async def test_missing_usage_on_done_is_ignored() -> None:
    acc = CallUsageAccumulator()
    acc.add({"type": "response.done", "response": {"id": "x"}})
    acc.add({"type": "response.done"})
    assert acc.snapshot().response_count == 0
