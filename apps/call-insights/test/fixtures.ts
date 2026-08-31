import { tmpdir } from "node:os";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { FastifyInstance } from "fastify";
import type {
  AiProvider,
  CallAnalysisInput,
  QualityAnalysisInput,
} from "../src/ai/provider.js";
import { MockAiProvider } from "../src/ai/mock-provider.js";
import {
  buildApp,
  type WorkerHealthSource,
} from "../src/api/app.js";
import type { ConfigHealth } from "../src/profiles/runtime-config.js";
import { AnalysisPipeline } from "../src/application/analysis-pipeline.js";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import { RatingService } from "../src/application/rating-service.js";
import type { ReplayDependencies } from "../src/cli/replay.js";
import type {
  Call,
  CallAnalysis,
  NormalizedEvent,
  ProfileRegistry,
  QualityAnalysis,
} from "../src/domain/types.js";
import {
  OutboxPlanner,
  type OutboundMode,
  type OutboxPlanningSink,
} from "../src/outbound/outbox-planner.js";
import { loadProfile, profileRegistry } from "../src/profiles/profiles.js";
import { ArtifactWriter } from "../src/reports/artifact-writer.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import {
  AnalysisWorker,
  type WorkerScheduler,
} from "../src/worker/analysis-worker.js";
import endOfCallFixture from "../fixtures/vapi/end-of-call.json" with { type: "json" };
import statusUpdateFixture from "../fixtures/vapi/status-update.json" with { type: "json" };

export interface TemporaryResource {
  path: string;
  close(): void;
}

export interface TemporaryDirectory extends TemporaryResource {
  findFiles(suffix: string): string[];
}

export interface CliHarness {
  fixturePath: string;
  rootPath: string;
  databasePath: string;
  artifactRoot: string;
  dependencies: ReplayDependencies;
  readonly networkCalls: number;
  expectedArtifactPaths(profile: string, callId: string): string[];
  close(): void;
}

export const lucaplusProfile = loadProfile("lucaplus")!;
export const inpGroupProfile = loadProfile("inp-group")!;
export const sanitizedEndOfCallEnvelope = endOfCallFixture;
export const sanitizedStatusUpdateEnvelope = statusUpdateFixture;

export class CountingAiProvider implements AiProvider {
  readonly name: "mock" | "deepseek";
  callAnalysisCalls = 0;
  qualityAnalysisCalls = 0;

  constructor(private readonly delegate: AiProvider = new MockAiProvider()) {
    this.name = delegate.name;
  }

  close(): void {
    this.delegate.close();
  }

  async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    this.callAnalysisCalls += 1;
    return this.delegate.analyzeCall(input);
  }

  async analyzeQuality(input: QualityAnalysisInput): Promise<QualityAnalysis> {
    this.qualityAnalysisCalls += 1;
    return this.delegate.analyzeQuality(input);
  }
}

export class InvalidAiProvider implements AiProvider {
  readonly name = "mock" as const;

  close(): void {}

  async analyzeCall(): Promise<CallAnalysis> {
    return {
      ...makeAnalysis(),
      mainTopics: "not-an-array" as unknown as string[],
    };
  }

  async analyzeQuality(): Promise<QualityAnalysis> {
    throw new Error("unreachable");
  }
}

export interface PipelineHarness {
  store: SqliteStore;
  ingestion: EventIngestionService;
  ai: AiProvider & {
    callAnalysisCalls: number;
    qualityAnalysisCalls: number;
  };
  worker: AnalysisWorker;
  artifacts: {
    list(profile: string, callId: string): string[];
    exists(profile: string, callId: string, filename: string): boolean;
    block(profile: string, callId: string, filename: string): void;
    unblock(profile: string, callId: string, filename: string): void;
  };
  close(): void;
}

export interface ApiHarness {
  app: FastifyInstance;
  store: SqliteStore;
  close(): Promise<void>;
}

export interface ApiHarnessOptions {
  workerHealth?: WorkerHealthSource;
  mailExpected?: boolean;
  webhookAuth?: {
    required: boolean;
    token: string | null;
  };
  ingestAuth?: {
    required: boolean;
    token: string | null;
  };
  recordingRedirect?: {
    apiKey: string | null;
    fetchCall(callId: string): Promise<unknown>;
  };
  configHealth?: { getHealth(): ConfigHealth };
}

interface InternalApiHarness {
  harness: ApiHarness;
  pipeline: PipelineHarness;
}

