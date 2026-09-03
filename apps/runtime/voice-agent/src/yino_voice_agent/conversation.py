"""Conversation phase machine and Voice UX policy. FakeClock-friendly."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .session_trace import OBSERVED_EVENTS, Clock, FakeClock, SessionTrace, SystemClock
from .voice_ux_config import VoiceUxSettings

_MAX_ACTION_LOG = 32


class ConversationPhase(StrEnum):
    WAITING_FOR_USER = "waiting_for_user"
    USER_SPEAKING = "user_speaking"
    THINKING = "thinking"
    ASSISTANT_SPEAKING = "assistant_speaking"
    TOOL_RUNNING = "tool_running"
    CLOSING = "closing"
    CLOSED = "closed"


class ConversationEvent(StrEnum):
    SESSION_READY = "session_ready"
    GREETING_STARTED = "greeting_started"
    GREETING_FINISHED = "greeting_finished"
    USER_SPEECH_START = "user_speech_start"
    USER_SPEECH_END = "user_speech_end"
    TRANSCRIPT_FINAL = "transcript_final"
    ASSISTANT_RESPONSE_START = "assistant_response_start"
    ASSISTANT_AUDIO_START = "assistant_audio_start"
    ASSISTANT_RESPONSE_DONE = "assistant_response_done"
    INTERRUPT = "interrupt"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    PROVIDER_DISCONNECT = "provider_disconnect"
    PROVIDER_ERROR = "provider_error"
    PARTICIPANT_DISCONNECT = "participant_disconnect"
    SILENCE_TIMER = "silence_timer"
    IDLE_TIMER = "idle_timer"
    SESSION_TIMER = "session_timer"
    ASSISTANT_LIMIT_TIMER = "assistant_limit_timer"
    TOOL_BRIDGE_TIMER = "tool_bridge_timer"
    HANGUP = "hangup"
    RECONNECT_ATTEMPT = "reconnect_attempt"
    GOODBYE_SAID = "goodbye_said"


class ActionKind(StrEnum):
    SPEAK_GREETING = "speak_greeting"
    SKIP_GREETING = "skip_greeting"
    SPEAK_SILENCE_PROMPT = "speak_silence_prompt"
    SPEAK_POLITE_CLOSE = "speak_polite_close"
    SPEAK_SESSION_LIMIT = "speak_session_limit"
    SPEAK_TOOL_BRIDGE = "speak_tool_bridge"
    SPEAK_TOOL_FAILURE = "speak_tool_failure"
    CANCEL_ASSISTANT = "cancel_assistant"
    SUPPRESS_LATE_AUDIO = "suppress_late_audio"
    REQUEST_FINISH = "request_finish"
    ACCEPT_TRANSCRIPT = "accept_transcript"
    DROP_TRANSCRIPT = "drop_transcript"


LEGAL_TRANSITIONS: dict[ConversationPhase, frozenset[ConversationPhase]] = {
    ConversationPhase.WAITING_FOR_USER: frozenset(
        {
            ConversationPhase.USER_SPEAKING,
            ConversationPhase.THINKING,
            ConversationPhase.ASSISTANT_SPEAKING,
            ConversationPhase.TOOL_RUNNING,
            ConversationPhase.CLOSING,
            ConversationPhase.CLOSED,
        }
    ),
    ConversationPhase.USER_SPEAKING: frozenset(
        {
            ConversationPhase.WAITING_FOR_USER,
            ConversationPhase.THINKING,
            ConversationPhase.CLOSING,
            ConversationPhase.CLOSED,
        }
    ),
    ConversationPhase.THINKING: frozenset(
        {
            ConversationPhase.ASSISTANT_SPEAKING,
            ConversationPhase.TOOL_RUNNING,
            ConversationPhase.WAITING_FOR_USER,
            ConversationPhase.USER_SPEAKING,
            ConversationPhase.CLOSING,
            ConversationPhase.CLOSED,
        }
    ),
    ConversationPhase.ASSISTANT_SPEAKING: frozenset(
        {
            ConversationPhase.WAITING_FOR_USER,
            ConversationPhase.USER_SPEAKING,
            ConversationPhase.TOOL_RUNNING,
            ConversationPhase.THINKING,
            ConversationPhase.CLOSING,
            ConversationPhase.CLOSED,
        }
    ),
    ConversationPhase.TOOL_RUNNING: frozenset(
        {
            ConversationPhase.THINKING,
            ConversationPhase.ASSISTANT_SPEAKING,
            ConversationPhase.WAITING_FOR_USER,
            ConversationPhase.USER_SPEAKING,
            ConversationPhase.CLOSING,
            ConversationPhase.CLOSED,
        }
    ),
    ConversationPhase.CLOSING: frozenset({ConversationPhase.CLOSED}),
    ConversationPhase.CLOSED: frozenset(),
}


class IllegalConversationTransitionError(ValueError):
    """Raised when production code forces an illegal phase jump."""

    def __init__(self, current: ConversationPhase, target: ConversationPhase) -> None:
        super().__init__(f"illegal conversation transition {current} -> {target}")
        self.current = current
        self.target = target


@dataclass(frozen=True, slots=True)
class Action:
    kind: ActionKind
    text: str = ""
    finish_status: str = ""
    finish_reason: str = ""


@dataclass(frozen=True, slots=True)
class ConversationState:
    phase: ConversationPhase = ConversationPhase.WAITING_FOR_USER
    greeting_count: int = 0
    greeting_started: bool = False
    greeting_finished: bool = False
    silence_prompt_count: int = 0
    finish_count: int = 0
    active_responses: int = 0
    active_tool: bool = False
    user_speaking: bool = False
    early_user_speech: bool = False
    last_activity_at: float = 0.0
    session_started_at: float = 0.0
    silence_deadline: float | None = None
    idle_deadline: float | None = None
    session_deadline: float | None = None
    tool_bridge_deadline: float | None = None
    assistant_limit_deadline: float | None = None
    suppressed_response: bool = False
    pending_bridge: bool = False
    finish_status: str = ""
    finish_reason: str = ""
    tool_succeeded: bool = False


def assert_invariants(state: ConversationState) -> None:
    if state.greeting_count > 1:
        raise AssertionError("greeting_count exceeds 1")
    if state.active_responses > 1:
        raise AssertionError("more than one active assistant response")
    if state.finish_count > 1:
        raise AssertionError("finish_count exceeds 1")
    if state.phase is ConversationPhase.CLOSED and state.finish_count < 1:
        raise AssertionError("CLOSED without finish")
    if state.phase is ConversationPhase.CLOSED and state.active_tool:
        raise AssertionError("tool still active after CLOSED")
    if (
        state.phase is ConversationPhase.CLOSING
        and state.active_tool
        and state.finish_count
    ):
        raise AssertionError("new tool after closing finish")


def can_transition(current: ConversationPhase, target: ConversationPhase) -> bool:
    return target in LEGAL_TRANSITIONS[current]


def force_transition(
    state: ConversationState, target: ConversationPhase
) -> ConversationState:
    if not can_transition(state.phase, target):
        raise IllegalConversationTransitionError(state.phase, target)
    return replace(state, phase=target)


def _arm_silence(
    state: ConversationState, settings: VoiceUxSettings, now: float
) -> ConversationState:
    timeout = (
        settings.initial_silence_s
        if state.silence_prompt_count == 0
        else settings.followup_silence_s
    )
    return replace(state, silence_deadline=now + timeout)


def _arm_idle(
    state: ConversationState, settings: VoiceUxSettings, now: float
) -> ConversationState:
    return replace(
        state,
        last_activity_at=now,
        idle_deadline=now + settings.max_idle_s,
    )


def _clear_silence(state: ConversationState) -> ConversationState:
    return replace(state, silence_deadline=None)


def _enter(
    state: ConversationState,
    phase: ConversationPhase,
    *,
    extra: dict[str, Any] | None = None,
) -> ConversationState:
    if state.phase is phase:
        updated = state
    elif can_transition(state.phase, phase):
        updated = replace(state, phase=phase)
    else:
        return state
    if extra:
        updated = replace(updated, **extra)
    return updated


def _finish(
    state: ConversationState, status: str, reason: str
) -> tuple[ConversationState, tuple[Action, ...]]:
    if state.finish_count >= 1 or state.phase is ConversationPhase.CLOSED:
        closed = (
            state
            if state.phase is ConversationPhase.CLOSED
            else _enter(state, ConversationPhase.CLOSED)
        )
        return closed, ()
    closing = state
    if state.phase is not ConversationPhase.CLOSING:
        closing = _enter(
            state,
            ConversationPhase.CLOSING,
            extra={"active_tool": False, "active_responses": 0},
        )
    closed = _enter(
        closing,
        ConversationPhase.CLOSED,
        extra={
            "finish_count": closing.finish_count + 1,
            "finish_status": status,
            "finish_reason": reason,
            "active_tool": False,
            "active_responses": 0,
            "user_speaking": False,
            "silence_deadline": None,
            "idle_deadline": None,
            "session_deadline": None,
            "tool_bridge_deadline": None,
            "assistant_limit_deadline": None,
        },
    )
    return closed, (
        Action(
            ActionKind.REQUEST_FINISH,
            finish_status=status,
            finish_reason=reason,
        ),
    )


class ConversationPolicy:
    def __init__(self, settings: VoiceUxSettings | None = None) -> None:
        self.settings = settings or VoiceUxSettings()

    def apply(
        self,
        state: ConversationState,
        event: ConversationEvent,
        now: float,
        payload: dict[str, Any] | None = None,
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        data = payload or {}
        if state.phase is ConversationPhase.CLOSED:
            return state, ()
        handler = getattr(self, f"_on_{event.value}", None)
        if handler is None:
            return state, ()
        next_state, actions = handler(state, now, data)
        assert_invariants(next_state)
        return next_state, actions

    def _on_session_ready(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        started = replace(
            state,
            session_started_at=now,
            last_activity_at=now,
            session_deadline=now + self.settings.max_session_s,
            idle_deadline=now + self.settings.max_idle_s,
        )
        if started.greeting_count >= 1 or started.greeting_started:
            return started, ()
        if started.early_user_speech or data.get("user_speaking"):
            skipped = _enter(
                replace(
                    started,
                    early_user_speech=True,
                    greeting_started=True,
                    greeting_finished=True,
                    user_speaking=True,
                ),
                ConversationPhase.USER_SPEAKING,
            )
            return skipped, (Action(ActionKind.SKIP_GREETING),)
        speaking = _enter(
            started,
            ConversationPhase.ASSISTANT_SPEAKING,
            extra={
                "greeting_started": True,
                "greeting_count": 1,
                "active_responses": 1,
                "assistant_limit_deadline": now + self.settings.max_assistant_turn_s,
            },
        )
        return speaking, (Action(ActionKind.SPEAK_GREETING),)

    def _on_greeting_started(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        if state.greeting_count > 1:
            return state, ()
        return replace(
            state, greeting_started=True, greeting_count=max(state.greeting_count, 1)
        ), ()

    def _on_greeting_finished(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        waiting = _enter(
            replace(
                state,
                greeting_finished=True,
                active_responses=0,
                assistant_limit_deadline=None,
            ),
            ConversationPhase.WAITING_FOR_USER,
        )
        armed = _arm_idle(_arm_silence(waiting, self.settings, now), self.settings, now)
        return armed, ()

    def _on_user_speech_start(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        if state.phase is ConversationPhase.CLOSING:
            return state, ()
        actions: list[Action] = []
        extra: dict[str, Any] = {
            "user_speaking": True,
            "early_user_speech": not state.greeting_started,
            "silence_deadline": None,
            "suppressed_response": False,
        }
        if (
            state.phase is ConversationPhase.ASSISTANT_SPEAKING
            or state.active_responses
        ):
            extra["active_responses"] = 0
            extra["assistant_limit_deadline"] = None
            extra["suppressed_response"] = True
            actions.append(Action(ActionKind.CANCEL_ASSISTANT))
            actions.append(Action(ActionKind.SUPPRESS_LATE_AUDIO))
        next_state = _enter(
            _arm_idle(replace(state, **extra), self.settings, now),
            ConversationPhase.USER_SPEAKING,
        )
        if not state.greeting_started and state.greeting_count == 0:
            next_state = replace(next_state, early_user_speech=True)
            actions.insert(0, Action(ActionKind.SKIP_GREETING))
        return next_state, tuple(actions)

    def _on_user_speech_end(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        if state.phase is ConversationPhase.CLOSING:
            return replace(state, user_speaking=False), ()
        thinking = _enter(
            replace(state, user_speaking=False),
            ConversationPhase.THINKING,
        )
        return _arm_idle(thinking, self.settings, now), ()

    def _on_transcript_final(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        accepted = bool(data.get("accepted", True))
        if not accepted:
            waiting = _enter(
                replace(state, user_speaking=False),
                ConversationPhase.WAITING_FOR_USER,
            )
            return _arm_silence(
                _arm_idle(waiting, self.settings, now), self.settings, now
            ), (Action(ActionKind.DROP_TRANSCRIPT),)
        thinking = _enter(
            replace(state, user_speaking=False),
            ConversationPhase.THINKING,
        )
        return _arm_idle(thinking, self.settings, now), (
            Action(ActionKind.ACCEPT_TRANSCRIPT),
        )

    def _on_assistant_response_start(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        if state.phase is ConversationPhase.CLOSING:
            return state, (
                Action(ActionKind.CANCEL_ASSISTANT),
                Action(ActionKind.SUPPRESS_LATE_AUDIO),
            )
        if state.suppressed_response:
            return state, (Action(ActionKind.SUPPRESS_LATE_AUDIO),)
        speaking = _enter(
            replace(
                state,
                active_responses=1,
                silence_deadline=None,
                assistant_limit_deadline=now + self.settings.max_assistant_turn_s,
                pending_bridge=False,
                tool_bridge_deadline=None,
            ),
            ConversationPhase.ASSISTANT_SPEAKING,
        )
        return _arm_idle(speaking, self.settings, now), ()

    def _on_assistant_audio_start(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        return self._on_assistant_response_start(state, now, data)

    def _on_assistant_response_done(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        cleared = replace(
            state,
            active_responses=0,
            assistant_limit_deadline=None,
            suppressed_response=False,
        )
        if (
            cleared.user_speaking
            or cleared.phase is ConversationPhase.USER_SPEAKING
            or cleared.phase is ConversationPhase.CLOSING
        ):
            return cleared, ()
        waiting = _enter(cleared, ConversationPhase.WAITING_FOR_USER)
        return _arm_silence(
            _arm_idle(waiting, self.settings, now), self.settings, now
        ), ()

    def _on_interrupt(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        return self._on_user_speech_start(state, now, data)

    def _on_tool_request(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        if state.phase is ConversationPhase.CLOSING:
            return state, ()
        running = _enter(
            replace(
                state,
                active_tool=True,
                tool_succeeded=False,
                pending_bridge=False,
                tool_bridge_deadline=now + self.settings.tool_bridge_after_s,
                silence_deadline=None,
            ),
            ConversationPhase.TOOL_RUNNING,
        )
        return _arm_idle(running, self.settings, now), ()

    def _on_tool_result(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        success = bool(data.get("success"))
        actions: list[Action] = []
        after = replace(
            state,
            active_tool=False,
            tool_succeeded=success,
            pending_bridge=False,
            tool_bridge_deadline=None,
        )
        if not success:
            actions.append(
                Action(
                    ActionKind.SPEAK_TOOL_FAILURE,
                    text=self.settings.tool_failure_phrase,
                )
            )
            after = _enter(
                replace(after, active_responses=1),
                ConversationPhase.ASSISTANT_SPEAKING,
            )
        else:
            after = _enter(after, ConversationPhase.WAITING_FOR_USER)
            after = _arm_silence(after, self.settings, now)
        return _arm_idle(after, self.settings, now), tuple(actions)

    def _on_provider_disconnect(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return _finish(state, "failed", "agent_error")

    def _on_provider_error(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return _finish(state, "failed", "agent_error")

    def _on_participant_disconnect(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return _finish(state, "completed", "user_hangup")

    def _on_hangup(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return _finish(state, "completed", "user_hangup")

    def _on_silence_timer(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = data
        if state.user_speaking or state.phase is ConversationPhase.USER_SPEAKING:
            return _clear_silence(state), ()
        if state.phase in {
            ConversationPhase.ASSISTANT_SPEAKING,
            ConversationPhase.TOOL_RUNNING,
            ConversationPhase.THINKING,
            ConversationPhase.CLOSING,
        }:
            return _clear_silence(state), ()
        if state.silence_prompt_count >= self.settings.max_silence_prompts:
            closing, finish_actions = _finish(state, "completed", "completed")
            return closing, (
                Action(
                    ActionKind.SPEAK_POLITE_CLOSE,
                    text=self.settings.polite_close_phrase,
                ),
                *finish_actions,
            )
        index = min(state.silence_prompt_count, len(self.settings.silence_prompts) - 1)
        phrase = self.settings.silence_prompts[index]
        prompted = _arm_silence(
            _arm_idle(
                replace(
                    state,
                    silence_prompt_count=state.silence_prompt_count + 1,
                    active_responses=1,
                ),
                self.settings,
                now,
            ),
            self.settings,
            now,
        )
        return prompted, (Action(ActionKind.SPEAK_SILENCE_PROMPT, text=phrase),)

    def _on_idle_timer(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        if state.active_tool or state.phase is ConversationPhase.TOOL_RUNNING:
            return state, ()
        if (
            state.phase is ConversationPhase.ASSISTANT_SPEAKING
            and state.active_responses
        ):
            return state, ()
        if state.user_speaking:
            return state, ()
        return _finish(state, "completed", "completed")

    def _on_session_timer(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        closing, finish_actions = _finish(state, "completed", "completed")
        return closing, (
            Action(
                ActionKind.SPEAK_SESSION_LIMIT, text=self.settings.session_limit_phrase
            ),
            *finish_actions,
        )

    def _on_assistant_limit_timer(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        if state.phase is not ConversationPhase.ASSISTANT_SPEAKING:
            return replace(state, assistant_limit_deadline=None), ()
        waiting = _enter(
            replace(
                state,
                active_responses=0,
                assistant_limit_deadline=None,
                suppressed_response=True,
            ),
            ConversationPhase.WAITING_FOR_USER,
        )
        return _arm_silence(
            _arm_idle(waiting, self.settings, now), self.settings, now
        ), (
            Action(ActionKind.CANCEL_ASSISTANT),
            Action(ActionKind.SUPPRESS_LATE_AUDIO),
        )

    def _on_tool_bridge_timer(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        if state.phase is not ConversationPhase.TOOL_RUNNING or not state.active_tool:
            return replace(state, tool_bridge_deadline=None), ()
        if state.pending_bridge:
            return state, ()
        bridged = replace(state, pending_bridge=True, tool_bridge_deadline=None)
        return bridged, (
            Action(ActionKind.SPEAK_TOOL_BRIDGE, text=self.settings.tool_bridge_phrase),
        )

    def _on_reconnect_attempt(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return state, ()

    def _on_goodbye_said(
        self, state: ConversationState, now: float, data: dict[str, Any]
    ) -> tuple[ConversationState, tuple[Action, ...]]:
        _ = now, data
        return _finish(state, "completed", "completed")


class ConversationDirector:
    """Applies policy, expires FakeClock timers, and owns one timer task."""

    def __init__(
        self,
        settings: VoiceUxSettings | None = None,
        *,
        clock: Clock | None = None,
        trace: SessionTrace | None = None,
        sleep: Callable[[float], Coroutine[Any, Any, None]] | None = None,
        on_actions: Callable[[tuple[Action, ...]], None] | None = None,
    ) -> None:
        self.settings = settings or VoiceUxSettings()
        self._policy = ConversationPolicy(self.settings)
        self._clock: Clock = clock or SystemClock()
        self._trace = trace
        self._sleep = sleep or asyncio.sleep
        self._on_actions = on_actions
        self._state = ConversationState()
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._recent_actions: list[Action] = []

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def phase(self) -> ConversationPhase:
        return self._state.phase

    @property
    def greeting_count(self) -> int:
        return self._state.greeting_count

    @property
    def silence_prompt_count(self) -> int:
        return self._state.silence_prompt_count

    @property
    def finish_count(self) -> int:
        return self._state.finish_count

    @property
    def recent_actions(self) -> tuple[Action, ...]:
        return tuple(self._recent_actions)

    def handle(
        self,
        event: ConversationEvent,
        now: float | None = None,
        **payload: Any,
    ) -> tuple[Action, ...]:
        timestamp = self._clock.monotonic() if now is None else now
        next_state, actions = self._policy.apply(self._state, event, timestamp, payload)
        self._state = next_state
        self._note(event, actions)
        self._wakeup.set()
        if actions and self._on_actions is not None:
            self._on_actions(actions)
        return actions

    def expire_due(self, now: float | None = None) -> tuple[Action, ...]:
        timestamp = self._clock.monotonic() if now is None else now
        due: list[ConversationEvent] = []
        if (
            self._state.session_deadline is not None
            and timestamp >= self._state.session_deadline
        ):
            due.append(ConversationEvent.SESSION_TIMER)
        if (
            self._state.assistant_limit_deadline is not None
            and timestamp >= self._state.assistant_limit_deadline
        ):
            due.append(ConversationEvent.ASSISTANT_LIMIT_TIMER)
        if (
            self._state.tool_bridge_deadline is not None
            and timestamp >= self._state.tool_bridge_deadline
        ):
            due.append(ConversationEvent.TOOL_BRIDGE_TIMER)
        if (
            self._state.idle_deadline is not None
            and timestamp >= self._state.idle_deadline
        ):
            due.append(ConversationEvent.IDLE_TIMER)
        if (
            self._state.silence_deadline is not None
            and timestamp >= self._state.silence_deadline
        ):
            due.append(ConversationEvent.SILENCE_TIMER)
        collected: list[Action] = []
        for event in due:
            collected.extend(self.handle(event, timestamp))
            if self._state.phase is ConversationPhase.CLOSED:
                break
        return tuple(collected)

    def seconds_until_deadline(self, now: float | None = None) -> float | None:
        timestamp = self._clock.monotonic() if now is None else now
        deadlines = [
            value
            for value in (
                self._state.silence_deadline,
                self._state.idle_deadline,
                self._state.session_deadline,
                self._state.tool_bridge_deadline,
                self._state.assistant_limit_deadline,
            )
            if value is not None
        ]
        if not deadlines:
            return None
        return max(0.0, min(deadlines) - timestamp)

    def start_background(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._loop(), name="conversation-ux-timers"
            )

    async def aclose(self) -> None:
        self._wakeup.set()
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _loop(self) -> None:
        try:
            while self._state.phase is not ConversationPhase.CLOSED:
                delay = self.seconds_until_deadline()
                self._wakeup.clear()
                if delay is None:
                    await self._wakeup.wait()
                    continue
                if delay <= 0:
                    self.expire_due()
                    await self._sleep(0)
                    continue
                try:
                    await asyncio.wait_for(self._wakeup.wait(), timeout=delay)
                except TimeoutError:
                    self.expire_due()
                except asyncio.CancelledError:
                    raise
        except asyncio.CancelledError:
            return

    def _note(self, event: ConversationEvent, actions: tuple[Action, ...]) -> None:
        if self._trace is not None:
            mark = _TRACE_FOR_EVENT.get(event)
            if mark is not None and mark in OBSERVED_EVENTS:
                self._trace.mark(mark)
            for action in actions:
                mark = _TRACE_FOR_ACTION.get(action.kind)
                if mark is not None and mark in OBSERVED_EVENTS:
                    self._trace.mark(mark)
        if actions:
            self._recent_actions.extend(actions)
            overflow = len(self._recent_actions) - _MAX_ACTION_LOG
            if overflow > 0:
                del self._recent_actions[:overflow]


_TRACE_FOR_EVENT = {
    ConversationEvent.SESSION_READY: "runtime_ready",
    ConversationEvent.USER_SPEECH_START: "first_user_audio",
    ConversationEvent.USER_SPEECH_END: "user_speech_end",
    ConversationEvent.TRANSCRIPT_FINAL: "final_user_transcript",
    ConversationEvent.ASSISTANT_RESPONSE_START: "assistant_response_start",
    ConversationEvent.ASSISTANT_AUDIO_START: "first_assistant_audio",
    ConversationEvent.INTERRUPT: "interrupt_start",
    ConversationEvent.TOOL_REQUEST: "tool_request",
    ConversationEvent.TOOL_RESULT: "tool_result",
    ConversationEvent.PROVIDER_DISCONNECT: "provider_disconnect",
    ConversationEvent.IDLE_TIMER: "idle_timeout",
    ConversationEvent.SESSION_TIMER: "session_timeout",
    ConversationEvent.HANGUP: "session_close",
    ConversationEvent.PARTICIPANT_DISCONNECT: "session_close",
}

_TRACE_FOR_ACTION = {
    ActionKind.SPEAK_GREETING: "greeting_started",
    ActionKind.SKIP_GREETING: "greeting_skipped",
    ActionKind.SPEAK_SILENCE_PROMPT: "silence_prompt",
    ActionKind.CANCEL_ASSISTANT: "response_cancelled",
    ActionKind.REQUEST_FINISH: "finish_start",
}


def advance_and_expire(
    director: ConversationDirector, seconds: float
) -> tuple[Action, ...]:
    """Test helper: FakeClock.advance then expire timers. Never sleeps."""

    clock = director._clock
    if not isinstance(clock, FakeClock):
        raise TypeError("advance_and_expire requires FakeClock")
    clock.advance(seconds)
    return director.expire_due()
