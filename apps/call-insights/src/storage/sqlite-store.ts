import { DatabaseSync, type SQLOutputValue } from "node:sqlite";
import { CallAnalysisSchema, QualityAnalysisSchema } from "../domain/schemas.js";
import type {
  MailKind,
  MailOutboxInput,
  MailOutboxRecord,
  MailStatus,
} from "../outbound/outbox.js";
import type {
  AnalysisJob,
  Call,
  CallAnalysis,
  IngestResult,
  JobStatus,
  NormalizedEvent,
  QualityAnalysis,
  Rating,
  StoredAnalysis,
} from "../domain/types.js";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  profile TEXT NOT NULL,
  call_id TEXT,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  received_at TEXT NOT NULL,
  payload_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calls (
  profile TEXT NOT NULL,
  call_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  transcript TEXT NOT NULL,
  summary TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  duration_seconds REAL NOT NULL,
  recording_url TEXT,
  received_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'vapi',
  PRIMARY KEY (profile, call_id)
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile TEXT NOT NULL,
  call_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','running','succeeded','failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (profile, call_id)
);
CREATE TABLE IF NOT EXISTS analyses (
  profile TEXT NOT NULL,
  call_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  call_analysis_json TEXT NOT NULL,
  quality_analysis_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (profile, call_id)
);
CREATE TABLE IF NOT EXISTS ratings (
  profile TEXT NOT NULL,
  call_id TEXT NOT NULL,
  score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
  rated_at TEXT NOT NULL,
  PRIMARY KEY (profile, call_id)
);
CREATE TABLE IF NOT EXISTS mail_outbox (
  outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile TEXT NOT NULL,
  call_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('customer','quality')),
  subject TEXT NOT NULL,
  html_path TEXT NOT NULL,
  recipient_roles_json TEXT NOT NULL,
  message_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('suppressed','pending','sending','sent','failed','uncertain')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT,
  last_error TEXT,
  provider_message_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT,
  UNIQUE(profile, call_id, kind)
);
CREATE TABLE IF NOT EXISTS runtime_health (
  key TEXT PRIMARY KEY CHECK(key = 'mail_worker_heartbeat'),
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_config (
  key TEXT PRIMARY KEY CHECK(key = 'mail_cutover_not_before'),
  value TEXT NOT NULL
);
`;

export const DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 5_000;

export interface SqliteStoreOptions {
  busyTimeoutMs?: number;
}

export interface OperationalSummary {
  queues: {
    analysis: {
      pending: number;
      running: number;
      failed: number;
    };
    mail: {
      suppressed: number;
      pending: number;
      sending: number;
      failed: number;
      uncertain: number;
    };
  };
  lastSuccess: {
    analysis: string | null;
    mail: string | null;
  };
  mailWorker: {
    status: "ok" | "degraded";
  };
}

function asString(value: SQLOutputValue | undefined, field: string): string {
  if (typeof value !== "string") {
    throw new Error(`expected string for ${field}`);
  }
  return value;
}

function asNumber(value: SQLOutputValue | undefined, field: string): number {
  if (typeof value === "bigint") {
    return Number(value);
  }
  if (typeof value !== "number") {
    throw new Error(`expected number for ${field}`);
  }
  return value;
}

function asNullableString(value: SQLOutputValue | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    throw new Error("expected string or null");
  }
  return value;
}

function asJobStatus(value: SQLOutputValue | undefined): JobStatus {
  if (value === "pending" || value === "running" || value === "succeeded" || value === "failed") {
    return value;
  }
  throw new Error("invalid job status");
}

function asProvider(value: SQLOutputValue | undefined): "mock" | "deepseek" {
  if (value === "mock" || value === "deepseek") {
    return value;
  }
  throw new Error("invalid provider");
}

function asMailKind(value: SQLOutputValue | undefined): MailKind {
  if (value === "customer" || value === "quality") {
    return value;
  }
  throw new Error("invalid mail kind");
}

function asMailStatus(value: SQLOutputValue | undefined): MailStatus {
  if (
    value === "suppressed" ||
    value === "pending" ||
    value === "sending" ||
    value === "sent" ||
    value === "failed" ||
    value === "uncertain"
  ) {
    return value;
  }
  throw new Error("invalid mail status");
}

function asRecipientRoles(value: SQLOutputValue | undefined): string[] {
  const parsed: unknown = JSON.parse(asString(value, "recipient_roles_json"));
  if (
    !Array.isArray(parsed) ||
    !parsed.every((role) => typeof role === "string" && role.length > 0)
  ) {
    throw new Error("invalid recipient roles");
  }
  return parsed;
}

export class SqliteStore {
  private readonly db: DatabaseSync;

  constructor(path: string, options: SqliteStoreOptions = {}) {
    const busyTimeoutMs =
      options.busyTimeoutMs ?? DEFAULT_SQLITE_BUSY_TIMEOUT_MS;
    if (
      !Number.isSafeInteger(busyTimeoutMs) ||
      busyTimeoutMs <= 0 ||
      busyTimeoutMs > 60_000
    ) {
      throw new Error("SQLite busy timeout must be an integer from 1 to 60000ms");
    }
    this.db = new DatabaseSync(path);
    try {
      this.db.exec(`PRAGMA busy_timeout = ${busyTimeoutMs}`);
      this.db.exec("PRAGMA journal_mode = WAL");
      this.db.exec(SCHEMA);
      this.ensureCallChannelColumn();
    } catch (error) {
      this.db.close();
      throw error;
    }
  }

  private ensureCallChannelColumn(): void {
    const columns = this.db.prepare("PRAGMA table_info(calls)").all() as Array<{
      name: string;
    }>;
    if (!columns.some((column) => column.name === "channel")) {
      this.db.exec(
        "ALTER TABLE calls ADD COLUMN channel TEXT NOT NULL DEFAULT 'vapi'",
      );
    }
  }

  close(): void {
    if (this.db.isOpen) {
      this.db.close();
    }
  }

  ingest(event: NormalizedEvent): IngestResult {
    return this.transact(() => {
      const existingEvent = this.db
        .prepare("SELECT event_id, call_id, status FROM events WHERE event_id = ?")
        .get(event.eventId);
      if (existingEvent) {
        if (asString(existingEvent.status, "status") === "skipped") {
          return {
            status: "skipped",
            eventId: event.eventId,
            callId: asNullableString(existingEvent.call_id) ?? event.callId,
            jobId: null,
          };
        }
        return this.duplicateResult(
          event.eventId,
          event.profile,
          asNullableString(existingEvent.call_id) ?? event.callId,
        );
      }

      if (event.action === "skip") {
        this.insertEvent(event, "skipped");
        return {
          status: "skipped",
          eventId: event.eventId,
          callId: event.callId,
          jobId: null,
        };
      }

      if (!event.call || event.callId === null) {
        throw new Error("analyze event requires a call");
      }

      const existingCall = this.db
        .prepare("SELECT call_id FROM calls WHERE profile = ? AND call_id = ?")
        .get(event.profile, event.callId);
      if (existingCall) {
        this.insertEvent(event, "duplicate");
        return this.duplicateResult(event.eventId, event.profile, event.callId);
      }

      const now = this.now();
      this.insertEvent(event, "accepted");
      this.db
        .prepare(
          `INSERT INTO calls (
            profile, call_id, event_id, transcript, summary, started_at, ended_at,
            duration_seconds, recording_url, received_at, updated_at, channel
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          event.call.profile,
          event.call.callId,
          event.call.eventId,
          event.call.transcript,
          event.call.summary,
          event.call.startedAt,
          event.call.endedAt,
          event.call.durationSeconds,
          event.call.recordingUrl,
          event.call.receivedAt,
          now,
          event.call.channel,
        );

      const inserted = this.db
        .prepare(
          `INSERT INTO jobs (profile, call_id, status, attempts, last_error, created_at, updated_at)
           VALUES (?, ?, 'pending', 0, NULL, ?, ?)`,
        )
        .run(event.profile, event.callId, now, now);

      return {
        status: "accepted",
        eventId: event.eventId,
        callId: event.callId,
        jobId: Number(inserted.lastInsertRowid),
      };
    });
  }

  claimNextJob(): AnalysisJob | null {
    return this.transact(() => {
      const row = this.db
        .prepare(
          `SELECT job_id FROM jobs
           WHERE status = 'pending'
           ORDER BY created_at ASC, job_id ASC
           LIMIT 1`,
        )
        .get();
      if (!row) {
        return null;
      }
      const jobId = asNumber(row.job_id, "job_id");
      this.db
        .prepare("UPDATE jobs SET status = 'running', attempts = attempts + 1, updated_at = ? WHERE job_id = ?")
        .run(this.now(), jobId);
      return this.getJob(jobId);
    });
  }

  recoverStaleRunningJobs(staleBefore: string): number {
    return this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'pending', updated_at = ?
           WHERE status = 'running' AND updated_at < ?`,
        )
        .run(this.now(), staleBefore);
      return Number(result.changes);
    });
  }

  recoverStaleRunningJob(jobId: number, staleBefore: string): boolean {
    return this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'pending', updated_at = ?
           WHERE job_id = ? AND status = 'running' AND updated_at < ?`,
        )
        .run(this.now(), jobId, staleBefore);
      return Number(result.changes) === 1;
    });
  }

  releaseRunningJobForShutdown(jobId: number): void {
    this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'pending', last_error = NULL, updated_at = ?
           WHERE job_id = ? AND status = 'running'`,
        )
        .run(this.now(), jobId);
      if (Number(result.changes) !== 1) {
        throw new Error(
          "expected exactly one running job to release for shutdown",
        );
      }
    });
  }

  retryJob(jobId: number): void {
    this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'pending', last_error = NULL, updated_at = ?
           WHERE job_id = ? AND status = 'failed'`,
        )
        .run(this.now(), jobId);
      if (Number(result.changes) !== 1) {
        throw new Error("expected exactly one failed job to retry");
      }
    });
  }

  saveAnalysis(
    profile: string,
    callId: string,
    provider: "mock" | "deepseek",
    call: CallAnalysis,
    quality: QualityAnalysis,
    createdAt: string,
  ): void {
    this.transact(() => {
      this.db
        .prepare(
          `INSERT INTO analyses (
            profile, call_id, provider, call_analysis_json, quality_analysis_json, created_at
          ) VALUES (?, ?, ?, ?, ?, ?)
          ON CONFLICT(profile, call_id) DO UPDATE SET
            provider = excluded.provider,
            call_analysis_json = excluded.call_analysis_json,
            quality_analysis_json = excluded.quality_analysis_json,
            created_at = excluded.created_at`,
        )
        .run(profile, callId, provider, JSON.stringify(call), JSON.stringify(quality), createdAt);
    });
  }

  succeedJob(jobId: number): void {
    this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'succeeded', last_error = NULL, updated_at = ?
           WHERE job_id = ? AND status = 'running'`,
        )
        .run(this.now(), jobId);
      if (Number(result.changes) !== 1) {
        throw new Error("expected exactly one running job to succeed");
      }
    });
  }

  failJob(jobId: number, safeError: string): void {
    this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE jobs
           SET status = 'failed', last_error = ?, updated_at = ?
           WHERE job_id = ? AND status = 'running'`,
        )
        .run(safeError, this.now(), jobId);
      if (Number(result.changes) !== 1) {
        throw new Error("expected exactly one running job to fail");
      }
    });
  }

  getCall(profile: string, callId: string): Call | null {
    const row = this.db
      .prepare("SELECT * FROM calls WHERE profile = ? AND call_id = ?")
      .get(profile, callId);
    if (!row) {
      return null;
    }
    return {
      profile: asString(row.profile, "profile"),
      callId: asString(row.call_id, "call_id"),
      eventId: asString(row.event_id, "event_id"),
      transcript: asString(row.transcript, "transcript"),
      summary: asString(row.summary, "summary"),
      startedAt: asString(row.started_at, "started_at"),
      endedAt: asString(row.ended_at, "ended_at"),
      durationSeconds: asNumber(row.duration_seconds, "duration_seconds"),
      recordingUrl: asNullableString(row.recording_url),
      receivedAt: asString(row.received_at, "received_at"),
      channel: row.channel === "yino" ? "yino" : "vapi",
    };
  }

  getJob(jobId: number): AnalysisJob | null {
    const row = this.db.prepare("SELECT * FROM jobs WHERE job_id = ?").get(jobId);
    if (!row) {
      return null;
    }
    return {
      jobId: asNumber(row.job_id, "job_id"),
      profile: asString(row.profile, "profile"),
      callId: asString(row.call_id, "call_id"),
      status: asJobStatus(row.status),
      attempts: asNumber(row.attempts, "attempts"),
      lastError: asNullableString(row.last_error),
      createdAt: asString(row.created_at, "created_at"),
      updatedAt: asString(row.updated_at, "updated_at"),
    };
  }

  getAnalysis(profile: string, callId: string): StoredAnalysis | null {
    const row = this.db
      .prepare("SELECT * FROM analyses WHERE profile = ? AND call_id = ?")
      .get(profile, callId);
    if (!row) {
      return null;
    }
    return {
      profile: asString(row.profile, "profile"),
      callId: asString(row.call_id, "call_id"),
      provider: asProvider(row.provider),
      callAnalysis: CallAnalysisSchema.parse(
        JSON.parse(asString(row.call_analysis_json, "call_analysis_json")),
      ),
      qualityAnalysis: QualityAnalysisSchema.parse(
        JSON.parse(asString(row.quality_analysis_json, "quality_analysis_json")),
      ),
      createdAt: asString(row.created_at, "created_at"),
    };
  }

  upsertRating(profile: string, callId: string, score: number, ratedAt: string): Rating {
    return this.transact(() => {
      this.db
        .prepare(
          `INSERT INTO ratings (profile, call_id, score, rated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(profile, call_id) DO UPDATE SET
             score = excluded.score,
             rated_at = excluded.rated_at`,
        )
        .run(profile, callId, score, ratedAt);
      const rating = this.getRating(profile, callId);
      if (!rating) {
        throw new Error("rating upsert failed");
      }
      return rating;
    });
  }

  getRating(profile: string, callId: string): Rating | null {
    const row = this.db
      .prepare("SELECT * FROM ratings WHERE profile = ? AND call_id = ?")
      .get(profile, callId);
    if (!row) {
      return null;
    }
    return {
      profile: asString(row.profile, "profile"),
      callId: asString(row.call_id, "call_id"),
      score: asNumber(row.score, "score"),
      ratedAt: asString(row.rated_at, "rated_at"),
    };
  }

  enqueueMail(input: MailOutboxInput): MailOutboxRecord {
    return this.transact(() => this.enqueueMailWithinTransaction(input));
  }

  enqueueMailBatch(
    inputs: readonly MailOutboxInput[],
  ): MailOutboxRecord[] {
    return this.transact(() =>
      inputs.map((input) => this.enqueueMailWithinTransaction(input))
    );
  }

  claimNextMail(now: string): MailOutboxRecord | null {
    return this.transact(() => {
      const row = this.db
        .prepare(
          `SELECT outbox_id FROM mail_outbox
           WHERE status = 'pending'
             AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
           ORDER BY COALESCE(next_attempt_at, created_at), outbox_id
           LIMIT 1`,
        )
        .get(now);
      if (!row) {
        return null;
      }
      const outboxId = asNumber(row.outbox_id, "outbox_id");
      const updated = this.db
        .prepare(
          `UPDATE mail_outbox
           SET status = 'sending', attempts = attempts + 1,
               next_attempt_at = NULL, updated_at = ?
           WHERE outbox_id = ? AND status = 'pending'`,
        )
        .run(now, outboxId);
      if (Number(updated.changes) !== 1) {
        throw new Error("expected exactly one pending mail to claim");
      }
      const record = this.getMail(outboxId);
      if (!record) {
        throw new Error("claimed mail missing");
      }
      return record;
    });
  }

  markMailSent(
    outboxId: number,
    providerMessageId: string | null,
    sentAt: string,
  ): void {
    this.updateSendingMail(
      outboxId,
      `status = 'sent', provider_message_id = ?, sent_at = ?,
       last_error = NULL, next_attempt_at = NULL, updated_at = ?`,
      providerMessageId,
      sentAt,
      sentAt,
    );
  }

  retryMail(outboxId: number, safeError: string, nextAttemptAt: string): void {
    this.updateSendingMail(
      outboxId,
      `status = 'pending', last_error = ?, next_attempt_at = ?, updated_at = ?`,
      safeError,
      nextAttemptAt,
      this.now(),
    );
  }

  markMailFailed(outboxId: number, safeError: string): void {
    this.updateSendingMail(
      outboxId,
      `status = 'failed', last_error = ?, next_attempt_at = NULL, updated_at = ?`,
      safeError,
      this.now(),
    );
  }

  markMailUncertain(outboxId: number, safeError: string): void {
    this.updateSendingMail(
      outboxId,
      `status = 'uncertain', last_error = ?, next_attempt_at = NULL, updated_at = ?`,
      safeError,
      this.now(),
    );
  }

  recoverStaleSendingMail(staleBefore: string): number {
    return this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE mail_outbox
           SET status = 'uncertain', last_error = 'mail_delivery_uncertain',
               next_attempt_at = NULL, updated_at = ?
           WHERE status = 'sending' AND updated_at < ?`,
        )
        .run(this.now(), staleBefore);
      return Number(result.changes);
    });
  }

  getMail(outboxId: number): MailOutboxRecord | null {
    const row = this.db
      .prepare("SELECT * FROM mail_outbox WHERE outbox_id = ?")
      .get(outboxId);
    return row ? this.mailRecord(row) : null;
  }

  listMail(profile: string, callId: string): MailOutboxRecord[] {
    return this.db
      .prepare(
        `SELECT * FROM mail_outbox
         WHERE profile = ? AND call_id = ?
         ORDER BY outbox_id`,
      )
      .all(profile, callId)
      .map((row) => this.mailRecord(row));
  }

  countMail(): number {
    return this.count("mail_outbox");
  }

  countMailByStatus(status: MailStatus): number {
    const row = this.db
      .prepare("SELECT COUNT(*) AS count FROM mail_outbox WHERE status = ?")
      .get(status);
    return asNumber(row?.count, "count");
  }

  recordMailWorkerHeartbeat(at: string): void {
    if (
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(at) ||
      !Number.isFinite(Date.parse(at)) ||
      new Date(Date.parse(at)).toISOString() !== at
    ) {
      throw new Error("invalid mail worker heartbeat");
    }
    this.transact(() => {
      this.db
        .prepare(
          `INSERT INTO runtime_health (key, value)
           VALUES ('mail_worker_heartbeat', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
        )
        .run(at);
    });
  }

  initializeRuntimeMailCutover(cutoverNotBefore: string): void {
    this.transact(() => {
      this.db
        .prepare(
          `INSERT INTO runtime_config (key, value)
           VALUES ('mail_cutover_not_before', ?)
           ON CONFLICT(key) DO NOTHING`,
        )
        .run(cutoverNotBefore);
      this.assertRuntimeMailCutover(cutoverNotBefore);
    });
  }

  assertRuntimeMailCutover(cutoverNotBefore: string): void {
    const row = this.db
      .prepare(
        `SELECT value FROM runtime_config
         WHERE key = 'mail_cutover_not_before'`,
      )
      .get();
    if (
      !row ||
      asString(row.value, "mail_cutover_not_before") !==
        cutoverNotBefore
    ) {
      throw new Error("mail_cutover_mismatch");
    }
  }

  getOperationalSummary(
    now: Date = new Date(),
    options: { mailExpected?: boolean } = {},
  ): OperationalSummary {
    const analysis = this.db
      .prepare(
        `SELECT
           COUNT(*) FILTER (WHERE status = 'pending') AS pending,
           COUNT(*) FILTER (WHERE status = 'running') AS running,
           COUNT(*) FILTER (WHERE status = 'failed') AS failed,
           MAX(CASE WHEN status = 'succeeded' THEN updated_at END) AS last_success
         FROM jobs`,
      )
      .get();
    const mail = this.db
      .prepare(
        `SELECT
           COUNT(*) FILTER (WHERE status = 'suppressed') AS suppressed,
           COUNT(*) FILTER (WHERE status = 'pending') AS pending,
           COUNT(*) FILTER (WHERE status = 'sending') AS sending,
           COUNT(*) FILTER (WHERE status = 'failed') AS failed,
           COUNT(*) FILTER (WHERE status = 'uncertain') AS uncertain,
           MAX(CASE WHEN status = 'sent' THEN sent_at END) AS last_success
         FROM mail_outbox`,
      )
      .get();
    const heartbeat = this.db
      .prepare(
        `SELECT value FROM runtime_health
         WHERE key = 'mail_worker_heartbeat'`,
      )
      .get();
    const heartbeatAt = heartbeat
      ? asString(heartbeat.value, "mail_worker_heartbeat")
      : null;
    const heartbeatAge = heartbeatAt === null
      ? null
      : now.getTime() - Date.parse(heartbeatAt);
    const failedMail = asNumber(mail?.failed, "mail failed");
    const uncertainMail = asNumber(mail?.uncertain, "mail uncertain");
    const mailDegraded =
      (heartbeatAge !== null && heartbeatAge > 2 * 60 * 1_000) ||
      (options.mailExpected === true &&
        (heartbeatAge === null || failedMail > 0 || uncertainMail > 0));
    return {
      queues: {
        analysis: {
          pending: asNumber(analysis?.pending, "analysis pending"),
          running: asNumber(analysis?.running, "analysis running"),
          failed: asNumber(analysis?.failed, "analysis failed"),
        },
        mail: {
          suppressed: asNumber(mail?.suppressed, "mail suppressed"),
          pending: asNumber(mail?.pending, "mail pending"),
          sending: asNumber(mail?.sending, "mail sending"),
          failed: failedMail,
          uncertain: uncertainMail,
        },
      },
      lastSuccess: {
        analysis: asNullableString(analysis?.last_success),
        mail: asNullableString(mail?.last_success),
      },
      mailWorker: {
        status: mailDegraded ? "degraded" : "ok",
      },
    };
  }

  countEvents(): number {
    return this.count("events");
  }

  countCalls(): number {
    return this.count("calls");
  }

  countJobs(): number {
    return this.count("jobs");
  }

  countRatings(): number {
    return this.count("ratings");
  }

  private count(
    table: "events" | "calls" | "jobs" | "ratings" | "mail_outbox",
  ): number {
    const row = this.db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get();
    return asNumber(row?.count, "count");
  }

  private insertEvent(event: NormalizedEvent, status: IngestResult["status"]): void {
    this.db
      .prepare(
        `INSERT INTO events (event_id, profile, call_id, event_type, status, received_at, payload_hash)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        event.eventId,
        event.profile,
        event.callId,
        event.eventType,
        status,
        event.receivedAt,
        event.payloadHash,
      );
  }

  private duplicateResult(eventId: string, profile: string, callId: string | null): IngestResult {
    const jobRow = callId
      ? this.db.prepare("SELECT job_id FROM jobs WHERE profile = ? AND call_id = ?").get(profile, callId)
      : undefined;
    return {
      status: "duplicate",
      eventId,
      callId,
      jobId: jobRow ? asNumber(jobRow.job_id, "job_id") : null,
    };
  }

  private getMailByIdentity(
    profile: string,
    callId: string,
    kind: MailKind,
  ): MailOutboxRecord | null {
    const row = this.db
      .prepare(
        `SELECT * FROM mail_outbox
         WHERE profile = ? AND call_id = ? AND kind = ?`,
      )
      .get(profile, callId, kind);
    return row ? this.mailRecord(row) : null;
  }

  private mailRecord(
    row: Record<string, SQLOutputValue>,
  ): MailOutboxRecord {
    return {
      outboxId: asNumber(row.outbox_id, "outbox_id"),
      profile: asString(row.profile, "profile"),
      callId: asString(row.call_id, "call_id"),
      kind: asMailKind(row.kind),
      subject: asString(row.subject, "subject"),
      htmlPath: asString(row.html_path, "html_path"),
      recipientRoles: asRecipientRoles(row.recipient_roles_json),
      messageId: asString(row.message_id, "message_id"),
      status: asMailStatus(row.status),
      attempts: asNumber(row.attempts, "attempts"),
      nextAttemptAt: asNullableString(row.next_attempt_at),
      lastError: asNullableString(row.last_error),
      providerMessageId: asNullableString(row.provider_message_id),
      createdAt: asString(row.created_at, "created_at"),
      updatedAt: asString(row.updated_at, "updated_at"),
      sentAt: asNullableString(row.sent_at),
    };
  }

  private updateSendingMail(
    outboxId: number,
    assignments: string,
    ...values: Array<string | null>
  ): void {
    this.transact(() => {
      const result = this.db
        .prepare(
          `UPDATE mail_outbox SET ${assignments}
           WHERE outbox_id = ? AND status = 'sending'`,
        )
        .run(...values, outboxId);
      if (Number(result.changes) !== 1) {
        throw new Error("expected exactly one sending mail to update");
      }
    });
  }

  private now(): string {
    return new Date().toISOString();
  }

  private enqueueMailWithinTransaction(
    input: MailOutboxInput,
  ): MailOutboxRecord {
    const now = this.now();
    this.db
      .prepare(
        `INSERT INTO mail_outbox (
          profile, call_id, kind, subject, html_path, recipient_roles_json,
          message_id, status, attempts, next_attempt_at, last_error,
          provider_message_id, created_at, updated_at, sent_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, ?, ?, NULL)
        ON CONFLICT(profile, call_id, kind) DO NOTHING`,
      )
      .run(
        input.profile,
        input.callId,
        input.kind,
        input.subject,
        input.htmlPath,
        JSON.stringify(input.recipientRoles),
        input.messageId,
        input.status,
        input.nextAttemptAt,
        now,
        now,
      );
    const record = this.getMailByIdentity(
      input.profile,
      input.callId,
      input.kind,
    );
    if (!record) {
      throw new Error("mail outbox enqueue failed");
    }
    return record;
  }

  private transact<T>(fn: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      if (this.db.isTransaction) {
        this.db.exec("ROLLBACK");
      }
      throw error;
    }
  }
}
