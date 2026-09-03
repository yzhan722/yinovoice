from __future__ import annotations

import json
import logging
from uuid import UUID

import httpx
import pytest
from hardening_support import FakePlatform, make_spec, run_synthetic_session

from yino_voice_agent.runtime_config import DispatchMetadata, RuntimeConfigurationError
from yino_voice_agent.session_trace import redact_phone_numbers, sanitize_url_for_log
from yino_voice_agent.tool_client import ToolInvocationClient


def test_sanitize_url_strips_number_query() -> None:
    url = "https://platform.test/api/v1/phone-numbers/lookup?number=+61411111111"
    cleaned = sanitize_url_for_log(url)
    assert "+61411111111" not in cleaned
    assert "number=" not in cleaned
    assert cleaned.endswith("/api/v1/phone-numbers/lookup")


def test_redact_does_not_keep_e164() -> None:
    assert "+61411111111" not in redact_phone_numbers("caller +61411111111 joined")


@pytest.mark.asyncio
async def test_synthetic_session_logs_do_not_contain_pii(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    spec = make_spec(0, session_id="pii-room", room_name="pii-room")
    with caplog.at_level(logging.DEBUG):
        async with httpx.AsyncClient(
            transport=platform, base_url="http://platform.test"
        ) as http:
            await run_synthetic_session(http, spec)
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "+614" not in text
    assert "13800138000" not in text
    assert "dashscope-test-key" not in text


def test_dispatch_missing_tenant_fails_closed() -> None:
    with pytest.raises(RuntimeConfigurationError):
        DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": "00000000-0000-4000-8000-000000000101",
                    "config_version": 1,
                }
            )
        )


def test_dispatch_missing_service_fails_closed() -> None:
    with pytest.raises(RuntimeConfigurationError):
        DispatchMetadata.from_json(
            json.dumps(
                {
                    "tenant_id": "00000000-0000-4000-8000-000000000001",
                    "config_version": 1,
                }
            )
        )


def test_invalid_provider_channel_fails_closed() -> None:
    with pytest.raises(RuntimeConfigurationError):
        DispatchMetadata.from_json(
            json.dumps(
                {
                    "customer_service_id": "00000000-0000-4000-8000-000000000101",
                    "tenant_id": "00000000-0000-4000-8000-000000000001",
                    "config_version": 1,
                    "channel": "vapi",
                }
            )
        )


@pytest.mark.asyncio
async def test_tool_client_logs_omit_exception_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Boom(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(
                "failed",
                request=httpx.Request(
                    "POST",
                    "http://platform.test/api/v1/tool-invocations?number=+61400000001",
                ),
            )

    with caplog.at_level(logging.ERROR):
        async with httpx.AsyncClient(
            transport=_Boom(), base_url="http://platform.test"
        ) as http:
            client = ToolInvocationClient(
                http, UUID("00000000-0000-4000-8000-000000000001")
            )
            await client.invoke(
                session_id="room-log",
                tool_name="create_appointment",
                arguments={"day": "2026-09-02"},
            )
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "+61400000001" not in text
    assert "number=" not in text
