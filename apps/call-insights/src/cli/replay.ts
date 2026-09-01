import { mkdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createAiProvider, type AiProvider } from "../ai/provider.js";
import { AnalysisPipeline } from "../application/analysis-pipeline.js";
import { EventIngestionService } from "../application/event-ingestion-service.js";
import { normalizeVapiEvent } from "../application/normalize-vapi-event.js";
import { loadConfig } from "../config.js";
import type { NormalizedEvent, ProfileRegistry } from "../domain/types.js";
import { OFF_OUTBOX_PLANNER } from "../outbound/outbox-planner.js";
import { profileRegistry } from "../profiles/profiles.js";
import { ArtifactWriter } from "../reports/artifact-writer.js";
import { SqliteStore } from "../storage/sqlite-store.js";
import {
  AnalysisWorker,
  DEFAULT_JOB_LEASE_MS,
} from "../worker/analysis-worker.js";

const DEFAULT_DATABASE_PATH = "data/vapi-call-insights.sqlite";
const DEFAULT_ARTIFACT_DIRECTORY = "artifacts";

export interface ReplayResult {
  status: "accepted" | "duplicate" | "skipped" | "active" | "succeeded" | "failed";
  eventId: string;
  callId: string | null;
  jobId: number | null;
  files: string[];
}

export interface ReplayDependencies {
  profiles: ProfileRegistry;
  store: SqliteStore;
  ingestion: EventIngestionService;
  worker: AnalysisWorker;
  artifacts: ArtifactWriter;
  readTextFile(path: string): Promise<string>;
  clock?: () => Date;
  jobLeaseMs?: number;
}

export interface ReplayRuntime {
  dependencies: ReplayDependencies;
  close(): Promise<void>;
}

export interface ReplayRuntimeOptions {
  provider?: AiProvider;
  clock?: () => Date;
  jobLeaseMs?: number;
}

interface ReplayOptions {
  profile: string;
  filePath: string;
  wait: boolean;
  databasePath: string;
  artifactDirectory: string;
}

interface PreparedReplay {
  options: ReplayOptions;
  event: NormalizedEvent;
}

interface ReplayPreflightDependencies {
  profiles: ProfileRegistry;
  readTextFile(path: string): Promise<string>;
}

type LineWriter = (line: string) => void;

export async function runReplay(
  args: readonly string[],
  dependencies: ReplayDependencies,
): Promise<ReplayResult> {
  const prepared = await prepareReplay(args, dependencies);
  return runPreparedReplay(prepared, dependencies);
}

async function prepareReplay(
  args: readonly string[],
  dependencies: ReplayPreflightDependencies,
): Promise<PreparedReplay> {
  const options = parseReplayOptions(args);
  const profile = dependencies.profiles.get(options.profile);
  if (!profile) {
    throw new Error("unknown_profile");
  }

  let input: unknown;
  try {
    input = JSON.parse(await dependencies.readTextFile(options.filePath));
  } catch {
    throw new Error("invalid_fixture");
  }

  let event: NormalizedEvent;
  try {
    event = normalizeVapiEvent(profile, input, new Date());
  } catch {
    throw new Error("invalid_fixture");
  }
  return { options, event };
}

async function runPreparedReplay(
  prepared: PreparedReplay,
  dependencies: ReplayDependencies,
): Promise<ReplayResult> {
  const ingested = dependencies.ingestion.ingest(prepared.event);
  const { options } = prepared;
  if (!options.wait || ingested.jobId === null) {
    return {
      status: ingested.status,
      eventId: ingested.eventId,
      callId: ingested.callId,
      jobId: ingested.jobId,
      files: [],
    };
  }

  const clock = dependencies.clock ?? (() => new Date());
  const jobLeaseMs = dependencies.jobLeaseMs ?? DEFAULT_JOB_LEASE_MS;
  const staleCutoff = new Date(
    clock().getTime() - jobLeaseMs,
  ).toISOString();
  dependencies.store.recoverStaleRunningJob(ingested.jobId, staleCutoff);
  let job = dependencies.store.getJob(ingested.jobId);
  if (job?.status === "running") {
    return {
      status: "active",
      eventId: ingested.eventId,
      callId: ingested.callId,
      jobId: ingested.jobId,
      files: [],
    };
  }
  while (job?.status === "pending") {
    let runOnceResult: boolean | null = null;
    try {
      runOnceResult = await dependencies.worker.runOnce();
    } catch {
      // The requested job is re-read below before the local error is classified.
    }
    job = dependencies.store.getJob(ingested.jobId);
    if (job?.status === "running") {
      return {
        status: "active",
        eventId: ingested.eventId,
        callId: ingested.callId,
        jobId: ingested.jobId,
        files: [],
      };
    }
    if (job?.status === "pending" && runOnceResult !== true) {
      throw new Error("replay_job_stalled");
    }
  }
  if (!job || (job.status !== "succeeded" && job.status !== "failed")) {
    throw new Error("replay_job_not_terminal");
  }

  let files: string[] = [];
  if (job.status === "succeeded" && ingested.callId !== null) {
    try {
      files = await dependencies.artifacts.listFiles(
        options.profile,
        ingested.callId,
      );
    } catch {
      return {
        status: "failed",
        eventId: ingested.eventId,
        callId: ingested.callId,
        jobId: ingested.jobId,
        files: [],
      };
    }
  }
  return {
    status: job.status,
    eventId: ingested.eventId,
    callId: ingested.callId,
    jobId: ingested.jobId,
    files,
  };
}

