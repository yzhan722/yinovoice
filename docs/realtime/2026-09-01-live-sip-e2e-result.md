# DEV-A Live SIP Stage Result

Date: 2026-09-01  
Worktree: `feat/a-runtime-finish-once`  
Code gate (unchanged): **READY_FOR_LIVE_SIP_TEST**

Verdict: **BLOCKED**  
Stop state: **NEEDS_LIVEKIT_PROVISIONING**

This pass was read-only. No LiveKit trunks, dispatch rules, numbers, or worker env were created or changed.

## Preflight (this machine)

`python scripts/sip_preflight.py --probe` (voice-agent venv, no `.env.local`, no process env):

```text
FAIL LIVEKIT_URL: missing
FAIL LIVEKIT_API_KEY: missing
FAIL LIVEKIT_API_SECRET: missing
FAIL PLATFORM_API_URL: missing
ok LIVEKIT_AGENT_NAME: yino-customer-service
probe skipped: credentials incomplete
```

| Check | Result |
|---|---|
| Worker running / connected to LiveKit | No (`yino_voice_agent.server` not running) |
| Local LiveKit `:7880` | Not listening |
| Local Platform `:8000` | Not listening |
| `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV` | Not set here; `.env.example` is `false` (cannot confirm a live worker) |
| `PLATFORM_API_URL` private | Unverifiable (variable missing) |

## Missing for a real inbound call

1. Voice-agent `.env.local` with `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `PLATFORM_API_URL` (and real DashScope values for audio)
2. Running named worker (`LIVEKIT_AGENT_NAME`, default `yino-customer-service`)
3. Pre-provisioned inbound SIP trunk with a test DID
4. Long-lived dispatch rule: matching trunk, `agentName` = worker name, **empty** agent metadata, prefer `hide_phone_number=true`
5. Platform reachable on a **private** URL, with an enabled phone-number row for that callee bound to the intended tenant/agent
6. A human (or authorized handset) to place the inbound PSTN call — this agent cannot dial out (outbound is out of scope)

Phone ingress: **not verified** (no DID / trunk visible)  
Trunk: **unknown** (probe skipped)  
Dispatch: **unknown** (not listed; would require LiveKit credentials, still read-only)  
Agent dispatch: **not running**  
Platform lookup: **not reachable from this session**

## Real calls tested

Real calls tested: **0**  
Successful calls: **0**  
Failed calls: **0**

STT: not exercised  
LLM: not exercised  
TTS: not exercised  
Tools: not exercised  

Hangup: not exercised  
Finish requests per call: n/a  

Concurrency / repeated calls: n/a (simulated 5-call isolation remains in unit/e2e only)

Latency:  
startup: n/a  
turn: n/a  
tool_rtt: n/a  
close_to_finish: n/a  

Problems found: Live SIP E2E cannot start until the external resources above exist and a caller can dial the test DID.  
Fixes made: none (no architecture change this pass)  

External resources changed: **None**

Unknown-number fail-closed: not re-tested on a live trunk (would need a second unbound DID or trunk change). Existing automated tests still cover lookup 404.

## Next

Not `READY_FOR_RECORDING_EGRESS`.

When you have a Stage DID + trunk + empty-metadata dispatch rule + private Platform + running worker:

1. Put credentials only in `apps/runtime/voice-agent/.env.local` (never commit)
2. Start the worker: `.\.venv\Scripts\python.exe -m yino_voice_agent.server dev`
3. Confirm `sip_preflight.py --probe` shows inbound trunks
4. Confirm the **live** dispatch rule has empty agent metadata
5. Dial the test number from a real phone and re-run this checklist
