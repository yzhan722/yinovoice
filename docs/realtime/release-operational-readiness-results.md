# DEV-A Release & Operational Readiness results (OFFLINE / SYNTHETIC)

Date: 2026-09-02
Worktree: `D:\Repos\yinovoice-realtime` (DEV-A)
Branch: `feat/a-runtime-finish-once`
Start HEAD: `ece562ffec5975b12cf0d0877d91e01c485af896`
Test environment: Windows 10, voice-agent venv Python 3.12.10, pytest 8, FakeClock. No LiveKit Cloud mutation, no PSTN, no paid Qwen probe.

**Verdict: `DEV_A_RELEASE_READY_OFFLINE`**

**Real PSTN: NOT TESTED. Real calls tested: 0.**
**Live SIP: `NEEDS_LIVEKIT_PROVISIONING`.** Do not read this file as `LIVE_SIP_E2E_PASS`.

## Fresh verification (do not reuse older counts)

| Check | Result |
|---|---|
| `python -m pytest -q` | **401 passed** (~16.9s), 1 DashScope Assistants deprecation warning |
| `ruff check src tests scripts` | All checks passed |
| `ruff format --check src tests scripts` | 87 files already formatted |
| `python -m yino_voice_agent.release_gate --mode full` | **PASS** + `LIVE_SIP_STATUS=NEEDS_LIVEKIT_PROVISIONING` |
| `git diff --check` | clean |
| Critical races 20 repeats (`lifecycle` + `worker` + `ops_shutdown`) | 18 passed × 20 |
| Stress 3 repeats (hardening stress/concurrency + 50-session drain) | 8 passed × 3 |

## Versions

| Item | Value |
|---|---|
| Python | 3.12.10 |
| livekit | 1.1.15 |
| livekit-agents | 1.7.1 |
| DashScope | 1.27.2 |

Baseline at campaign start: 357 passed; ruff format drift on 12 files including `qwen_realtime.py`. See `docs/realtime/release-readiness-baseline.md`.

## Previous P2 closed

| Item | Result |
|---|---|
| WorkerSessionRegistry | Wired in `local_voice_agent`: register on job accept, unregister in `finally` (config failure, cancel, hangup). Duplicate register raises. Drain rejects new sessions. |
| Suppressed response IDs | Shared `BoundedIdWindow` (capacity 4096) with usage dedup. Duplicate cancel does not grow. No `clear()` on interrupt. |
| Qwen format | `ruff format` limited to the voice-agent package. |

## Worker lifecycle

LiveKit `AgentServer.drain` (default 3600s) is unchanged. Runtime wraps it to `begin_drain` → SDK drain → leftover registry cleanup (`VOICE_WORKER_DRAIN_TIMEOUT_SECONDS`, default 30, range 1–300) → ops close → `STOPPED`.

Per job: `JobContext.add_shutdown_callback` still drives exactly-once `/finish`.

Drain matrix (0 / 1 / 10 / 50) and 50-session drain × 3: `active_sessions → 0`, new register rejected, readyz false.

## Configuration

`WorkerStartupSettings` modes: `local-dev` | `synthetic-test` | `stage`.

Stage fail-fast: LiveKit URL/key/secret, Platform URL, lookup token, DashScope key, empty-metadata opt-in must be false. Errors name the variable only.

`synthetic-test` skips live provider credentials (pytest).

`0.0.0.0` ops host is coerced to `127.0.0.1`.

## Operations

Optional (`VOICE_OPS_ENABLED` default false). `/livez` process alive; `/readyz` accept new calls; `/status` counters only. Default bind loopback.

LiveKit Agents `GET /` is **not** used as liveness (503 on LiveKit disconnect in 1.7.1).

Platform/Qwen HTTP probes: **DEPENDENCY_PROBE_UNAVAILABLE** (no B health endpoint; no paid Qwen session for readiness).

## Metrics

Process-lifetime Worker counters + latency deque maxlen 1024. No tenant/call/phone labels. Restart = new `WorkerRuntime`. Qwen/tool/finish/hangup wired on production types and covered by tests.

Synthetic latency regression gate unchanged (loose +0.15 vs p50 0.2495 / p95 0.2941 / p99 0.2980).

## Restart / crash

Graceful: finish + unregister + empty registry.
Hard kill: **cannot** promise exactly-once `/finish`. No fake crash recovery.

## Security

`/status` has no env dump, secrets, or PII fields. Gate scans **tracked** A files for `.env` / `.env.local` / `.pem` / `.key` / `.p12` **names** (not a content oracle). Local untracked `.env.local` does not fail the gate.

## Review

- Superpowers executing-plans (inline, same worktree), TDD, verification-before-completion, ECC local review.
- Round 1 P1: `package_root()` pointed at `src/` so a real gate would run pytest in the wrong directory. Fixed; unit test asserts `pyproject.toml` + `tests/`.
- P0: 0. P1: 0 after that fix.
- P2: leftover drain sessions counted as `completed` if jobs did not unregister; hung drain finishers may complete after timeout; secret scan is filename-based.

## External

No push, PR, merge, deploy, LiveKit mutation, PSTN, or real S3.
