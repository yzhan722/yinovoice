import json

import pytest

from yino_voice_agent.qwen_realtime_protocol import (
    QwenProtocolError,
    QwenSessionOptions,
    build_audio_append,
    build_response_cancel,
    build_response_create,
    build_session_update,
    decode_audio_delta,
    parse_server_event,
)


def test_session_update_enables_audio_text_and_smart_turn() -> None:
    event = build_session_update(
        QwenSessionOptions(
            instructions="使用标准普通话自然回答。",
            voice="longanqian",
        )
    )

    assert event["type"] == "session.update"
    session = event["session"]
    assert session["modalities"] == ["text", "audio"]
    assert session["voice"] == "longanqian"
    assert session["instructions"] == "使用标准普通话自然回答。"
    assert session["input_audio_format"] == "pcm"
    assert session["output_audio_format"] == "pcm"
    assert session["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.35,
        "silence_duration_ms": 450,
    }


def test_audio_append_base64_encodes_pcm() -> None:
    assert build_audio_append(b"\x01\x02") == {
        "type": "input_audio_buffer.append",
        "audio": "AQI=",
    }


def test_response_events_request_audio_and_text_or_cancel() -> None:
    assert build_response_create() == {"type": "response.create"}
    assert build_response_cancel() == {"type": "response.cancel"}


def test_valid_server_event_is_parsed() -> None:
    raw = '{"type":"response.done","response":{"id":"resp-1"}}'
    assert parse_server_event(raw) == {
        "type": "response.done",
        "response": {"id": "resp-1"},
    }


def test_audio_delta_decodes_even_nonempty_pcm() -> None:
    event = {"type": "response.audio.delta", "delta": "AQA="}
    assert decode_audio_delta(event) == b"\x01\x00"


def test_audio_delta_rejects_odd_pcm_without_echoing_payload() -> None:
    event = {"type": "response.audio.delta", "delta": "AA=="}
    with pytest.raises(QwenProtocolError) as error:
        decode_audio_delta(event)
    assert "AA==" not in str(error.value)


@pytest.mark.parametrize("delta", ["", "not-base64!"])
def test_audio_delta_rejects_empty_or_invalid_base64_without_echoing_payload(
    delta: str,
) -> None:
    with pytest.raises(QwenProtocolError) as error:
        decode_audio_delta({"type": "response.audio.delta", "delta": delta})
    if delta:
        assert delta not in str(error.value)


@pytest.mark.parametrize(
    "raw",
    [
        '{"authorization":"secret-value"}',
        '["secret-value"]',
        "not-json-secret-value",
    ],
)
def test_invalid_event_does_not_echo_secret_fields(raw: str) -> None:
    with pytest.raises(QwenProtocolError) as error:
        parse_server_event(raw)
    assert "secret-value" not in str(error.value)


def test_invalid_json_discards_payload_from_entire_exception_chain() -> None:
    raw = '{"authorization":"private-material"'

    with pytest.raises(QwenProtocolError) as caught:
        parse_server_event(raw)

    error: BaseException | None = caught.value
    while error is not None:
        assert "private-material" not in str(error)
        assert not isinstance(error, json.JSONDecodeError)
        error = error.__cause__ or error.__context__
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
