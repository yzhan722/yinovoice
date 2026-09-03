# Voice Worker operations runbook

Audience: someone who can follow commands but does not know this codebase.

This document is **offline / Stage operational** guidance for the DEV-A Voice Worker (`apps/runtime/voice-agent`). It is not a live telephone certificate.

- Real PSTN calls: **0** / **NOT TESTED**
- Live SIP status: **NEEDS_LIVEKIT_PROVISIONING**
- Do not treat a green release gate as `LIVE_SIP_E2E_PASS`

SIP Stage (read-only LiveKit probe, DID/trunk/dispatch checklist) remains:

- `docs/realtime/2026-09-01-sip-inbound-stage-runbook.md`
- `docs/realtime/2026-09-01-live-sip-e2e-result.md`
- Repo launcher: `scripts/sip_preflight.py` (never mutates trunks or dispatch rules)

## Prerequisites

- Python 3.11–3.14 (this worktree uses 3.12)
- Git checkout of this repository
- For a local named worker: LiveKit server, Platform API, DashScope/Qwen credentials in **`.env.local` only**
- For synthetic tests / release gate: **no** LiveKit Cloud, **no** PSTN, **no** paid Qwen session is required

Do not put secrets in `VITE_*`, README, chat logs, or `.env.example`.

## Install

Working directory is always `apps/runtime/voice-agent` unless a command says otherwise.

### Windows (CMD)

```bat
cd /d D:\Repos\yinovoice-realtime\apps\runtime\voice-agent
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.local
```

Then edit `.env.local` with a local editor. Replace DashScope placeholders. Do not print the file.

### Windows (PowerShell)

```powershell
Set-Location D:\Repos\yinovoice-realtime\apps\runtime\voice-agent
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env.local
```

### Linux

```bash
cd /path/to/yinovoice-realtime/apps/runtime/voice-agent
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
cp .env.example .env.local
```

If PyPI TLS fails, the README documents an Aliyun mirror fallback. Do not log credentials.

## Environment variables

Copy `.env.example` → `.env.local`. Classification:

| Name | Class | Notes |
|---|---|---|
| `VOICE_RUNTIME_MODE` | STAGE REQUIRED `stage`; local default `local-dev`; tests `synthetic-test` | Stage rejects `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=true` |
| `LIVEKIT_URL` | REQUIRED for worker; STAGE REQUIRED | `ws(s)` or `http(s)` |
| `LIVEKIT_API_KEY` | REQUIRED for worker; STAGE REQUIRED | Never log the value |
| `LIVEKIT_API_SECRET` | REQUIRED for worker; STAGE REQUIRED | Never log the value |
| `LIVEKIT_AGENT_NAME` | OPTIONAL (default `yino-customer-service`) | Must match Dispatch Rule `agentName` |
| `PLATFORM_API_URL` | REQUIRED for dispatched/SIP sessions; STAGE REQUIRED | No default tenant fallback |
| `PHONE_LOOKUP_TOKEN` | STAGE REQUIRED; fail-closed if missing on SIP lookup | Must match Control Plane. Never put in `VITE_*` |
| `DASHSCOPE_API_KEY` | REQUIRED for live Qwen worker; STAGE REQUIRED | Static presence only at startup |
| `QWEN_REALTIME_URL` | REQUIRED for qwen-realtime | Workspace host, not a secret dump |
| `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV` | LOCAL DEV ONLY for `server console` | Stage must be `false` |
| `VOICE_WORKER_DRAIN_TIMEOUT_SECONDS` | OPTIONAL (default 30, range 1–300) | Runtime lifecycle cleanup. **Not** LiveKit `AgentServer.drain` (SDK default 3600s) |
| `VOICE_OPS_ENABLED` | OPTIONAL (default false) | Ops HTTP is not required for calls |
| `VOICE_OPS_HOST` | OPTIONAL (default `127.0.0.1`) | `0.0.0.0` is coerced to loopback |
| `VOICE_OPS_PORT` | OPTIONAL (default 8091) | |
| `VOICE_UX_*` | OPTIONAL | See `.env.example` |

