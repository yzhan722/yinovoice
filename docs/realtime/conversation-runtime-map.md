# Conversation Runtime Map

Recorded from `apps/runtime/voice-agent` on 2026-09-02. This is the code path, not a live-call claim. All later Voice UX results are **SYNTHETIC / SIMULATED**.

## Layers

```text
Realtime Provider (QwenRealtimeModel / pipeline)
  → ConversationDirector / ConversationPolicy (Voice UX)
  → AgentSession (LiveKit)
  → ToolOrchestrator / ToolInvocationClient
  → CallLifecycleClient
```

Authoritative turn-end in `qwen-realtime` mode: **Qwen `server_vad`**. LiveKit Silero VAD is only loaded for `pipeline` mode. `AgentSession(turn_detection="realtime_llm")` does not run a second endpointing system.

## Greeting

- Dispatched sessions wait for Platform config (`create_dispatched_runtime` / `DispatchMetadata.from_json`). Missing tenant or service fails closed. There is no default merchant fallback.
- After `session.start`, `ConversationDirector` handles `SESSION_READY`.
- Normal: one `session.say(greeting, allow_interruptions=True, add_to_chat_ctx=False)` in `server.py`.
- Greeting text: `RuntimeCustomerService.greeting` or `VoiceSettings.greeting`.
- If the caller is already speaking, policy emits `SKIP_GREETING` and does not speak.
- Qwen `say()` is interruptible. Uplink PCM is forwarded during `say` (barge-in uses `INPUT_BARGE_IN_PEAK` so quiet 嗯 / echo is less likely to cancel).
- `GREETING_FINISHED` is notified when the Qwen say response completes (`qwen greeting finished`).

## When listening starts

- Qwen drops uplink until `session.updated` (`_session_accepts_audio`).
- After greeting finishes, policy is `WAITING_FOR_USER` and arms silence / idle / session timers.

## When the user is done speaking

- Qwen `input_audio_buffer.speech_stopped` (server VAD `silence_duration_ms`, default 450).
- Backup only: stuck-speech watchdog commit if `speech_stopped` never arrives.
- Empty / noise-only / duplicate-`item_id` finals are dropped (`FinalTranscriptGate`) and are not appended to lifecycle.

## When a response is created

- Server VAD auto-creates a response after commit. Runtime does not send a second `response.create` for that turn (`qwen_realtime.py`).
- `generate_reply` / `say()` are guarded against an already-active response.

## Interruption

- `speech_started` while an assistant response is active: barge-in confirm (`BARGE_IN_CONFIRM_S` + meaningful appends) then `interrupt()` → `response.cancel` + `_suppressed_response_ids`.
- Late audio/text for suppressed ids is dropped (`_is_response_suppressed`).
- Policy: `USER_SPEECH_START` during assistant speech → `CANCEL_ASSISTANT` + `SUPPRESS_LATE_AUDIO`.

## Silence / idle / duration

- None of these existed as session UX before this campaign. They live in `ConversationPolicy` + `ConversationDirector` (FakeClock-friendly; production uses one timer task).
- Defaults: initial silence 8s, follow-up 12s, max 2 prompts, idle 180s, max session 1800s. Env: `VOICE_UX_*` in `.env.example`.
- Silence prompt loses to user speech in the same tick. Timers cancel on `HANGUP` / `CLOSED`.

## Session close

- `AgentSession` `close` and/or `JobContext.add_shutdown_callback` → `CallLifecycleClient.finish` once.
- Director `REQUEST_FINISH` uses the same `request_finish` helper.
- `ToolOrchestrator.mark_closed()` cancels in-flight tool tasks.

## Tools

- Hidden `[[tool:...]]` markers. Writes (`create_appointment`, `create_callback`) are not auto-retried. `check_availability` may retry transport/5xx once.
- Structured errors include `customer_message` with HTTP/JSON/trace stripped. Appointment conflict stays `status=error`.
- Optional bridge phrase after `VOICE_UX_TOOL_BRIDGE_AFTER_S` while `TOOL_RUNNING`.

## Provider disconnect

- Policy constant: `FAIL_SESSION_ON_PROVIDER_DISCONNECT`.
- Qwen connection close / fatal server error notifies the director and finishes. No silent reconnect. No second provider call just to speak a fallback phrase.

## Context

- Qwen `message_truncation=False`, `mutable_chat_context=False`. `truncate()` raises. Context is provider-managed. Runtime does not client-delete conversation items.
