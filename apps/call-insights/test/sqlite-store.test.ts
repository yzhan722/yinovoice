import { spawn } from "node:child_process";
import { once } from "node:events";
import { DatabaseSync } from "node:sqlite";
import { afterEach, describe, expect, it } from "vitest";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import { RatingService } from "../src/application/rating-service.js";
import type { MailOutboxInput } from "../src/outbound/outbox.js";
import {
  makeAnalysis,
  makeNormalizedReportEvent,
  makeQuality,
  makeSkippedEvent,
  tempDatabase,
} from "./fixtures.js";

interface LockHolder {
  release(): void;
  close(): Promise<void>;
}

async function startLockHolder(
  databasePath: string,
  releaseAfterMs: number | null,
): Promise<LockHolder> {
  const script = `
    import { DatabaseSync } from "node:sqlite";
    const db = new DatabaseSync(process.env.TEST_DATABASE_PATH);
    let released = false;
    let timer;
    const release = () => {
      if (released) return;
      released = true;
      if (timer) clearTimeout(timer);
      try {
        db.exec("COMMIT");
        db.close();
        process.stdout.write("RELEASED\\n", () => process.exit(0));
      } catch (error) {
        process.stderr.write(String(error), () => process.exit(1));
      }
    };
    db.exec("BEGIN IMMEDIATE");
    process.stdout.write("LOCKED\\n");
    process.stdin.once("data", release);
    process.stdin.resume();
    const releaseAfterMs = Number(process.env.TEST_RELEASE_AFTER_MS);
    if (Number.isFinite(releaseAfterMs) && releaseAfterMs >= 0) {
      timer = setTimeout(release, releaseAfterMs);
    }
  `;
  let stderr = "";
  const child = spawn(
    process.execPath,
    ["--input-type=module", "--eval", script],
    {
      env: {
        ...process.env,
        TEST_DATABASE_PATH: databasePath,
        TEST_RELEASE_AFTER_MS:
          releaseAfterMs === null ? "none" : String(releaseAfterMs),
      },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  child.stdin.on("error", (error: NodeJS.ErrnoException) => {
    if (error.code !== "EPIPE") {
      stderr += String(error);
    }
  });
  const ready = await Promise.race([
    once(child.stdout, "data").then(([chunk]) => ({
      kind: "data" as const,
      value: String(chunk),
    })),
    once(child, "exit").then(([code]) => ({
      kind: "exit" as const,
      value: String(code),
    })),
    once(child, "error").then(([error]) => ({
      kind: "error" as const,
      value: String(error),
    })),
  ]);
  if (ready.kind !== "data" || !ready.value.includes("LOCKED")) {
    throw new Error(`lock holder failed to start: ${ready.value} ${stderr}`);
  }

  let releaseSent = false;
  const release = (): void => {
    if (releaseSent || child.exitCode !== null) {
      return;
    }
    releaseSent = true;
    if (!child.stdin.destroyed && child.stdin.writable) {
      child.stdin.end("release\n");
    }
  };
  return {
    release,
    async close(): Promise<void> {
      release();
      if (child.exitCode === null) {
        await once(child, "exit");
      }
      if (child.exitCode !== 0) {
        throw new Error(`lock holder failed: ${stderr}`);
      }
    },
  };
}

describe("SqliteStore", () => {
  const resources: Array<{ close(): void }> = [];
  afterEach(() => resources.splice(0).reverse().forEach((resource) => resource.close()));

  it("creates one call and one job for duplicate reports", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const service = new EventIngestionService(store);
    const event = makeNormalizedReportEvent("lucaplus", "call_demo_001");
    const first = service.ingest(event);
    const second = service.ingest(event);
    expect(first.status).toBe("accepted");
    expect(second.status).toBe("duplicate");
    expect(store.countCalls()).toBe(1);
    expect(store.countJobs()).toBe(1);
  });

  it("creates distinct events and jobs for distinct helper call ids", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const service = new EventIngestionService(store);

    const first = service.ingest(makeNormalizedReportEvent("lucaplus", "call_demo_101"));
    const second = service.ingest(makeNormalizedReportEvent("lucaplus", "call_demo_102"));

    expect(first.status).toBe("accepted");
    expect(second.status).toBe("accepted");
    expect(first.eventId).not.toBe(second.eventId);
    expect(store.countCalls()).toBe(2);
    expect(store.countJobs()).toBe(2);
  });

  it("persists yino channel on the stored call", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const event = makeNormalizedReportEvent("lucaplus", "yino_store_001");
    if (event.call) {
      event.call.channel = "yino";
    }
    new EventIngestionService(store).ingest(event);
    expect(store.getCall("lucaplus", "yino_store_001")?.channel).toBe("yino");
  });

  it("uses WAL and waits for a separate writer that releases within the bound", async () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const inspector = new DatabaseSync(database.path);
    const journalMode = inspector.prepare("PRAGMA journal_mode").get();
    inspector.close();
    expect(journalMode?.journal_mode).toBe("wal");

    const holder = await startLockHolder(database.path, 200);
    try {
      const startedAt = performance.now();
      const result = new EventIngestionService(store).ingest(
        makeNormalizedReportEvent("lucaplus", "call_contended_success"),
      );
      const elapsedMs = performance.now() - startedAt;

      expect(result.status).toBe("accepted");
      expect(elapsedMs).toBeGreaterThanOrEqual(100);
      expect(elapsedMs).toBeLessThan(2_000);
    } finally {
      await holder.close();
    }
  });

  it("stops waiting when a separate writer outlives the configured busy timeout", async () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path, { busyTimeoutMs: 100 });
    resources.push(store);
    const holder = await startLockHolder(database.path, null);
    try {
      const startedAt = performance.now();
      expect(() =>
        new EventIngestionService(store).ingest(
          makeNormalizedReportEvent("lucaplus", "call_contended_timeout"),
        ),
      ).toThrow(/busy|locked/i);
      const elapsedMs = performance.now() - startedAt;

      expect(elapsedMs).toBeGreaterThanOrEqual(75);
      expect(elapsedMs).toBeLessThan(1_000);
    } finally {
      holder.release();
      await holder.close();
    }
  });

  it("keeps duplicate skipped events skipped without calls or jobs", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const ingestion = new EventIngestionService(store);
    const first = ingestion.ingest(makeSkippedEvent());
    const duplicate = ingestion.ingest(makeSkippedEvent());
    expect(first.status).toBe("skipped");
    expect(duplicate.status).toBe("skipped");
    expect(store.countEvents()).toBe(1);
    expect(store.countJobs()).toBe(0);
  });

  it("keeps one suppressed outbox row per call and kind and never claims it", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const customer = makeMailInput({
      kind: "customer",
      messageId: "<customer-demo@calls.yino.au>",
      status: "suppressed",
    });
    const quality = makeMailInput({
      kind: "quality",
      messageId: "<quality-demo@calls.yino.au>",
      status: "suppressed",
    });

    store.enqueueMail(customer);
    store.enqueueMail(customer);
    store.enqueueMail(quality);

    expect(store.listMail("lucaplus", "call_demo_001")).toHaveLength(2);
    expect(store.countMail()).toBe(2);
    expect(store.countMailByStatus("suppressed")).toBe(2);
    expect(store.claimNextMail("2026-08-13T10:00:00.000Z")).toBeNull();
  });

  it("rolls back the whole mail batch when either row is invalid", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const invalidQuality = {
      ...makeMailInput({
        kind: "quality",
        messageId: "<quality-invalid@calls.yino.au>",
      }),
      status: "invalid",
    } as unknown as MailOutboxInput;

    expect(() =>
      store.enqueueMailBatch([
        makeMailInput({ messageId: "<customer-valid@calls.yino.au>" }),
        invalidQuality,
      ])
    ).toThrow(/constraint/i);
    expect(store.countMail()).toBe(0);
  });

  it("enqueues both valid mail rows in one batch", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);

    expect(store.enqueueMailBatch([
      makeMailInput({ messageId: "<customer-batch@calls.yino.au>" }),
      makeMailInput({
        kind: "quality",
        messageId: "<quality-batch@calls.yino.au>",
      }),
    ])).toHaveLength(2);
    expect(store.countMail()).toBe(2);
  });

  it("claims only due pending mail and persists terminal and retry states", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const first = store.enqueueMail(makeMailInput({
      callId: "call_mail_first",
      messageId: "<mail-first@calls.yino.au>",
      status: "pending",
      nextAttemptAt: "2026-08-13T09:00:00.000Z",
    }));
    store.enqueueMail(makeMailInput({
      callId: "call_mail_later",
      messageId: "<mail-later@calls.yino.au>",
      status: "pending",
      nextAttemptAt: "2026-08-13T11:00:00.000Z",
    }));

    const claimed = store.claimNextMail("2026-08-13T10:00:00.000Z");
    expect(claimed).toMatchObject({
      outboxId: first.outboxId,
      status: "sending",
      attempts: 1,
    });
    expect(store.claimNextMail("2026-08-13T10:00:00.000Z")).toBeNull();

    store.retryMail(
      first.outboxId,
      "smtp_temporary_failure",
      "2026-08-13T10:05:00.000Z",
    );
    expect(store.getMail(first.outboxId)).toMatchObject({
      status: "pending",
      lastError: "smtp_temporary_failure",
      nextAttemptAt: "2026-08-13T10:05:00.000Z",
    });

    expect(store.claimNextMail("2026-08-13T10:05:00.000Z")?.outboxId)
      .toBe(first.outboxId);
    store.markMailSent(
      first.outboxId,
      "provider-message-demo",
      "2026-08-13T10:06:00.000Z",
    );
    expect(store.getMail(first.outboxId)).toMatchObject({
      status: "sent",
      attempts: 2,
      providerMessageId: "provider-message-demo",
      sentAt: "2026-08-13T10:06:00.000Z",
    });
  });

  it("moves stale sending mail to uncertain instead of retrying it", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const queued = store.enqueueMail(makeMailInput({
      messageId: "<stale-mail@calls.yino.au>",
      status: "pending",
      nextAttemptAt: "2000-01-01T00:00:00.000Z",
    }));
    expect(store.claimNextMail("2026-08-13T09:00:00.000Z")?.outboxId)
      .toBe(queued.outboxId);

    expect(store.recoverStaleSendingMail("9999-01-01T00:00:00.000Z")).toBe(1);
    expect(store.getMail(queued.outboxId)).toMatchObject({
      status: "uncertain",
      lastError: "mail_delivery_uncertain",
    });
    expect(store.claimNextMail("9999-01-01T00:00:00.000Z")).toBeNull();
  });

  it("recovers running jobs and upserts one rating per call", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const event = makeNormalizedReportEvent("inp-group", "call_demo_003");
    new EventIngestionService(store).ingest(event);
    const claimed = store.claimNextJob();
    expect(claimed?.status).toBe("running");
    const staleCutoff = new Date(Date.parse(claimed!.updatedAt) + 1).toISOString();
    expect(store.recoverStaleRunningJobs(staleCutoff)).toBe(1);
    store.upsertRating("inp-group", "call_demo_003", 3, "2026-08-13T02:00:00Z");
    store.upsertRating("inp-group", "call_demo_003", 5, "2026-08-13T03:00:00Z");
    expect(store.getRating("inp-group", "call_demo_003")?.score).toBe(5);
    expect(store.countRatings()).toBe(1);
  });

  it("recovers only running jobs older than the supplied cutoff and requested id", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const ingestion = new EventIngestionService(store);
    const first = ingestion.ingest(
      makeNormalizedReportEvent("lucaplus", "call_demo_lease_1"),
    );
    const second = ingestion.ingest(
      makeNormalizedReportEvent("lucaplus", "call_demo_lease_2"),
    );
    const claimed = store.claimNextJob()!;
    expect(claimed.jobId).toBe(first.jobId);
    const equalCutoff = claimed.updatedAt;
    const staleCutoff = new Date(Date.parse(claimed.updatedAt) + 1).toISOString();

    expect(store.recoverStaleRunningJob(second.jobId!, staleCutoff)).toBe(false);
    expect(store.recoverStaleRunningJob(claimed.jobId, equalCutoff)).toBe(false);
    expect(store.getJob(claimed.jobId)?.status).toBe("running");
    expect(store.recoverStaleRunningJobs(equalCutoff)).toBe(0);
    expect(store.recoverStaleRunningJob(claimed.jobId, staleCutoff)).toBe(true);
    expect(store.getJob(claimed.jobId)?.status).toBe("pending");
    expect(store.getJob(second.jobId!)?.status).toBe("pending");
  });

  it("validates both persisted analysis documents when reading", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);

    store.saveAnalysis(
      "lucaplus",
      "call_bad_call_analysis",
      "mock",
      makeAnalysis({ customerName: 42 as unknown as string }),
      makeQuality(),
      "2026-08-13T03:00:00.000Z",
    );
    expect(() => store.getAnalysis("lucaplus", "call_bad_call_analysis")).toThrow();

    store.saveAnalysis(
      "lucaplus",
      "call_bad_quality_analysis",
      "mock",
      makeAnalysis(),
      makeQuality({ shouldUpdatePrompt: "yes" as unknown as boolean }),
      "2026-08-13T03:00:00.000Z",
    );
    expect(() => store.getAnalysis("lucaplus", "call_bad_quality_analysis")).toThrow();
  });

  it("finalizes exactly one currently running job", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const accepted = new EventIngestionService(store).ingest(
      makeNormalizedReportEvent("lucaplus", "call_demo_103"),
    );
    const jobId = accepted.jobId!;

    expect(() => store.succeedJob(jobId)).toThrow(/running job/i);
    expect(() => store.failJob(jobId, "not running")).toThrow(/running job/i);
    expect(() => store.succeedJob(999_999)).toThrow(/running job/i);
    expect(() => store.failJob(999_999, "missing")).toThrow(/running job/i);

    expect(store.claimNextJob()?.jobId).toBe(jobId);
    store.succeedJob(jobId);
    expect(store.getJob(jobId)?.status).toBe("succeeded");
    expect(() => store.succeedJob(jobId)).toThrow(/running job/i);
    expect(() => store.failJob(jobId, "already complete")).toThrow(/running job/i);
  });

  it("releases exactly one running job for shutdown and clears its error", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const ingestion = new EventIngestionService(store);
    const active = ingestion.ingest(
      makeNormalizedReportEvent("lucaplus", "call_shutdown_active"),
    );
    const unrelated = ingestion.ingest(
      makeNormalizedReportEvent("lucaplus", "call_shutdown_unrelated"),
    );
    expect(store.claimNextJob()?.jobId).toBe(active.jobId);

    const inspector = new DatabaseSync(database.path);
    inspector
      .prepare("UPDATE jobs SET last_error = ? WHERE job_id = ?")
      .run("stale safe error", active.jobId!);
    inspector.close();

    store.releaseRunningJobForShutdown(active.jobId!);

    expect(store.getJob(active.jobId!)).toMatchObject({
      status: "pending",
      attempts: 1,
      lastError: null,
    });
    expect(store.getJob(unrelated.jobId!)).toMatchObject({
      status: "pending",
      attempts: 0,
      lastError: null,
    });
    expect(() =>
      store.releaseRunningJobForShutdown(active.jobId!),
    ).toThrow(/running job/i);
    expect(() =>
      store.releaseRunningJobForShutdown(unrelated.jobId!),
    ).toThrow(/running job/i);
  });

  it("lets only the API initialize the immutable runtime mail cutoff", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const cutoff = "2026-08-17T00:00:00.000Z";

    expect(() => store.assertRuntimeMailCutover(cutoff))
      .toThrow("mail_cutover_mismatch");
    store.initializeRuntimeMailCutover(cutoff);
    expect(() => store.assertRuntimeMailCutover(cutoff)).not.toThrow();
    expect(() => store.assertRuntimeMailCutover(
      "2026-08-18T00:00:00.000Z",
    )).toThrow("mail_cutover_mismatch");
  });
});

function makeMailInput(
  overrides: Partial<MailOutboxInput> = {},
): MailOutboxInput {
  return {
    profile: "lucaplus",
    callId: "call_demo_001",
    kind: "customer",
    subject: "Call Report for Demo Customer",
    htmlPath: "artifacts/lucaplus/call_demo_001/customer-report.html",
    recipientRoles: ["customer-report-primary"],
    messageId: "<mail-demo@calls.yino.au>",
    status: "suppressed",
    nextAttemptAt: null,
    ...overrides,
  };
}

describe("RatingService", () => {
  const resources: Array<{ close(): void }> = [];
  afterEach(() => resources.splice(0).reverse().forEach((resource) => resource.close()));

  it("rejects scores outside 1 to 5 and unknown calls", () => {
    const database = tempDatabase();
    resources.push(database);
    const store = new SqliteStore(database.path);
    resources.push(store);
    const ratingService = new RatingService(store);
    expect(() => ratingService.rate("lucaplus", "call_demo_001", 0)).toThrow(/1.*5/);
    expect(() => ratingService.rate("lucaplus", "missing", 5)).toThrow(/not found/i);
  });
});
