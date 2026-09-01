import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { DeepSeekAiProvider } from "../src/ai/deepseek-provider.js";
import { MockAiProvider } from "../src/ai/mock-provider.js";
import type {
  CallAnalysisInput,
  QualityAnalysisInput,
} from "../src/ai/provider.js";
import { AnalysisPipeline } from "../src/application/analysis-pipeline.js";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import {
  createReplayRuntime,
  replayMain,
  runReplay,
  runReplayCommand,
} from "../src/cli/replay.js";
import type { CallAnalysis, QualityAnalysis } from "../src/domain/types.js";
import { profileRegistry } from "../src/profiles/profiles.js";
import { ArtifactWriter } from "../src/reports/artifact-writer.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import {
  AnalysisWorker,
  DEFAULT_JOB_LEASE_MS,
} from "../src/worker/analysis-worker.js";
import { createCliHarness, tempDirectory } from "./fixtures.js";

function deferred<T = void>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

class CountingMockAiProvider extends MockAiProvider {
  callAnalysisCalls = 0;
  qualityAnalysisCalls = 0;

  override async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    this.callAnalysisCalls += 1;
    return super.analyzeCall(input);
  }

  override async analyzeQuality(input: QualityAnalysisInput): Promise<QualityAnalysis> {
    this.qualityAnalysisCalls += 1;
    return super.analyzeQuality(input);
  }
}

class BlockingMockAiProvider extends CountingMockAiProvider {
  readonly started = deferred();
  private readonly released = deferred();

  override async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    this.started.resolve();
    await this.released.promise;
    return super.analyzeCall(input);
  }

  release(): void {
    this.released.resolve();
  }
}

const PRIVATE_OR_AI_FRAGMENTS = [
  "Customer: I need an invoice workflow.",
  "Customer asked about invoice automation.",
  "https://example.invalid/recordings/demo.mp3",
  "+61000000000",
  "Demo Customer",
  "demo@example.invalid",
  "The assistant handled the demo invoice request clearly with one follow-up gap.",
] as const;

