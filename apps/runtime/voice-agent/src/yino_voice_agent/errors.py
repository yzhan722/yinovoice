"""Runtime error types. Prefer these over opaque RuntimeError where they help debug."""

from __future__ import annotations

from .runtime_config import RuntimeConfigurationError


class TelephonyNormalizationError(RuntimeConfigurationError):
    """SIP / LiveKit participant attributes cannot be turned into an inbound call."""


class DestinationResolutionError(RuntimeConfigurationError):
    """Callee lookup failed closed. Never fall back to another tenant."""


class QwenTransportError(RuntimeError):
    """Qwen realtime transport failed. Message must not include payloads."""


class ToolTransportError(RuntimeError):
    """Tool HTTP transport failed. Callers should not retry non-idempotent tools."""


class ToolBusinessError(RuntimeError):
    """Platform rejected a tool with a structured business code."""


class LifecycleTransportError(RuntimeError):
    """Call lifecycle HTTP failed. Finish remains best-effort and exactly-once."""


class WorkerNotAcceptingError(RuntimeError):
    """Worker drain has started; new synthetic sessions must not be accepted."""
