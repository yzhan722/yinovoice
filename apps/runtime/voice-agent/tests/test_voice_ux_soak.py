from __future__ import annotations

import asyncio
import random

import pytest

from yino_voice_agent.conversation import (
    ActionKind,
    ConversationDirector,
    ConversationEvent,
    ConversationPhase,
    advance_and_expire,
    assert_invariants,
)
from yino_voice_agent.latency import summarize
from yino_voice_agent.session_trace import FakeClock, SessionTrace
from yino_voice_agent.voice_ux_config import VoiceUxSettings

# Previous hardening SYNTHETIC speech_end_to_first_audio (100 FakeClock traces).
_PREV_P50 = 0.2495
_PREV_P95 = 0.2941
_PREV_P99 = 0.2980


def _ux() -> VoiceUxSettings:
    return VoiceUxSettings(
        initial_silence_s=8.0,
        followup_silence_s=10.0,
        max_silence_prompts=2,
        max_idle_s=60.0,
        max_session_s=600.0,
        tool_bridge_after_s=1.0,
        max_assistant_turn_s=20.0,
    )


def test_five_hundred_turn_soak_with_ux_events() -> None:
    clock = FakeClock()
    director = ConversationDirector(_ux(), clock=clock)
    director.handle(ConversationEvent.SESSION_READY)
    director.handle(ConversationEvent.GREETING_FINISHED)
    for turn in range(500):
        director.handle(ConversationEvent.USER_SPEECH_START)
        director.handle(ConversationEvent.TRANSCRIPT_FINAL, accepted=True)
        if turn % 17 == 0:
            director.handle(ConversationEvent.INTERRUPT)
        if turn % 11 == 0:
            director.handle(ConversationEvent.TOOL_REQUEST)
            if turn % 33 == 0:
                advance_and_expire(director, 1.0)
            director.handle(ConversationEvent.TOOL_RESULT, success=turn % 29 != 0)
        else:
            director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
            director.handle(ConversationEvent.ASSISTANT_RESPONSE_DONE)
        if turn % 23 == 0:
            clock.advance(8.0)
            director.expire_due()
        assert_invariants(director.state)
        assert director.greeting_count <= 1
        assert director.finish_count <= 1
        assert director.state.active_responses <= 1
    director.handle(ConversationEvent.HANGUP)
    assert director.finish_count == 1
    assert director.phase is ConversationPhase.CLOSED


def test_one_thousand_synthetic_sessions_keep_invariants() -> None:
    for index in range(1000):
        clock = FakeClock()
        director = ConversationDirector(_ux(), clock=clock)
        director.handle(ConversationEvent.SESSION_READY)
        director.handle(ConversationEvent.GREETING_FINISHED)
        director.handle(ConversationEvent.USER_SPEECH_START)
        director.handle(ConversationEvent.TRANSCRIPT_FINAL, accepted=True)
        director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
        director.handle(ConversationEvent.ASSISTANT_RESPONSE_DONE)
        if index % 10 == 0:
            advance_and_expire(director, 8.0)
        director.handle(ConversationEvent.HANGUP)
        assert director.greeting_count <= 1
        assert director.finish_count == 1
        assert_invariants(director.state)


@pytest.mark.asyncio
async def test_fifty_directors_are_isolated() -> None:
    async def one(index: int) -> ConversationDirector:
        director = ConversationDirector(_ux(), clock=FakeClock())
        director.handle(ConversationEvent.SESSION_READY)
        director.handle(ConversationEvent.GREETING_FINISHED)
        director.handle(ConversationEvent.USER_SPEECH_START)
        director.handle(ConversationEvent.HANGUP)
        return director

    directors = await asyncio.gather(*[one(index) for index in range(50)])
    assert all(item.finish_count == 1 for item in directors)
    assert all(item.greeting_count <= 1 for item in directors)


def test_fuzz_three_seeds_never_corrupt_state() -> None:
    events = [
        ConversationEvent.USER_SPEECH_START,
        ConversationEvent.USER_SPEECH_END,
        ConversationEvent.ASSISTANT_RESPONSE_START,
        ConversationEvent.ASSISTANT_RESPONSE_DONE,
        ConversationEvent.INTERRUPT,
        ConversationEvent.TOOL_REQUEST,
        ConversationEvent.TOOL_RESULT,
        ConversationEvent.SILENCE_TIMER,
        ConversationEvent.IDLE_TIMER,
        ConversationEvent.HANGUP,
        ConversationEvent.PARTICIPANT_DISCONNECT,
        ConversationEvent.PROVIDER_DISCONNECT,
    ]
    for seed in (42, 2026, 9001):
        rng = random.Random(seed)
        for _ in range(40):
            director = ConversationDirector(_ux(), clock=FakeClock())
            director.handle(ConversationEvent.SESSION_READY)
            for _step in range(30):
                event = rng.choice(events)
                payload: dict[str, object] = {}
                if event is ConversationEvent.TOOL_RESULT:
                    payload["success"] = rng.choice([True, False])
                director.handle(event, **payload)
                assert_invariants(director.state)
                if director.phase is ConversationPhase.CLOSED:
                    break
            assert director.greeting_count <= 1
            assert director.finish_count <= 1


def test_synthetic_latency_regression_is_loose() -> None:
    samples: list[float] = []
    for index in range(100):
        clock = FakeClock()
        trace = SessionTrace(session_id=f"ux-lat-{index}", clock=clock)
        director = ConversationDirector(_ux(), clock=clock, trace=trace)
        director.handle(ConversationEvent.SESSION_READY)
        director.handle(ConversationEvent.GREETING_FINISHED)
        trace.mark("user_speech_end")
        clock.advance(0.2 + index * 0.001)
        trace.mark("first_assistant_audio")
        samples.append(trace.derived()["speech_end_to_first_audio"])
    summary = summarize(samples)
    assert summary.p50 < _PREV_P50 + 0.15
    assert summary.p95 < _PREV_P95 + 0.15
    assert summary.p99 < _PREV_P99 + 0.15


def test_long_answer_safety_bound_cancels() -> None:
    clock = FakeClock()
    director = ConversationDirector(_ux(), clock=clock)
    director.handle(ConversationEvent.SESSION_READY)
    director.handle(ConversationEvent.GREETING_FINISHED)
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
    actions = advance_and_expire(director, 20.0)
    kinds = {action.kind for action in actions}
    assert ActionKind.CANCEL_ASSISTANT in kinds
    assert director.phase is ConversationPhase.WAITING_FOR_USER
