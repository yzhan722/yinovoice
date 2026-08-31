import { assertPublicOrigin, DEFAULT_PUBLIC_ORIGIN } from "./domain/public-origin.js";
import type { OutboundMode } from "./outbound/outbox-planner.js";

export type AiProviderName = "mock" | "deepseek";
export type AppEnvironment = "local" | "production";

export type AppConfig = {
  appEnvironment: AppEnvironment;
  host: "127.0.0.1" | "0.0.0.0";
  port: 3210;
  publicOrigin: string;
  vapiApiKey: string | null;
  webhookAuthRequired: boolean;
  webhookAuthToken: string | null;
  ingestAuthToken: string | null;
  outboundMode: OutboundMode;
  mailCutoverNotBefore: string | null;
  aiProvider: AiProviderName;
  deepseekApiKey: string | null;
  sqlitePath: string;
  artifactDirectory: string;
  profilesDirectory: string | null;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const appEnvironment = parseAppEnvironment(env.APP_ENV);
  const aiProvider = parseAiProvider(env.AI_PROVIDER);
  const deepseekApiKey = env.DEEPSEEK_API_KEY ? env.DEEPSEEK_API_KEY : null;
  if (aiProvider === "deepseek" && !deepseekApiKey) {
    throw new Error("DEEPSEEK_API_KEY is required when AI_PROVIDER=deepseek");
  }
  const vapiApiKey = env.VAPI_API_KEY?.trim() ? env.VAPI_API_KEY.trim() : null;
  const webhookAuthRequired = parseRequiredBoolean(
    env.WEBHOOK_AUTH_REQUIRED,
    "WEBHOOK_AUTH_REQUIRED",
  );
  const webhookAuthToken = env.WEBHOOK_AUTH_TOKEN?.trim()
    ? env.WEBHOOK_AUTH_TOKEN.trim()
    : null;
  if (webhookAuthRequired && !webhookAuthToken) {
    throw new Error("WEBHOOK_AUTH_TOKEN is required when WEBHOOK_AUTH_REQUIRED=true");
  }
  const outboundMode = parseOutboundMode(env.OUTBOUND_MODE);
  const mailCutoverNotBefore = parseMailCutover(env.MAIL_CUTOVER_NOT_BEFORE);
  const publicOrigin = assertPublicOrigin(
    env.PUBLIC_ORIGIN?.trim() || DEFAULT_PUBLIC_ORIGIN,
  );
  if (outboundMode === "live" && !mailCutoverNotBefore) {
    throw new Error(
      "MAIL_CUTOVER_NOT_BEFORE is required when OUTBOUND_MODE=live",
    );
  }
  if (
    outboundMode === "live" &&
    (!webhookAuthRequired || aiProvider !== "deepseek")
  ) {
    throw new Error(
      "live outbound requires WEBHOOK_AUTH_REQUIRED=true and AI_PROVIDER=deepseek",
    );
  }
  if (appEnvironment === "production") {
    if (
      !publicOrigin.startsWith("https://") ||
      !vapiApiKey ||
      aiProvider !== "deepseek" ||
      !webhookAuthRequired ||
      !webhookAuthToken ||
      webhookAuthToken.length < 32
    ) {
      throw new Error(
        "production requires HTTPS, VAPI/DeepSeek keys, and WEBHOOK_AUTH_REQUIRED=true with a strong token",
      );
    }
  }
  return {
    appEnvironment,
    host: env.LISTEN_HOST?.trim() === "0.0.0.0" ? "0.0.0.0" : "127.0.0.1",
    port: 3210,
    publicOrigin,
    vapiApiKey,
    webhookAuthRequired,
    webhookAuthToken,
    ingestAuthToken: env.INGEST_AUTH_TOKEN?.trim()
      ? env.INGEST_AUTH_TOKEN.trim()
      : null,
    outboundMode,
    mailCutoverNotBefore,
    aiProvider,
    deepseekApiKey,
    sqlitePath: env.SQLITE_PATH || "data/vapi-call-insights.sqlite",
    artifactDirectory: env.ARTIFACT_DIRECTORY || "artifacts",
    profilesDirectory: env.PROFILES_DIRECTORY?.trim() || null,
  };
}

function parseAppEnvironment(value: string | undefined): AppEnvironment {
  const normalized = value?.trim() || "local";
  if (normalized !== "local" && normalized !== "production") {
    throw new Error("APP_ENV must be local or production");
  }
  return normalized;
}

function parseAiProvider(value: string | undefined): AiProviderName {
  const normalized = value?.trim() || "mock";
  if (normalized !== "mock" && normalized !== "deepseek") {
    throw new Error("AI_PROVIDER must be mock or deepseek");
  }
  return normalized;
}

function parseRequiredBoolean(
  value: string | undefined,
  name: string,
): boolean {
  const normalized = value?.trim();
  if (!normalized) {
    return false;
  }
  if (normalized !== "true" && normalized !== "false") {
    throw new Error(`${name} must be true or false`);
  }
  return normalized === "true";
}

function parseOutboundMode(value: string | undefined): OutboundMode {
  const normalized = value?.trim() || "off";
  if (
    normalized !== "off" &&
    normalized !== "shadow" &&
    normalized !== "live"
  ) {
    throw new Error("OUTBOUND_MODE must be off, shadow, or live");
  }
  return normalized;
}

function parseMailCutover(value: string | undefined): string | null {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(normalized) ||
    !Number.isFinite(Date.parse(normalized)) ||
    new Date(Date.parse(normalized)).toISOString() !== normalized
  ) {
    throw new Error(
      "MAIL_CUTOVER_NOT_BEFORE must be an exact UTC timestamp",
    );
  }
  return normalized;
}
