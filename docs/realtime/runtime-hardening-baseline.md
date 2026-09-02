# Runtime Hardening Baseline

Recorded: 2026-09-02. Synthetic Runtime only. Not a live SIP result.

## Git

- Repository: `https://github.com/yzhan722/yinovoice`
- Worktree: DEV-A (`D:\Repos\yinovoice-realtime`)
- Branch: `feat/a-runtime-finish-once`
- HEAD: `af85e7041882f371754dc23b65e24f92cb933846`
- `origin/feat/a-runtime-finish-once`: same
- `origin/main`: `9b66f5d0e8e632fa3e8349192a38fcffb03f2ba4`

## Environment

- OS: Windows 10 (`win32 10.0.19045`)
- Python: 3.12.10
- livekit: 1.1.15
- livekit-agents: 1.7.1
- dashscope: 1.27.2
- httpx: 0.28.1
- aiohttp: 3.14.3
- pytest: 8.4.2
- ruff: 0.16.5

## Voice Agent baseline

Command: `python -m pytest -q` in `apps/runtime/voice-agent`

- tests passed: **230**
- tests failed: **0**
- warnings: 1 (`dashscope.assistants` Assistants API DeprecationWarning)
- runtime: ~21.5s

## A baseline

Existing Runtime coverage before this campaign: Qwen Realtime, AgentSession lifecycle, Tool client, SessionTrace, SIP normalize/dispatch/preflight, Fake Telephony, usage accumulation, finish exactly-once, concurrency harness (10 fake sessions).

## Known warnings

- DashScope Assistants API deprecation in `dashscope/__init__.py`. Out of Runtime control.

## B-side CI / local

Mark as **OUT_OF_SCOPE_B_BASELINE**. This campaign does not fix:

- Control Plane API tests
- Call Insights sqlite / scheduling tests
- Web UI

Uncommitted Control Plane / web files in this worktree were left untouched.

## External

- Real PSTN / LiveKit SIP provisioning: **NEEDS_LIVEKIT_PROVISIONING**
- Real calls tested: **0**
