#!/usr/bin/env python3
"""Pull new Vapi calls and their audio into Yino every day (plan P1.5).

Vapi retains a call for roughly ten days. Of 819 historical calls only 43
still had retrievable audio when the migration was rehearsed, so until the
phone numbers are cut over to Yino this job is the only thing preventing
further permanent loss. Transcripts survive in the legacy console database;
audio does not.

Designed for a systemd timer: idempotent (a state file maps Vapi ids to Yino
ids and finished work is skipped), safe to run concurrently with a manual
import against the same state file, and it never deletes anything.

Environment (read from an EnvironmentFile in production):
    VAPI_API_KEY        read-only use of the Vapi API
    YINO_API_BASE       e.g. http://127.0.0.1:8000
    YINO_ADMIN_ACCOUNT  platform_admin console account
    YINO_ADMIN_PASSWORD its password (or YINO_ADMIN_PASSWORD_FILE)
    SYNC_DIR            working directory holding state.json and assistants
    SYNC_LOOKBACK_DAYS  optional, default 14
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "apps/control-plane/api/src")
)

from yino_platform_api.vapi_import import (
    ImportState,
    VapiImporter,
)

VAPI_BASE = "https://api.vapi.ai"


def log(message: str) -> None:
    print(f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}", flush=True)


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is required")
    return value


def admin_password() -> str:
    path = os.environ.get("YINO_ADMIN_PASSWORD_FILE", "").strip()
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return require("YINO_ADMIN_PASSWORD")


def make_downloader(vapi_key: str):
    """Only the API route is used: stored recordingUrl values expire."""

    def download(call_id: str, _url: str | None) -> tuple[bytes, str]:
        with httpx.Client(timeout=180, follow_redirects=True) as client:
            response = client.get(
                f"{VAPI_BASE}/call/{call_id}/mono-recording",
                headers={"Authorization": f"Bearer {vapi_key}"},
            )
            if response.status_code == 200 and response.content:
                mime = response.headers.get("content-type", "audio/wav").split(";")[0]
                return response.content, mime.strip() or "audio/wav"
            raise RuntimeError(f"api {response.status_code}")

    return download


def main() -> int:
    vapi_key = require("VAPI_API_KEY")
    api_base = os.environ.get("YINO_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    sync_dir = Path(os.environ.get("SYNC_DIR", ".")).resolve()
    sync_dir.mkdir(parents=True, exist_ok=True)
    lookback = int(os.environ.get("SYNC_LOOKBACK_DAYS", "14"))

    tenant_map_path = sync_dir / "legacy-tenant-map.json"
    tenant_map = (
        json.loads(tenant_map_path.read_text(encoding="utf-8"))
        if tenant_map_path.is_file()
        else {}
    )
    default_tenant = os.environ.get("YINO_DEFAULT_TENANT_ID") or tenant_map.get(
        "default_tenant_id"
    )
    if not default_tenant:
        sys.exit("YINO_DEFAULT_TENANT_ID or a tenant map is required")
    per_assistant = {
        key: UUID(value) for key, value in (tenant_map.get("assistants") or {}).items()
    }

    api = httpx.Client(base_url=api_base, timeout=120)
    login = api.post(
        "/api/v1/auth/login",
        json={
            "account": require("YINO_ADMIN_ACCOUNT"),
            "password": admin_password(),
        },
    )
    if login.status_code != 200:
        return fail(f"console login failed: {login.status_code}")
    token = login.json()["token"]

    vapi = httpx.Client(
        base_url=VAPI_BASE, headers={"Authorization": f"Bearer {vapi_key}"}, timeout=60
    )
    since = datetime.now(UTC) - timedelta(days=lookback)
    calls: list[dict] = []
    created_before: str | None = None
    while True:
        params: dict[str, object] = {"limit": 100}
        if created_before:
            params["createdAtLt"] = created_before
        page = vapi.get("/call", params=params)
        if page.status_code != 200:
            return fail(f"vapi /call failed: {page.status_code} {page.text[:200]}")
        items = page.json()
        if not items:
            break
        calls.extend(items)
        created_before = items[-1].get("createdAt")
        oldest = str(created_before or "")[:19]
        if len(items) < 100 or not created_before:
            break
        if oldest and oldest < since.isoformat()[:19]:
            break
    log(f"vapi returned {len(calls)} calls (lookback {lookback}d)")

    assistants_path = sync_dir / "assistants.json"
    listed = vapi.get("/assistant", params={"limit": 1000})
    if listed.status_code == 200:
        assistants_path.write_text(
            json.dumps(listed.json(), ensure_ascii=False), encoding="utf-8"
        )
    assistants = (
        json.loads(assistants_path.read_text(encoding="utf-8"))
        if assistants_path.is_file()
        else []
    )

    state = ImportState(sync_dir / "state.json")
    known_assistants = len(state.assistants)
    known_calls = len(state.calls)
    known_recordings = len(state.recordings)

    importer = VapiImporter(
        api,
        state=state,
        tenant_for=lambda vapi_id: per_assistant.get(vapi_id, UUID(default_tenant)),
        token=token,
        downloader=make_downloader(vapi_key),
    )
    # New assistants must exist before their calls can be attached.
    importer.import_assistants(assistants)
    importer.import_calls(calls)

    report_path = sync_dir / f"sync-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    report_path.write_text(
        json.dumps(importer.report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for old in sorted(sync_dir.glob("sync-*.json"))[:-14]:
        old.unlink(missing_ok=True)

    new_assistants = len(state.assistants) - known_assistants
    new_calls = len(state.calls) - known_calls
    new_recordings = len(state.recordings) - known_recordings
    failures = [
        entry
        for entry in importer.report
        if str(entry.get("recording", "")).startswith(
            ("download_failed", "upload_failed")
        )
    ]
    log(
        f"new assistants={new_assistants} new calls={new_calls} "
        f"new recordings={new_recordings} recording failures={len(failures)}"
    )
    if failures:
        # Expected for calls Vapi has already aged out; surfaced, not fatal.
        log(f"  first failure: {failures[0].get('recording')}")
    log(f"report {report_path.name}")
    return 0


def fail(message: str) -> int:
    log(f"ERROR {message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