export function createPipelineHarness(options: {
  ai?: AiProvider;
  profiles?: ProfileRegistry;
  scheduler?: WorkerScheduler;
  workerClock?: () => Date;
  jobLeaseMs?: number;
  outboundMode?: OutboundMode;
  cutoverNotBefore?: string | null;
  outbox?: OutboxPlanningSink;
} = {}): PipelineHarness {
  const root = tempDirectory();
  const store = new SqliteStore(join(root.path, "test.sqlite"));
  const ingestion = new EventIngestionService(store);
  const ai = new CountingAiProvider(options.ai);
  const artifactRoot = join(root.path, "artifacts");
  const pipeline = new AnalysisPipeline(
    store,
    options.profiles ?? profileRegistry,
    ai,
    new ArtifactWriter(artifactRoot),
    () => new Date("2026-08-13T04:00:00.000Z"),
    options.outbox ?? new OutboxPlanner(store, {
      mode: options.outboundMode ?? "off",
      cutoverNotBefore: options.cutoverNotBefore ?? null,
    }),
  );
  const worker = new AnalysisWorker(
    store,
    pipeline,
    250,
    options.scheduler,
    options.workerClock,
    options.jobLeaseMs,
  );

  const artifactPath = (profile: string, callId: string, filename?: string): string =>
    join(artifactRoot, profile, callId, ...(filename ? [filename] : []));

  return {
    store,
    ingestion,
    ai,
    worker,
    artifacts: {
      list(profile: string, callId: string): string[] {
        const directory = artifactPath(profile, callId);
        return existsSync(directory) ? readdirSync(directory).sort() : [];
      },
      exists(profile: string, callId: string, filename: string): boolean {
        return existsSync(artifactPath(profile, callId, filename));
      },
      block(profile: string, callId: string, filename: string): void {
        mkdirSync(artifactPath(profile, callId, filename), { recursive: true });
      },
      unblock(profile: string, callId: string, filename: string): void {
        rmSync(artifactPath(profile, callId, filename), { recursive: true, force: true });
      },
    },
    close(): void {
      store.close();
      root.close();
    },
  };
}

export function createCliHarness(): CliHarness {
  const root = tempDirectory();
  const databasePath = join(root.path, "database", "cli.sqlite");
  mkdirSync(join(root.path, "database"), { recursive: true });
  const artifactRoot = join(root.path, "artifacts");
  const store = new SqliteStore(databasePath);
  const ingestion = new EventIngestionService(store);
  const artifacts = new ArtifactWriter(artifactRoot);
  const pipeline = new AnalysisPipeline(
    store,
    profileRegistry,
    new MockAiProvider(),
    artifacts,
    () => new Date("2026-08-13T04:00:00.000Z"),
  );
  const worker = new AnalysisWorker(store, pipeline);
  const originalFetch = globalThis.fetch;
  let networkCalls = 0;
  let closed = false;
  globalThis.fetch = (async () => {
    networkCalls += 1;
    throw new Error("network forbidden in CLI tests");
  }) as typeof fetch;

  return {
    fixturePath: fileURLToPath(
      new URL("../fixtures/vapi/end-of-call.json", import.meta.url),
    ),
    rootPath: root.path,
    databasePath,
    artifactRoot,
    dependencies: {
      profiles: profileRegistry,
      store,
      ingestion,
      worker,
      artifacts,
      readTextFile: (path) => readFile(path, "utf8"),
    },
    get networkCalls(): number {
      return networkCalls;
    },
    expectedArtifactPaths(profile: string, callId: string): string[] {
      return [
        "call.json",
        "customer-report.html",
        "quality-report.html",
        "manifest.json",
      ].map((filename) => join(artifactRoot, profile, callId, filename));
    },
    close(): void {
      if (closed) {
        return;
      }
      closed = true;
      globalThis.fetch = originalFetch;
      store.close();
      root.close();
    },
  };
}

function createInternalApiHarness(options: ApiHarnessOptions = {}): InternalApiHarness {
  const pipeline = createPipelineHarness();
  const app = buildApp({
    profiles: profileRegistry,
    ingestion: pipeline.ingestion,
    rating: new RatingService(
      pipeline.store,
      () => new Date("2026-08-13T09:30:00.000Z"),
    ),
    store: pipeline.store,
    worker: options.workerHealth ?? pipeline.worker,
    clock: () => new Date("2026-08-13T09:00:00.000Z"),
    mailExpected: options.mailExpected ?? false,
    ...(options.webhookAuth ? { webhookAuth: options.webhookAuth } : {}),
    ...(options.ingestAuth ? { ingestAuth: options.ingestAuth } : {}),
    ...(options.recordingRedirect
      ? { recordingRedirect: options.recordingRedirect }
      : {}),
    ...(options.configHealth ? { configHealth: options.configHealth } : {}),
  });
  const harness: ApiHarness = {
    app,
    store: pipeline.store,
    async close(): Promise<void> {
      try {
        await app.close();
      } finally {
        try {
          await pipeline.worker.stop();
        } finally {
          pipeline.close();
        }
      }
    },
  };
  return { harness, pipeline };
}

