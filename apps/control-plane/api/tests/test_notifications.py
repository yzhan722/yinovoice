from datetime import UTC, datetime
from uuid import UUID

import pytest

from yino_platform_api.services.notifications import (
    FakeNotificationSink,
    InMemoryNotificationRepository,
    NotificationService,
    NotificationSettings,
    SmtpNotificationSink,
)


@pytest.mark.asyncio
async def test_notification_failure_is_recorded_and_does_not_raise() -> None:
    repo = InMemoryNotificationRepository()
    sink = FakeNotificationSink()
    sink.fail = True
    service = NotificationService(repo, sink)
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    await repo.upsert_settings(
        NotificationSettings(
            tenant_id=tenant_id,
            email="ops@example.test",
            enabled=True,
            updated_at=datetime.now(UTC),
        )
    )
    await service.notify(
        tenant_id,
        kind="appointment",
        subject="新预约",
        body="synthetic",
    )
    assert repo._events[0].status == "failed"
    assert sink.sent == []


@pytest.mark.asyncio
async def test_notification_sends_when_enabled() -> None:
    repo = InMemoryNotificationRepository()
    sink = FakeNotificationSink()
    service = NotificationService(repo, sink)
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    await repo.upsert_settings(
        NotificationSettings(
            tenant_id=tenant_id,
            email="ops@example.test",
            enabled=True,
            updated_at=datetime.now(UTC),
        )
    )
    await service.notify(
        tenant_id,
        kind="callback",
        subject="新回拨",
        body="synthetic",
    )
    assert sink.sent[0][0] == "ops@example.test"
    assert repo._events[0].status == "sent"


class _FakeSmtp:
    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent = None

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message: object) -> None:
        self.sent = message


@pytest.mark.asyncio
async def test_smtp_sink_uses_starttls_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, _FakeSmtp] = {}

    def factory(host: str, port: int, timeout: float | None = None) -> _FakeSmtp:
        smtp = _FakeSmtp(host, port, timeout)
        captured["smtp"] = smtp
        return smtp

    monkeypatch.setattr(
        "yino_platform_api.services.notifications.smtplib.SMTP",
        factory,
    )
    sink = SmtpNotificationSink(
        host="smtp.example.test",
        port=587,
        from_addr="noreply@example.test",
        username="smtp-user",
        password="smtp-secret",
    )
    await sink.send(to="ops@example.test", subject="新预约", body="synthetic")
    smtp = captured["smtp"]
    assert smtp.host == "smtp.example.test"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("smtp-user", "smtp-secret")
    assert smtp.sent is not None
    assert smtp.sent["To"] == "ops@example.test"
    assert smtp.sent["From"] == "noreply@example.test"
