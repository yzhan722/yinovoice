from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, unquote

ToolName = Literal["check_availability", "create_appointment", "create_callback"]

_ALLOWED: set[str] = {
    "check_availability",
    "create_appointment",
    "create_callback",
}
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(_ALLOWED)
IDEMPOTENT_TOOL_NAMES: frozenset[str] = frozenset({"check_availability"})
_MARKER_PREFIX = "[[tool:"
_MARKER_SUFFIX = "]]"


@dataclass(frozen=True, slots=True)
class ParsedToolMarker:
    tool_name: ToolName
    arguments: dict[str, str]
    raw: str


@dataclass(frozen=True, slots=True)
class SpokenTurn:
    spoken: str
    marker: ParsedToolMarker | None


def encode_tool_marker(tool_name: ToolName, arguments: dict[str, str]) -> str:
    parts = [f"tool:{tool_name}"]
    for key, value in arguments.items():
        parts.append(f"{key}={quote(value, safe='')}")
    return "[[" + "|".join(parts) + "]]"


def parse_tool_marker(line: str) -> ParsedToolMarker | None:
    text = line.strip()
    if not (text.startswith(_MARKER_PREFIX) and text.endswith(_MARKER_SUFFIX)):
        return None
    inner = text[len(_MARKER_PREFIX) : -len(_MARKER_SUFFIX)]
    if "|" in inner:
        name, *pairs = inner.split("|")
    else:
        name, pairs = inner, []
    if name not in _ALLOWED:
        return None
    arguments: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            return None
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if not key:
            return None
        arguments[key] = unquote(raw_value)
    return ParsedToolMarker(tool_name=name, arguments=arguments, raw=text)  # type: ignore[arg-type]


def split_assistant_final(text: str) -> SpokenTurn:
    blob = (text or "").replace("\r\n", "\n").strip()
    if not blob:
        return SpokenTurn(spoken="", marker=None)
    lines = blob.split("\n")
    last = lines[-1].strip()
    marker = parse_tool_marker(last)
    if marker is not None:
        spoken = "\n".join(lines[:-1]).strip()
        return SpokenTurn(spoken=spoken, marker=marker)
    if last.startswith(_MARKER_PREFIX):
        spoken = "\n".join(lines[:-1]).strip()
        return SpokenTurn(spoken=spoken, marker=None)
    return SpokenTurn(spoken=blob, marker=None)
