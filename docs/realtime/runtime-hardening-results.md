# Runtime Hardening Results

Recorded: 2026-09-02. All latency numbers are **SYNTHETIC**. Not live SIP / PSTN.

## HEAD

`af85e7041882f371754dc23b65e24f92cb933846` (campaign started here; local uncommitted Runtime hardening on top)

## Test environment

- OS: Windows 10
- Python: 3.12.10
- livekit: 1.1.15
- livekit-agents: 1.7.1
- dashscope: 1.27.2
- httpx: 0.28.1
- aiohttp: 3.14.3

Voice Agent: **308 passed** in ~16s (`python -m pytest -q` in `apps/runtime/voice-agent`). 1 DashScope Assistants deprecation warning.

## Concurrency

- 10 / 25 / 50 concurrent synthetic calls: isolated tenants, transcripts, tools, finish, usage
- Cross-session contamination: 0
- Cross-tenant contamination: 0

## Lifecycle

Race matrix (20 repeats): hangup+shutdown, hangup+agent_error, hangup+tool_timeout, agent_error+shutdown, Qwen/LiveKit disconnect pair, session close+shutdown, multiple close callbacks, finish while append in flight.

- Duplicate `/finish` HTTP: 0
- Precedence unchanged: `agent_error` > `user_hangup` > `completed`

## Failure injection

Shared `FailureScenario` + `FakePlatform`: delay, tool timeout, 4xx/5xx, malformed/empty body, connect/DNS-like errors, lookup 401/404/500.

## Qwen Realtime

- Unexpected events (`session.created`, unknown types): session stays up
- Malformed JSON / wrong field types: skipped, usage not polluted
- Duplicate `response.done` with the same protocol `response.id`: counted once
- Interruption: one `response.cancel`; late audio discarded; hangup+error after cancel does not crash

## Tool Runtime

- `check_availability` still retries transport/5xx once
- `create_appointment` / `create_callback` do not retry
- Hangup cancels in-flight tool tasks; no resurrect after close
- `CancelledError` propagates from the tool client

## Latency — SYNTHETIC

FakeClock single-trace example (seconds):

- startup: 0.12
- speech_end_to_transcript: 0.08
- transcript_to_model: 0.03
- model_to_first_audio: 0.15
- speech_end_to_first_audio: 0.26
- tool_rtt: 0.05
- barge_in_stop: 0.025
- close_to_finish: 0.04

`speech_end_to_first_audio` over 100 synthetic traces (`0.200 + i*0.001`):

```text
count: 100
p50: 0.249500
p95: 0.294050
p99: 0.298010
```

These are FakeClock deltas, not phone-network RTT.

## Soak / leaks

- 500-turn session on FakeClock (~30 min simulated): 1 finish, 1000 messages
- 1000 `response.done` (with duplicate ids): response_count 1000, no double count
- Repeated Qwen connect/aclose: Runtime-owned tasks return to baseline
- Tool/Lifecycle/Resolver share injected `httpx.AsyncClient` (no per-request client)

Windows: `/proc/self/fd` not used.

## Replay

- Sanitized fixture schema v1; secrets/audio/transcripts/full numbers stripped on load
- Same fixture ×3: identical finish, tools, usage, trace order
- SIP synthetic matrix: normal, hidden/missing caller, fallback callID, missing callee/callID, lookup 401/404/500, unknown/disabled destination, lookup timeout

## Shutdown

WorkerSessionRegistry drain: 0 / 1 / 10 / 50 sessions, one finish each, reject new registers. Uses existing LiveKit `add_shutdown_callback` in production; no invented drain API.

## Recording seam

Disabled / start success / start failure / session ends before start / finish while pending. Failures do not raise into the voice path. No real S3.

## Security

- Qwen fatal errors no longer log raw event dicts
- Tool/lifecycle failures log `error_type`, not exception repr/URLs
- Lookup query strings stripped by `sanitize_url_for_log`
- Dispatch still fail-closed (no default tenant)

## Known limitations

- Real PSTN still **NEEDS_LIVEKIT_PROVISIONING**
- Synthetic load is not a substitute for Stage DID
- Control Plane / Call Insights CI: **OUT_OF_SCOPE_B_BASELINE**
