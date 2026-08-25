from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class ToolInvocationClient:
    """Best-effort Tool HTTP client. Failures never raise."""

    def __init__(self, http: httpx.AsyncClient, tenant_id: UUID) -> None:
        self._http = http
        self._tenant_id = tenant_id

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
        try:
            response = await self._http.post(
                "/api/v1/tool-invocations",
                headers={"X-Tenant-ID": str(self._tenant_id)},
                json=payload,
            )
            if response.status_code >= 400:
                logger.error(
                    "tool invocation HTTP %s tenant_id=%s session_id=%s",
                    response.status_code,
                    self._tenant_id,
                    session_id,
                )
                return None
            body = response.json()
            if hasattr(body, "__await__"):
                body = await body
            if not isinstance(body, dict):
                return None
            return body
        except Exception:
            logger.exception(
                "tool invocation failed tenant_id=%s session_id=%s tool=%s",
                self._tenant_id,
                session_id,
                tool_name,
            )
            return None