Startup validation is **static** (names present, types in range, Stage guards). It does **not** require Platform HTTP 200 or a live Qwen socket.

- Platform / Qwen **availability** is observed at runtime (`DEGRADED` is not dead).
- There is **no** paid Qwen readiness probe.
- There is **no** Control Plane health probe from A (`DEPENDENCY_PROBE_UNAVAILABLE`). Do not add B endpoints for this.

## Start Worker

Start LiveKit and Platform first when you intend real rooms (not needed for pytest).

### Windows (CMD)

```bat
cd /d D:\Repos\yinovoice-realtime\apps\runtime\voice-agent
.\.venv\Scripts\python.exe -m yino_voice_agent.server dev
```

Optional ops HTTP (loopback only):

```bat
set VOICE_OPS_ENABLED=true
set VOICE_OPS_HOST=127.0.0.1
set VOICE_OPS_PORT=8091
.\.venv\Scripts\python.exe -m yino_voice_agent.server dev
```

Console (local audio devices; **not** Stage):

```bat
set ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=true
.\.venv\Scripts\python.exe -m yino_voice_agent.server console
```

### Linux

```bash
cd /path/to/yinovoice-realtime/apps/runtime/voice-agent
. .venv/bin/activate
python -m yino_voice_agent.server dev
```

Optional ops:

```bash
export VOICE_OPS_ENABLED=true
export VOICE_OPS_HOST=127.0.0.1
export VOICE_OPS_PORT=8091
python -m yino_voice_agent.server dev
```

Stage worker (fail-fast if static config is incomplete):

```bash
export VOICE_RUNTIME_MODE=stage
export ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=false
python -m yino_voice_agent.server dev
```

Missing `PHONE_LOOKUP_TOKEN` / LiveKit / DashScope in `stage` exits at process start with a **name-only** error (`PHONE_LOOKUP_TOKEN missing`). Values are not printed.

## Check /livez /readyz /status

Ops HTTP is **off** unless `VOICE_OPS_ENABLED=true`. Default bind is `127.0.0.1`. If you set another host, you must restrict access with a reverse proxy, VPN, or container network. This Worker does not ship a large auth subsystem.

### Windows (CMD)

```bat
curl http://127.0.0.1:8091/livez
curl http://127.0.0.1:8091/readyz
curl http://127.0.0.1:8091/status
```

### Linux

```bash
curl -sS http://127.0.0.1:8091/livez
curl -sS http://127.0.0.1:8091/readyz
curl -sS http://127.0.0.1:8091/status
```

Semantics:

| Endpoint | Meaning |
|---|---|
| `GET /livez` | Process event loop can serve. Always `{"status":"ok"}` if this server is up. Qwen/Platform blips must **not** flip livez. |
| `GET /readyz` | Should this process take **new** calls? `STARTING` / `DRAINING` / `STOPPED` → not ready (`503`). `READY` or `DEGRADED` → ready unless draining. |
| `GET /status` | Worker state, uptime, session counters, bounded latency percentiles. **No** env dump, secrets, tenant lists, call ids, rooms, phones, or transcripts. |

Do not use LiveKit Agents `GET /` as liveness. In livekit-agents 1.7.1 that endpoint returns 503 when LiveKit is disconnected and would restart a healthy Runtime.

`DEGRADED ≠ DEAD`. Recent Qwen transport errors mark `DEGRADED` while livez stays ok and readyz stays true until drain.

## Run release gate

From `apps/runtime/voice-agent`. Offline only: pytest, ruff, static config, races/stress/replay (full), tracked-file secret **name** scan. No PSTN, no LiveKit mutation, no S3, no paid Qwen.

### Windows (CMD)

```bat
cd /d D:\Repos\yinovoice-realtime\apps\runtime\voice-agent
.\.venv\Scripts\python.exe -m yino_voice_agent.release_gate --mode fast
.\.venv\Scripts\python.exe -m yino_voice_agent.release_gate --mode full
```

