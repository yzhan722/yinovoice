# 2026-09-01 LiveKit SIP inbound Stage runbook

Status: code is **READY_FOR_LIVE_SIP_TEST**. 2026-09-01 live attempt: **BLOCKED** / **NEEDS_LIVEKIT_PROVISIONING** — see `docs/realtime/2026-09-01-live-sip-e2e-result.md`. This runbook does **not** authorize buying numbers or mutating trunks.

## What the Runtime does

```text
LiveKit SIP participant
  -> normalize (livekit_sip)
  -> GET /api/v1/phone-numbers/lookup?number=<callee>
     header X-Phone-Lookup-Token
  -> DispatchMetadata (tenant / voice agent / config version)
  -> existing create_dispatched_runtime()
  -> existing AgentSession + tools + exactly-once /finish
     (optional usage from Qwen response.done)
```

Empty `ctx.job.metadata` plus `ParticipantKind.SIP` selects this path.

Non-empty job metadata keeps the existing Platform-dispatch / browser path.

Ordinary Web participants with empty metadata remain fail-closed unless `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=true`.

## Mapping (LiveKit docs + livekit 1.1.x / agents 1.7.1)

| Field | Source | Notes |
|---|---|---|
| provider | `livekit_sip` | Upstream Twilio/Telnyx is not the Runtime provider |
| provider_call_id | `sip.callIDFull` then `sip.callID` | Missing both is malformed; no random IDs |
| caller_number | `sip.phoneNumber` | Optional; HidePhoneNumber / anonymous -> `None` |
| callee_number | `sip.trunkPhoneNumber` | Required; never fall back to caller |
| room | `ctx.room.name` | Unique per individual dispatch rule |
| hangup | SIP BYE → participant `DisconnectReason.CLIENT_INITIATED`; session close is `CloseReason.PARTICIPANT_DISCONNECTED` | `user_hangup` |
| unclear close | other documented reasons | generic `completed` |

`sip.twilio.callSid` is optional debug correlation only.

## Platform lookup

A does not open Platform DB.

Expected object keys: `tenant_id`, `voice_agent_instance_id`, `config_version`, `enabled`. Extra keys (full `PhoneNumberView`) are ignored.

Failure behavior is **fail closed** (no local default agent):

- 404 unknown -> `destination not found`
- `enabled=false` -> `destination is disabled`
- timeout / transport error -> `destination lookup failed`
- HTTP 401 / 403 -> `destination lookup HTTP …` (token missing or wrong)
- HTTP 5xx -> `destination lookup HTTP …`
- Runtime token unset -> fail closed before HTTP (`destination lookup token is not configured`)

Header: `X-Phone-Lookup-Token`. Control Plane `PHONE_LOOKUP_TOKEN` empty ⇒ every lookup is 401.

## Stage preflight (read-only)

Worker env:

```text
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
PLATFORM_API_URL
LIVEKIT_AGENT_NAME   # default yino-customer-service
PHONE_LOOKUP_TOKEN   # must match Control Plane
```

```text
python scripts/sip_preflight.py
python scripts/sip_preflight.py --probe
```

`--probe` may list inbound trunks. It must not create, update, or delete trunks or dispatch rules.

## Dispatch rule (long-lived)

See `integrations/sip/livekit/dispatch-rule.example.json`.

- One individual rule, unique room per call (`roomPrefix`: `yino-sip-`)
- `roomConfig.agents[0].agentName` = `LIVEKIT_AGENT_NAME`
- Agent `metadata` empty so callee lookup can choose the tenant
- `hide_phone_number`: true (caller not copied into room name / identity)
- Do not create a new rule per phone call from Runtime
- Confirm the **live** rule matches this template; leftover agent metadata skips lookup and pins every inbound call to one tenant

## Live-test gate (no code P0)

- Worker: `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=false`
- `PHONE_LOOKUP_TOKEN` set on both Control Plane and Runtime; lookup is not a public enumerator
- Prefer `hide_phone_number: true` on the live rule

## Live test still needs (external)

- LiveKit project
- Pre-provisioned inbound SIP trunk
- Matching dispatch rule
- Test DID + SIP provider routing
- Platform number row for that callee, enabled, bound to the intended tenant/agent

## Not in this stage

- Real PSTN call (needs separate authorization)
- Trunk / dispatch mutations from this repo
- Live S3 credentials / running Egress worker (code path exists; still needs env)
- Outbound AI calling
- Production deploy