describe("replay CLI", () => {
  it("replays a sanitized fixture and waits for four local artifacts", async () => {
    const harness = createCliHarness();
    try {
      const result = await runReplay(
        ["--profile", "lucaplus", "--file", harness.fixturePath, "--wait"],
        harness.dependencies,
      );

      expect(result).toEqual({
        status: "succeeded",
        eventId: expect.stringMatching(/^[a-f0-9]{64}$/),
        callId: "call_demo_001",
        jobId: 1,
        files: harness.expectedArtifactPaths("lucaplus", "call_demo_001"),
      });
      expect(result.files.every(existsSync)).toBe(true);
      expect(harness.networkCalls).toBe(0);
      expect(harness.databasePath.startsWith(harness.rootPath)).toBe(true);
      expect(harness.artifactRoot.startsWith(harness.rootPath)).toBe(true);
    } finally {
      harness.close();
    }
  });

  it("forces replay outbound planning off even when the environment requests live mail", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "replay-off.sqlite");
    const args = [
      "--profile",
      "lucaplus",
      "--file",
      join(process.cwd(), "fixtures", "vapi", "end-of-call.json"),
      "--wait",
      "--database",
      databasePath,
      "--artifacts",
      join(root.path, "artifacts"),
    ];
    const runtime = createReplayRuntime(args, {
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-17T00:00:00.000Z",
    });
    try {
      expect((await runReplay(args, runtime.dependencies)).status)
        .toBe("succeeded");
      expect(runtime.dependencies.store.countMail()).toBe(0);
    } finally {
      await runtime.close();
      root.close();
    }
  });

  it("leaves an accepted job pending when wait is omitted", async () => {
    const harness = createCliHarness();
    try {
      const result = await runReplay(
        ["--profile", "inp-group", "--file", harness.fixturePath],
        harness.dependencies,
      );

      expect(result.status).toBe("accepted");
      expect(result.files).toEqual([]);
      expect(harness.dependencies.store.getJob(result.jobId!)?.status).toBe("pending");
      expect(harness.networkCalls).toBe(0);
    } finally {
      harness.close();
    }
  });

  it("returns shutdown-cancelled DeepSeek work to pending and resumes with Mock", async () => {
    const root = tempDirectory();
    const fetchStarted = deferred<AbortSignal>();
    const fetchFn = async (_url: string, init?: RequestInit): Promise<Response> => {
      if (!(init?.signal instanceof AbortSignal)) {
        throw new Error("missing cancellation signal");
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
      requestTimeoutMs: 60_000,
    });
    const databasePath = join(root.path, "cli-cancel.sqlite");
    const artifactRoot = join(root.path, "artifacts");
    const args = [
      "--profile",
      "lucaplus",
      "--file",
      join(process.cwd(), "fixtures", "vapi", "end-of-call.json"),
      "--database",
      databasePath,
      "--artifacts",
      artifactRoot,
    ];
    const runtime = createReplayRuntime(args, {}, { provider });
    let restarted: ReturnType<typeof createReplayRuntime> | null = null;
    let running: Promise<boolean> | null = null;
    let closing: Promise<void> | null = null;

    try {
      const accepted = await runReplay(args, runtime.dependencies);
      expect(accepted.status).toBe("accepted");
      running = runtime.dependencies.worker.runOnce();
      const signal = await fetchStarted.promise;

      closing = runtime.close();
      const outcome = await Promise.race([
        closing.then(() => "closed" as const),
        new Promise<"blocked">((resolveBlocked) => {
          setTimeout(() => resolveBlocked("blocked"), 50);
        }),
      ]);

      expect(outcome).toBe("closed");
      expect(signal.aborted).toBe(true);
      expect(await running).toBe(true);
      await closing;

      const inspection = new SqliteStore(databasePath);
      try {
        expect(inspection.getJob(accepted.jobId!)).toMatchObject({
          status: "pending",
          attempts: 1,
          lastError: null,
        });
        expect(
          inspection.getAnalysis("lucaplus", "call_demo_001"),
        ).toBeNull();
        expect(
          existsSync(
            join(
              artifactRoot,
              "lucaplus",
              "call_demo_001",
              "manifest.json",
            ),
          ),
        ).toBe(false);
      } finally {
        inspection.close();
      }

      const waitArgs = [...args, "--wait"];
      restarted = createReplayRuntime(waitArgs, {}, {
        provider: new MockAiProvider(),
      });
      const resumed = await runReplay(waitArgs, restarted.dependencies);
      expect(resumed).toEqual({
        status: "succeeded",
        eventId: accepted.eventId,
        callId: "call_demo_001",
        jobId: accepted.jobId,
        files: [
          "call.json",
          "customer-report.html",
          "quality-report.html",
          "manifest.json",
        ].map((filename) =>
          join(artifactRoot, "lucaplus", "call_demo_001", filename)
        ),
      });
      expect(restarted.dependencies.store.getJob(accepted.jobId!)).toMatchObject({
        status: "succeeded",
        attempts: 2,
        lastError: null,
      });
    } finally {
      provider.close();
      await restarted?.close().catch(() => undefined);
      await running?.catch(() => undefined);
      await closing?.catch(() => undefined);
      await runtime.close().catch(() => undefined);
      root.close();
    }
  });

  it("prints only replay metadata and artifact paths", async () => {
    const harness = createCliHarness();
    const output: string[] = [];
    try {
      const result = await runReplayCommand(
        ["--profile", "lucaplus", "--file", harness.fixturePath, "--wait"],
        harness.dependencies,
        (line) => output.push(line),
      );

      expect(output).toHaveLength(1);
      expect(JSON.parse(output[0]!)).toEqual({
        status: result.status,
        callId: result.callId,
        jobId: result.jobId,
        files: result.files,
      });
      expect(Object.keys(JSON.parse(output[0]!)).sort()).toEqual([
        "callId",
        "files",
        "jobId",
        "status",
      ]);
      for (const fragment of PRIVATE_OR_AI_FRAGMENTS) {
        expect(output[0]).not.toContain(fragment);
      }
    } finally {
      harness.close();
    }
  });

  it("returns active when another process claims the requested job during runOnce", async () => {
    const harness = createCliHarness();
    const externalStore = new SqliteStore(harness.databasePath);
    let runOnceCalls = 0;
    const racingWorker = {
      async runOnce(): Promise<boolean> {
        runOnceCalls += 1;
        expect(externalStore.claimNextJob()?.status).toBe("running");
        return false;
      },
    } as unknown as AnalysisWorker;

    try {
      const result = await runReplay(
        [
          "--profile",
          "lucaplus",
          "--file",
          harness.fixturePath,
          "--wait",
        ],
        {
          ...harness.dependencies,
          worker: racingWorker,
        },
      );

      expect(result).toMatchObject({
        status: "active",
        callId: "call_demo_001",
        jobId: 1,
        files: [],
      });
      expect(runOnceCalls).toBe(1);
      expect(externalStore.getJob(1)).toMatchObject({
        status: "running",
        attempts: 1,
      });
    } finally {
      externalStore.close();
      harness.close();
    }
  });

  it("discovers exact artifacts when another worker completes before runOnce errors", async () => {
    const harness = createCliHarness();
    const externalStore = new SqliteStore(harness.databasePath);
    const externalAi = new CountingMockAiProvider();
    const externalArtifacts = new ArtifactWriter(harness.artifactRoot);
    const externalWorker = new AnalysisWorker(
      externalStore,
      new AnalysisPipeline(
        externalStore,
        profileRegistry,
        externalAi,
        externalArtifacts,
      ),
    );
    const racingWorker = {
      async runOnce(): Promise<boolean> {
        expect(await externalWorker.runOnce()).toBe(true);
        throw new Error("simulated local claim race");
      },
    } as unknown as AnalysisWorker;

    try {
      const result = await runReplay(
        [
          "--profile",
          "lucaplus",
          "--file",
          harness.fixturePath,
          "--wait",
        ],
        {
          ...harness.dependencies,
          worker: racingWorker,
        },
      );

      expect(result).toEqual({
        status: "succeeded",
        eventId: expect.stringMatching(/^[a-f0-9]{64}$/),
        callId: "call_demo_001",
        jobId: 1,
        files: harness.expectedArtifactPaths("lucaplus", "call_demo_001"),
      });
      expect(result.files.every(existsSync)).toBe(true);
      expect(externalAi.callAnalysisCalls).toBe(1);
      expect(externalAi.qualityAnalysisCalls).toBe(1);
    } finally {
      await externalWorker.stop().catch(() => undefined);
      externalAi.close();
      externalStore.close();
      harness.close();
    }
  });

  it("returns a failing exit code without printing failed-pipeline content", async () => {
    const root = tempDirectory();
    const fixturePath = join(root.path, "failed-pipeline.json");
    const artifactRoot = join(root.path, "artifacts");
    writeFileSync(
      fixturePath,
      JSON.stringify({
        message: {
          type: "end-of-call-report",
          timestamp: 1786600000000,
          call: { id: "bad_id" },
          startedAt: "2026-08-13T01:00:00.000Z",
          endedAt: "2026-08-13T01:02:30.000Z",
          transcript: "private failed-pipeline transcript",
          summary: "private failed-pipeline summary",
        },
      }),
      "utf8",
    );
    mkdirSync(
      join(
        artifactRoot,
        "lucaplus",
        "bad_id",
        "customer-report.html",
      ),
      { recursive: true },
    );
    const output: string[] = [];
    const errors: string[] = [];

    try {
      const exitCode = await replayMain(
        [
          "--profile",
          "lucaplus",
          "--file",
          fixturePath,
          "--wait",
          "--database",
          join(root.path, "failed.sqlite"),
          "--artifacts",
          artifactRoot,
        ],
        {},
        (line) => output.push(line),
        (line) => errors.push(line),
      );

      expect(exitCode).toBe(1);
      expect(output).toHaveLength(1);
      expect(JSON.parse(output[0]!)).toEqual({
        status: "failed",
        callId: "bad_id",
        jobId: 1,
        files: [],
      });
      expect(output[0]).not.toContain("private failed-pipeline");
      expect(errors).toEqual([]);
    } finally {
      root.close();
    }
  });

  it.each([
    {
      name: "unknown profile",
      profile: "unknown",
      fixtureContents: JSON.stringify({
        message: {
          type: "status-update",
          timestamp: 1786600000000,
        },
      }),
    },
    {
      name: "invalid JSON",
      profile: "lucaplus",
      fixtureContents: "{not-json",
    },
    {
      name: "invalid VAPI payload",
      profile: "lucaplus",
      fixtureContents: JSON.stringify({ message: { type: "end-of-call-report" } }),
    },
  ])(
    "preflights $name before creating SQLite or artifact directories",
    async ({ profile, fixtureContents }) => {
      const root = tempDirectory();
      const fixturePath = join(root.path, "preflight.json");
      const dataDirectory = join(root.path, "data");
      const databasePath = join(dataDirectory, "preflight.sqlite");
      const artifactRoot = join(root.path, "artifacts");
      writeFileSync(fixturePath, fixtureContents, "utf8");
      const output: string[] = [];
      const errors: string[] = [];

      try {
        const exitCode = await replayMain(
          [
            "--profile",
            profile,
            "--file",
            fixturePath,
            "--database",
            databasePath,
            "--artifacts",
            artifactRoot,
          ],
          {},
          (line) => output.push(line),
          (line) => errors.push(line),
        );

        expect(exitCode).toBe(1);
        expect(output).toEqual([]);
        expect(errors).toEqual(["replay_failed"]);
        expect(existsSync(dataDirectory)).toBe(false);
        expect(existsSync(databasePath)).toBe(false);
        expect(existsSync(artifactRoot)).toBe(false);
      } finally {
        root.close();
      }
    },
  );

  it("recovers a stale running job before a duplicate wait replay", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "recovery.sqlite");
    const artifactRoot = join(root.path, "artifacts");
    const baseArgs = [
      "--profile",
      "lucaplus",
      "--file",
      join(
        process.cwd(),
        "fixtures",
        "vapi",
        "end-of-call.json",
      ),
      "--database",
      databasePath,
      "--artifacts",
      artifactRoot,
    ];
    const firstRuntime = createReplayRuntime(baseArgs, {});
    let secondRuntime: ReturnType<typeof createReplayRuntime> | null = null;

    try {
      const accepted = await runReplay(baseArgs, firstRuntime.dependencies);
      expect(accepted.status).toBe("accepted");
      expect(firstRuntime.dependencies.store.claimNextJob()?.status).toBe("running");
      expect(firstRuntime.dependencies.store.getJob(accepted.jobId!)?.attempts).toBe(1);
      const staleNow = new Date(
        Date.parse(
          firstRuntime.dependencies.store.getJob(accepted.jobId!)!.updatedAt,
        ) +
          DEFAULT_JOB_LEASE_MS +
          1,
      );
      await firstRuntime.close();

      const waitArgs = [...baseArgs, "--wait"];
      secondRuntime = createReplayRuntime(waitArgs, {}, {
        clock: () => staleNow,
        jobLeaseMs: DEFAULT_JOB_LEASE_MS,
      });
      const recovered = await runReplay(waitArgs, secondRuntime.dependencies);

      expect(recovered.status).toBe("succeeded");
      expect(recovered.jobId).toBe(accepted.jobId);
      expect(recovered.files).toHaveLength(4);
      expect(secondRuntime.dependencies.store.getJob(accepted.jobId!)).toMatchObject({
        status: "succeeded",
        attempts: 2,
      });
    } finally {
      await secondRuntime?.close();
      await firstRuntime.close();
      root.close();
    }
  });

  it("does not disturb a fresh job owned by another runtime", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "concurrent.sqlite");
    const fixturePath = join(
      process.cwd(),
      "fixtures",
      "vapi",
      "end-of-call.json",
    );
    const ownerArtifactRoot = join(root.path, "owner-artifacts");
    const observerArtifactRoot = join(root.path, "observer-artifacts");
    const mainArtifactRoot = join(root.path, "main-artifacts");
    const baseArgs = [
      "--profile",
      "lucaplus",
      "--file",
      fixturePath,
      "--database",
      databasePath,
      "--artifacts",
      ownerArtifactRoot,
    ];
    const ownerStore = new SqliteStore(databasePath);
    const ownerAi = new BlockingMockAiProvider();
    const ownerArtifacts = new ArtifactWriter(ownerArtifactRoot);
    const ownerWorker = new AnalysisWorker(
      ownerStore,
      new AnalysisPipeline(
        ownerStore,
        profileRegistry,
        ownerAi,
        ownerArtifacts,
      ),
    );
    const ownerDependencies = {
      profiles: profileRegistry,
      store: ownerStore,
      ingestion: new EventIngestionService(ownerStore),
      worker: ownerWorker,
      artifacts: ownerArtifacts,
      readTextFile: (path: string) => readFile(path, "utf8"),
    };
    const observerStore = new SqliteStore(databasePath);
    const observerAi = new CountingMockAiProvider();
    const observerArtifacts = new ArtifactWriter(observerArtifactRoot);
    const observerWorker = new AnalysisWorker(
      observerStore,
      new AnalysisPipeline(
        observerStore,
        profileRegistry,
        observerAi,
        observerArtifacts,
      ),
    );
    const output: string[] = [];
    const errors: string[] = [];
    let ownerRun: Promise<boolean> | null = null;

    try {
      const accepted = await runReplay(baseArgs, ownerDependencies);
      ownerRun = ownerWorker.runOnce();
      await ownerAi.started.promise;
      const running = ownerStore.getJob(accepted.jobId!)!;
      const freshNow = new Date(
        Date.parse(running.updatedAt) + DEFAULT_JOB_LEASE_MS,
      );
      const observerDependencies = {
        profiles: profileRegistry,
        store: observerStore,
        ingestion: new EventIngestionService(observerStore),
        worker: observerWorker,
        artifacts: observerArtifacts,
        readTextFile: (path: string) => readFile(path, "utf8"),
        clock: () => freshNow,
        jobLeaseMs: DEFAULT_JOB_LEASE_MS,
      };

      const observed = await runReplay(
        [...baseArgs.slice(0, -1), observerArtifactRoot, "--wait"],
        observerDependencies,
      );

      expect(observed).toMatchObject({
        status: "active",
        callId: "call_demo_001",
        jobId: accepted.jobId,
        files: [],
      });
      expect(observerAi.callAnalysisCalls).toBe(0);
      expect(observerAi.qualityAnalysisCalls).toBe(0);
      expect(observerStore.getJob(accepted.jobId!)).toMatchObject({
        status: "running",
        attempts: 1,
        updatedAt: running.updatedAt,
      });
      expect(observerStore.getAnalysis("lucaplus", "call_demo_001")).toBeNull();
      expect(existsSync(observerArtifactRoot)).toBe(false);

      const exitCode = await replayMain(
        [
          ...baseArgs.slice(0, -1),
          mainArtifactRoot,
          "--wait",
        ],
        {},
        (line) => output.push(line),
        (line) => errors.push(line),
      );
      expect(exitCode).toBe(1);
      expect(output).toHaveLength(1);
      expect(JSON.parse(output[0]!)).toEqual({
        status: "active",
        callId: "call_demo_001",
        jobId: accepted.jobId,
        files: [],
      });
      expect(errors).toEqual([]);
      expect(ownerStore.getJob(accepted.jobId!)).toMatchObject({
        status: "running",
        attempts: 1,
        updatedAt: running.updatedAt,
      });
      expect(existsSync(mainArtifactRoot)).toBe(false);

      ownerAi.release();
      expect(await ownerRun).toBe(true);
      expect(ownerStore.getJob(accepted.jobId!)).toMatchObject({
        status: "succeeded",
        attempts: 1,
      });
      expect(ownerAi.callAnalysisCalls).toBe(1);
      expect(ownerAi.qualityAnalysisCalls).toBe(1);
      expect(
        await ownerArtifacts.listFiles("lucaplus", "call_demo_001"),
      ).toHaveLength(4);
    } finally {
      ownerAi.release();
      await ownerRun?.catch(() => undefined);
      await observerWorker.stop().catch(() => undefined);
      await ownerWorker.stop().catch(() => undefined);
      observerStore.close();
      ownerStore.close();
      root.close();
    }
  });

  it("returns a fixed failure when a succeeded database uses a different artifact root", async () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "completed.sqlite");
    const fixturePath = join(
      process.cwd(),
      "fixtures",
      "vapi",
      "end-of-call.json",
    );
    const originalArgs = [
      "--profile",
      "lucaplus",
      "--file",
      fixturePath,
      "--wait",
      "--database",
      databasePath,
      "--artifacts",
      join(root.path, "original-artifacts"),
    ];
    const firstRuntime = createReplayRuntime(originalArgs, {});
    const output: string[] = [];
    const errors: string[] = [];

    try {
      expect(
        (await runReplay(originalArgs, firstRuntime.dependencies)).status,
      ).toBe("succeeded");
      await firstRuntime.close();

      const exitCode = await replayMain(
        [
          "--profile",
          "lucaplus",
          "--file",
          fixturePath,
          "--wait",
          "--database",
          databasePath,
          "--artifacts",
          join(root.path, "wrong-artifacts"),
        ],
        {},
        (line) => output.push(line),
        (line) => errors.push(line),
      );

      expect(exitCode).toBe(1);
      expect(output).toHaveLength(1);
      expect(JSON.parse(output[0]!)).toEqual({
        status: "failed",
        callId: "call_demo_001",
        jobId: 1,
        files: [],
      });
      expect(errors).toEqual([]);
      expect(existsSync(join(root.path, "wrong-artifacts"))).toBe(false);
    } finally {
      await firstRuntime.close();
      root.close();
    }
  });
});
