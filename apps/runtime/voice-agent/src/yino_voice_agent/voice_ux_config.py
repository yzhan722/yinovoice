"""Runtime-owned Voice UX timers and endpointing. Not a Control Plane contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NoReturn

PROVIDER_DISCONNECT_POLICY = "FAIL_SESSION_ON_PROVIDER_DISCONNECT"
CONTEXT_POLICY = "PROVIDER_MANAGED_NO_CLIENT_TRUNCATE"
ENDPOINT_AUTHORITY = "qwen_server_vad"

# Telephone-safe defaults. Long consults must still fit under max_session_s.
DEFAULT_INITIAL_SILENCE_S = 8.0
DEFAULT_FOLLOWUP_SILENCE_S = 12.0
DEFAULT_MAX_SILENCE_PROMPTS = 2
DEFAULT_MAX_IDLE_S = 180.0
DEFAULT_MAX_SESSION_S = 1800.0
DEFAULT_TOOL_BRIDGE_AFTER_S = 1.0
DEFAULT_MAX_ASSISTANT_TURN_S = 45.0
DEFAULT_ENDPOINT_SILENCE_MS = 450
DEFAULT_ENDPOINT_THRESHOLD = 0.35

SILENCE_PROMPTS = (
    "您好，请问还在吗？",
    "还在的话我继续帮您。",
)
POLITE_CLOSE_PHRASE = "这边先不打扰您了，再见。"
SESSION_LIMIT_PHRASE = "这次通话有点久了，我这边先结束，需要请再拨打。"
TOOL_BRIDGE_PHRASE = "我帮您查一下。"
TOOL_FAILURE_PHRASE = "我这边暂时查不到，稍后再试一次好吗？"


def _config_error(message: str) -> NoReturn:
    from .config import ConfigurationError

    raise ConfigurationError(message)


def _read_float(
    values: Mapping[str, str], name: str, default: float, *, lo: float, hi: float
) -> float:
    raw = values.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        _config_error(f"{name} must be a number")
    if not lo <= value <= hi:
        _config_error(f"{name} must be between {lo} and {hi}")
    return value


def _read_int(
    values: Mapping[str, str], name: str, default: int, *, lo: int, hi: int
) -> int:
    raw = values.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip(), 10)
    except ValueError:
        _config_error(f"{name} must be an integer")
    if not lo <= value <= hi:
        _config_error(f"{name} must be between {lo} and {hi}")
    return value


@dataclass(frozen=True, slots=True)
class VoiceUxSettings:
    """Validated Runtime Voice UX knobs. Fail closed on invalid env values."""

    initial_silence_s: float = DEFAULT_INITIAL_SILENCE_S
    followup_silence_s: float = DEFAULT_FOLLOWUP_SILENCE_S
    max_silence_prompts: int = DEFAULT_MAX_SILENCE_PROMPTS
    max_idle_s: float = DEFAULT_MAX_IDLE_S
    max_session_s: float = DEFAULT_MAX_SESSION_S
    tool_bridge_after_s: float = DEFAULT_TOOL_BRIDGE_AFTER_S
    max_assistant_turn_s: float = DEFAULT_MAX_ASSISTANT_TURN_S
    endpoint_silence_ms: int = DEFAULT_ENDPOINT_SILENCE_MS
    endpoint_threshold: float = DEFAULT_ENDPOINT_THRESHOLD
    silence_prompts: tuple[str, ...] = SILENCE_PROMPTS
    polite_close_phrase: str = POLITE_CLOSE_PHRASE
    session_limit_phrase: str = SESSION_LIMIT_PHRASE
    tool_bridge_phrase: str = TOOL_BRIDGE_PHRASE
    tool_failure_phrase: str = TOOL_FAILURE_PHRASE
    provider_disconnect_policy: str = PROVIDER_DISCONNECT_POLICY
    context_policy: str = CONTEXT_POLICY
    endpoint_authority: str = ENDPOINT_AUTHORITY

    def __post_init__(self) -> None:
        if self.max_session_s < self.max_idle_s:
            _config_error("VOICE_UX_MAX_SESSION_S must be >= VOICE_UX_MAX_IDLE_S")
        if self.max_silence_prompts > 0 and not self.silence_prompts:
            _config_error("silence prompts are required")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> VoiceUxSettings:
        import os

        values: Mapping[str, str] = os.environ if env is None else env
        settings = cls(
            initial_silence_s=_read_float(
                values,
                "VOICE_UX_INITIAL_SILENCE_S",
                DEFAULT_INITIAL_SILENCE_S,
                lo=2.0,
                hi=60.0,
            ),
            followup_silence_s=_read_float(
                values,
                "VOICE_UX_FOLLOWUP_SILENCE_S",
                DEFAULT_FOLLOWUP_SILENCE_S,
                lo=2.0,
                hi=60.0,
            ),
            max_silence_prompts=_read_int(
                values,
                "VOICE_UX_MAX_SILENCE_PROMPTS",
                DEFAULT_MAX_SILENCE_PROMPTS,
                lo=1,
                hi=4,
            ),
            max_idle_s=_read_float(
                values, "VOICE_UX_MAX_IDLE_S", DEFAULT_MAX_IDLE_S, lo=30.0, hi=3600.0
            ),
            max_session_s=_read_float(
                values,
                "VOICE_UX_MAX_SESSION_S",
                DEFAULT_MAX_SESSION_S,
                lo=60.0,
                hi=7200.0,
            ),
            tool_bridge_after_s=_read_float(
                values,
                "VOICE_UX_TOOL_BRIDGE_AFTER_S",
                DEFAULT_TOOL_BRIDGE_AFTER_S,
                lo=0.4,
                hi=5.0,
            ),
            max_assistant_turn_s=_read_float(
                values,
                "VOICE_UX_MAX_ASSISTANT_TURN_S",
                DEFAULT_MAX_ASSISTANT_TURN_S,
                lo=10.0,
                hi=120.0,
            ),
            endpoint_silence_ms=_read_int(
                values,
                "VOICE_UX_ENDPOINT_SILENCE_MS",
                DEFAULT_ENDPOINT_SILENCE_MS,
                lo=200,
                hi=2000,
            ),
            endpoint_threshold=_read_float(
                values,
                "VOICE_UX_ENDPOINT_THRESHOLD",
                DEFAULT_ENDPOINT_THRESHOLD,
                lo=0.1,
                hi=0.9,
            ),
        )
        return settings
