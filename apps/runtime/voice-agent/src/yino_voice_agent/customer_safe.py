"""Customer-visible strings must never include HTTP, JSON, or exception text."""

from __future__ import annotations

import re

_UNSAFE = re.compile(
    r"(?is)(\bHTTP\b|\bHTTPS\b|status code|\bJSON\b|stack trace|"
    r"traceback|exception|aiohttp|httpx|websocket|wss://|https?://|"
    r"\b5\d\d\b|\b4\d\d\b)"
)
CUSTOMER_UNAVAILABLE = "暂时无法查询，请稍后再试。"
_MAX_CUSTOMER_CHARS = 160


def looks_technical(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return bool(
        _UNSAFE.search(stripped) or stripped[:1] in "{[<" or "Traceback" in stripped
    )


def customer_safe_message(
    text: str | None, *, fallback: str = CUSTOMER_UNAVAILABLE
) -> str:
    if not isinstance(text, str) or looks_technical(text):
        return fallback
    cleaned = " ".join(text.split())
    if len(cleaned) > _MAX_CUSTOMER_CHARS:
        return fallback
    return cleaned