export async function runReplayCommand(
  args: readonly string[],
  dependencies: ReplayDependencies,
  writeLine: LineWriter = console.log,
): Promise<ReplayResult> {
  const result = await runReplay(args, dependencies);
  writeReplayResult(result, writeLine);
  return result;
}

export function createReplayRuntime(
  args: readonly string[],
  env: NodeJS.ProcessEnv = process.env,
  runtimeOptions: ReplayRuntimeOptions = {},
): ReplayRuntime {
  const options = parseReplayOptions(args);
  const config = loadConfig({
    ...env,
    APP_ENV: "local",
    OUTBOUND_MODE: "off",
    MAIL_CUTOVER_NOT_BEFORE: "",
    SQLITE_PATH: options.databasePath,
    ARTIFACT_DIRECTORY: options.artifactDirectory,
  });
  const provider = runtimeOptions.provider ?? createAiProvider(config);
  const clock = runtimeOptions.clock ?? (() => new Date());
  const jobLeaseMs = runtimeOptions.jobLeaseMs ?? DEFAULT_JOB_LEASE_MS;

  if (options.databasePath !== ":memory:") {
    mkdirSync(dirname(resolve(options.databasePath)), { recursive: true });
  }
  const store = new SqliteStore(options.databasePath);
  try {
    const ingestion = new EventIngestionService(store);
    const artifacts = new ArtifactWriter(options.artifactDirectory, {
      publicOrigin: config.publicOrigin,
    });
    const pipeline = new AnalysisPipeline(
      store,
      profileRegistry,
      provider,
      artifacts,
      clock,
      OFF_OUTBOX_PLANNER,
    );
    const worker = new AnalysisWorker(
      store,
      pipeline,
      250,
      undefined,
      clock,
      jobLeaseMs,
    );
    let closed = false;

    return {
      dependencies: {
        profiles: profileRegistry,
        store,
        ingestion,
        worker,
        artifacts,
        readTextFile: (path) => readFile(path, "utf8"),
        clock,
        jobLeaseMs,
      },
      async close(): Promise<void> {
        if (closed) {
          return;
        }
        closed = true;
        let failed = false;
        try {
          provider.close();
        } catch {
          failed = true;
        }
        try {
          await worker.stop();
        } catch {
          failed = true;
        } finally {
          try {
            store.close();
          } catch {
            failed = true;
          }
        }
        if (failed) {
          throw new Error("replay_shutdown_failed");
        }
      },
    };
  } catch {
    provider.close();
    store.close();
    throw new Error("replay_initialization_failed");
  }
}

export async function replayMain(
  args: readonly string[] = process.argv.slice(2),
  env: NodeJS.ProcessEnv = process.env,
  writeLine: LineWriter = console.log,
  writeError: LineWriter = console.error,
): Promise<number> {
  let runtime: ReplayRuntime | null = null;
  let exitCode = 0;
  try {
    const prepared = await prepareReplay(args, {
      profiles: profileRegistry,
      readTextFile: (path) => readFile(path, "utf8"),
    });
    runtime = createReplayRuntime(args, env);
    const result = await runPreparedReplay(prepared, runtime.dependencies);
    writeReplayResult(result, writeLine);
    if (result.status === "failed" || result.status === "active") {
      exitCode = 1;
    }
  } catch {
    writeError("replay_failed");
    exitCode = 1;
  }

  if (runtime) {
    try {
      await runtime.close();
    } catch {
      writeError("replay_shutdown_failed");
      exitCode = 1;
    }
  }
  return exitCode;
}

function writeReplayResult(result: ReplayResult, writeLine: LineWriter): void {
  writeLine(
    JSON.stringify({
      status: result.status,
      callId: result.callId,
      jobId: result.jobId,
      files: result.files,
    }),
  );
}

function parseReplayOptions(args: readonly string[]): ReplayOptions {
  let profile: string | null = null;
  let filePath: string | null = null;
  let wait = false;
  let databasePath = DEFAULT_DATABASE_PATH;
  let artifactDirectory = DEFAULT_ARTIFACT_DIRECTORY;
  const seen = new Set<string>();

  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index]!;
    if (seen.has(argument)) {
      throw new Error("invalid_arguments");
    }
    switch (argument) {
      case "--profile":
        seen.add(argument);
        profile = readOptionValue(args, ++index);
        break;
      case "--file":
        seen.add(argument);
        filePath = readOptionValue(args, ++index);
        break;
      case "--wait":
        seen.add(argument);
        wait = true;
        break;
      case "--database":
        seen.add(argument);
        databasePath = readOptionValue(args, ++index);
        break;
      case "--artifacts":
        seen.add(argument);
        artifactDirectory = readOptionValue(args, ++index);
        break;
      default:
        throw new Error("invalid_arguments");
    }
  }

  if (profile === null || filePath === null) {
    throw new Error("invalid_arguments");
  }
  return { profile, filePath, wait, databasePath, artifactDirectory };
}

function readOptionValue(args: readonly string[], index: number): string {
  const value = args[index];
  if (!value || value.startsWith("--")) {
    throw new Error("invalid_arguments");
  }
  return value;
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return (
    entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href
  );
}

if (isEntrypoint()) {
  void replayMain().then((exitCode) => {
    process.exitCode = exitCode;
  });
}
