import type { Call, CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import type { AppConfig } from "../config.js";
import { MockAiProvider } from "./mock-provider.js";
import { DeepSeekAiProvider, type FetchLike } from "./deepseek-provider.js";

export type { FetchLike };

export interface CallAnalysisInput {
  call: Call;
  profile: ClientProfile;
}

export interface QualityAnalysisInput {
  call: Call;
  profile: ClientProfile;
}

export class AiProviderShutdownError extends Error {
  readonly code = "AI_PROVIDER_SHUTDOWN";

  constructor() {
    super("AI provider shutdown cancelled active work");
    this.name = "AiProviderShutdownError";
  }
}

export interface AiProvider {
  readonly name: "mock" | "deepseek";
  analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis>;
  analyzeQuality(input: QualityAnalysisInput): Promise<QualityAnalysis>;
  close(): void;
}

export type AiProviderDependencies = {
  fetchFn?: FetchLike;
  delay?: (milliseconds: number) => Promise<void>;
};

export function createAiProvider(
  config: Pick<AppConfig, "aiProvider" | "deepseekApiKey">,
  dependencies: AiProviderDependencies = {},
): AiProvider {
  if (config.aiProvider !== "deepseek") {
    return new MockAiProvider();
  }
  if (!config.deepseekApiKey) {
    throw new Error("DEEPSEEK_API_KEY is required when AI_PROVIDER=deepseek");
  }
  const options: ConstructorParameters<typeof DeepSeekAiProvider>[0] = {
    apiKey: config.deepseekApiKey,
  };
  if (dependencies.fetchFn) {
    options.fetchFn = dependencies.fetchFn;
  }
  if (dependencies.delay) {
    options.delay = dependencies.delay;
  }
  return new DeepSeekAiProvider(options);
}
