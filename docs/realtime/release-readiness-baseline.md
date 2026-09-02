# Release readiness baseline (SYNTHETIC)

Date: 2026-09-02
Worktree: DEV-A `D:\Repos\yinovoice-realtime`
Branch: `feat/a-runtime-finish-once`
HEAD at baseline: `ece562ffec5975b12cf0d0877d91e01c485af896`

This is an offline snapshot. It is not live telephone evidence.

## Runtime

| Item | Value |
|---|---|
| Python | 3.12.10 |
| livekit | 1.1.15 |
| livekit-agents | 1.7.1 |
| DashScope | 1.27.2 |
| pytest | 357 passed (~17s), 1 DashScope Assistants deprecation warning |

## Ruff (before this campaign)

| Check | Result |
|---|---|
| `ruff check src tests` | 2 RUF001 in `tests/test_tool_protocol.py` (Chinese fullwidth comma in spoken fixture) |
| `ruff format --check src tests` | 12 files would be reformatted, including `qwen_realtime.py` |

This campaign formats the voice-agent package only and ignores intentional Chinese fixtures.

## Live SIP

Status: **NEEDS_LIVEKIT_PROVISIONING**

Real PSTN calls: **0**
