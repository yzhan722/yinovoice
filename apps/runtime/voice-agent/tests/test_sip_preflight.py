from __future__ import annotations

import json
from pathlib import Path

import pytest

from yino_voice_agent.config import DEFAULT_LIVEKIT_AGENT_NAME
from yino_voice_agent.telephony.preflight import (
    check_sip_preflight,
    probe_livekit_readonly,
)


def test_preflight_reports_missing_and_invalid_env() -> None:
    checks = {item.name: item for item in check_sip_preflight({})}
    assert checks["LIVEKIT_URL"].ok is False
    assert checks["LIVEKIT_API_KEY"].ok is False
    assert checks["LIVEKIT_API_SECRET"].ok is False
    assert checks["PLATFORM_API_URL"].ok is False
    assert checks["LIVEKIT_AGENT_NAME"].ok is True
    assert checks["LIVEKIT_AGENT_NAME"].detail == DEFAULT_LIVEKIT_AGENT_NAME
    assert checks["PHONE_LOOKUP_TOKEN"].ok is False


def test_preflight_accepts_valid_shapes() -> None:
    checks = {
        item.name: item
        for item in check_sip_preflight(
            {
                "LIVEKIT_URL": "wss://PLACEHOLDER.livekit.cloud",
                "LIVEKIT_API_KEY": "APIplaceholder",
                "LIVEKIT_API_SECRET": "secret-placeholder",
                "PLATFORM_API_URL": "https://platform.example.invalid",
                "LIVEKIT_AGENT_NAME": "yino-customer-service",
                "PHONE_LOOKUP_TOKEN": "placeholder-lookup-token",
            }
        )
    }
    assert all(item.ok for item in checks.values())


def test_preflight_rejects_bad_urls() -> None:
    checks = {
        item.name: item
        for item in check_sip_preflight(
            {
                "LIVEKIT_URL": "not-a-url",
                "LIVEKIT_API_KEY": "APIplaceholder",
                "LIVEKIT_API_SECRET": "secret-placeholder",
                "PLATFORM_API_URL": "ftp://platform.example.invalid",
                "PHONE_LOOKUP_TOKEN": "placeholder-lookup-token",
            }
        )
    }
    assert checks["LIVEKIT_URL"].ok is False
    assert checks["PLATFORM_API_URL"].ok is False


def test_preflight_details_do_not_echo_secrets() -> None:
    secret = "super-secret-value-do-not-log"
    checks = check_sip_preflight(
        {
            "LIVEKIT_URL": "wss://PLACEHOLDER.livekit.cloud",
            "LIVEKIT_API_KEY": "APIplaceholder",
            "LIVEKIT_API_SECRET": secret,
            "PLATFORM_API_URL": "https://platform.example.invalid",
            "PHONE_LOOKUP_TOKEN": secret,
        }
    )
    rendered = " ".join(item.detail for item in checks)
    assert secret not in rendered
    assert "APIplaceholder" not in rendered


@pytest.mark.asyncio
async def test_probe_skips_without_credentials() -> None:
    message = await probe_livekit_readonly({})
    assert message.startswith("probe skipped")


def test_dispatch_rule_template_hides_caller_and_keeps_empty_metadata() -> None:
    path = (
        Path(__file__).resolve().parents[4]
        / "integrations"
        / "sip"
        / "livekit"
        / "dispatch-rule.example.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    rule = payload["dispatch_rule"]
    assert rule["hide_phone_number"] is True
    agents = rule["roomConfig"]["agents"]
    assert agents[0]["metadata"] == ""
    assert agents[0]["agentName"] == DEFAULT_LIVEKIT_AGENT_NAME
