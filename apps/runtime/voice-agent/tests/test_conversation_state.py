from __future__ import annotations

import pytest

from yino_voice_agent.conversation import (
    ConversationPhase,
    ConversationState,
    IllegalConversationTransitionError,
    assert_invariants,
    can_transition,
    force_transition,
)


def test_closed_cannot_return_to_speaking() -> None:
    closed = ConversationState(phase=ConversationPhase.CLOSED, finish_count=1)
    with pytest.raises(IllegalConversationTransitionError):
        force_transition(closed, ConversationPhase.ASSISTANT_SPEAKING)
    assert not can_transition(ConversationPhase.CLOSED, ConversationPhase.TOOL_RUNNING)


def test_closing_cannot_start_a_tool() -> None:
    closing = ConversationState(phase=ConversationPhase.CLOSING)
    with pytest.raises(IllegalConversationTransitionError):
        force_transition(closing, ConversationPhase.TOOL_RUNNING)
    assert can_transition(ConversationPhase.CLOSING, ConversationPhase.CLOSED)


def test_waiting_can_enter_user_or_assistant() -> None:
    waiting = ConversationState(phase=ConversationPhase.WAITING_FOR_USER)
    assert force_transition(waiting, ConversationPhase.USER_SPEAKING).phase is (
        ConversationPhase.USER_SPEAKING
    )
    assert force_transition(waiting, ConversationPhase.ASSISTANT_SPEAKING).phase is (
        ConversationPhase.ASSISTANT_SPEAKING
    )


def test_invariants_reject_duplicate_greeting_and_finish() -> None:
    with pytest.raises(AssertionError, match="greeting"):
        assert_invariants(ConversationState(greeting_count=2))
    with pytest.raises(AssertionError, match="finish"):
        assert_invariants(ConversationState(finish_count=2))
    with pytest.raises(AssertionError, match="CLOSED"):
        assert_invariants(ConversationState(phase=ConversationPhase.CLOSED))
