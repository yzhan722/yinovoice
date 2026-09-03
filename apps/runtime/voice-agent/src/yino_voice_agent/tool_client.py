from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import httpx

from .customer_safe import CUSTOMER_UNAVAILABLE, customer_safe_message
from .session_trace import SessionTrace, redact_phone_numbers
from .tool_protocol import ALLOWED_TOOL_NAMES, IDEMPOTENT_TOOL_NAMES

logger = logging.getLogger(__name__)

DEFAULT_TOOL_TIMEOUT_S = 5.0
_MAX_IDEMPOTENT_ATTEMPTS = 2
MAX_TOOL_ARGUMENTS_BYTES = 16_384


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "customer_message": customer_safe_message(message),
    }


class ToolInvocationClient:
    """Best-effort Tool HTTP client. Failures never raise."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        tenant_id: UUID,
        *,
        timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
        trace: SessionTrace | None = None,
        metrics: object | None = None,
    ) -> None:
        self._http = http
        self._tenant_id = tenant_id
        self._timeout_s = timeout_s
        self._trace = trace
        self._metrics = metrics

    async def invoke(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        voice_agent_instance_id: UUID | None = None,
        call_record_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(tool_name, str) or tool_name not in ALLOWED_TOOL_NAMES:
            logger.error(
                "tool invocation rejected unknown_tool session_id=%s",
                redact_phone_numbers(session_id),
            )
            return _error_payload("unknown_tool", "unsupported tool")
        if not isinstance(arguments, dict):
            logger.error(
                "tool invocation rejected invalid_arguments session_id=%s",
                redact_phone_numbers(session_id),
            )
            return _error_payload("invalid_arguments", "arguments must be an object")
        try:
            encoded = json.dumps(arguments)
        except (TypeError, ValueError):
            return _error_payload("invalid_arguments", "arguments must be json")
        if len(encoded.encode("utf-8")) > MAX_TOOL_ARGUMENTS_BYTES:
            return _error_payload("invalid_arguments", "arguments too large")

        payload: dict[str, Any] = {
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": arguments,
        }
        if voice_agent_instance_id is not None:
            payload["voice_agent_instance_id"] = str(voice_agent_instance_id)
        if call_record_id is not None:
            payload["call_record_id"] = str(call_record_id)
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key

        attempts = _MAX_IDEMPOTENT_ATTEMPTS if tool_name in IDEMPOTENT_TOOL_NAMES else 1
        last: dict[str, Any] | None = None
        note = getattr(self._metrics, "note_tool_request", None)
        if callable(note):
            note()
        for attempt in range(attempts):
            if self._trace is not None:
                self._trace.mark("tool_request")
            last = await self._post_once(
                payload, session_id=session_id, tool_name=tool_name
            )
            if self._trace is not None:
                self._trace.mark("tool_result")
            if last is not None and last.get("code") == "retryable_transport":
                if attempt + 1 < attempts:
                    continue
                method = (
                    "note_tool_timeout"
                    if last.get("message") == "timeout"
                    else "note_tool_error"
                )
                fn = getattr(self._metrics, method, None)
                if callable(fn):
                    fn()
                return last
            return last
        return last

    async def _post_once(
        self,
        payload: dict[str, Any],
        *,
        session_id: str,
        tool_name: str,
    ) -> dict[str, Any] | None:
        try:
            response = await asyncio.wait_for(
                self._http.post(
                    "/api/v1/tool-invocations",
                    headers={"X-Tenant-ID": str(self._tenant_id)},
                    json=payload,
                ),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            logger.error(
                "tool invocation timeout tenant_id=%s session_id=%s tool=%s",
                self._tenant_id,
                redact_phone_numbers(session_id),
                tool_name,
            )
            return _error_payload("retryable_transport", "timeout")
        except Exception as error:
            logger.error(
                "tool invocation failed tenant_id=%s session_id=%s tool=%s "
                "error_type=%s",
                self._tenant_id,
                redact_phone_numbers(session_id),
                tool_name,
                type(error).__name__,
            )
            return _error_payload("retryable_transport", "transport")

        if response.status_code >= 500:
            logger.error(
                "tool invocation HTTP %s tenant_id=%s session_id=%s",
                response.status_code,
                self._tenant_id,
                redact_phone_numbers(session_id),
            )
            return _error_payload("retryable_transport", "http_5xx")
        if response.status_code >= 400:
            body = _read_json_object(response)
            if body is not None:
                code = body.get("code")
                message = body.get("message") or body.get("detail")
                if isinstance(code, str):
                    raw_message = (
                        message if isinstance(message, str) else "platform error"
                    )
                    safe = customer_safe_message(raw_message)
                    return {
                        "status": body.get("status", "error"),
                        "code": code,
                        "message": safe,
                        "customer_message": safe,
                        "data": body.get("data"),
                    }
            logger.error(
                "tool invocation HTTP %s tenant_id=%s session_id=%s",
                response.status_code,
                self._tenant_id,
                redact_phone_numbers(session_id),
            )
            return _error_payload("platform_error", CUSTOMER_UNAVAILABLE)
        body = _read_json_object(response)
        return body


def _read_json_object(response: httpx.Response) -> dict[str, Any] | None:
    try:
        raw = response.json()
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return raw
