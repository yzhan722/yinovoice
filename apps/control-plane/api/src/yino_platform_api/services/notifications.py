from __future__ import annotations

import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    email: str = Field(default="", max_length=200)
    enabled: bool = True
    updated_at: datetime

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str) -> str:
        return value.strip()


class NotificationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(default="", max_length=200)
    enabled: bool = True

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str) -> str:
        return value.strip()


class NotificationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    kind: str
    target: str
    status: str
    detail: str = ""
    created_at: datetime


class NotificationSink(Protocol):
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class FakeNotificationSink:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    async def send(self, *, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("smtp unavailable")
        self.sent.append((to, subject, body))


class SmtpNotificationSink:
    """Send mail via SMTP. Password is never logged."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_addr: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._from_addr = from_addr
        self._username = username
        self._password = password

    async def send(self, *, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body)

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_addr
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if self._port == 465:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=20) as smtp:
                self._authenticate(smtp)
                smtp.send_message(message)
            return
        with smtplib.SMTP(self._host, self._port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            self._authenticate(smtp)
            smtp.send_message(message)

    def _authenticate(self, smtp: smtplib.SMTP) -> None:
        if self._username:
            smtp.login(self._username, self._password or "")


class NotificationRepository(Protocol):
    async def get_settings(self, tenant_id: UUID) -> NotificationSettings | None: ...

    async def upsert_settings(
        self, settings: NotificationSettings
    ) -> NotificationSettings: ...

    async def add_event(self, event: NotificationEvent) -> NotificationEvent: ...


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self._settings: dict[UUID, NotificationSettings] = {}
        self._events: list[NotificationEvent] = []

    async def get_settings(self, tenant_id: UUID) -> NotificationSettings | None:
        item = self._settings.get(tenant_id)
        return item.model_copy() if item is not None else None

    async def upsert_settings(
        self, settings: NotificationSettings
    ) -> NotificationSettings:
        stored = settings.model_copy(
            update={"updated_at": datetime.now(UTC)}
        )
        self._settings[stored.tenant_id] = stored
        return stored.model_copy()

    async def add_event(self, event: NotificationEvent) -> NotificationEvent:
        self._events.append(event.model_copy())
        return event.model_copy()


class NotificationService:
    def __init__(
        self,
        repository: NotificationRepository,
        sink: NotificationSink | None,
    ) -> None:
        self._repository = repository
        self._sink = sink

    async def get_settings(self, tenant_id: UUID) -> NotificationSettings | None:
        return await self._repository.get_settings(tenant_id)

    async def upsert_settings(
        self, settings: NotificationSettings
    ) -> NotificationSettings:
        return await self._repository.upsert_settings(settings)

    async def notify(
        self,
        tenant_id: UUID,
        *,
        kind: str,
        subject: str,
        body: str,
    ) -> None:
        settings = await self._repository.get_settings(tenant_id)
        if (
            settings is None
            or not settings.enabled
            or not settings.email
            or self._sink is None
        ):
            return
        status = "sent"
        detail = ""
        try:
            await self._sink.send(
                to=settings.email,
                subject=subject,
                body=body,
            )
        except Exception as error:
            status = "failed"
            detail = str(error)
        await self._repository.add_event(
            NotificationEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                kind=kind,
                target=settings.email,
                status=status,
                detail=detail[:500],
                created_at=datetime.now(UTC),
            )
        )
