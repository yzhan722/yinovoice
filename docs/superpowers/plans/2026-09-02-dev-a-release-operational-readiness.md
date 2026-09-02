# DEV-A Release & Operational Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Do **not** use a fresh worktree. This worktree is DEV-A (`D:\Repos\yinovoice-realtime`). Protect pre-existing Control Plane / Web dirt: never `git add .`, `git reset --hard`, `git clean`, or `git stash`.

**Goal:** Make the Voice Worker offline-release-ready (`DEV_A_RELEASE_READY_OFFLINE`) without real PSTN, LiveKit resource mutation, or Control Plane / Call Insights changes.

**Architecture:** Keep LiveKit Agents 1.7.1 `AgentServer.drain()` / `GET /` as SDK-owned worker drain and coarse health. Add a Runtime-owned layer: `BoundedIdWindow`, wired `WorkerSessionRegistry`, `WorkerRuntime` (state + bounded metrics), loopback ops HTTP (`/livez` `/readyz` `/status`), static `WorkerStartupSettings` validation, and a Python `release_gate`. Do not treat LiveKit `GET /` as liveness: it returns 503 on LiveKit disconnect.

**Tech Stack:** Python 3.11–3.14, pytest, ruff, livekit 1.1.15, livekit-agents 1.7.1, dashscope 1.27.x, aiohttp, httpx. FakeClock for timer tests. No Prometheus/OTel.

## Global Constraints

- Ownership: `apps/runtime/voice-agent/**`, `docs/realtime/**`, `docs/superpowers/plans/**`, `integrations/sip/**` only. No `apps/control-plane/**`, no `apps/call-insights/**`.
- Real PSTN / SIP trunk / DID / dispatch / S3 / production deploy: forbidden. Status stays `NEEDS_LIVEKIT_PROVISIONING`. Never write `LIVE_SIP_E2E_PASS`.
- Secrets never appear in errors, logs, `/status`, `.env.example`, or reports.
- TDD for new behavior. No skip/xfail/weaken. No real `sleep(5)` in tests.
- LiveKit APIs only from 1.1.15 / agents 1.7.1 (`AgentServer.drain`, `JobContext.add_shutdown_callback`, `cli.run_app`). Do not invent SDK methods.
- `AgentServer.drain_timeout` default is 3600. Runtime drain timeout is **lifecycle cleanup**, not a replacement for SDK drain.
- Commits: local only, explicit paths, 3–5 logical commits. No push.

## File map

| File | Responsibility |
|---|---|
| `src/yino_voice_agent/bounded_ids.py` | Ordered id window (capacity 4096). Used by usage + Qwen suppression. |
| `src/yino_voice_agent/usage.py` | Switch `_seen_ids` to `BoundedIdWindow`. |
| `src/yino_voice_agent/qwen_realtime.py` | Bounded suppression; ruff format. |
| `src/yino_voice_agent/worker.py` | Registry: drain flag, totals, once-register, timeout drain, optional lifecycle. |
| `src/yino_voice_agent/ops.py` | `WorkerState`, `RuntimeMetrics`, `WorkerRuntime`, loopback ops HTTP. |
| `src/yino_voice_agent/startup.py` | `RuntimeMode`, `WorkerStartupSettings`, secret-safe static validation. |
| `src/yino_voice_agent/server.py` | Fail-fast at `__main__`; register/unregister; shutdown → drain; ops start. |
| `src/yino_voice_agent/config.py` | Drain timeout + ops env on `VoiceSettings` **or** only via `startup.py` (prefer `startup.py` so existing `VoiceSettings.from_env` tests stay provider-focused). |
| `src/yino_voice_agent/call_lifecycle.py` | Optional metrics: `finish_failures`. |
| `src/yino_voice_agent/tool_client.py` | Optional metrics: tool_requests / errors / timeouts. |
| `src/yino_voice_agent/release_gate.py` | Fast/full gate; mockable runner; no PSTN. |
| `scripts/release_gate.py` | Thin launcher under voice-agent. |
| `docs/realtime/release-readiness-baseline.md` | Versions + pytest/ruff snapshot. |
| `docs/realtime/operations-runbook.md` | Windows/Linux install-start-stop-troubleshoot. |
| `docs/realtime/release-checklist.md` | Offline vs external stage. Real PSTN: NOT TESTED. |
| `docs/realtime/release-operational-readiness-results.md` | Campaign results. SYNTHETIC. |

---

### Task 1: Baseline evidence

**Files:** Create `docs/realtime/release-readiness-baseline.md`

- [ ] Run `python -m pytest -q` in `apps/runtime/voice-agent`. Record count.
- [ ] Run `python -m ruff check src tests` and `python -m ruff format --check src tests`. Record failures (known: `qwen_realtime.py` format drift).
- [ ] Record Python, livekit, livekit-agents, dashscope versions via `importlib.metadata`.
- [ ] Write baseline doc. Mark all numbers SYNTHETIC. Live SIP: `NEEDS_LIVEKIT_PROVISIONING`.

---

