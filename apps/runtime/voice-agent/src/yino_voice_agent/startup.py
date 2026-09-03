"""Static worker startup validation. Not a SIP probe and not business config."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from .config import (
    DEFAULT_LIVEKIT_AGENT_NAME,
    ConfigurationError,
    VoiceSettings,
)
from .voice_ux_config import VoiceUxSettings

RuntimeMode = Literal["local-dev", "synthetic-test", "stage"]
DEFAULT_DRAIN_TIMEOUT_S = 30.0
DEFAULT_OPS_HOST = "127.0.0.1"
DEFAULT_OPS_PORT = 8091


def _present(values: Mapping[str, str], name: str) -> str | None:
    raw = values.get(name)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip()


def _missing(name: str) -> None:
    raise ConfigurationError(f"{name} missing")


def _read_bool(values: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = values.get(name)
    if raw is None or not str(raw).strip():
        return default
    normalized = str(raw).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _read_float(
    values: Mapping[str, str], name: str, default: float, *, lo: float, hi: float
) -> float:
    raw = _present(values, name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigurationError(f"{name} must be a number") from None
    if not lo <= value <= hi:
        raise ConfigurationError(f"{name} must be between {lo} and {hi}")
    return value


def _read_int(
    values: Mapping[str, str], name: str, default: int, *, lo: int, hi: int
) -> int:
    raw = _present(values, name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError:
        raise ConfigurationError(f"{name} must be an integer") from None
    if not lo <= value <= hi:
        raise ConfigurationError(f"{name} must be between {lo} and {hi}")
    return value


def parse_runtime_mode(values: Mapping[str, str]) -> RuntimeMode:
    raw = _present(values, "VOICE_RUNTIME_MODE") or "local-dev"
    if raw not in {"local-dev", "synthetic-test", "stage"}:
        raise ConfigurationError(
            "VOICE_RUNTIME_MODE must be local-dev, synthetic-test, or stage"
        )
    return raw  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class WorkerStartupSettings:
    mode: RuntimeMode
    livekit_url_configured: bool
    livekit_api_key_configured: bool
    livekit_api_secret_configured: bool
    livekit_agent_name: str
    platform_api_url_configured: bool
    phone_lookup_token_configured: bool
    dashscope_api_key_configured: bool
    allow_empty_dispatch_metadata_local_dev: bool
    drain_timeout_s: float
    ops_enabled: bool
    ops_host: str
    ops_port: int
    provider: VoiceSettings | None

    def sanitized_summary(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "livekit_url": "configured" if self.livekit_url_configured else "missing",
            "livekit_api_key": (
                "configured" if self.livekit_api_key_configured else "missing"
            ),
            "livekit_api_secret": (
                "configured" if self.livekit_api_secret_configured else "missing"
            ),
            "livekit_agent_name": self.livekit_agent_name,
            "platform_api_url": (
                "configured" if self.platform_api_url_configured else "missing"
            ),
            "phone_lookup_token": (
                "configured" if self.phone_lookup_token_configured else "missing"
            ),
            "dashscope_api_key": (
                "configured" if self.dashscope_api_key_configured else "missing"
            ),
            "allow_empty_dispatch_metadata_local_dev": (
                self.allow_empty_dispatch_metadata_local_dev
            ),
            "drain_timeout_s": self.drain_timeout_s,
            "ops_enabled": self.ops_enabled,
            "ops_host": self.ops_host,
            "ops_port": self.ops_port,
        }

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        mode: RuntimeMode | None = None,
    ) -> WorkerStartupSettings:
        values: Mapping[str, str] = os.environ if env is None else env
        resolved = mode or parse_runtime_mode(values)
        allow_empty = _read_bool(
            values, "ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV", False
        )
        drain_timeout_s = _read_float(
            values,
            "VOICE_WORKER_DRAIN_TIMEOUT_SECONDS",
            DEFAULT_DRAIN_TIMEOUT_S,
            lo=1.0,
            hi=300.0,
        )
        ops_enabled = _read_bool(values, "VOICE_OPS_ENABLED", False)
        ops_host = _present(values, "VOICE_OPS_HOST") or DEFAULT_OPS_HOST
        if ops_host.strip() == "0.0.0.0":
            ops_host = DEFAULT_OPS_HOST
        ops_port = _read_int(values, "VOICE_OPS_PORT", DEFAULT_OPS_PORT, lo=1, hi=65535)
        agent_name = (
            _present(values, "LIVEKIT_AGENT_NAME") or DEFAULT_LIVEKIT_AGENT_NAME
        )
        if not agent_name.strip():
            _missing("LIVEKIT_AGENT_NAME")

        livekit_url = _present(values, "LIVEKIT_URL")
        if livekit_url is not None:
            parsed = urlsplit(livekit_url)
            if parsed.scheme not in {"ws", "wss", "http", "https"} or not parsed.netloc:
                raise ConfigurationError("LIVEKIT_URL must be a ws(s) or http(s) URL")

        provider: VoiceSettings | None = None
        if resolved != "synthetic-test":
            provider = VoiceSettings.from_env(values)
            VoiceUxSettings.from_env(values)

        if resolved == "stage":
            if allow_empty:
                raise ConfigurationError(
                    "ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV must be false in stage"
                )
            if livekit_url is None:
                _missing("LIVEKIT_URL")
            if _present(values, "LIVEKIT_API_KEY") is None:
                _missing("LIVEKIT_API_KEY")
            if _present(values, "LIVEKIT_API_SECRET") is None:
                _missing("LIVEKIT_API_SECRET")
            if _present(values, "PLATFORM_API_URL") is None:
                _missing("PLATFORM_API_URL")
            if _present(values, "PHONE_LOOKUP_TOKEN") is None:
                _missing("PHONE_LOOKUP_TOKEN")
            if _present(values, "DASHSCOPE_API_KEY") is None:
                _missing("DASHSCOPE_API_KEY")

        return cls(
            mode=resolved,
            livekit_url_configured=livekit_url is not None,
            livekit_api_key_configured=_present(values, "LIVEKIT_API_KEY") is not None,
            livekit_api_secret_configured=_present(values, "LIVEKIT_API_SECRET")
            is not None,
            livekit_agent_name=agent_name,
            platform_api_url_configured=_present(values, "PLATFORM_API_URL")
            is not None,
            phone_lookup_token_configured=_present(values, "PHONE_LOOKUP_TOKEN")
            is not None,
            dashscope_api_key_configured=_present(values, "DASHSCOPE_API_KEY")
            is not None,
            allow_empty_dispatch_metadata_local_dev=allow_empty,
            drain_timeout_s=drain_timeout_s,
            ops_enabled=ops_enabled,
            ops_host=ops_host,
            ops_port=ops_port,
            provider=provider,
        )
