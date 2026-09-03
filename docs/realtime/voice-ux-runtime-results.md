# Voice UX Runtime results (SYNTHETIC / SIMULATED)

Date: 2026-09-02
Worktree: DEV-A `yinovoice-realtime`
Branch: `feat/a-runtime-finish-once`
Start HEAD (campaign): `af85e7041882f371754dc23b65e24f92cb933846`
Hardening commit: `2c2d1f82d73e17877a455711965e76ce82a5a803`
Test environment: Windows 10, `apps/runtime/voice-agent` venv Python 3.12, pytest 8, FakeClock. No LiveKit Cloud, no PSTN.

**Real PSTN calls: 0.** Status remains **NEEDS_LIVEKIT_PROVISIONING**. Do not read this as live telephone UX.

## Tests

| Suite | Result |
|---|---|
| Full `python -m pytest -q` | **357 passed** (~16.6s), 1 DashScope Assistants deprecation warning |
| Hardening baseline (prior commit) | 308 passed |
| New Voice UX tests | ~49 (state/policy/endpointing/transcript/config/replay/soak) |
| Lifecycle / silence / duration races | 20 repeats, 0 fails |
| Stress + 50-call isolation | 3 repeats, 0 fails |
| Fuzz seeds | 42, 2026, 9001 |
| SIP synthetic replay | still in full suite |
| Browser `job.metadata` path | `tests/test_server.py` still in full suite |

Ruff on campaign-owned new/changed modules: clean. Pre-existing `qwen_realtime.py` / SIP test formatting drift was **not** bulk-rewritten.

## Greeting

| Case | Result (SYNTHETIC) |
|---|---|
| Session ready → greeting → listen | `SESSION_READY` → `SPEAK_GREETING` once; then `WAITING_FOR_USER` |
| Caller interrupts greeting | `allow_interruptions=True`; Qwen uplink not dropped during `say` |
| Caller already speaking | `SKIP_GREETING`; `greeting_count` stays 0; no late greeting |
| Duplicate greeting | reconnect / second `SESSION_READY` / tool return do not greet again |
| Slow / missing config | dispatched sessions still fail closed; no default merchant |

## Silence

| Case | Result |
|---|---|
| Initial silence after greeting | 8s default → first short prompt |
| Follow-up | 12s → second prompt |
| Max prompts | 2 then polite close + finish |
| Silence during assistant speech | not treated as caller silence |
| Silence during tool | idle/silence paused; slow tool may emit one bridge phrase |
| Timer vs user speech same tick | user speech wins |
| Hangup during silence timer | finish once; timers cancelled |

## Idle / duration

| Case | Result |
|---|---|
| `max_idle_s` | 180s default; paused while user/assistant/tool active |
| Idle + disconnect | finish once |
| Idle + tool result | tool result wins; idle re-armed after |
| `max_session_s` | 1800s default; graceful `SPEAK_SESSION_LIMIT` + finish even during speech/tool |

Platform Runtime Config has no tenant fields yet. See `contract-change-request-voice-ux-timers.md`. Runtime env: `VOICE_UX_*`.

## Endpointing

Authoritative detector in `qwen-realtime` mode: **Qwen `server_vad`**. LiveKit Silero VAD is pipeline-only. `AgentSession(turn_detection="realtime_llm")`.

Synthetic timeline (`endpointing.py`): short intra-sentence pause is not a turn end; configured `silence_duration_ms` (default 450) is.

Config maps only real protocol fields: `threshold`, `silence_duration_ms`. No invented `prefix_padding`.

## Barge-in

Cancel + suppress late audio for cancelled `response.id` still in place. Quiet 嗯 / low peak does not confirm barge-in (`INPUT_BARGE_IN_PEAK`). Double interrupt stays single active assistant response. `barge_in_stop_latency` path unchanged from hardening.

## Tool UX

| Case | Result |
|---|---|
| Success | existing `[[tool:...]]` path |
| Slow (>1s) | one bridge phrase while `TOOL_RUNNING` |
| Timeout / 5xx / transport | structured `{status:error, code, customer_message}`; no HTTP/JSON to customer |
| 4xx business (`appointment_conflict`) | stays `status=error`; never rewritten to success |
| Writes | `create_appointment` / `create_callback` still 1 attempt |
| After `CLOSING`/`CLOSED` | no new tool invocation |

## Provider recovery

Policy: **`FAIL_SESSION_ON_PROVIDER_DISCONNECT`**.

Qwen WebSocket close / fatal server error finishes the session. No silent reconnect (conversation state is not proven restorable). No second provider call solely to speak a fallback phrase. Malformed events still skipped (hardening).

## Context

Qwen `message_truncation=False`, `mutable_chat_context=False`. Client `truncate()` raises. **PROVIDER_MANAGED_NO_CLIENT_TRUNCATE**. No client delete hack.

Trace order cap 512. Usage id window 4096. Director recent-action log 32. Silence prompt count bounded by config.

## Stress / soak / fuzz (SYNTHETIC)

- 50 concurrent directors: isolated, finish=1, greeting≤1
- 500-turn FakeClock soak with silence / barge-in / tool / long-answer cancel
- 1000 synthetic sessions keep invariants
- Seeded fuzz: no illegal phase after `CLOSED`, finish≤1, greeting≤1

## Synthetic latency regression

Same FakeClock recipe as hardening (100 traces, `0.2 + i*0.001`):

| | Previous | Current | Gate |
|---|---|---|---|
| p50 | 0.2495 | 0.2495 | +0.15 |
| p95 | 0.2941 | 0.2941 | +0.15 |
| p99 | 0.2980 | 0.2980 | +0.15 |

These are **not** telephone RTT.

## Security

- Ordinary logs: no transcript body, no prompt, no raw tool args, no E.164
- `customer_message` sanitizes HTTP/JSON/traceback
- No secrets in `.env.example` (`VOICE_UX_*` comments only)
- No Control Plane / Call Insights implementation in this campaign

## Known external blockers

- No LiveKit SIP credentials / trunk / DID / dispatch in this worktree
- Real barge-in / silence / greeting UX on PSTN is **unverified**
- Per-tenant Voice UX timers need a future B contract (request only)

## P2 leftovers (not Voice UX blockers)

- `WorkerSessionRegistry` still not wired into `server.py` (hardening leftover)
- Qwen `_suppressed_response_ids` set is still unbounded per session
