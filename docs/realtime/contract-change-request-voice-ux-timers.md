# Contract change request — Voice UX timers (DEV-A → DEV-B)

Date: 2026-09-02
Status: **request only**. DEV-A did not change Control Plane APIs.

## Why

Voice UX silence / idle / max-session currently use Runtime defaults (`VOICE_UX_*`). Tenants cannot publish different telephone wait times through Platform Runtime Config.

## Ask (optional future fields on published runtime config)

If product wants per-tenant control, consider additive fields such as:

- `voice_ux.initial_silence_s`
- `voice_ux.followup_silence_s`
- `voice_ux.max_silence_prompts`
- `voice_ux.max_idle_s`
- `voice_ux.max_session_s`

Validation should remain fail-closed. Missing fields must keep current Runtime defaults.

## Not requested

- Outbound calling
- Billing
- Insights
- LiveKit SIP resource mutation
