# DEV-A Voice Worker release checklist

Use this before calling the Runtime **offline** release-ready. Two columns must stay separate. Passing Offline does **not** mean live telephone.

Live SIP status remains **NEEDS_LIVEKIT_PROVISIONING** until a later authorized live campaign.

## Offline (this repository, synthetic)

Run from `apps/runtime/voice-agent` with the package venv.

| Check | Command / evidence | Status |
|---|---|---|
| Tests | `python -m pytest -q` all green | |
| Lint | `python -m ruff check src tests scripts` | |
| Format | `python -m ruff format --check src tests scripts` | |
| Stress | `tests/test_hardening_stress.py` and concurrency 10/25/50 | |
| Replay | hardening replay + Voice UX replay + SIP synthetic `tests/test_sip_e2e.py` | |
| Config | `WorkerStartupSettings` stage fail-fast; local-dev empty-metadata guard; synthetic-test skips live keys | |
| Security | Release gate tracked-file name scan (`.env.local`, `.env`, `.pem`/`.key`/`.p12`); no secret values in errors or `/status` | |
| Ops readiness | `/livez` ≠ `/readyz`; default bind `127.0.0.1`; metrics bounded; registry register/unregister once | |
| Release gate | `python -m yino_voice_agent.release_gate --mode full` → `PASS` | |

Gate still prints:

```text
LIVE_SIP_STATUS=NEEDS_LIVEKIT_PROVISIONING
```

## External Stage (not claimed by offline PASS)

| Check | Status |
|---|---|
| LiveKit credentials on the worker host | NOT TESTED here |
| DID | NOT TESTED |
| Inbound trunk | NOT TESTED (do not mutate from this repo) |
| Dispatch rule | NOT TESTED (do not mutate from this repo) |
| Private Platform reachable from worker | NOT TESTED |
| Real PSTN | **NOT TESTED** |
| Real Egress / S3 | NOT TESTED |

Read-only SIP probe (when credentials exist): `scripts/sip_preflight.py` — see `docs/realtime/2026-09-01-sip-inbound-stage-runbook.md`.

```text
Real PSTN: NOT TESTED
Real calls tested: 0
```

Until a later live campaign actually dials, **never** write `LIVE_SIP_E2E_PASS`.
