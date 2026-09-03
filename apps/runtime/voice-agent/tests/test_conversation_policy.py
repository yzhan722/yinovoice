from __future__ import annotations

import random

from yino_voice_agent.conversation import (
    ActionKind,
    ConversationDirector,
    ConversationEvent,
    ConversationPhase,
    ConversationPolicy,
    ConversationState,
    advance_and_expire,
    assert_invariants,
)
from yino_voice_agent.session_trace import FakeClock
from yino_voice_agent.voice_ux_config import VoiceUxSettings


def _director(clock: FakeClock | None = None) -> ConversationDirector:
    settings = VoiceUxSettings(
        initial_silence_s=8.0,
        followup_silence_s=10.0,
        max_silence_prompts=2,
        max_idle_s=30.0,
        max_session_s=120.0,
        tool_bridge_after_s=1.0,
        max_assistant_turn_s=20.0,
    )
    return ConversationDirector(settings, clock=clock or FakeClock())


def _greet(director: ConversationDirector) -> None:
    actions = director.handle(ConversationEvent.SESSION_READY)
    assert any(action.kind is ActionKind.SPEAK_GREETING for action in actions)
    director.handle(ConversationEvent.GREETING_STARTED)
    director.handle(ConversationEvent.GREETING_FINISHED)


def test_normal_greeting_then_listen() -> None:
    director = _director()
    _greet(director)
    assert director.greeting_count == 1
    assert director.phase is ConversationPhase.WAITING_FOR_USER


def test_caller_interrupts_greeting() -> None:
    director = _director()
    director.handle(ConversationEvent.SESSION_READY)
    actions = director.handle(ConversationEvent.USER_SPEECH_START)
    assert director.greeting_count == 1
    kinds = {action.kind for action in actions}
    assert ActionKind.CANCEL_ASSISTANT in kinds
    assert director.phase is ConversationPhase.USER_SPEAKING


def test_caller_speaks_before_greeting_skips_it() -> None:
    director = _director()
    actions = director.handle(ConversationEvent.SESSION_READY, user_speaking=True)
    assert any(action.kind is ActionKind.SKIP_GREETING for action in actions)
    assert director.greeting_count == 0
    assert director.state.greeting_started is True
    later = director.handle(ConversationEvent.SESSION_READY)
    assert later == ()
    assert director.greeting_count == 0


def test_reconnect_and_tool_return_do_not_greet_again() -> None:
    director = _director()
    _greet(director)
    director.handle(ConversationEvent.RECONNECT_ATTEMPT)
    director.handle(ConversationEvent.TOOL_REQUEST)
    director.handle(ConversationEvent.TOOL_RESULT, success=True)
    again = director.handle(ConversationEvent.SESSION_READY)
    assert again == ()
    assert director.greeting_count == 1


def test_initial_and_followup_silence_then_close() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    first = advance_and_expire(director, 8.0)
    assert first[0].kind is ActionKind.SPEAK_SILENCE_PROMPT
    assert director.silence_prompt_count == 1
    second = advance_and_expire(director, 10.0)
    assert second[0].kind is ActionKind.SPEAK_SILENCE_PROMPT
    assert director.silence_prompt_count == 2
    close = advance_and_expire(director, 10.0)
    kinds = [action.kind for action in close]
    assert ActionKind.SPEAK_POLITE_CLOSE in kinds
    assert ActionKind.REQUEST_FINISH in kinds
    assert director.finish_count == 1
    assert director.phase is ConversationPhase.CLOSED


def test_silence_after_turn_and_tool() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.USER_SPEECH_START)
    director.handle(ConversationEvent.TRANSCRIPT_FINAL, accepted=True)
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_DONE)
    prompt = advance_and_expire(director, 8.0)
    assert prompt[0].kind is ActionKind.SPEAK_SILENCE_PROMPT
    director.handle(ConversationEvent.TOOL_REQUEST)
    during_tool = advance_and_expire(director, 8.0)
    assert not any(
        action.kind is ActionKind.SPEAK_SILENCE_PROMPT for action in during_tool
    )
    assert not any(action.kind is ActionKind.REQUEST_FINISH for action in during_tool)
    director.handle(ConversationEvent.TOOL_RESULT, success=True)
    after_tool = advance_and_expire(director, 10.0)
    assert after_tool[0].kind is ActionKind.SPEAK_SILENCE_PROMPT


def test_silence_ignored_while_assistant_speaking() -> None:
    clock = FakeClock()
    director = _director(clock)
    director.handle(ConversationEvent.SESSION_READY)
    assert director.phase is ConversationPhase.ASSISTANT_SPEAKING
    assert advance_and_expire(director, 8.0) == ()


def test_silence_timer_loses_to_user_speech() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    clock.advance(8.0)
    director.handle(ConversationEvent.USER_SPEECH_START)
    assert director.expire_due() == ()
    assert director.phase is ConversationPhase.USER_SPEAKING
    assert director.silence_prompt_count == 0


def test_hangup_during_silence_timer_finishes_once() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.HANGUP)
    assert director.finish_count == 1
    clock.advance(30.0)
    assert director.expire_due() == ()
    assert director.finish_count == 1


def test_idle_timeout_paused_during_tool() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.TOOL_REQUEST)
    clock.advance(30.0)
    director.handle(ConversationEvent.TOOL_RESULT, success=True)
    assert director.phase is not ConversationPhase.CLOSED
    idle = advance_and_expire(director, 30.0)
    assert any(action.kind is ActionKind.REQUEST_FINISH for action in idle)


