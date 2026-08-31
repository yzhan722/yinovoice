import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import type { FastifyInstance } from "fastify";
import { createAiProvider, type AiProvider } from "../ai/provider.js";
import { AnalysisPipeline } from "../application/analysis-pipeline.js";
import { EventIngestionService } from "../application/event-ingestion-service.js";
import { RatingService } from "../application/rating-service.js";
import { loadConfig, type AppConfig } from "../config.js";
import { fetchVapiCallJson, VapiCallFetchError } from "../integrations/vapi-client.js";
import { OutboxPlanner } from "../outbound/outbox-planner.js";
import { profileRegistry } from "../profiles/profiles.js";
import {
  CONFIG_POLL_INTERVAL_MS,
  RuntimeProfileSource,
} from "../profiles/runtime-config.js";
import { ArtifactWriter } from "../reports/artifact-writer.js";
import { SqliteStore } from "../storage/sqlite-store.js";
import { AnalysisWorker } from "../worker/analysis-worker.js";
import { buildApp } from "./app.js";

export interface ClosableRuntime {
  app: {
    close(): Promise<void>;
  };
  provider: Pick<AiProvider, "close">;
  worker: Pick<AnalysisWorker, "stop">;
  store: Pick<SqliteStore, "close">;
  stopConfig?: () => void;
}

interface ServerRuntime extends ClosableRuntime {
  app: FastifyInstance;
  provider: AiProvider;
  worker: AnalysisWorker;
  store: SqliteStore;
  config: AppConfig;
}

export type ShutdownSignal = "SIGINT" | "SIGTERM";

export interface SignalSource {
  on(signal: ShutdownSignal, listener: () => void): unknown;
  off(signal: ShutdownSignal, listener: () => void): unknown;
}

export interface SignalShutdownController {
  shutdown(): Promise<void>;
}

export async function closeRuntime(runtime: ClosableRuntime): Promise<void> {
  let failed = false;
  try {
    await runtime.app.close();
  } catch {
    failed = true;
  }
  try {
    runtime.provider.close();
  } catch {
    failed = true;
  }
  try {
    await runtime.worker.stop();
  } catch {
    failed = true;
  }
  try {
    runtime.stopConfig?.();
  } catch {
    failed = true;
  }
  try {
    runtime.store.close();
  } catch {
    failed = true;
  }
  if (failed) {
    throw new Error("shutdown_failed");
  }
}

export function installSignalShutdown(
  runtime: ClosableRuntime,
  signals: SignalSource = process,
  onFailure: () => void = reportShutdownFailure,
): SignalShutdownController {
  let shutdownPromise: Promise<void> | null = null;
  const removeSignalHandlers = (): void => {
    signals.off("SIGINT", handleSignal);
    signals.off("SIGTERM", handleSignal);
  };
  const shutdown = (): Promise<void> => {
    shutdownPromise ??= closeRuntime(runtime).finally(removeSignalHandlers);
    return shutdownPromise;
  };
  const handleSignal = (): void => {
    void shutdown().catch(onFailure);
  };

  signals.on("SIGINT", handleSignal);
  signals.on("SIGTERM", handleSignal);
  return { shutdown };
}

export function listenOptions(
  config: Pick<AppConfig, "host" | "port">,
): Pick<AppConfig, "host" | "port"> {
  return { host: config.host, port: config.port };
}

export async function serve(): Promise<void> {
  const runtime = await createRuntime();
  const shutdown = installSignalShutdown(runtime);

  try {
    await runtime.app.listen(listenOptions(runtime.config));
  } catch {
    await shutdown.shutdown().catch(() => undefined);
    throw new Error("server_start_failed");
  }
}

async function createRuntime(): Promise<ServerRuntime> {
  const config = loadConfig();
  if (config.sqlitePath !== ":memory:") {
    mkdirSync(dirname(resolve(config.sqlitePath)), { recursive: true });
  }
  const store = new SqliteStore(config.sqlitePath);
  let worker: AnalysisWorker | null = null;
  let provider: AiProvider | null = null;
  let stopConfig: (() => void) | undefined;
  try {
    const profileSource = config.profilesDirectory
      ? new RuntimeProfileSource({ directory: config.profilesDirectory })
      : null;
    if (profileSource && !await profileSource.load()) {
      throw new Error("server_initialization_failed");
    }
    if (profileSource) {
      const timer = setInterval(() => {
        void profileSource.load().catch(() => undefined);
      }, CONFIG_POLL_INTERVAL_MS);
      stopConfig = () => clearInterval(timer);
    }
    const profiles = profileSource?.registry ?? profileRegistry;
    const ingestion = new EventIngestionService(store);
    const rating = new RatingService(store);
    provider = createAiProvider(config);
    const pipeline = new AnalysisPipeline(
      store,
      profiles,
      provider,
      new ArtifactWriter(config.artifactDirectory, {
        publicOrigin: config.publicOrigin,
      }),
      () => new Date(),
      new OutboxPlanner(store, {
        mode: config.outboundMode,
        cutoverNotBefore: config.mailCutoverNotBefore,
      }),
    );
    worker = new AnalysisWorker(store, pipeline);
    worker.start();
    const app = buildApp({
      profiles,
      ingestion,
      rating,
      store,
      worker,
      webhookAuth: {
        required: config.webhookAuthRequired,
        token: config.webhookAuthToken,
      },
      ingestAuth: {
        required: true,
        token: config.ingestAuthToken,
      },
      mailExpected: config.outboundMode === "live",
      ...(profileSource ? { configHealth: profileSource } : {}),
      recordingRedirect: {
        apiKey: config.vapiApiKey,
        fetchCall: async (callId) => {
          if (!config.vapiApiKey) {
            throw new VapiCallFetchError();
          }
          return fetchVapiCallJson(callId, config.vapiApiKey);
        },
      },
    });
    return {
      app,
      provider,
      worker,
      store,
      config,
      ...(stopConfig ? { stopConfig } : {}),
    };
  } catch {
    stopConfig?.();
    provider?.close();
    await worker?.stop().catch(() => undefined);
    store.close();
    throw new Error("server_initialization_failed");
  }
}

function reportShutdownFailure(): void {
  process.exitCode = 1;
  console.error("server_shutdown_failed");
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isEntrypoint()) {
  void serve().catch(() => {
    process.exitCode = 1;
    console.error("server_start_failed");
  });
}
