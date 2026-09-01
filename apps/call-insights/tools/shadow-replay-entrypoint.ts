import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createAiProvider, type AiProvider } from "../src/ai/provider.js";
import { AnalysisPipeline } from "../src/application/analysis-pipeline.js";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import { normalizeVapiEvent } from "../src/application/normalize-vapi-event.js";
import { assertPublicOrigin } from "../src/domain/public-origin.js";
import {
  fetchVapiCallJson,
  listVapiCalls,
} from "../src/integrations/vapi-client.js";
import { OutboxPlanner } from "../src/outbound/outbox-planner.js";
import { profileRegistry } from "../src/profiles/profiles.js";
import { ArtifactWriter } from "../src/reports/artifact-writer.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import { AnalysisWorker } from "../src/worker/analysis-worker.js";
import {
  runShadowReplay,
  type ShadowReplayResult,
  type ShadowReplayDependencies,
} from "./shadow-replay.js";

type LineWriter = (line: string) => void;

export interface ShadowReplayRuntime {
  workRoot: string;
  dependencies: ShadowReplayDependencies;
  close(): Promise<void>;
}

export interface ShadowReplayRuntimeOptions {
  provider?: AiProvider;
  createProvider?: typeof createAiProvider;
  vapiFetch?: typeof fetch;
  clock?: () => Date;
}

export type ShadowReplayRuntimeFactory = (
  env: NodeJS.ProcessEnv,
) => ShadowReplayRuntime;

export function createShadowReplayRuntime(
  env: NodeJS.ProcessEnv = process.env,
  runtimeOptions: ShadowReplayRuntimeOptions = {},
): ShadowReplayRuntime {
  const vapiApiKey = env.VAPI_API_KEY?.trim();
  const deepseekApiKey = env.DEEPSEEK_API_KEY?.trim();
  const publicOrigin = assertPublicOrigin(env.PUBLIC_ORIGIN?.trim() || "");
  if (!vapiApiKey || !deepseekApiKey) {
    throw new Error("shadow_replay_configuration_invalid");
  }

  const workRoot = mkdtempSync(join(tmpdir(), "vapi-shadow-replay-"));
  const clock = runtimeOptions.clock ?? (() => new Date());
  const vapiFetch = runtimeOptions.vapiFetch ?? fetch;
  let store: SqliteStore | null = null;
  let provider: AiProvider | null = null;
  let worker: AnalysisWorker | null = null;
  try {
    store = new SqliteStore(join(workRoot, "shadow.sqlite"));
    provider = runtimeOptions.provider ??
      (runtimeOptions.createProvider ?? createAiProvider)({
        aiProvider: "deepseek",
        deepseekApiKey,
      });
    const activeStore = store;
    const activeProvider = provider;
    const ingestion = new EventIngestionService(store);
    const artifacts = new ArtifactWriter(join(workRoot, "artifacts"), {
      publicOrigin,
    });
    const pipeline = new AnalysisPipeline(
      store,
      profileRegistry,
      provider,
      artifacts,
      clock,
      new OutboxPlanner(store, {
        mode: "shadow",
        cutoverNotBefore: null,
      }),
    );
    worker = new AnalysisWorker(store, pipeline, 250, undefined, clock);
    let closed = false;

    return {
      workRoot,
      dependencies: {
        listCalls: (assistantId, limit, createdAtLt) =>
          listVapiCalls(
            vapiApiKey,
            assistantId,
            limit,
            vapiFetch,
            createdAtLt,
          ),
        fetchCall: (callId) =>
          fetchVapiCallJson(callId, vapiApiKey, vapiFetch),
        async processEnvelope(profileSlug, envelope) {
          const profile = profileRegistry.get(profileSlug);
          if (!profile) {
            throw new Error("shadow_replay_failed");
          }
          const event = normalizeVapiEvent(profile, envelope, clock());
          const result = ingestion.ingest(event);
          if (
            result.status !== "accepted" ||
            result.jobId === null ||
            result.callId === null
          ) {
            throw new Error("shadow_replay_failed");
          }
          while (activeStore.getJob(result.jobId)?.status === "pending") {
            if (await worker!.runOnce() !== true) {
              throw new Error("shadow_replay_failed");
            }
          }
          if (
            activeStore.getJob(result.jobId)?.status !== "succeeded" ||
            activeStore.listMail(profileSlug, result.callId).length !== 2 ||
            !activeStore.listMail(profileSlug, result.callId)
              .every((mail) => mail.status === "suppressed")
          ) {
            throw new Error("shadow_replay_failed");
          }
        },
        countSuppressedMail: () =>
          activeStore.countMailByStatus("suppressed"),
      },
      async close(): Promise<void> {
        if (closed) {
          return;
        }
        closed = true;
        let failed = false;
        try {
          activeProvider.close();
        } catch {
          failed = true;
        }
        try {
          await worker!.stop();
        } catch {
          failed = true;
        }
        try {
          activeStore.close();
        } catch {
          failed = true;
        }
        try {
          rmSync(workRoot, { recursive: true, force: true });
        } catch {
          failed = true;
        }
        if (failed) {
          throw new Error("shadow_replay_shutdown_failed");
        }
      },
    };
  } catch {
    provider?.close();
    void worker?.stop();
    store?.close();
    rmSync(workRoot, { recursive: true, force: true });
    throw new Error("shadow_replay_initialization_failed");
  }
}

export async function shadowReplayMain(
  args: readonly string[] = process.argv.slice(2),
  env: NodeJS.ProcessEnv = process.env,
  writeLine: LineWriter = console.log,
  writeError: LineWriter = console.error,
  runtimeFactory: ShadowReplayRuntimeFactory =
    (runtimeEnv) => createShadowReplayRuntime(runtimeEnv),
): Promise<number> {
  let runtime: ShadowReplayRuntime | null = null;
  let result: ShadowReplayResult | null = null;
  let exitCode = 0;
  try {
    runtime = runtimeFactory(env);
    result = await runShadowReplay(args, runtime.dependencies);
  } catch {
    writeError("shadow_replay_failed");
    exitCode = 1;
  }
  if (runtime) {
    try {
      await runtime.close();
    } catch {
      writeError("shadow_replay_shutdown_failed");
      exitCode = 1;
    }
  }
  if (exitCode === 0 && result !== null) {
    writeLine(JSON.stringify(result));
  }
  return exitCode;
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isEntrypoint()) {
  void shadowReplayMain().then((exitCode) => {
    process.exitCode = exitCode;
  });
}
