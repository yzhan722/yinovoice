# 2026-09-01 Egress / usage / lookup auth

Status: **code landed** on `feat/a-runtime-finish-once`. No production overlay. No live S3 upload in CI.

## LiveKit Egress → S3

Control Plane starts **RoomComposite** audio-only OGG egress when all of these are set:

- `RECORDING_S3_ENDPOINT`
- `RECORDING_S3_BUCKET`
- `RECORDING_S3_ACCESS_KEY`
- `RECORDING_S3_SECRET_KEY`
- `LIVEKIT_API_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`

Object key is unchanged: `recordings/{tenant_id}/{yyyy}/{mm}/{call_record_id}.ogg`.

Inbound session start still swallows egress errors (`recording_status=failed`, `egress_start_failed`). Incomplete S3 config leaves egress off. Tests use a Fake sink; the LiveKit client is mocked and never talks to a real bucket.

Optional `RECORDING_S3_REGION` (default `us-east-1`). Uploads use `force_path_style=true` for S3-compatible endpoints.

## `response.done` Token 对账

Qwen `response.done.usage` is accumulated in Runtime and posted on `POST /api/v1/call-sessions/{id}/finish` as optional `usage`:

```json
{
  "input_audio_tokens": 0,
  "input_text_tokens": 0,
  "output_audio_tokens": 0,
  "output_text_tokens": 0,
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "response_count": 0
}
```

Stored as nullable JSONB `call_records.usage` (Alembic `20260901_0012`). Missing usage keeps the previous column null. Logs only `response_count` and `total_tokens` — no transcripts, audio, or secrets.

## Lookup 鉴权（Control Plane）

`GET /api/v1/phone-numbers/lookup` requires header `X-Phone-Lookup-Token` matching `PHONE_LOOKUP_TOKEN`.

- Empty configured token → 401 (fail closed; no public number enumeration)
- Missing / wrong header → 401
- Runtime unset token → fail closed before HTTP
- 401/404/5xx still must not fall through to a local default agent

Same token is required on the voice-agent worker (`PHONE_LOOKUP_TOKEN`). Preflight reports it as missing when blank.
