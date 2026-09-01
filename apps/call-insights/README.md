# VAPI Call Insights

VAPI Call Insights normalizes VAPI end-of-call events, stores calls and
DeepSeek analysis in SQLite, writes report artifacts, and durably plans
outbound reports. Replay uses the deterministic Mock AI provider by default
and does not require a server.

## Offline quick start

Node.js 24 is required.

```powershell
cd apps/call-insights
npm install
npm test
npm run typecheck
npm run replay -- --profile lucaplus --file fixtures/vapi/end-of-call.json --wait --database .tmp/quickstart.sqlite --artifacts .tmp/quickstart-artifacts
```

The replay command prints only its status, call ID, job ID, and local artifact
paths. It does not print the event ID, transcript, summary, recording URL, or
AI analysis.

## Replay and serve commands

Replay one JSON envelope through the same normalizer, ingestion service,
SQLite store, Worker, AI provider, and artifact writer used by the local API:

```powershell
npm run replay -- --profile lucaplus --file fixtures/vapi/end-of-call.json --wait
npm run replay -- --profile inp-group --file fixtures/vapi/end-of-call.json --wait
```

Supported replay options are:

```text
--profile <lucaplus|inp-group>
--file <path>
--wait
--database <path>
--artifacts <path>
```

Without `--wait`, an analysis job remains queued in SQLite. With `--wait`, the
CLI runs local Worker iterations until that job succeeds or fails. A duplicate
wait replay recovers only its requested job and only after its running lease is
older than 15 minutes. A fresh job owned by another process is left unchanged;
the CLI prints the fixed `active` status and exits nonzero without invoking AI
or writing artifacts. Worker startup applies the same 15-minute stale cutoff.
An owner token and heartbeat remain deferred: each DeepSeek analysis has at
most four 60-second attempts plus bounded 1/2/4-second retry delays, so both
sequential analysis requests are bounded to about 8 minutes 14 seconds of
network work, comfortably below the 15-minute stale-job lease. Shutdown also
aborts the currently active request before waiting for the Worker.

The optional local HTTP API binds to `127.0.0.1:3210` by default:

```powershell
npm run serve
```

Set `LISTEN_HOST=0.0.0.0` only when a reverse proxy or tunnel must reach this
process. `HOST` is ignored. Set `PUBLIC_ORIGIN` to the public `https://`
origin that rating stars and `/recording` links should use. `n8n.cloud`
origins are rejected. Replay does not start Fastify or open a TCP listener.

Webhook ingest is already `POST /v1/vapi/<lucaplus|inp-group>`. Do not PATCH
VAPI or change assistant Server URLs until an explicit cutover.

`GET /recording?profile=<slug>&call_id=<id>` 302s to a fresh VAPI GET
presigned URL for calls that already exist in local SQLite. It is not an open
VAPI proxy. Unsigned R2 URLs are never written into HTML.

Outbound mail is separated from analysis by the SQLite outbox. `off` creates no
rows, `shadow` creates permanently suppressed audit rows, and `live` queues
only calls completed at or after the exact UTC `MAIL_CUTOVER_NOT_BEFORE`.
The separately deployed mail worker is the only general sending component.
Replay and shadow replay force sending off regardless of environment settings.

## Profiles

- `lucaplus` — LucaPlus branding and migration-audit report-role metadata.
- `inp-group` — INP Group branding and migration-audit report-role metadata.

The two profiles use one processing pipeline. Manifests contain only
non-address role labels such as `customer-report-primary` and
`quality-report-internal`; default runtime Profiles contain no routable
recipient address and no label is passed to a sending component.

## AI provider configuration

Mock is the default provider. It is deterministic and makes no network calls.
No environment variables are needed for offline use.

DeepSeek is optional and is enabled only when both variables are explicitly
set:

```powershell
$env:AI_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "<key>"
```

That opt-in mode permits outbound HTTPS only to the fixed DeepSeek endpoint.
Redirects are rejected, and every attempt has a fresh 60-second deadline.
Unset `AI_PROVIDER` (or set it to `mock`) for offline replay. Never place a key
in a fixture, command output, SQLite data, or generated artifact.

## Local storage and artifacts

Defaults:

- SQLite: `data/vapi-call-insights.sqlite`
- Artifacts: `artifacts/<profile>/<call_id>/`

SQLite uses WAL mode and a bounded five-second busy timeout so separate local
CLI and server processes can wait briefly for one another without waiting
indefinitely.

Each successful call directory contains:

```text
call.json
customer-report.html
quality-report.html
manifest.json
```

Use `--database` and `--artifacts` to override the replay locations. Runtime
data, artifacts, coverage, `.env`, `node_modules`, and `.tmp` are ignored at
the repository root.

## Local rating and recording routes

After starting the local API, customer reports link to:

```text
GET http://127.0.0.1:3210/rating?score=<1-5>&call_id=<id>&profile=<slug>
GET http://127.0.0.1:3210/recording?call_id=<id>&profile=<slug>
```

