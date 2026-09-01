# LiveKit SIP inbound templates (DEV-A)

These files are **configuration templates** for a later Stage live telephone test.

They do **not** create trunks, dispatch rules, or phone numbers.

## Required external resources (not provisioned by this campaign)

- LiveKit Cloud or self-hosted project
- Pre-created inbound SIP trunk
- One long-lived dispatch rule (reuse; never create a rule per call)
- Test DID routed by the SIP provider to that trunk
- Platform API `GET /api/v1/phone-numbers/lookup` for the callee E.164 number, with header `X-Phone-Lookup-Token`

## Runtime worker

The voice-agent worker name comes from `LIVEKIT_AGENT_NAME` (default `yino-customer-service`).

Dispatch rule `roomConfig.agents[].agentName` must match that value.

Leave agent `metadata` **empty**. Non-empty job metadata takes the explicit Platform-dispatch path and **skips** callee lookup. A static tenant in the rule would pin every inbound call to one merchant.

China PSTN trunks often present callee as `0519…`, `010…`, or `400…` rather than `+86…`. Runtime maps those forms to E.164 before Platform lookup. Bind the Yino phone-number row as E.164 (for Changzhou landline: `+86519…`).

Set `hide_phone_number` to **true** for the first live DID so LiveKit does not put the caller into the room name or identity. Runtime already treats a hidden caller as `caller_number=None`.

Username/password trunks use `inbound-trunk.example.json`. Operator IP-ACL trunks (no SIP user) use `inbound-trunk.ip-acl.example.json` and must list the carrier signaling IPs in `allowed_addresses`.

## Room naming

Use an **individual** rule so each call gets a unique room.

LiveKit currently may put the caller number into individual room names. Yino Runtime logs redact E.164 strings; LiveKit's own traces may still record the room name.

## Read-only preflight

From the repo root (no trunk mutations):

```text
python scripts/sip_preflight.py
python scripts/sip_preflight.py --probe
```

`--probe` lists inbound trunks if credentials are present. It never creates or updates resources.

## Out of scope here

- Outbound / campaign calling
- Buying numbers
- Editing production trunks or rules
- Live S3 credentials (Control Plane Egress client is implemented separately; see `docs/realtime/2026-09-01-egress-usage-lookup-auth.md`)
