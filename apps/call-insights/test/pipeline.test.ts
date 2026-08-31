import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { DeepSeekAiProvider } from "../src/ai/deepseek-provider.js";
import type {
  AiProvider,
  CallAnalysisInput,
  QualityAnalysisInput,
} from "../src/ai/provider.js";
import { AnalysisPipeline } from "../src/application/analysis-pipeline.js";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import type {
  CallAnalysis,
  ProfileRegistry,
  QualityAnalysis,
} from "../src/domain/types.js";
import { profileRegistry } from "../src/profiles/profiles.js";
import { ArtifactWriter } from "../src/reports/artifact-writer.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import {
  AnalysisWorker,
  type WorkerScheduler,
} from "../src/worker/analysis-worker.js";
import {
  CountingAiProvider,
  InvalidAiProvider,
  createPipelineHarness,
  lucaplusProfile,
  makeAnalysis,
  makeNormalizedReportEvent,
  makeQuality,
  makeSkippedEvent,
  tempDirectory,
} from "./fixtures.js";

const TEST_JOB_LEASE_MS = 15 * 60 * 1000;

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function createManualScheduler(): WorkerScheduler {
  return {
    setInterval(): NodeJS.Timeout {
      return {} as NodeJS.Timeout;
    },
    clearInterval(): void {},
  };
}

class TickableScheduler implements WorkerScheduler {
  private callback: (() => void) | null = null;

  setInterval(callback: () => void): NodeJS.Timeout {
    this.callback = callback;
    return {} as NodeJS.Timeout;
  }

  clearInterval(): void {
    this.callback = null;
  }

  async tick(): Promise<void> {
    if (!this.callback) {
      throw new Error("scheduler is not started");
    }
    await this.callback();
  }
}

class BlockingAiProvider implements AiProvider {
  readonly name = "mock" as const;
  readonly started = deferred<void>();
  private readonly releaseGate = deferred<void>();

  release(): void {
    this.releaseGate.resolve();
  }

  close(): void {
    this.release();
  }

  async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    this.started.resolve();
    await this.releaseGate.promise;
    return makeAnalysis({ formattedTranscript: input.call.transcript });
  }

  async analyzeQuality(_input: QualityAnalysisInput): Promise<QualityAnalysis> {
    return makeQuality();
  }
}

class ThrowingAiProvider implements AiProvider {
  readonly name = "mock" as const;

  constructor(private readonly message: string) {}

  close(): void {}

  async analyzeCall(): Promise<CallAnalysis> {
    throw new Error(this.message);
  }

  async analyzeQuality(): Promise<QualityAnalysis> {
    throw new Error("unreachable");
  }
}