Email clients cannot submit a POST from inside the message, so the 1–5 links
are still GET. That GET does not write a score (link scanners would otherwise
rate the call). It returns a short capture page that auto-submits POST `/rating`
in the browser. The POST is the only write, then the customer sees “Rating
saved”. Local `file://` previews skip the auto-submit.

Structured local clients can use:

```text
POST http://127.0.0.1:3210/v1/ratings
```

Ratings are saved only in the configured SQLite database.

## n8n replacement prep (do not switch VAPI yet)

These pieces are in the app now. Mail dispatch stays in `shadow`. Assistant
Server URLs stay on n8n until shadow acceptance and an explicit cutover.

1. `npm run serve` already starts Fastify plus the analysis worker.
2. Ingest path is `POST /v1/vapi/lucaplus` and `POST /v1/vapi/inp-group`.
3. Default bind is `127.0.0.1:3210`. Use `LISTEN_HOST=0.0.0.0` only behind a
   tunnel or reverse proxy. `HOST` is ignored.
4. Set `PUBLIC_ORIGIN` to your public `https://` origin so stars and recording
   links are not `n8n.cloud` and not a 30-minute R2 URL. Default remains
   `http://127.0.0.1:3210`.
5. Set `VAPI_API_KEY` so `GET /recording` can refresh a presigned URL with a
   VAPI GET. Missing key or unknown local call returns `recording_unavailable`
   / `not_found`. The process never writes raw VAPI GET JSON to disk.
6. Set `WEBHOOK_AUTH_REQUIRED=true` and provision a high-entropy
   `WEBHOOK_AUTH_TOKEN` before exposing ingest. VAPI must eventually send the
   same bearer value through a VAPI Custom Credential.
7. Keep `OUTBOUND_MODE=shadow`, keep the mail systemd unit disabled, and verify
   real calls with `npm run shadow:replay`.
8. Last step, not done here: change VAPI Server URL and retry policy away from
   n8n, set a future cutover timestamp, and enable live mail.

Public server deployments set `APP_ENV=production`. That mode refuses startup
unless the origin is HTTPS, VAPI and DeepSeek keys are present, DeepSeek is the
selected provider, webhook authentication is enabled, and its token is at
least 32 characters. Live outbound enforces DeepSeek and authentication even
outside production mode. End-of-call webhooks must also contain the exact
assistant ID assigned to their URL profile.

Transient analysis failures are retried automatically up to three claimed job
attempts. A terminal failed job can be retried only from loopback with
`POST /v1/jobs/<jobId>/retry`; Nginx does not expose job routes publicly.

## Hardened Linux deployment

Deployment assets are under `deploy/`. The API and mail worker run as separate
unprivileged accounts, share only the runtime group, use different environment
files, and can write only runtime data and logs. The API listens on loopback
port 3210. The supplied Nginx vhost proxies only `calls.yino.au` to that
loopback listener, caps request bodies at 5 MiB, and does not expose the
PII-bearing job/call diagnostic routes.

First inspect a release without changing the server:

```bash
python3 deploy-calls-yino.py --host <ssh-host> --dry-run
```

The real deploy uses SSH agent/config credentials, packages only an explicit
source allowlist with normalized Linux modes, requires Node.js 24, installs an
immutable content-identified release under
`/opt/vapi-call-insights/releases`, and runs `npm ci`. Activation restarts the
API and probes its loopback health route; failure restores the previous
symlink and units. It leaves the mail service disabled by default. It does not
install the Nginx vhost and does not create real environment files, TLS
certificates, secrets, or recipient addresses.

Provision these files directly on the server:

```text
/etc/vapi-call-insights/api.env
/etc/vapi-call-insights/mail.env
/etc/vapi-call-insights/mail-recipients.json
```

Use the committed examples as schemas, not as production values. Keep both
environment files root-owned mode `0600`. The mail worker opens the recipient
file itself, so that file must be owned by `vapi-call-insights-mail`, mode
`0400`, and its exact SHA-256 must be stored in
`MAIL_RECIPIENT_CONFIG_SHA256`. During shadow acceptance:

```text
OUTBOUND_MODE=shadow
MAIL_CUTOVER_NOT_BEFORE=
```

Do not start `vapi-call-insights-mail.service`. Install the Nginx file only
after checking that no existing vhost owns `calls.yino.au`; let Baota provision
and retain the TLS directives. Test with `nginx -t` before reload.

At live cutover, both API and mail env files must independently contain
`OUTBOUND_MODE=live` and the same exact UTC cutover timestamp. The mail worker
refuses to start in any other mode and rechecks each queued call's completion
time before SMTP.

Deployment enables the committed daily backup and retention systemd timers.
Their underlying commands can also be run manually:

```bash
/opt/vapi-call-insights/current/scripts/backup-runtime.sh
cd /opt/vapi-call-insights/current && npm run runtime:retain
```

The backup script writes a private temporary SQLite `.backup`, verifies
`quick_check` read-only, atomically publishes it, and keeps backups for 30
days. Retention removes terminal call PII and artifacts after 90 days while
preserving scrubbed outbox audit metadata; pending analysis or mail is skipped.

For a manual code-only rollback, keep mail stopped, save the current release,
then repoint and probe:

