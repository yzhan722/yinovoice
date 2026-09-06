#!/usr/bin/env python
"""Import Vapi assistants, calls and recordings into the Yino Platform API.

Plan P1.4 (docs/superpowers/plans/2026-09-03-vapi-replacement-final-phase.md).
Read-only against Vapi; writes only to the Yino API you point it at.

Run from apps/control-plane/api with its virtualenv (the mapping code lives in
yino_platform_api.vapi_import):

    .venv\\Scripts\\python.exe ..\\..\\..\\scripts\\import_vapi.py ^
        --api-base http://127.0.0.1:8000 --tenant-id <uuid> ^
        --fetch --dry-run

Inputs
  --fetch                 pull /assistant and /call from Vapi (env VAPI_API_KEY)
  --assistants-json FILE  or use exported JSON arrays instead of --fetch
  --calls-json FILE       Vapi /call objects
  --legacy-calls-json F   rows of the legacy console table ai_assistant_call
                          (Vapi's list API only keeps recent calls). Export:
                            mysql -N -e "SELECT JSON_ARRAYAGG(JSON_OBJECT(
                              'aac_call_id',aac_call_id,'aac_assistant_id',aac_assistant_id,
                              'aac_call_type',aac_call_type,'aac_status',aac_status,
                              'aac_ended_reason',aac_ended_reason,
                              'aac_customer_number',aac_customer_number,
                              'aac_started_at',aac_started_at,'aac_ended_at',aac_ended_at,
                              'aac_summary',aac_summary,
                              'aac_recording_url',aac_recording_url,
                              'aac_messages',aac_messages))
                              FROM ai_assistant_call" ai_voice
  --legacy-tz-offset      offset of legacy DATETIME columns (default +11:00, the
                          console's JDBC serverTimezone)
  --tenant-map FILE       {"default_tenant_id": "...",
                           "assistants": {"<vapi assistant id>": "<tenant uuid>"},
                           "tenants": [{"id": "...", "name": "..."}],
                           "users": [{"account": "...", "tenant_id": "...",
                                      "nickname": "..."}]}
  --voice-map FILE        {"<vapi voiceId>": "<yino tts_voice>"}

Idempotency: --state-file (default vapi-import-state.json) records vapi id ->
yino id; re-runs skip everything already imported. A JSON report is written to
--report-file with warnings (prompt overflow, unmapped voices, tool ids, ...).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

import httpx
from yino_platform_api.vapi_import import (
    ImportState,
    VapiImporter,
    legacy_row_to_call,
)

VAPI_BASE = "https://api.vapi.ai"


def _load_json(path: str | None):
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _vapi_client() -> httpx.Client:
    key = os.environ.get("VAPI_API_KEY")
    if not key:
        sys.exit("VAPI_API_KEY is required for --fetch")
    return httpx.Client(
        base_url=VAPI_BASE, headers={"Authorization": f"Bearer {key}"}, timeout=60
    )


def fetch_assistants(vapi: httpx.Client) -> list[dict]:
    response = vapi.get("/assistant", params={"limit": 1000})
    response.raise_for_status()
    return response.json()


def fetch_calls(vapi: httpx.Client, *, page_size: int = 100) -> list[dict]:
    calls: list[dict] = []
    created_before: str | None = None
    while True:
        params: dict[str, object] = {"limit": page_size}
        if created_before:
            params["createdAtLt"] = created_before
        response = vapi.get("/call", params=params)
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        calls.extend(page)
        created_before = page[-1].get("createdAt")
        if len(page) < page_size or not created_before:
            break
    return calls


def _audio_mime(response: httpx.Response, url: str | None) -> str:
    mime = response.headers.get("content-type", "").split(";")[0].strip()
    if mime.startswith("audio/"):
        return mime
    return "audio/mpeg" if (url or "").lower().endswith(".mp3") else "audio/wav"


def make_downloader(vapi_key: str | None):
    """Fetch call audio, preferring Vapi's recording route over stored URLs.

    Stored recordingUrl values rot: R2 presigned links expire and the old
    storage.vapi.ai host no longer resolves. GET /call/{id}/mono-recording
    works while Vapi still retains the call (about 10 days), so try it first
    and fall back to whatever URL the export carried.
    """

    def download(call_id: str, url: str | None) -> tuple[bytes, str]:
        errors: list[str] = []
        with httpx.Client(timeout=180, follow_redirects=True) as client:
            attempts = []
            if vapi_key and call_id:
                attempts.append(
                    (
                        f"{VAPI_BASE}/call/{call_id}/mono-recording",
                        {"Authorization": f"Bearer {vapi_key}"},
                        "api",
                    )
                )
            if url:
                headers = {"Authorization": f"Bearer {vapi_key}"} if vapi_key else {}
                attempts.append((url, headers, "url"))
            for target, headers, label in attempts:
                try:
                    response = client.get(target, headers=headers)
                except httpx.HTTPError as error:
                    errors.append(f"{label} {type(error).__name__}")
                    continue
                if response.status_code == 200 and response.content:
                    return response.content, _audio_mime(response, target)
                errors.append(f"{label} {response.status_code}")
        raise RuntimeError("; ".join(errors) or "no recording source")

    return download


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api-base", required=True, help="Yino Platform API base URL")
    parser.add_argument(
        "--token",
        default=os.environ.get("YINO_ADMIN_TOKEN"),
        help="platform_admin bearer token (needed for tenants/users)",
    )
    parser.add_argument(
        "--tenant-id", help="default tenant UUID when no --tenant-map entry matches"
    )
    parser.add_argument("--tenant-map")
    parser.add_argument("--voice-map")
    parser.add_argument("--assistants-json")
    parser.add_argument("--calls-json")
    parser.add_argument("--legacy-calls-json")
    parser.add_argument("--legacy-tz-offset", default="+11:00")
    parser.add_argument(
        "--fetch", action="store_true", help="read assistants and calls from Vapi"
    )
    parser.add_argument("--skip-calls", action="store_true")
    parser.add_argument("--skip-recordings", action="store_true")
    parser.add_argument("--state-file", default="vapi-import-state.json")
    parser.add_argument("--report-file", default="vapi-import-report.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tenant_map = _load_json(args.tenant_map) or {}
    default_tenant = args.tenant_id or tenant_map.get("default_tenant_id")
    if not default_tenant:
        sys.exit("--tenant-id or tenant-map.default_tenant_id is required")
    per_assistant = {
        k: UUID(v) for k, v in (tenant_map.get("assistants") or {}).items()
    }

    def tenant_for(vapi_assistant_id: str) -> UUID:
        return per_assistant.get(vapi_assistant_id, UUID(default_tenant))

    assistants = _load_json(args.assistants_json)
    fetched_calls: list[dict] = []
    vapi_key = os.environ.get("VAPI_API_KEY")
    if args.fetch:
        with _vapi_client() as vapi:
            assistants = assistants or fetch_assistants(vapi)
            if not args.skip_calls:
                fetched_calls = fetch_calls(vapi)
    if assistants is None:
        sys.exit("no assistants: pass --fetch or --assistants-json")

    # Priority when the same call id appears in several sources: live Vapi
    # objects (richest), then a Vapi JSON export, then legacy console rows.
    calls: list[dict] = []
    seen: set[str] = set()
    legacy_calls = [
        legacy_row_to_call(row, tz_offset=args.legacy_tz_offset)
        for row in (_load_json(args.legacy_calls_json) or [])
    ]
    for source in (fetched_calls, _load_json(args.calls_json) or [], legacy_calls):
        for call in source:
            call_id = str(call.get("id") or "")
            if call_id and call_id not in seen:
                seen.add(call_id)
                calls.append(call)

    api = httpx.Client(base_url=args.api_base, timeout=120)
    importer = VapiImporter(
        api,
        state=ImportState(Path(args.state_file)),
        tenant_for=tenant_for,
        token=args.token,
        dry_run=args.dry_run,
        voice_map=_load_json(args.voice_map),
        downloader=None if args.skip_recordings else make_downloader(vapi_key),
    )

    if tenant_map.get("tenants"):
        importer.ensure_tenants(tenant_map["tenants"])
    importer.import_assistants(assistants)
    if calls and not args.skip_calls:
        importer.import_calls(calls)
    if tenant_map.get("users"):
        importer.ensure_users(tenant_map["users"])

    Path(args.report_file).write_text(
        json.dumps(importer.report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for entry in importer.report:
        key = f"{entry['kind']}:{entry.get('status')}"
        counts[key] = counts.get(key, 0) + 1
    for key in sorted(counts):
        print(f"{key:32s} {counts[key]}")
    print(
        f"report: {args.report_file}  state: {args.state_file}  dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