describe("analysis pipeline", () => {
  it("processes one accepted call into validated SQLite analysis and four files", async () => {
    const harness = createPipelineHarness();
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_010"),
      );

      expect(accepted.status).toBe("accepted");
      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("pending");
      expect(await harness.worker.runOnce()).toBe(true);

      const job = harness.store.getJob(accepted.jobId!);
      expect(job?.status).toBe("succeeded");
      expect(job?.attempts).toBe(1);
      expect(harness.store.getAnalysis("lucaplus", "call_demo_010")?.provider).toBe("mock");
      expect(harness.artifacts.list("lucaplus", "call_demo_010")).toEqual([
        "call.json",
        "customer-report.html",
        "manifest.json",
        "quality-report.html",
      ]);
    } finally {
      harness.close();
    }
  });

  it("plans exactly two suppressed outbound messages after a shadow report succeeds", async () => {
    const harness = createPipelineHarness({ outboundMode: "shadow" });
    try {
      const event = makeNormalizedReportEvent(
        "lucaplus",
        "call_shadow_outbox",
      );
      expect(harness.ingestion.ingest(event).status).toBe("accepted");
      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.listMail("lucaplus", "call_shadow_outbox"))
        .toMatchObject([
          { kind: "customer", status: "suppressed" },
          { kind: "quality", status: "suppressed" },
        ]);
      expect(await harness.worker.runOnce()).toBe(false);
      expect(harness.store.countMail()).toBe(2);
    } finally {
      harness.close();
    }
  });

  it("fails the job with a fixed category when outbox planning fails", async () => {
    const harness = createPipelineHarness({
      outbox: {
        plan() {
          throw new Error("private database detail");
        },
      },
    });
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_outbox_failure"),
      );
      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getJob(accepted.jobId!)).toMatchObject({
        status: "failed",
        attempts: 3,
        lastError: "outbox_planning_failed",
      });
    } finally {
      harness.close();
    }
  });

  it("does not call AI for skipped or duplicate events", async () => {
    const harness = createPipelineHarness();
    try {
      harness.ingestion.ingest(makeSkippedEvent());
      const event = makeNormalizedReportEvent("inp-group", "call_demo_011");
      expect(harness.ingestion.ingest(event).status).toBe("accepted");
      expect(harness.ingestion.ingest(event).status).toBe("duplicate");

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);
      expect(await harness.worker.runOnce()).toBe(false);
    } finally {
      harness.close();
    }
  });

  it("marks schema-invalid AI output failed without storing analysis or a manifest", async () => {
    const harness = createPipelineHarness({ ai: new InvalidAiProvider() });
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_012"),
      );

      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("failed");
      expect(harness.store.getJob(accepted.jobId!)?.lastError).toBe("call analysis failed");
      expect(harness.store.getAnalysis("lucaplus", "call_demo_012")).toBeNull();
      expect(harness.artifacts.exists("lucaplus", "call_demo_012", "manifest.json")).toBe(false);
      expect(harness.ai.callAnalysisCalls).toBe(3);
      expect(harness.ai.qualityAnalysisCalls).toBe(0);
    } finally {
      harness.close();
    }
  });

  it("requeues a DeepSeek deadline abort for bounded automatic retry", async () => {
    vi.useFakeTimers();
    const fetchStarted = deferred<AbortSignal>();
    const fetchFn = async (
      _url: string,
      init?: RequestInit,
    ): Promise<Response> => {
      if (!(init?.signal instanceof AbortSignal)) {
        throw new Error("missing deadline signal");
      }
      fetchStarted.resolve(init.signal);
      return new Promise<Response>((_resolve, reject) => {
        init.signal!.addEventListener(
          "abort",
          () => reject(init.signal!.reason),
          { once: true },
        );
      });
    };
    const provider = new DeepSeekAiProvider({
      apiKey: "test-key",
      fetchFn,
      requestTimeoutMs: 50,
    });
    const harness = createPipelineHarness({ ai: provider });

    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_deadline_terminal"),
      );
      const running = harness.worker.runOnce();
      await fetchStarted.promise;
      await vi.advanceTimersByTimeAsync(50);
      expect(await running).toBe(true);

      expect(harness.store.getJob(accepted.jobId!)).toMatchObject({
        status: "pending",
        attempts: 1,
        lastError: null,
      });
      expect(
        harness.artifacts.exists(
          "lucaplus",
          "call_deadline_terminal",
          "manifest.json",
        ),
      ).toBe(false);
    } finally {
      provider.close();
      vi.useRealTimers();
      harness.close();
    }
  });

  it("persists analysis before artifact failure and reuses it on retry", async () => {
    const harness = createPipelineHarness();
    try {
      const profile = "lucaplus";
      const callId = "call_demo_013";
      const accepted = harness.ingestion.ingest(makeNormalizedReportEvent(profile, callId));
      harness.artifacts.block(profile, callId, "customer-report.html");

      expect(await harness.worker.runOnce()).toBe(true);

      const failed = harness.store.getJob(accepted.jobId!);
      expect(failed?.status).toBe("pending");
      expect(failed?.attempts).toBe(1);
      expect(harness.store.getAnalysis(profile, callId)).not.toBeNull();
      expect(harness.artifacts.exists(profile, callId, "manifest.json")).toBe(false);
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);

      harness.artifacts.unblock(profile, callId, "customer-report.html");
      expect(await harness.worker.runOnce()).toBe(true);

      const succeeded = harness.store.getJob(accepted.jobId!);
      expect(succeeded?.status).toBe("succeeded");
      expect(succeeded?.attempts).toBe(2);
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);
      expect(harness.artifacts.exists(profile, callId, "manifest.json")).toBe(true);
      expect(harness.artifacts.list(profile, callId)).toEqual([
        "call.json",
        "customer-report.html",
        "manifest.json",
        "quality-report.html",
      ]);
    } finally {
      harness.close();
    }
  });

  it("rejects a call and loaded Profile slug mismatch before AI or artifacts", async () => {
    const mismatchedProfile = { ...lucaplusProfile, slug: "inp-group" };
    const profiles: ProfileRegistry = {
      get(slug: string) {
        return slug === "lucaplus" ? mismatchedProfile : null;
      },
      list() {
        return [mismatchedProfile];
      },
    };
    const harness = createPipelineHarness({ profiles });
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_014"),
      );

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("failed");
      expect(harness.store.getJob(accepted.jobId!)?.lastError).toBe("pipeline input invalid");
      expect(harness.ai.callAnalysisCalls).toBe(0);
      expect(harness.ai.qualityAnalysisCalls).toBe(0);
      expect(harness.store.getAnalysis("lucaplus", "call_demo_014")).toBeNull();
      expect(harness.artifacts.list("lucaplus", "call_demo_014")).toEqual([]);
    } finally {
      harness.close();
    }
  });

  it("stores only a bounded generic category for arbitrary provider failures", async () => {
    const leakedFragments = [
      "DeepSeek HTTP 500 body: raw model response",
      "Customer: I need an invoice workflow.",
      "https://example.invalid/recordings/demo.mp3",
      "pipeline-test-secret",
    ];
    const provider = new ThrowingAiProvider(
      `${leakedFragments.join(" | ")} ${"x".repeat(800)}`,
    );
    const harness = createPipelineHarness({ ai: provider });
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_015"),
      );

      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);

      const job = harness.store.getJob(accepted.jobId!);
      expect(job?.status).toBe("failed");
      expect(job?.attempts).toBe(3);
      expect(job?.lastError).toBe("call analysis failed");
      expect(job?.lastError?.length).toBeLessThanOrEqual(500);
      for (const leaked of leakedFragments) {
        expect(job?.lastError).not.toContain(leaked);
      }
      expect(harness.artifacts.exists("lucaplus", "call_demo_015", "manifest.json")).toBe(false);
    } finally {
      harness.close();
    }
  });
});

