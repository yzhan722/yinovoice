"""Runtime recording seam. Never talks to real S3 or LiveKit Egress."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class RecordingSink(Protocol):
    async def start(self, session_id: str) -> str | None:
        """Return an opaque egress id, or None when recording is skipped."""

    async def stop(self, egress_id: str) -> None:
        """Best-effort stop. Must not raise into the voice path."""


class NullRecordingSink:
    async def start(self, session_id: str) -> str | None:
        _ = session_id
        return None

    async def stop(self, egress_id: str) -> None:
        _ = egress_id


class RecordingController:
    """Start/stop recording without coupling voice to Egress failures."""

    def __init__(
        self,
        *,
        enabled: bool,
        sink: RecordingSink | None = None,
    ) -> None:
        self._enabled = enabled
        self._sink = sink or NullRecordingSink()
        self._egress_id: str | None = None
        self._start_task: asyncio.Task[None] | None = None
        self._session_ended = False
        self._failed = False

    @property
    def egress_id(self) -> str | None:
        return self._egress_id

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def pending(self) -> bool:
        task = self._start_task
        return task is not None and not task.done()

    def request_start(self, session_id: str) -> None:
        if not self._enabled or self._session_ended:
            return
        if self._start_task is not None:
            return

        async def _start() -> None:
            try:
                egress_id = await self._sink.start(session_id)
            except Exception:
                self._failed = True
                logger.error("recording start failed session_id=%s", session_id)
                return
            if self._session_ended:
                if egress_id:
                    await self._safe_stop(egress_id)
                return
            self._egress_id = egress_id

        self._start_task = asyncio.create_task(
            _start(), name="RecordingController.start"
        )

    async def notify_session_ended(self) -> None:
        self._session_ended = True
        task = self._start_task
        if task is not None and not task.done():
            await asyncio.gather(task, return_exceptions=True)
        if self._egress_id:
            await self._safe_stop(self._egress_id)
            self._egress_id = None

    async def _safe_stop(self, egress_id: str) -> None:
        try:
            await self._sink.stop(egress_id)
        except Exception:
            self._failed = True
            logger.error("recording stop failed")
