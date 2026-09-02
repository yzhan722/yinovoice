"""Control Plane call-session client used by the voice runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx

from .runtime_config import DispatchMetadata
from .session_trace import SessionTrace, redact_phone_numbers
from .usage import CallUsageAccumulator

logger = logging.getLogger(__name__)

_MAX_PENDING_MESSAGES = 4096


def _finish_rank(status: str, ended_reason: str) -> int:
    if status == "failed" or ended_reason == "agent_error":
        return 2
    if ended_reason == "user_hangup":
        return 1
    return 0


async def _success_json(response: Any) -> dict[str, Any]:
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and status_code >= 400:
        raise RuntimeError(f"call lifecycle HTTP {status_code}")
    raw = response.json()
    if hasattr(raw, "__await__"):
        raw = await raw
    if not isinstance(raw, Mapping):
        raise RuntimeError("call lifecycle response must be a JSON object")
    return dict(raw)


def direction_for_channel(channel: str) -> str:
    return "inbound" if channel == "sip" else "web"


class CallLifecycleClient:
    """Best-effort call session writer. Network failures never raise."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        tenant_id: UUID,
        *,
        trace: SessionTrace | None = None,
    ) -> None:
        self._http = http
        self._tenant_id = tenant_id
        self._trace = trace
        self.record_id: UUID | None = None
        self._start_payload: dict[str, Any] | None = None
        self._pending_messages: list[dict[str, Any]] = []
        self._finish_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._finish_http_started = False
        self._finish_committed = False
        self._finish_selected: tuple[str, str] | None = None
        self.usage = CallUsageAccumulator()

    def record_usage(self, event: Mapping[str, object]) -> None:
        self.usage.add(event)

    @property
    def finish_committed(self) -> bool:
        return self._finish_committed

    @property
    def finish_selected(self) -> tuple[str, str] | None:
        return self._finish_selected

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Tenant-ID": str(self._tenant_id)}

    def _buffer_message(self, message: dict[str, Any]) -> None:
        if len(self._pending_messages) >= _MAX_PENDING_MESSAGES:
            self._pending_messages.pop(0)
            logger.error(
                "call lifecycle pending messages truncated tenant_id=%s",
                self._tenant_id,
            )
        self._pending_messages.append(message)

    async def start_from_dispatch(
        self,
        metadata: DispatchMetadata,
        room_name: str,
    ) -> None:
        payload: dict[str, Any] = {
            "customer_service_id": str(metadata.customer_service_id),
            "room_name": room_name,
            "direction": direction_for_channel(metadata.channel),
        }
        if metadata.caller_number is not None:
            payload["caller_number"] = metadata.caller_number
        if metadata.callee_number is not None:
            payload["callee_number"] = metadata.callee_number
        if metadata.provider_call_id is not None:
            payload["provider_call_id"] = metadata.provider_call_id
        self._start_payload = payload
        if self._trace is not None:
            self._trace.mark("session_start")
        await self._post_start(payload)

    async def append_final(self, role: str, text: str, sequence: int) -> None:
        message = {"role": role, "text": text, "sequence": sequence}
        async with self._write_lock:
            if self.record_id is None:
                self._buffer_message(message)
                return
            await self._post_message_unlocked(message)

    def _select_finish_outcome(self, candidate: tuple[str, str]) -> None:
        if self._finish_selected is None or _finish_rank(*candidate) > _finish_rank(
            *self._finish_selected
        ):
            self._finish_selected = candidate

    async def finish(
        self,
        *,
        status: str = "completed",
        ended_reason: str = "completed",
    ) -> None:
        candidate = (status, ended_reason)
        async with self._finish_lock:
            if self._finish_committed:
                return
            self._select_finish_outcome(candidate)
            if self._finish_http_started:
                return
        await asyncio.sleep(0)
        async with self._finish_lock:
            if self._finish_committed:
                return
            self._select_finish_outcome(candidate)
            if self._finish_http_started:
                return
            self._finish_http_started = True
            selected_status, selected_reason = self._finish_selected or candidate
        if self._trace is not None:
            self._trace.mark("finish_start")
        try:
            await self._send_finish(selected_status, selected_reason)
        finally:
            async with self._finish_lock:
                self._finish_committed = True
            if self._trace is not None:
                self._trace.mark("finish_complete")

    async def _send_finish(self, status: str, ended_reason: str) -> None:
        async with self._write_lock:
            if self.record_id is None and self._start_payload is not None:
                await self._post_start_unlocked(self._start_payload)
            pending = list(self._pending_messages)
            self._pending_messages.clear()
            for message in pending:
                await self._post_message_unlocked(message)
            if self.record_id is None:
                logger.error(
                    "call lifecycle finish dropped; start never succeeded tenant_id=%s",
                    self._tenant_id,
                )
                return
            payload: dict[str, Any] = {
                "status": status,
                "ended_reason": ended_reason,
            }
            snapshot = self.usage.snapshot()
            if snapshot.has_data():
                payload["usage"] = snapshot.as_dict()
                logger.info(
                    "call usage recorded tenant_id=%s record_id=%s "
                    "response_count=%s total_tokens=%s",
                    self._tenant_id,
                    self.record_id,
                    snapshot.response_count,
                    snapshot.total_tokens,
                )
            try:
                response = await self._http.post(
                    f"/api/v1/call-sessions/{self.record_id}/finish",
                    headers=self._headers,
                    json=payload,
                )
                await _success_json(response)
            except Exception as error:
                logger.error(
                    "call lifecycle finish failed tenant_id=%s record_id=%s "
                    "error_type=%s",
                    self._tenant_id,
                    self.record_id,
                    type(error).__name__,
                )

    async def _post_start(self, payload: dict[str, Any]) -> None:
        async with self._write_lock:
            await self._post_start_unlocked(payload)

    async def _post_start_unlocked(self, payload: dict[str, Any]) -> None:
        try:
            response = await self._http.post(
                "/api/v1/call-sessions/start",
                headers=self._headers,
                json=payload,
            )
            body = await _success_json(response)
            self.record_id = UUID(str(body["id"]))
            pending = list(self._pending_messages)
            self._pending_messages.clear()
            for message in pending:
                await self._post_message_unlocked(message)
        except Exception as error:
            logger.error(
                "call lifecycle start failed tenant_id=%s room=%s error_type=%s",
                self._tenant_id,
                redact_phone_numbers(str(payload.get("room_name") or "-")),
                type(error).__name__,
            )

    async def _post_message_unlocked(self, message: dict[str, Any]) -> None:
        if self.record_id is None:
            self._buffer_message(message)
            return
        try:
            response = await self._http.post(
                f"/api/v1/call-sessions/{self.record_id}/messages",
                headers=self._headers,
                json=message,
            )
            await _success_json(response)
        except Exception as error:
            logger.error(
                "call lifecycle message failed tenant_id=%s record_id=%s error_type=%s",
                self._tenant_id,
                self.record_id,
                type(error).__name__,
            )
            self._buffer_message(message)
