from yino_voice_agent.usage import CallUsageAccumulator, parse_response_usage


def _done_event() -> dict[str, object]:
    return {
        "type": "response.done",
        "response": {
            "id": "resp-1",
            "usage": {
                "total_tokens": 90,
                "input_tokens": 58,
                "output_tokens": 32,
                "input_tokens_details": {
                    "text_tokens": 10,
                    "audio_tokens": 48,
                },
                "output_tokens_details": {
                    "text_tokens": 0,
                    "audio_tokens": 32,
                },
            },
        },
    }


def test_parse_response_done_usage_splits_audio_and_text() -> None:
    parsed = parse_response_usage(_done_event())
    assert parsed is not None
    assert parsed.input_audio_tokens == 48
    assert parsed.input_text_tokens == 10
    assert parsed.output_audio_tokens == 32
    assert parsed.output_text_tokens == 0
    assert parsed.total_tokens == 90
    assert parsed.response_count == 1


def test_parse_ignores_response_done_without_usage() -> None:
    event = {"type": "response.done", "response": {"id": "x"}}
    assert parse_response_usage(event) is None


def test_accumulator_sums_distinct_responses() -> None:
    acc = CallUsageAccumulator()
    first = _done_event()
    second = _done_event()
    second["response"]["id"] = "resp-2"
    acc.add(first)
    acc.add(second)
    acc.add({"type": "response.done", "response": {"id": "empty"}})
    snapshot = acc.snapshot()
    assert snapshot.response_count == 2
    assert snapshot.total_tokens == 180
    assert snapshot.input_audio_tokens == 96
    assert acc.snapshot().total_tokens == 180


def test_duplicate_response_done_id_is_not_double_counted() -> None:
    acc = CallUsageAccumulator()
    acc.add(_done_event())
    acc.add(_done_event())
    snapshot = acc.snapshot()
    assert snapshot.response_count == 1
    assert snapshot.total_tokens == 90
