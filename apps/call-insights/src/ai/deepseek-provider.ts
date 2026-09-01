import { CallAnalysisSchema, QualityAnalysisSchema } from "../domain/schemas.js";
import type { Call, CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import { flattenContactInfo } from "./flatten-contact-info.js";
import {
  AiProviderShutdownError,
  type AiProvider,
  type CallAnalysisInput,
  type QualityAnalysisInput,
} from "./provider.js";

const DEEPSEEK_URL = "https://api.deepseek.com/chat/completions";
const DEEPSEEK_MODEL = "deepseek-chat";
const MAX_ATTEMPTS = 4;
const RETRY_DELAYS_MS = [1000, 2000, 4000] as const;
export const DEEPSEEK_REQUEST_TIMEOUT_MS = 60_000;

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export type DeepSeekProviderOptions = {
  apiKey: string;
  fetchFn?: FetchLike;
  delay?: (milliseconds: number) => Promise<void>;
  requestTimeoutMs?: number;
};

type ChatCompletionPayload = {
  choices?: Array<{
    message?: {
      content?: string;
    };
  }>;
};

export class DeepSeekAiProvider implements AiProvider {
  readonly name = "deepseek" as const;
  private readonly apiKey: string;
  private readonly fetchFn: FetchLike;
  private readonly delay: (milliseconds: number) => Promise<void>;
  private readonly requestTimeoutMs: number;
  private readonly activeRequests = new Set<AbortController>();
  private closed = false;

  constructor(options: DeepSeekProviderOptions) {
    this.apiKey = options.apiKey;
    this.fetchFn = options.fetchFn ?? ((input, init) => fetch(input, init));
    this.delay = options.delay ?? ((milliseconds) =>
      new Promise((resolve) => {
        setTimeout(resolve, milliseconds);
      }));
    this.requestTimeoutMs = options.requestTimeoutMs ?? DEEPSEEK_REQUEST_TIMEOUT_MS;
    if (
      !Number.isSafeInteger(this.requestTimeoutMs) ||
      this.requestTimeoutMs <= 0
    ) {
      throw new Error("DeepSeek request timeout must be a positive integer");
    }
  }

  async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    const analysis = await this.complete(
      input,
      "call",
      CallAnalysisSchema,
      buildCallAnalysisSystemPrompt(input.profile),
    );
    return {
      ...analysis,
      localCallTime: formatLocalCallTime(
        input.call.startedAt,
        input.profile.timezone,
      ),
    };
  }

  async analyzeQuality(input: QualityAnalysisInput): Promise<QualityAnalysis> {
    return this.complete(input, "quality", QualityAnalysisSchema, buildQualitySystemPrompt(input.profile));
  }

  close(): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    for (const controller of this.activeRequests) {
      controller.abort(new AiProviderShutdownError());
    }
  }

  private async complete<T>(
    input: { call: Call; profile: ClientProfile },
    kind: "call" | "quality",
    schema: { parse(data: unknown): T },
    systemPrompt: string,
  ): Promise<T> {
    let lastRetryable: Error | null = null;
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      this.assertOpen();
      const controller = new AbortController();
      this.activeRequests.add(controller);
      const deadline = setTimeout(() => {
        controller.abort(
          new Error(
            `DeepSeek request timed out after ${this.requestTimeoutMs}ms`,
          ),
        );
      }, this.requestTimeoutMs);
      let retryDelay: number | null = null;
      try {
        const response = await this.fetchFn(
          DEEPSEEK_URL,
          this.buildRequestInit(input.call, systemPrompt, controller.signal),
        );
        if (isRetryableStatus(response.status)) {
          lastRetryable = new Error(`DeepSeek HTTP ${response.status}`);
          if (attempt === MAX_ATTEMPTS) {
            this.fail(lastRetryable);
          }
          retryDelay = RETRY_DELAYS_MS[attempt - 1] ?? 4000;
        } else if (!response.ok) {
          const text = await response.text();
          this.fail(new Error(`DeepSeek HTTP ${response.status}: ${text}`));
        } else {
          return await this.parseResponse(response, kind, schema);
        }
      } catch (error) {
        if (
          controller.signal.aborted &&
          controller.signal.reason instanceof AiProviderShutdownError
        ) {
          throw controller.signal.reason;
        }
        this.fail(error);
      } finally {
        clearTimeout(deadline);
        this.activeRequests.delete(controller);
      }

      if (retryDelay !== null) {
        await this.delay(retryDelay);
        this.assertOpen();
      }
    }

    this.fail(lastRetryable ?? new Error(`Invalid ${kind} analysis: exhausted retries`));
  }

  private async parseResponse<T>(
    response: Response,
    kind: "call" | "quality",
    schema: { parse(data: unknown): T },
  ): Promise<T> {
    let payload: ChatCompletionPayload;
    try {
      payload = (await response.json()) as ChatCompletionPayload;
    } catch (error) {
      throw new Error(`Invalid ${kind} analysis: ${stringifyError(error)}`);
    }
    const content = payload.choices?.[0]?.message?.content;
    if (typeof content !== "string" || content.trim().length === 0) {
      throw new Error(`Invalid ${kind} analysis: missing model content`);
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(stripMarkdownFence(content));
    } catch (error) {
      throw new Error(`Invalid ${kind} analysis: ${stringifyError(error)}`);
    }
    try {
      return schema.parse(kind === "call" ? coerceCallAnalysis(parsed) : parsed);
    } catch (error) {
      throw new Error(`Invalid ${kind} analysis: ${stringifyError(error)}`);
    }
  }

  private buildRequestInit(
    call: Call,
    systemPrompt: string,
    signal: AbortSignal,
  ): RequestInit {
    return {
      method: "POST",
      redirect: "error",
      signal,
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: DEEPSEEK_MODEL,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: buildUserPrompt(call) },
        ],
      }),
    };
  }

  private assertOpen(): void {
    if (this.closed) {
      throw new AiProviderShutdownError();
    }
  }

  private fail(error: unknown): never {
    if (error instanceof AiProviderShutdownError) {
      throw error;
    }
    throw new Error(this.redact(stringifyError(error)));
  }

  private redact(message: string): string {
    if (!this.apiKey) {
      return message;
    }
    return message.split(this.apiKey).join("[REDACTED]");
  }
}