### Task 2: BoundedIdWindow (P2 #2)

**Files:**
- Create: `src/yino_voice_agent/bounded_ids.py`
- Modify: `usage.py`, `qwen_realtime.py`
- Test: `tests/test_bounded_ids.py`, `tests/test_qwen_realtime_conversation.py`

**Interfaces:**
- `class BoundedIdWindow: def __init__(self, capacity: int = 4096) -> None`
- `def add(self, item: str) -> bool` — True if newly inserted; duplicate returns False and does not grow
- `def __contains__(self, item: object) -> bool`
- `def discard(self, item: str) -> None` — remove if present; used on successful `response.done` for non-cancel paths
- `def __len__(self) -> int`
- `def clear(self) -> None`

- [ ] RED: add > capacity keeps `len == capacity`; latest id still contained; oldest evicted; duplicate add does not grow.
- [ ] GREEN: implement deque+set like `CallUsageAccumulator`.
- [ ] Refactor `CallUsageAccumulator` to use `BoundedIdWindow`.
- [ ] Qwen `_suppressed_response_ids` becomes `BoundedIdWindow`. `interrupt()` uses `add`. Duplicate interrupt does not grow. Do **not** `clear()` on cancel. Session `aclose` may `clear()` because the session is dead.
- [ ] Soak: 5000 cancel ids → len <= 4096; last 10 still suppressed.

---

### Task 3: Format A package (P2 #3)

- [ ] `ruff format src tests` **only** under `apps/runtime/voice-agent`.
- [ ] `ruff check src tests` and `ruff format --check src tests` must be 0 failures.
- [ ] Do not format repo root / Control Plane.

---

### Task 4: Registry drain semantics + wire server (P2 #1)

**Files:** Modify `worker.py`, `server.py`; Test `test_hardening_worker.py`, `test_server.py`

**Interfaces:**
- `begin_drain() -> None` — alias of stop accepting; `draining` True
- `total_started: int`
- `register(...)` raises `WorkerNotAcceptingError` if draining; raises `RuntimeError` if `session_id` already registered
- `unregister(session_id) -> bool` — True once
- `async def drain(self, *, timeout_s: float | None = None) -> None` — `asyncio.wait_for` around existing gather; on timeout still `wait_idle` best-effort then clear
- Lifecycle argument optional so console sessions still register

**server.py:**
- Module `get_worker() / set_worker()` so tests can isolate.
- `local_voice_agent`: try `register(room)` immediately after job starts (before Qwen). `finally`: unregister exactly once (even config failure, CancelledError, hangup).
- `ctx.add_shutdown_callback` already finishes lifecycle; keep finish-once. Do not call `HANGUP` from `director.aclose()`.
- `__main__`: validate startup, `set_worker(WorkerRuntime())`, `server.on("worker_started")` → mark READY + start ops if enabled. Do not call non-existent `worker.drain_everything_magic()`.
- On process SIG path we cannot hook AgentServer.drain from jobs; job-level register/unregister is the production guarantee. `begin_drain()` is invoked from ops shutdown helper and tests.

- [ ] RED: draining rejects new register; duplicate register raises; unregister twice → one True; 0/1/10/50 drain still finish once.
- [ ] RED: `local_voice_agent` with injected worker registers and unregisters even when dispatch metadata is invalid (fail closed).
- [ ] GREEN: wire try/finally.
- [ ] Existing SIP e2e + `test_server.py` stay green.

---

### Task 5: Startup config validation

**Files:** Create `startup.py`; Test `test_startup.py`; Modify `.env.example`

**Interfaces:**
- `RuntimeMode = Literal["local-dev", "synthetic-test", "stage"]`
- `WorkerStartupSettings.from_env(env, *, mode: RuntimeMode | None = None)`
- Fields: mode, livekit_url, livekit_api_key_present (bool, never store secret value in summary), livekit_api_secret_present, livekit_agent_name, platform_api_url, phone_lookup_token_present, dashscope present, allow_empty_dispatch, drain_timeout_s, ops_enabled, ops_host, ops_port, provider VoiceSettings when not synthetic-test
- `sanitized_summary() -> dict[str, object]` — no secret values, no tokens
- Stage fail-fast: missing Platform URL, lookup token, Qwen key, invalid timeouts, `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=true`
- local-dev: existing VoiceSettings rules; empty-dispatch still default false
- synthetic-test: does not require LiveKit/Qwen live credentials
- Errors: `ConfigurationError("LIVEKIT_API_SECRET missing")` never includes the value
- External availability is **not** checked here (no Platform GET, no Qwen websocket)

- [ ] RED/GREEN tests for stage/local-dev/synthetic-test and secret redaction.
- [ ] `sip_preflight.py` remains read-only SIP probe. Document split in runbook.

---

### Task 6: WorkerRuntime, liveness, readiness, metrics, ops HTTP

**Files:** Create `ops.py`; Tests `test_ops.py`, `test_runtime_metrics.py`

**State:** `STARTING | READY | DRAINING | STOPPED | DEGRADED`

