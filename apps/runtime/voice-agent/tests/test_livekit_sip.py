from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sip_fakes import (
    CALLEE_A,
    CALLER_A,
    sip_attributes,
    sip_kind,
    sip_participant,
    web_kind,
)

from yino_voice_agent.runtime_config import RuntimeConfigurationError
from yino_voice_agent.session_trace import FakeClock, SessionTrace, redact_phone_numbers
from yino_voice_agent.telephony import (
    FrozenUtcClock,
    coerce_presented_number_to_e164,
    is_sip_participant,
    normalize_livekit_sip_participant,
)
from yino_voice_agent.telephony import livekit_sip as livekit_sip_module


def test_livekit_sip_adapter_does_not_use_fake_seen_ids() -> None:
    source = livekit_sip_module.__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")
    assert "FakeInboundProvider" not in text
    assert "_seen_ids" not in text


def test_sip_kind_and_web_kind() -> None:
    assert is_sip_participant(sip_participant())
    assert is_sip_participant(SimpleNamespace(kind=3, attributes={}))
    assert not is_sip_participant(None)
    assert not is_sip_participant(
        SimpleNamespace(kind=web_kind(), attributes=sip_attributes())
    )


def test_normalize_uses_injected_clock_and_call_id_full() -> None:
    instant = datetime(2026, 9, 1, 4, 0, tzinfo=UTC)
    call = normalize_livekit_sip_participant(
        sip_participant(),
        room_name="yino-sip-room-1",
        clock=FrozenUtcClock(instant),
    )
    assert call.provider == "livekit_sip"
    assert call.provider_call_id == "provider-call-full-1"
    assert call.caller_number == CALLER_A
    assert call.callee_number == CALLEE_A
    assert call.connected_at == instant
    assert call.room_name == "yino-sip-room-1"
    assert call.trunk_id == "ST_PLACEHOLDER"
    assert call.rule_id == "SDR_PLACEHOLDER"


def test_normalize_falls_back_to_sip_call_id() -> None:
    call = normalize_livekit_sip_participant(
        sip_participant(
            attributes=sip_attributes(call_id_full=None, call_id="lk-only")
        ),
        room_name="room-fallback",
        clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
    )
    assert call.provider_call_id == "lk-only"


def test_normalize_rejects_missing_call_ids() -> None:
    with pytest.raises(RuntimeConfigurationError, match=r"sip\.callID"):
        normalize_livekit_sip_participant(
            sip_participant(
                attributes=sip_attributes(call_id_full=None, call_id=None)
            ),
            room_name="room-bad",
            clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
        )


def test_coerce_china_pstn_presentation_to_e164() -> None:
    assert coerce_presented_number_to_e164("+8613800138000") == "+8613800138000"
    assert coerce_presented_number_to_e164("13800138000") == "+8613800138000"
    assert coerce_presented_number_to_e164("051987654321") == "+8651987654321"
    assert coerce_presented_number_to_e164("01012345678") == "+861012345678"
    assert coerce_presented_number_to_e164("400-123-4567") == "+864001234567"
    assert coerce_presented_number_to_e164("008613800138000") == "+8613800138000"
    assert coerce_presented_number_to_e164("HidePhoneNumber") is None
    assert coerce_presented_number_to_e164("not-a-number") is None


def test_normalize_accepts_changzhou_landline_and_mobile_presentation() -> None:
    clock = FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC))
    landline = normalize_livekit_sip_participant(
        sip_participant(
            attributes=sip_attributes(callee="051987654321", caller="13800138000")
        ),
        room_name="room-cz",
        clock=clock,
    )
    assert landline.callee_number == "+8651987654321"
    assert landline.caller_number == "+8613800138000"


def test_normalize_still_rejects_unusable_callee() -> None:
    with pytest.raises(RuntimeConfigurationError, match=r"E\.164"):
        normalize_livekit_sip_participant(
            sip_participant(attributes=sip_attributes(callee="internal-ext-12")),
            room_name="room-ext",
            clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
        )


def test_normalize_requires_callee_and_does_not_use_caller() -> None:
    with pytest.raises(RuntimeConfigurationError, match="callee"):
        normalize_livekit_sip_participant(
            sip_participant(attributes=sip_attributes(callee=None)),
            room_name="room-no-callee",
            clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
        )


def test_anonymous_and_hidden_caller_are_none() -> None:
    clock = FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC))
    hidden = normalize_livekit_sip_participant(
        sip_participant(attributes=sip_attributes(caller="HidePhoneNumber")),
        room_name="room-hidden",
        clock=clock,
    )
    missing = normalize_livekit_sip_participant(
        sip_participant(attributes=sip_attributes(caller=None)),
        room_name="room-anon",
        clock=clock,
    )
    assert hidden.caller_number is None
    assert missing.caller_number is None
    assert hidden.callee_number == CALLEE_A


def test_twilio_call_sid_is_not_the_provider_call_id() -> None:
    attributes = sip_attributes(call_id_full="full-id", call_id="lk-id")
    attributes["sip.twilio.callSid"] = "CA_PLACEHOLDER"
    call = normalize_livekit_sip_participant(
        sip_participant(attributes=attributes),
        room_name="room-twilio",
        clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
    )
    assert call.provider_call_id == "full-id"
    assert call.provider == "livekit_sip"


def test_normalize_logs_do_not_include_phone_numbers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    room = f"call-{CALLER_A}_suffix"
    call_id = f"sip-{CALLER_A}@host.example"
    normalize_livekit_sip_participant(
        sip_participant(attributes=sip_attributes(call_id_full=call_id)),
        room_name=room,
        clock=FrozenUtcClock(datetime(2026, 9, 1, tzinfo=UTC)),
    )
    combined = caplog.text
    assert CALLER_A not in combined
    assert CALLEE_A not in combined
    assert call_id not in combined
    assert redact_phone_numbers(room) in combined or "room=" in combined


def test_session_trace_redacts_call_id(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    trace = SessionTrace(
        session_id="s-1",
        call_id=f"id-{CALLER_A}",
        clock=FakeClock(),
    )
    trace.mark("session_start")
    assert CALLER_A not in caplog.text


def test_redact_masks_e164_and_bare_msisdn_in_room_names() -> None:
    plus = redact_phone_numbers(f"call-{CALLER_A}_suffix")
    bare = redact_phone_numbers("call-61411111111_suffix")
    assert CALLER_A not in plus
    assert "61411111111" not in bare
    assert plus.startswith("call-")
    assert bare.startswith("call-")


def test_frozen_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FrozenUtcClock(datetime(2026, 9, 1))


def test_kind_name_sip_alias() -> None:
    participant = SimpleNamespace(
        kind=SimpleNamespace(name="SIP", value=3),
        attributes=sip_attributes(),
    )
    assert is_sip_participant(participant)
    assert sip_kind().value == 3