```bash
sudo systemctl disable --now vapi-call-insights-mail.service
readlink -f /opt/vapi-call-insights/current
sudo ln -sfn /opt/vapi-call-insights/releases/<known-good-release> /opt/vapi-call-insights/current.next
sudo mv -Tf /opt/vapi-call-insights/current.next /opt/vapi-call-insights/current
sudo systemctl daemon-reload
sudo systemctl restart vapi-call-insights.service
curl --fail --max-time 5 http://127.0.0.1:3210/livez
```

Do not restore SQLite for a code-only rollback. Database restore is a separate
data-loss operation: first stop both units and timers, preserve the current
database and WAL files, verify the selected backup with
`sqlite3 -readonly ... 'PRAGMA quick_check;'`, restore it, then start and probe
the API. Never enable the mail unit during rollback unless the restored outbox
and cutover gate have been reviewed.

## Safety and fixture data

**The API and analysis worker under `src/` cannot send email, SMS, WhatsApp, or
Twilio requests.** The separate `tools/mail-worker-entrypoint.ts` process owns
the Nodemailer adapter. Its service has a different environment file from the
API and is disabled throughout shadow acceptance.

All repository fixtures are fictional, including names, phone numbers, email
addresses, and recording URLs. Exported n8n workflow JSON and `pinData` are not
runtime inputs.

## Isolated real-email test

The repository has two explicit, local-only commands that can send email. The
production application under `src/` cannot reach either of them. Automated
tests never execute the wrappers.

The first command sends exactly one Mock-generated fictional LucaPlus customer
report. It has no sender, recipient, report, artifact-path, SMTP-endpoint, or
message-count override:

- From: `yinoagent@gmail.com`
- To: `867542127@qq.com`
- Subject: `[LOCAL TEST] LucaPlus Customer Call Report`
- SMTP: Gmail TLS on `smtp.gmail.com:465`
- Content: only `customer-report.html` generated from the fictional
  `fixtures/vapi/end-of-call.json` fixture through the existing Mock pipeline

Nodemailer is a development dependency and is loaded dynamically only by this
explicit command after the confirmation and credential checks. Automated
tests make SMTP unreachable by injecting fake transport wiring and replace
`fetch` with throwing sentinels around Mock report generation. They do not
claim to provide a general operating-system network sandbox, but they never
create a real Nodemailer transport or execute the guarded real-send entrypoint.

Before the manual test, enable two-step verification on the fixed Gmail sender
account and create a Gmail application password. Then run only the secure
PowerShell wrapper:

```powershell
cd C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights
.\scripts\send-test-email.ps1
```

The wrapper displays the fixed envelope, requires the exact confirmation
`SEND 867542127@qq.com`, and prompts for the application password as a
`SecureString`. The wrapper process holds the converted credential only long
enough to set process environment variables; npm and its entrypoint descendants
inherit those variables. The wrapper removes both variables and conditionally
zeroes the converted BSTR in `finally`, which bounds exposure but does not make
the credential cryptographically exclusive to one process.

The fixed From/To lines and prompts are interactive host UI. After npm is
invoked, the machine result is exactly `{"status":"sent"}` or one fixed
`email_test_*` error code; child noise and PowerShell exception formatting are
not forwarded. The wrapper is the only documented and recommended real-send
path, although a user who manually recreates its guarded environment could
technically execute the entrypoint directly.

Never paste the application password into chat, source files, `.env` files,
arguments, logs, or test artifacts. Do not run the wrapper during automated
verification.

## Isolated LucaPlus pull-and-email trial

The second command pulls one real LucaPlus VAPI call, analyzes it with
DeepSeek, and emails the n8n customer report and quality report as two
messages. It does not PATCH VAPI, does not change n8n, and does not expose the
local API. Profile, sender, recipient, and SMTP are fixed:

- From: `yinoagent@gmail.com`
- To: `867542127@qq.com`
- Subjects: `Call Report for <customer_name> <create_time>` and `[质量分析] Luca AI 评分: <score>/10 - <customer_name>`
- SMTP: Gmail TLS on `smtp.gmail.com:465`
- Customer mail attaches `recording.wav` when a presigned recording can be downloaded (about 30 minutes of VAPI signature is only used at send time)
- Profile: `lucaplus`
- Assistant: LucaPlus-Mia only
- Default call ID: `019ffebb-795d-711f-ae46-1674252cc39c`

Require the Gmail application password at the prompt. The wrapper reads the
VAPI private key from `C:\Users\yino\vapi api.txt` and the DeepSeek key from
`C:\Users\Public\ds_api.log` into the process environment. It does not copy
those files into the repository. Optional `TRIAL_CALL_ID` may override the call
ID with a UUID only.

```powershell
cd C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights
.\scripts\send-trial-email.ps1
```

The wrapper displays the fixed envelope, requires `SEND 867542127@qq.com`, and
prompts for the Gmail application password as a `SecureString`. Success stdout
is exactly `{"status":"sent"}`. Failures print one `trial_*` code. Do not run
this wrapper during automated verification. Never paste keys, the application
password, or call transcripts into chat.