**Liveness:** event-loop heartbeat / process alive → `/livez` `{"status":"ok"}`. Platform/Qwen failures do **not** flip livez.

**Readiness:** STARTING/DRAINING/STOPPED/invalid config → false; READY → true; DEGRADED → true (degraded ≠ dead) unless draining.

**Metrics (process lifetime, reset on new WorkerRuntime):**
counters: sessions_started, sessions_completed, sessions_failed, user_hangups, agent_errors, qwen_disconnects, qwen_errors, tool_requests, tool_errors, tool_timeouts, interruptions, finish_attempts, finish_failures
gauges: active_sessions, peak_active_sessions, draining
latency: bounded 1024 samples per name (`startup`, `speech_end_to_first_audio`, `tool_rtt`, `barge_in_stop`, `close_to_finish`) with count/p50/p95/p99 via existing `latency.summarize`
No tenant_id / call_id / room / phone labels.

**Ops HTTP:** aiohttp on `VOICE_OPS_HOST` default `127.0.0.1`, `VOICE_OPS_PORT` default `8091`, `VOICE_OPS_ENABLED` default false. Tests bind `127.0.0.1:0`. `/status` JSON without secrets/PII/env dump.

**Integration:**
- register/unregister update metrics
- Qwen fatal/disconnect → `note_qwen_*` via optional `attach_metrics` on model (getattr pattern like attach_trace)
- tool timeout/error → metrics in `ToolInvocationClient` optional callback
- lifecycle finish failure → `finish_failures`
- interrupt() → interruptions
- SessionTrace.derived() recorded on session close

- [ ] RED/GREEN unit tests including 50 concurrent counter updates.
- [ ] Restart test: WorkerRuntime A closed, B starts with active=0, empty suppression (new Qwen session), fresh metrics.

---

### Task 7: Shutdown / drain matrix + fault metrics

**Files:** Tests `test_ops_shutdown.py` (or extend hardening worker)

Cover 0/1/10/50 drain: draining true, readyz false, new register rejected, active→0, finish duplicate 0.

Races (deterministic, FakeClock / Events, no sleep 5): shutdown+hangup, +qwen disconnect, +tool timeout, +silence/session timer, +recording pending. finish<=1 unregister<=1.

Recording failure does not flip readiness.

Finish HTTP failure: existing bounded once; metrics finish_failures += 1; cleanup continues.

- [ ] Repeat drain-50 three times.

---

### Task 8: Release gate

**Files:** `src/yino_voice_agent/release_gate.py`, `apps/runtime/voice-agent/scripts/release_gate.py`, `tests/test_release_gate.py`

**CLI:** `python -m yino_voice_agent.release_gate --mode fast|full`

Steps (full): static config (synthetic-test), pytest, ruff check, ruff format --check, critical races (hardening lifecycle + worker), stress, replay, secret file-pattern scan (`.env.local`, `*.pem`, obvious key files in A-owned tree). No real PSTN/Qwen/S3.

Verdict: PASS | FAIL | BLOCKED_EXTERNAL. Offline success is PASS with `LIVE_SIP_STATUS=NEEDS_LIVEKIT_PROVISIONING`. Any pytest/lint/format/secret fail → exit != 0. No continue-on-error.

Fast: pytest -q plus ruff, skip 50-call stress repeats.

Gate unit tests mock runner: all green → PASS; pytest fail → FAIL.

---

### Task 9: Docs + env example

**Files:** runbook, checklist, results, `.env.example`, `docs/README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `DECISIONS.md`

Windows and Linux commands (venv, pip, copy env, `python -m yino_voice_agent.server dev`, ops curl, Ctrl+C / SIGTERM). Link existing SIP stage runbook and `scripts/sip_preflight.py`. External stage: credentials/DID/trunk/dispatch/PSTN **NOT TESTED**.

---

### Task 10: Verification, review, commits

- [ ] Fresh `pytest -q`, ruff check, ruff format --check, `release_gate --mode full`.
- [ ] Race 20×, stress 3×.
- [ ] ECC/Superpowers review: registry leak, drain deadlock, metrics race, ops PII, CancelledError, unbounded IDs, B expansion.
- [ ] P0/P1 = 0 (max 5 fix rounds).
- [ ] Local commits (explicit paths only):
  1. `fix: close remaining runtime readiness gaps`
  2. `feat: add worker operational state and health`
  3. `feat: add runtime release gate`
  4. `docs: add voice worker operations runbook`
- [ ] No push.

## Plan self-review

1. **Spec coverage:** Phases 1–76 map to Tasks 1–10 (P2s → 2–4; config → 5; ops/metrics → 6–7; gate → 8; docs → 9; verify → 10). SIP preflight preserved. No B contract change required (Platform health probe = `DEPENDENCY_PROBE_UNAVAILABLE`).
2. **Placeholders:** none.
3. **Types:** `BoundedIdWindow`, `WorkerRuntime`, `WorkerStartupSettings`, `RuntimeMode` used consistently.
4. **Ownership:** A-only paths. Control Plane dirt left untouched.