function coerceCallAnalysis(parsed: unknown): unknown {
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return parsed;
  }
  return {
    ...parsed,
    contactInfo: flattenContactInfo(
      (parsed as { contactInfo?: unknown }).contactInfo,
    ),
  };
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || (status >= 500 && status <= 599);
}

function stripMarkdownFence(text: string): string {
  const trimmed = text.trim();
  const match = /^```(?:json)?\r?\n([\s\S]*?)\r?\n```$/.exec(trimmed);
  return match?.[1]?.trim() ?? trimmed;
}

function stringifyError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function buildCallAnalysisSystemPrompt(profile: ClientProfile): string {
  return [
    `You are producing a structured call analysis for ${profile.brandName}.`,
    `The voice assistant is named ${profile.assistantName}.`,
    `Treat these company aliases as the same company: ${profile.companyAliases.join(", ")}.`,
    `Write all output in ${profile.analysisLanguage}.`,
    `Convert the call time to ${profile.timezone}; localCallTime is overwritten deterministically after analysis.`,
    'Use exactly "Not mentioned" for any unknown customer name, contact detail, or topic.',
    "Normalize spoken email forms such as 'at' and 'dot' into a lowercase email address when the transcript clearly provides one.",
    `Format the transcript in dialogue order with one speaker per line, a blank line between turns, customer labels using the customer name when known, and assistant labels as "${profile.assistantName}:".`,
    "Do not add HTML or Markdown to the formatted transcript.",
    "Return JSON only with exactly these keys: customerName, contactInfo, mainTopics, formattedTranscript, localCallTime.",
    "mainTopics must be an array of strings. Do not add other keys.",
  ].join(" ");
}

function formatLocalCallTime(isoTimestamp: string, timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: timezone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(new Date(isoTimestamp));
  const get = (type: Intl.DateTimeFormatPartTypes): string => {
    const value = parts.find((part) => part.type === type)?.value;
    if (!value) {
      throw new Error("local call time formatting failed");
    }
    return value;
  };
  return `${get("hour")}:${get("minute")}${get("dayPeriod").toLowerCase()} ` +
    `${get("day")}/${get("month")}/${get("year")}`;
}

function buildQualitySystemPrompt(profile: ClientProfile): string {
  return [
    `You are scoring assistant quality for ${profile.brandName} (${profile.assistantName}).`,
    "Evaluate these criteria: response brevity, redundant confirmation, interruption, guidance, resolution efficiency, language adaptation.",
    `Write all output in ${profile.qualityLanguage}.`,
    "Return JSON only with exactly these keys: score, strengths, weaknesses, suggestions, shouldUpdatePrompt, summary.",
    "score must be a number from 0 to 10. strengths, weaknesses, and suggestions must be string arrays. shouldUpdatePrompt must be a boolean.",
    "If score is 8.5 or above, shouldUpdatePrompt must be false.",
  ].join(" ");
}

function buildUserPrompt(call: Call): string {
  return [
    "Transcript:",
    call.transcript,
    "",
    "Summary:",
    call.summary,
    "",
    `Started: ${call.startedAt}`,
    `Ended: ${call.endedAt}`,
    `Duration seconds: ${call.durationSeconds}`,
  ].join("\n");
}
