import type { AnalysisPipeline } from "../application/analysis-pipeline.js";
import type { SqliteStore } from "../storage/sqlite-store.js";

export const DEFAULT_JOB_LEASE_MS = 15 * 60 * 1000;
export const MAX_ANALYSIS_JOB_ATTEMPTS = 3;

const RETRYABLE_JOB_ERRORS = new Set([
  "call analysis failed",
  "quality analysis failed",
  "analysis persistence failed",
  "artifact generation failed",
  "outbox_planning_failed",
  "analysis pipeline failed",
]);

export interface WorkerScheduler {
  setInterval(callback: () => void, intervalMs: number): NodeJS.Timeout;
  clearInterval(timer: NodeJS.Timeout): void;
}

const defaultScheduler: WorkerScheduler = {
  setInterval(callback, intervalMs) {
    return setInterval(callback, intervalMs);
  },
  clearInterval(timer) {
    clearInterval(timer);
  },
};

type WorkerLifecycle = "ready" | "started" | "stopping";

export interface WorkerHealth {
  status: "ok" | "degraded";
  lastFailure: {
    category: "worker_cycle_failed";
    at: string;
  } | null;
}

export class AnalysisWorker {
  private timer: NodeJS.Timeout | null = null;
  private inFlight: Promise<boolean> | null = null;
  private lifecycle: WorkerLifecycle = "ready";
  private recoverAfterInFlight = false;
  private lastFailure: WorkerHealth["lastFailure"] = null;

  constructor(
    private readonly store: SqliteStore,
    private readonly pipeline: AnalysisPipeline,
    private readonly pollIntervalMs = 250,
    private readonly scheduler: WorkerScheduler = defaultScheduler,
    private readonly clock: () => Date = () => new Date(),
    private readonly jobLeaseMs = DEFAULT_JOB_LEASE_MS,
  ) {}

  runOnce(): Promise<boolean> {
    if (this.lifecycle === "stopping") {
      return this.inFlight ?? Promise.resolve(false);
    }
    if (this.inFlight) {
      return this.inFlight;
    }

    const operation = this.processNextJob().finally(() => {
      this.runDeferredRecovery();
    });
    this.inFlight = operation;
    operation.then(
      () => this.clearInFlight(operation),
      () => this.clearInFlight(operation),
    );
    return operation;
  }

  start(): void {
    if (this.lifecycle !== "ready") {
      return;
    }
    this.lifecycle = "started";
    try {
      if (this.inFlight) {
        this.recoverAfterInFlight = true;
      } else {
        this.store.recoverStaleRunningJobs(this.staleCutoff());
      }
      this.timer = this.scheduler.setInterval(async () => {
        try {
          await this.runOnce();
          this.lastFailure = null;
        } catch {
          this.lastFailure = {
            category: "worker_cycle_failed",
            at: this.clock().toISOString(),
          };
        }
      }, this.pollIntervalMs);
    } catch (error) {
      this.recoverAfterInFlight = false;
      this.lifecycle = "ready";
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (this.lifecycle !== "stopping") {
      this.lifecycle = "stopping";
      if (this.timer) {
        this.scheduler.clearInterval(this.timer);
        this.timer = null;
      }
    }
    const inFlight = this.inFlight;
    try {
      if (inFlight) {
        await inFlight;
      }
    } finally {
      this.lifecycle = "ready";
    }
  }

  getHealth(): WorkerHealth {
    return this.lastFailure
      ? {
          status: "degraded",
          lastFailure: { ...this.lastFailure },
        }
      : {
          status: "ok",
          lastFailure: null,
        };
  }

  private async processNextJob(): Promise<boolean> {
    const job = this.store.claimNextJob();
    if (!job) {
      return false;
    }
    await this.pipeline.process(job);
    const processed = this.store.getJob(job.jobId);
    if (
      processed?.status === "failed" &&
      processed.attempts < MAX_ANALYSIS_JOB_ATTEMPTS &&
      processed.lastError !== null &&
      RETRYABLE_JOB_ERRORS.has(processed.lastError)
    ) {
      this.store.retryJob(processed.jobId);
    }
    return true;
  }

  private clearInFlight(operation: Promise<boolean>): void {
    if (this.inFlight === operation) {
      this.inFlight = null;
    }
  }

  private runDeferredRecovery(): void {
    if (!this.recoverAfterInFlight) {
      return;
    }
    this.recoverAfterInFlight = false;
    this.store.recoverStaleRunningJobs(this.staleCutoff());
  }

  private staleCutoff(): string {
    return new Date(this.clock().getTime() - this.jobLeaseMs).toISOString();
  }
}