def test_idle_timeout_with_disconnect_finishes_once() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    clock.advance(30.0)
    director.handle(ConversationEvent.PARTICIPANT_DISCONNECT)
    assert director.finish_count == 1
    assert director.expire_due() == ()


def test_idle_ignored_when_response_starts() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    clock.advance(30.0)
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
    assert director.expire_due() == ()
    assert director.phase is ConversationPhase.ASSISTANT_SPEAKING


def test_max_session_graceful_close_even_during_speech() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.USER_SPEECH_START)
    actions = advance_and_expire(director, 120.0)
    kinds = [action.kind for action in actions]
    assert ActionKind.SPEAK_SESSION_LIMIT in kinds
    assert ActionKind.REQUEST_FINISH in kinds
    assert director.finish_count == 1


def test_max_session_during_tool_still_finishes() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.TOOL_REQUEST)
    actions = advance_and_expire(director, 120.0)
    assert any(action.kind is ActionKind.REQUEST_FINISH for action in actions)
    assert director.phase is ConversationPhase.CLOSED


def test_slow_tool_emits_one_bridge_then_result() -> None:
    clock = FakeClock()
    director = _director(clock)
    _greet(director)
    director.handle(ConversationEvent.TOOL_REQUEST)
    bridge = advance_and_expire(director, 1.0)
    assert bridge[0].kind is ActionKind.SPEAK_TOOL_BRIDGE
    assert advance_and_expire(director, 1.0) == ()
    director.handle(ConversationEvent.TOOL_RESULT, success=True)
    assert director.state.tool_succeeded is True


def test_tool_failure_is_customer_safe_and_not_success() -> None:
    director = _director()
    _greet(director)
    director.handle(ConversationEvent.TOOL_REQUEST)
    actions = director.handle(ConversationEvent.TOOL_RESULT, success=False)
    assert actions[0].kind is ActionKind.SPEAK_TOOL_FAILURE
    assert "HTTP" not in actions[0].text
    assert director.state.tool_succeeded is False


def test_provider_disconnect_fails_session_without_fallback_speak() -> None:
    director = _director()
    _greet(director)
    actions = director.handle(ConversationEvent.PROVIDER_DISCONNECT)
    kinds = [action.kind for action in actions]
    assert ActionKind.REQUEST_FINISH in kinds
    assert ActionKind.SPEAK_GREETING not in kinds
    assert not any(kind.value.startswith("speak_") for kind in kinds)
    assert director.phase is ConversationPhase.CLOSED


def test_late_response_after_interrupt_is_suppressed() -> None:
    director = _director()
    _greet(director)
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_START)
    director.handle(ConversationEvent.INTERRUPT)
    actions = director.handle(ConversationEvent.ASSISTANT_AUDIO_START)
    assert ActionKind.SUPPRESS_LATE_AUDIO in {action.kind for action in actions}
    director.handle(ConversationEvent.ASSISTANT_RESPONSE_DONE)
    assert director.phase is ConversationPhase.USER_SPEAKING


def test_no_response_or_tool_after_closed() -> None:
    director = _director()
    director.handle(ConversationEvent.HANGUP)
    assert director.handle(ConversationEvent.ASSISTANT_RESPONSE_START) == ()
    assert director.handle(ConversationEvent.TOOL_REQUEST) == ()
    assert director.phase is ConversationPhase.CLOSED


def test_dropped_transcript_does_not_enter_thinking() -> None:
    director = _director()
    _greet(director)
    director.handle(ConversationEvent.USER_SPEECH_START)
    actions = director.handle(ConversationEvent.TRANSCRIPT_FINAL, accepted=False)
    assert actions[0].kind is ActionKind.DROP_TRANSCRIPT
    assert director.phase is ConversationPhase.WAITING_FOR_USER


def test_policy_handles_closed_events_as_noop() -> None:
    policy = ConversationPolicy()
    closed = ConversationState(phase=ConversationPhase.CLOSED, finish_count=1)
    state, actions = policy.apply(closed, ConversationEvent.SESSION_READY, 1.0)
    assert state.phase is ConversationPhase.CLOSED
    assert actions == ()


def test_fuzz_legal_sequences_keep_invariants() -> None:
    events = (
        ConversationEvent.USER_SPEECH_START,
        ConversationEvent.USER_SPEECH_END,
        ConversationEvent.TRANSCRIPT_FINAL,
        ConversationEvent.ASSISTANT_RESPONSE_START,
        ConversationEvent.ASSISTANT_RESPONSE_DONE,
        ConversationEvent.INTERRUPT,
        ConversationEvent.TOOL_REQUEST,
        ConversationEvent.TOOL_RESULT,
        ConversationEvent.SILENCE_TIMER,
        ConversationEvent.PROVIDER_ERROR,
        ConversationEvent.HANGUP,
        ConversationEvent.RECONNECT_ATTEMPT,
    )
    for seed in (42, 2026, 9001):
        rng = random.Random(seed)
        director = _director(FakeClock(start=0.0))
        director.handle(ConversationEvent.SESSION_READY)
        for _ in range(80):
            event = rng.choice(events)
            payload: dict[str, object] = {}
            if event is ConversationEvent.TRANSCRIPT_FINAL:
                payload["accepted"] = rng.random() > 0.2
            if event is ConversationEvent.TOOL_RESULT:
                payload["success"] = rng.random() > 0.4
            director.handle(event, **payload)
            assert_invariants(director.state)
            assert director.greeting_count <= 1
            assert director.finish_count <= 1
            assert director.state.active_responses <= 1
            if director.phase is ConversationPhase.CLOSED:
                break
        assert director.greeting_count <= 1
        assert director.finish_count <= 1
