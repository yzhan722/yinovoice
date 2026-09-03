"""Read-only LiveKit / Platform SIP preflight. Never mutates trunks or rules."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..config import DEFAULT_LIVEKIT_AGENT_NAME


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def _present(values: Mapping[str, str], name: str) -> str | None:
    raw = values.get(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def check_sip_preflight(env: Mapping[str, str] | None = None) -> list[PreflightCheck]:
    values = os.environ if env is None else env
    checks: list[PreflightCheck] = []

    url = _present(values, "LIVEKIT_URL")
    if url is None:
        checks.append(PreflightCheck("LIVEKIT_URL", False, "missing"))
    else:
        parsed = urlsplit(url)
        ok = parsed.scheme in {"wss", "ws", "https", "http"} and bool(parsed.netloc)
        checks.append(
            PreflightCheck(
                "LIVEKIT_URL",
                ok,
                "configured" if ok else "must be a ws(s) or http(s) URL",
            )
        )

    for name in ("LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        value = _present(values, name)
        checks.append(
            PreflightCheck(
                name,
                value is not None,
                "configured" if value else "missing",
            )
        )

    platform = _present(values, "PLATFORM_API_URL")
    if platform is None:
        checks.append(PreflightCheck("PLATFORM_API_URL", False, "missing"))
    else:
        parsed = urlsplit(platform)
        ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        checks.append(
            PreflightCheck(
                "PLATFORM_API_URL",
                ok,
                "configured" if ok else "must be an http(s) URL",
            )
        )

    agent_name = _present(values, "LIVEKIT_AGENT_NAME") or DEFAULT_LIVEKIT_AGENT_NAME
    checks.append(
        PreflightCheck(
            "LIVEKIT_AGENT_NAME",
            bool(agent_name.strip()),
            agent_name,
        )
    )

    lookup_token = _present(values, "PHONE_LOOKUP_TOKEN")
    checks.append(
        PreflightCheck(
            "PHONE_LOOKUP_TOKEN",
            lookup_token is not None,
            "configured" if lookup_token else "missing",
        )
    )
    return checks


async def probe_livekit_readonly(env: Mapping[str, str] | None = None) -> str:
    """List inbound trunks if the SDK supports it. Never create or update."""

    values = os.environ if env is None else env
    url = _present(values, "LIVEKIT_URL")
    key = _present(values, "LIVEKIT_API_KEY")
    secret = _present(values, "LIVEKIT_API_SECRET")
    if url is None or key is None or secret is None:
        return "probe skipped: credentials incomplete"
    try:
        from livekit import api
    except Exception as error:  # import/runtime only
        return f"probe skipped: livekit-api unavailable ({error.__class__.__name__})"

    lkapi = api.LiveKitAPI(url, key, secret)
    try:
        sip = getattr(lkapi, "sip", None)
        lister = getattr(sip, "list_sip_inbound_trunk", None)
        if not callable(lister):
            return "probe skipped: list_sip_inbound_trunk is unavailable"
        request_type = getattr(api, "ListSIPInboundTrunkRequest", None)
        request = request_type() if callable(request_type) else None
        result = await lister(request) if request is not None else await lister()
        items = getattr(result, "items", None)
        count = len(items) if items is not None else 0
        return f"probe ok: inbound trunks visible={count}"
    except Exception as error:
        return f"probe failed: {error.__class__.__name__}"
    finally:
        closer = getattr(lkapi, "aclose", None)
        if callable(closer):
            await closer()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only SIP preflight for Yino voice-agent"
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Optionally list LiveKit inbound trunks (read-only)",
    )
    args = parser.parse_args(argv)
    checks = check_sip_preflight()
    failed = False
    for check in checks:
        mark = "ok" if check.ok else "FAIL"
        print(f"{mark} {check.name}: {check.detail}")
        if not check.ok:
            failed = True
    if args.probe:
        print(asyncio.run(probe_livekit_readonly()))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