### Linux

```bash
python -m yino_voice_agent.release_gate --mode fast
python -m yino_voice_agent.release_gate --mode full
```

Equivalent launcher: `python scripts/release_gate.py --mode full` (same package directory).

Verdicts: `PASS`, `FAIL` (exit ≠ 0), or you may record `BLOCKED_EXTERNAL` by hand when live SIP is missing. A green **offline** gate still prints `LIVE_SIP_STATUS=NEEDS_LIVEKIT_PROVISIONING`. Missing PSTN must **not** make the offline gate fail.

## Stage SIP preflight

From the **repository root**. Read-only.

### Windows (CMD)

```bat
cd /d D:\Repos\yinovoice-realtime
.\apps\runtime\voice-agent\.venv\Scripts\python.exe scripts\sip_preflight.py
.\apps\runtime\voice-agent\.venv\Scripts\python.exe scripts\sip_preflight.py --probe
```

### Linux

```bash
cd /path/to/yinovoice-realtime
apps/runtime/voice-agent/.venv/bin/python scripts/sip_preflight.py
apps/runtime/voice-agent/.venv/bin/python scripts/sip_preflight.py --probe
```

`--probe` may list inbound trunks. It must not create, update, or delete trunks or dispatch rules.

Details: `docs/realtime/2026-09-01-sip-inbound-stage-runbook.md`.

## Graceful stop

Press Ctrl+C in the worker terminal.

Expected Runtime sequence (on top of LiveKit `AgentServer.drain`, default timeout 3600s):

1. `begin_drain` — reject new Runtime session registration
2. LiveKit waits for in-flight jobs
3. Per-job `add_shutdown_callback` finishes the call (exactly-once `/finish`)
4. Registry leftover cleanup (bounded `VOICE_WORKER_DRAIN_TIMEOUT_SECONDS`)
5. Ops HTTP closed
6. State `STOPPED` — readyz false

Hard kill (`taskkill` / `kill -9`) **cannot** promise exactly-once finish. Do not invent crash recovery. After a new process starts, session registry, suppression ids, metrics, and tool state are empty (process lifetime).

## Common failures

| Symptom | Likely cause | What to do (no secrets) |
|---|---|---|
| Worker will not start | Static config validation | Read the **variable name** in the exit message. Fill `.env.local`. Do not paste values into tickets. |
| `readyz=false` | `STARTING`, `DRAINING`, `STOPPED`, or ops not enabled / wrong port | Check `/status` `worker_state` and `draining`. Confirm `VOICE_OPS_ENABLED`. |
| Phone lookup 401 | Token missing or Control Plane / Runtime tokens differ | Set `PHONE_LOOKUP_TOKEN` on **both**. Empty Control Plane token is always 401. |
| Phone lookup 404 | DID not mapped or disabled | Bind the callee E.164 on Platform. Runtime has **no** default tenant. |
| Qwen disconnect | Provider transport | Call fails closed (`FAIL_SESSION_ON_PROVIDER_DISCONNECT`). livez stays ok. Metrics: `qwen_disconnects`. |
| Agent not dispatched | `LIVEKIT_AGENT_NAME` ≠ dispatch `agentName`, or worker not registered | Compare names. Confirm LiveKit URL. |
| Duplicate `/finish` | Runtime bug | **Release blocker.** Capture session_id hash only, not numbers or transcripts. |
| Recording start failed | S3/Egress not configured or sink error | Voice Runtime continues. Recording must not flip livez/readyz. |
| `/status` from another host | Bind / network exposure | Default is loopback. Do not publish 0.0.0.0 without an ACL. |

## Restart

A new Worker process is a new `WorkerRuntime`. Expect `active_sessions=0`, empty suppression windows, reset counters. Metrics are **not** persisted.

## What this runbook does not do

- Buy DID, create/modify SIP trunk or dispatch
- Production deploy
- Real S3 / Egress
- Outbound calling
- Control Plane or Call Insights development