describe("analysis worker", () => {
  it("records a fixed scheduled failure category and timestamp without leaking exception text", async () => {
    const leakedFragments = [
      "raw provider response",
      "Demo Customer",
      "https://example.invalid/private-recording.mp3",
      "worker-test-secret",
    ];
    const scheduler = new TickableScheduler();
    let failNextCycle = true;
    const failingStore = {
      recoverStaleRunningJobs: () => 0,
      claimNextJob: () => {
        if (failNextCycle) {
          failNextCycle = false;
          throw new Error(leakedFragments.join(" | "));
        }
        return null;
      },
    } as unknown as SqliteStore;
    const worker = new AnalysisWorker(
      failingStore,
      {} as AnalysisPipeline,
      250,
      scheduler,
      () => new Date("2026-08-13T09:00:00.000Z"),
    );

    try {
      worker.start();
      expect(worker.getHealth()).toEqual({
        status: "ok",
        lastFailure: null,
      });

      await scheduler.tick();

      const health = worker.getHealth();
      expect(health).toEqual({
        status: "degraded",
        lastFailure: {
          category: "worker_cycle_failed",
          at: "2026-08-13T09:00:00.000Z",
        },
      });
      for (const leaked of leakedFragments) {
        expect(JSON.stringify(health)).not.toContain(leaked);
      }
      await scheduler.tick();
      expect(worker.getHealth()).toEqual({
        status: "ok",
        lastFailure: null,
      });
    } finally {
      await worker.stop();
    }
  });

  it("does not recover its owned job when start and stop race with runOnce", async () => {
    const provider = new BlockingAiProvider();
    const harness = createPipelineHarness({
      ai: provider,
      scheduler: createManualScheduler(),
    });
    try {
      const accepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_019"),
      );

      const directRun = harness.worker.runOnce();
      await provider.started.promise;
      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("running");

      harness.worker.start();
      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("running");
      const concurrentRun = harness.worker.runOnce();
      let stopFinished = false;
      const stopping = harness.worker.stop().then(() => {
        stopFinished = true;
      });
      await Promise.resolve();
      expect(stopFinished).toBe(false);

      provider.release();
      expect(await directRun).toBe(true);
      expect(await concurrentRun).toBe(true);
      await stopping;

      expect(harness.store.getJob(accepted.jobId!)?.status).toBe("succeeded");
      expect(harness.store.getJob(accepted.jobId!)?.attempts).toBe(1);
      expect(harness.artifacts.exists("lucaplus", "call_demo_019", "manifest.json")).toBe(true);
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);
    } finally {
      provider.release();
      await harness.worker.stop().catch(() => undefined);
      harness.close();
    }
  });

  it("defers unrelated stale-job recovery until its owned job settles", async () => {
    const provider = new BlockingAiProvider();
    let recoveryNow = new Date();
    const harness = createPipelineHarness({
      ai: provider,
      scheduler: createManualScheduler(),
      workerClock: () => recoveryNow,
      jobLeaseMs: TEST_JOB_LEASE_MS,
    });
    try {
      const stale = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_017"),
      );
      const active = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_018"),
      );
      expect(harness.store.claimNextJob()?.jobId).toBe(stale.jobId);
      expect(harness.store.getJob(stale.jobId!)?.status).toBe("running");
      recoveryNow = new Date(
        Date.parse(harness.store.getJob(stale.jobId!)!.updatedAt) +
          TEST_JOB_LEASE_MS +
          1,
      );

      const directRun = harness.worker.runOnce();
      await provider.started.promise;
      expect(harness.store.getJob(active.jobId!)?.status).toBe("running");

      harness.worker.start();
      expect(harness.store.getJob(stale.jobId!)?.status).toBe("running");
      expect(harness.store.getJob(active.jobId!)?.status).toBe("running");
      const concurrentRun = harness.worker.runOnce();
      let stopFinished = false;
      const stopping = harness.worker.stop().then(() => {
        stopFinished = true;
      });
      await Promise.resolve();
      expect(stopFinished).toBe(false);

      provider.release();
      expect(await directRun).toBe(true);
      expect(await concurrentRun).toBe(true);
      await stopping;

      expect(harness.store.getJob(active.jobId!)?.status).toBe("succeeded");
      expect(harness.store.getJob(active.jobId!)?.attempts).toBe(1);
      expect(harness.store.getJob(stale.jobId!)?.status).toBe("pending");
      expect(harness.store.getJob(stale.jobId!)?.attempts).toBe(1);
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.store.getJob(stale.jobId!)?.status).toBe("succeeded");
      expect(harness.store.getJob(stale.jobId!)?.attempts).toBe(2);
      expect(harness.ai.callAnalysisCalls).toBe(2);
      expect(harness.ai.qualityAnalysisCalls).toBe(2);
    } finally {
      provider.release();
      await harness.worker.stop().catch(() => undefined);
      harness.close();
    }
  });

  it("coalesces concurrent runOnce calls and stop waits for the in-flight job", async () => {
    const provider = new BlockingAiProvider();
    const harness = createPipelineHarness({ ai: provider });
    try {
      const firstAccepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_020"),
      );
      const secondAccepted = harness.ingestion.ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_021"),
      );

      const firstRun = harness.worker.runOnce();
      await provider.started.promise;
      const concurrentRun = harness.worker.runOnce();
      let stopFinished = false;
      const stopping = harness.worker.stop().then(() => {
        stopFinished = true;
      });
      await Promise.resolve();
      expect(stopFinished).toBe(false);

      provider.release();
      const [firstResult, concurrentResult] = await Promise.all([firstRun, concurrentRun]);
      await stopping;

      expect(firstResult).toBe(true);
      expect(concurrentResult).toBe(true);
      expect(harness.store.getJob(firstAccepted.jobId!)?.status).toBe("succeeded");
      expect(harness.store.getJob(secondAccepted.jobId!)?.status).toBe("pending");
      expect(harness.ai.callAnalysisCalls).toBe(1);
      expect(harness.ai.qualityAnalysisCalls).toBe(1);

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.store.getJob(secondAccepted.jobId!)?.status).toBe("succeeded");
      expect(harness.ai.callAnalysisCalls).toBe(2);
      expect(harness.ai.qualityAnalysisCalls).toBe(2);
    } finally {
      harness.close();
    }
  });

  it("recovers a stale running job on start and processes it without real timers", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "recovery.sqlite");
    const artifactRoot = join(root.path, "artifacts");
    let store = new SqliteStore(databasePath);
    let worker: AnalysisWorker | null = null;
    try {
      const accepted = new EventIngestionService(store).ingest(
        makeNormalizedReportEvent("inp-group", "call_demo_022"),
      );
      expect(store.claimNextJob()?.status).toBe("running");
      expect(store.getJob(accepted.jobId!)?.attempts).toBe(1);
      const staleNow = new Date(
        Date.parse(store.getJob(accepted.jobId!)!.updatedAt) +
          TEST_JOB_LEASE_MS +
          1,
      );
      store.close();

      store = new SqliteStore(databasePath);
      const ai = new CountingAiProvider();
      const pipeline = new AnalysisPipeline(
        store,
        profileRegistry,
        ai,
        new ArtifactWriter(artifactRoot),
        () => new Date("2026-08-13T05:00:00.000Z"),
      );
      worker = new AnalysisWorker(
        store,
        pipeline,
        250,
        createManualScheduler(),
        () => staleNow,
        TEST_JOB_LEASE_MS,
      );

      worker.start();
      expect(store.getJob(accepted.jobId!)?.status).toBe("pending");
      expect(await worker.runOnce()).toBe(true);
      await worker.stop();

      expect(store.getJob(accepted.jobId!)?.status).toBe("succeeded");
      expect(store.getJob(accepted.jobId!)?.attempts).toBe(2);
      expect(ai.callAnalysisCalls).toBe(1);
      expect(ai.qualityAnalysisCalls).toBe(1);
      expect(existsSync(join(artifactRoot, "inp-group", "call_demo_022", "manifest.json")))
        .toBe(true);
    } finally {
      await worker?.stop();
      store.close();
      root.close();
    }
  });

  it("leaves a fresh externally running job untouched on Worker start", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "fresh-lease.sqlite");
    const store = new SqliteStore(databasePath);
    let worker: AnalysisWorker | null = null;
    try {
      const accepted = new EventIngestionService(store).ingest(
        makeNormalizedReportEvent("lucaplus", "call_demo_023"),
      );
      expect(store.claimNextJob()?.status).toBe("running");
      const running = store.getJob(accepted.jobId!)!;
      const boundaryNow = new Date(
        Date.parse(running.updatedAt) + TEST_JOB_LEASE_MS,
      );
      const pipeline = new AnalysisPipeline(
        store,
        profileRegistry,
        new CountingAiProvider(),
        new ArtifactWriter(join(root.path, "artifacts")),
      );
      worker = new AnalysisWorker(
        store,
        pipeline,
        250,
        createManualScheduler(),
        () => boundaryNow,
        TEST_JOB_LEASE_MS,
      );

      worker.start();

      expect(store.getJob(accepted.jobId!)).toMatchObject({
        status: "running",
        attempts: 1,
        updatedAt: running.updatedAt,
      });
      expect(await worker.runOnce()).toBe(false);
    } finally {
      await worker?.stop();
      store.close();
      root.close();
    }
  });
});
