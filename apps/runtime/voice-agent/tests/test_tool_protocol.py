from urllib.parse import quote

from yino_voice_agent.tool_protocol import (
    encode_tool_marker,
    parse_tool_marker,
    split_assistant_final,
)


def test_percent_encoded_marker_round_trip() -> None:
    marker = encode_tool_marker(
        "create_appointment",
        {"patient_name": "王女士", "phone": "13800138000", "service": "洁牙"},
    )
    parsed = parse_tool_marker(marker)
    assert parsed is not None
    assert parsed.tool_name == "create_appointment"
    assert parsed.arguments["patient_name"] == "王女士"
    assert parsed.arguments["phone"] == "13800138000"


def test_split_strips_last_line_marker_only() -> None:
    encoded_name = quote("王女士", safe="")
    text = (
        "已记下您的意向，工作人员会联系确认档期。\n"
        f"[[tool:create_appointment|patient_name={encoded_name}|phone=13800138000|service=洁牙]]"
    )
    turn = split_assistant_final(text)
    assert turn.spoken == "已记下您的意向，工作人员会联系确认档期。"
    assert "[[tool:" not in turn.spoken
    assert turn.marker is not None
    assert turn.marker.arguments["patient_name"] == "王女士"


def test_partial_marker_is_ignored() -> None:
    turn = split_assistant_final("请稍等\n[[tool:create_appointment|phone=138")
    assert turn.marker is None
    assert "请稍等" in turn.spoken


def test_unknown_tool_is_ignored() -> None:
    turn = split_assistant_final("好的\n[[tool:transfer_human|phone=13800138000]]")
    assert turn.marker is None