export function createApiHarness(options: ApiHarnessOptions = {}): ApiHarness {
  return createInternalApiHarness(options).harness;
}

export async function createApiHarnessWithCompletedCall(
  options: ApiHarnessOptions = {},
): Promise<ApiHarness> {
  const internal = createInternalApiHarness(options);
  const accepted = internal.pipeline.ingestion.ingest(
    makeNormalizedReportEvent("lucaplus", "call_demo_001"),
  );
  await internal.pipeline.worker.runOnce();
  if (
    accepted.status !== "accepted" ||
    accepted.jobId === null ||
    internal.pipeline.store.getJob(accepted.jobId)?.status !== "succeeded"
  ) {
    await internal.harness.close();
    throw new Error("completed API harness setup failed");
  }
  return internal.harness;
}

export function makeCall(overrides: Partial<Call> = {}): Call {
  const callId = overrides.callId ?? "call_demo_001";
  return {
    profile: "lucaplus",
    callId,
    eventId: overrides.eventId ?? `event_${callId}`,
    channel: "vapi",
    transcript: "Customer: I need an invoice workflow.",
    summary: "Customer asked about invoice automation.",
    startedAt: "2026-08-13T01:00:00.000Z",
    endedAt: "2026-08-13T01:02:30.000Z",
    durationSeconds: 150,
    recordingUrl: "https://example.invalid/recordings/demo.mp3",
    receivedAt: "2026-08-13T02:00:00.000Z",
    ...overrides,
  };
}

export function makeAnalysis(overrides: Partial<CallAnalysis> = {}): CallAnalysis {
  return {
    customerName: "Demo Customer",
    contactInfo: "demo@example.invalid",
    mainTopics: ["invoice automation"],
    formattedTranscript: "Customer: I need an invoice workflow.",
    localCallTime: "2026-08-13 11:00 AEST",
    ...overrides,
  };
}

export function makeQuality(overrides: Partial<QualityAnalysis> = {}): QualityAnalysis {
  return {
    score: 8,
    strengths: ["Clear greeting"],
    weaknesses: ["Missed follow-up"],
    suggestions: ["Confirm next steps"],
    shouldUpdatePrompt: false,
    summary: "Solid call with minor follow-up gap.",
    ...overrides,
  };
}

export function makeNormalizedReportEvent(
  profile = "lucaplus",
  callId = "call_demo_001",
): NormalizedEvent {
  const call = makeCall({ profile, callId });
  return {
    eventId: call.eventId,
    payloadHash: "payload_hash_demo",
    profile,
    eventType: "end-of-call-report",
    callId,
    receivedAt: call.receivedAt,
    action: "analyze",
    call,
  };
}

export function makeSkippedEvent(): NormalizedEvent {
  return {
    eventId: "event_skip_demo",
    payloadHash: "payload_hash_skip",
    profile: "lucaplus",
    eventType: "status-update",
    callId: "call_demo_002",
    receivedAt: "2026-08-13T02:00:00.000Z",
    action: "skip",
    call: null,
  };
}

function walkFiles(directory: string, suffix: string, matches: string[]): void {
  for (const entry of readdirSync(directory)) {
    const fullPath = join(directory, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walkFiles(fullPath, suffix, matches);
    } else if (fullPath.endsWith(suffix.startsWith("*") ? suffix.slice(1) : suffix)) {
      matches.push(fullPath);
    }
  }
}

export function tempDirectory(): TemporaryDirectory {
  const path = mkdtempSync(join(tmpdir(), "vapi-call-insights-"));
  return {
    path,
    findFiles(suffix: string): string[] {
      const matches: string[] = [];
      walkFiles(path, suffix, matches);
      return matches;
    },
    close(): void {
      rmSync(path, { recursive: true, force: true });
    },
  };
}

export function tempDatabase(): TemporaryResource {
  const directory = tempDirectory();
  return {
    path: join(directory.path, "test.sqlite"),
    close(): void {
      directory.close();
    },
  };
}
