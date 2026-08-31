import { afterEach, describe, expect, it, vi } from "vitest";
import { MockAiProvider } from "../src/ai/mock-provider.js";
import { DeepSeekAiProvider } from "../src/ai/deepseek-provider.js";
import { createAiProvider } from "../src/ai/provider.js";
import { loadConfig } from "../src/config.js";
import { makeCall, lucaplusProfile } from "./fixtures.js";

const DEEPSEEK_URL = "https://api.deepseek.com/chat/completions";

const validCallAnalysis = {
  customerName: "Demo Customer",
  contactInfo: "demo@example.invalid",
  mainTopics: ["invoice automation"],
  formattedTranscript: "Customer: Demo request",
  localCallTime: "11:00am 13/08/2026",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function completionResponse(content: string, status = 200): Response {
  return jsonResponse({ choices: [{ message: { content } }] }, status);
}

function unusedDelay() {
  return vi.fn(async () => {
    throw new Error("delay should not run");
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("AI providers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses deterministic offline results without fetch", async () => {
    const fetchFn = vi.fn(() => {
      throw new Error("network forbidden");
    });
    vi.stubGlobal("fetch", fetchFn);
    const provider = new MockAiProvider();
    const call = makeCall();
    const first = await provider.analyzeCall({ call, profile: lucaplusProfile });
    const second = await provider.analyzeCall({ call, profile: lucaplusProfile });
    expect(second).toEqual(first);
    expect(first.customerName).toBe("Demo Customer");
    expect(first.contactInfo).toBe("demo@example.invalid");
    expect(first.mainTopics).toEqual(["invoice automation"]);
    expect(first.formattedTranscript).toBe(call.transcript);
    expect(provider.name).toBe("mock");
    expect(fetchFn).not.toHaveBeenCalled();

    const firstQuality = await provider.analyzeQuality({ call, profile: lucaplusProfile });
    const secondQuality = await provider.analyzeQuality({ call, profile: lucaplusProfile });
    expect(secondQuality).toEqual(firstQuality);
    expect(firstQuality.score).toBe(8);
    expect(firstQuality.strengths).toHaveLength(1);
    expect(firstQuality.weaknesses).toHaveLength(1);
    expect(firstQuality.suggestions).toHaveLength(1);
    expect(firstQuality.shouldUpdatePrompt).toBe(true);
    expect(firstQuality.summary.length).toBeGreaterThan(0);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("coerces object contactInfo to a string before schema validation", async () => {
    const delay = unusedDelay();
    const fetchFn = vi.fn(async () => completionResponse(JSON.stringify({
      ...validCallAnalysis,
      contactInfo: {
        email: "demo@example.invalid",
        phone: "0400000000",
      },
    })));
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    const result = await provider.analyzeCall({
      call: makeCall(),
      profile: lucaplusProfile,
    });
    expect(result.contactInfo).toBe("email: demo@example.invalid; phone: 0400000000");
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(delay).not.toHaveBeenCalled();
  });

  it("calls only the fixed DeepSeek endpoint and validates JSON", async () => {
    const delay = unusedDelay();
    const fetchFn = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe(DEEPSEEK_URL);
      expect(init?.method).toBe("POST");
      expect(init?.redirect).toBe("error");
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      const headers = new Headers(init?.headers);
      expect(headers.get("authorization")).toBe("Bearer test-key");
      const body = JSON.parse(String(init?.body));
      expect(body.model).toBe("deepseek-chat");
      expect(body.response_format).toEqual({ type: "json_object" });
      expect(body.messages[0].role).toBe("system");
      expect(body.messages[0].content).toContain("LucaPlus");
      expect(body.messages[0].content).toContain("Luca AI");
      expect(body.messages[0].content).toContain("Luca Plus");
      expect(body.messages[0].content).toMatch(/\ben\b/);
      expect(body.messages[0].content).toContain("Australia/Sydney");
      expect(body.messages[0].content).toContain("Not mentioned");
      expect(body.messages[0].content).toMatch(/spoken email/i);
      expect(body.messages[0].content).toContain("Luca AI:");
      return completionResponse(JSON.stringify(validCallAnalysis));
    });
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    const result = await provider.analyzeCall({ call: makeCall(), profile: lucaplusProfile });
    expect(result).toEqual(validCallAnalysis);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(delay).not.toHaveBeenCalled();
    expect(provider.name).toBe("deepseek");
  });

  it("aborts a request when its per-attempt deadline expires", async () => {
    vi.useFakeTimers();
    try {
      let requestSignal: AbortSignal | null = null;
      const fetchFn = vi.fn((_url: string, init?: RequestInit) => {
        if (!(init?.signal instanceof AbortSignal)) {
          return Promise.reject(new Error("missing bounded request signal"));
        }
        requestSignal = init.signal;
        return new Promise<Response>((_resolve, reject) => {
          init.signal!.addEventListener(
            "abort",
            () => reject(init.signal!.reason),
            { once: true },
          );
        });
      });
      const provider = new DeepSeekAiProvider({
        apiKey: "test-key",
        fetchFn,
        delay: unusedDelay(),
        requestTimeoutMs: 50,
      });

      const operation = provider.analyzeCall({
        call: makeCall(),
        profile: lucaplusProfile,
      });
      const outcome = operation.catch((error: unknown) => error);
      await vi.advanceTimersByTimeAsync(50);
      const error = await outcome;

      expect(error).toBeInstanceOf(Error);
      expect((error as Error).message).toMatch(/timed out/i);
      expect((error as Error).constructor.name).not.toBe(
        "AiProviderShutdownError",
      );
      expect(requestSignal).not.toBeNull();
      expect(requestSignal!.aborted).toBe(true);
      expect(fetchFn).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("close aborts an in-flight request without waiting for its deadline", async () => {
    const fetchStarted = deferred<void>();
    let requestSignal: AbortSignal | null = null;
    const fetchFn = vi.fn((_url: string, init?: RequestInit) => {
      if (!(init?.signal instanceof AbortSignal)) {
        return Promise.reject(new Error("missing cancellable request signal"));
      }
      requestSignal = init.signal;
      fetchStarted.resolve();
      return new Promise<Response>((_resolve, reject) => {
        init.signal!.addEventListener(
          "abort",
          () => reject(init.signal!.reason),
          { once: true },
        );
      });
    });
    const provider = new DeepSeekAiProvider({
      apiKey: "test-key",
      fetchFn,
      delay: unusedDelay(),
      requestTimeoutMs: 60_000,
    });
    const close = (provider as DeepSeekAiProvider & { close?: () => void }).close;
    expect(close).toBeTypeOf("function");

    const operation = provider.analyzeCall({
      call: makeCall(),
      profile: lucaplusProfile,
    });
    await fetchStarted.promise;
    close!.call(provider);

    const error = await operation.catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).constructor.name).toBe(
      "AiProviderShutdownError",
    );
    expect((error as Error).message).toMatch(/shutdown|closed/i);
    expect(requestSignal).not.toBeNull();
    expect(requestSignal!.aborted).toBe(true);
  });

  it("rejects malformed model output without retry", async () => {
    const delay = unusedDelay();
    const fetchFn = vi.fn(async (_url: string, init?: RequestInit) =>
      completionResponse("{}"),
    );
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    await expect(provider.analyzeQuality({ call: makeCall(), profile: lucaplusProfile }))
      .rejects.toThrow(/quality/i);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(delay).not.toHaveBeenCalled();
    const body = JSON.parse(String(fetchFn.mock.calls[0]?.[1]?.body));
    expect(body.messages[0].content).toMatch(/response brevity/i);
    expect(body.messages[0].content).toMatch(/redundant confirmation/i);
    expect(body.messages[0].content).toMatch(/interruption/i);
    expect(body.messages[0].content).toMatch(/guidance/i);
    expect(body.messages[0].content).toMatch(/resolution efficiency/i);
    expect(body.messages[0].content).toMatch(/language adaptation/i);
  });

  it("retries 503 then 429 with injected delays 1000 and 2000", async () => {
    const delays: number[] = [];
    const requestSignals: AbortSignal[] = [];
    const delay = vi.fn(async (milliseconds: number) => {
      delays.push(milliseconds);
    });
    const responses = [
      new Response("unavailable", { status: 503 }),
      new Response("slow down", { status: 429 }),
      completionResponse(JSON.stringify(validCallAnalysis)),
    ];
    const fetchFn = vi.fn(async (_url: string, init?: RequestInit) => {
      if (!(init?.signal instanceof AbortSignal)) {
        throw new Error("missing bounded request signal");
      }
      requestSignals.push(init.signal);
      return responses.shift()!;
    });
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    const result = await provider.analyzeCall({ call: makeCall(), profile: lucaplusProfile });
    expect(result.customerName).toBe("Demo Customer");
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(delays).toEqual([1000, 2000]);
    expect(fetchFn.mock.calls.every(([url]) => url === DEEPSEEK_URL)).toBe(true);
    expect(new Set(requestSignals).size).toBe(3);
  });

  it("redacts the API key from surfaced errors", async () => {
    const delay = unusedDelay();
    const fetchFn = vi.fn(async () => {
      throw new Error("upstream failed for key test-key");
    });
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    await expect(provider.analyzeCall({ call: makeCall(), profile: lucaplusProfile }))
      .rejects.toSatisfy((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        return message.includes("[REDACTED]") && !message.includes("test-key");
      });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(delay).not.toHaveBeenCalled();
  });

  it("strips a single enclosing Markdown JSON fence", async () => {
    const delay = unusedDelay();
    const fenced = `\`\`\`json\n${JSON.stringify(validCallAnalysis)}\n\`\`\``;
    const fetchFn = vi.fn(async () => completionResponse(fenced));
    const provider = new DeepSeekAiProvider({ apiKey: "test-key", fetchFn, delay });
    const result = await provider.analyzeCall({ call: makeCall(), profile: lucaplusProfile });
    expect(result).toEqual(validCallAnalysis);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("defaults to Mock and refuses DeepSeek without a key", () => {
    const mock = createAiProvider({ aiProvider: "mock", deepseekApiKey: null });
    expect(mock).toBeInstanceOf(MockAiProvider);
    expect(mock.name).toBe("mock");
    expect(() => createAiProvider({ aiProvider: "deepseek", deepseekApiKey: null }))
      .toThrow(/DEEPSEEK_API_KEY/);
    const fetchFn = vi.fn(async () => {
      throw new Error("network forbidden");
    });
    const deepseek = createAiProvider(
      { aiProvider: "deepseek", deepseekApiKey: "test-key" },
      { fetchFn, delay: unusedDelay() },
    );
    expect(deepseek).toBeInstanceOf(DeepSeekAiProvider);
    expect(deepseek.name).toBe("deepseek");
  });

  it("loadConfig defaults to mock localhost and ignores public hosts", () => {
    const config = loadConfig({ HOST: "0.0.0.0" });
    expect(config.host).toBe("127.0.0.1");
    expect(config.port).toBe(3210);
    expect(config.publicOrigin).toBe("http://127.0.0.1:3210");
    expect(config.vapiApiKey).toBeNull();
    expect(config.webhookAuthRequired).toBe(false);
    expect(config.webhookAuthToken).toBeNull();
    expect(config.ingestAuthToken).toBeNull();
    expect(config.outboundMode).toBe("off");
    expect(config.mailCutoverNotBefore).toBeNull();
    expect(config.aiProvider).toBe("mock");
    expect(config.profilesDirectory).toBeNull();
    expect(loadConfig({
      PROFILES_DIRECTORY: " /etc/vapi-call-insights/profiles ",
    }).profilesDirectory).toBe("/etc/vapi-call-insights/profiles");
    expect(loadConfig({ LISTEN_HOST: "0.0.0.0" }).host).toBe("0.0.0.0");
    expect(loadConfig({ PUBLIC_ORIGIN: "https://calls.example.invalid" }).publicOrigin)
      .toBe("https://calls.example.invalid");
    expect(() => loadConfig({ PUBLIC_ORIGIN: "https://x.n8n.cloud" })).toThrow(/n8n\.cloud/);
    expect(loadConfig({ VAPI_API_KEY: "vapi-test-key" }).vapiApiKey).toBe("vapi-test-key");
    expect(loadConfig({
      WEBHOOK_AUTH_REQUIRED: "true",
      WEBHOOK_AUTH_TOKEN: " webhook-test-token ",
    })).toMatchObject({
      webhookAuthRequired: true,
      webhookAuthToken: "webhook-test-token",
    });
    expect(() => loadConfig({ WEBHOOK_AUTH_REQUIRED: "true" }))
      .toThrow(/WEBHOOK_AUTH_TOKEN/);
    expect(() => loadConfig({ WEBHOOK_AUTH_REQUIRED: "tru" }))
      .toThrow(/WEBHOOK_AUTH_REQUIRED/);
    expect(() => loadConfig({ AI_PROVIDER: "openai" }))
      .toThrow(/AI_PROVIDER/);
    expect(loadConfig({ OUTBOUND_MODE: "shadow" })).toMatchObject({
      outboundMode: "shadow",
      mailCutoverNotBefore: null,
    });
    expect(loadConfig({
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-17T00:00:00.000Z",
      AI_PROVIDER: "deepseek",
      DEEPSEEK_API_KEY: "test-key",
      WEBHOOK_AUTH_REQUIRED: "true",
      WEBHOOK_AUTH_TOKEN: "test-token",
    })).toMatchObject({
      outboundMode: "live",
      mailCutoverNotBefore: "2026-08-17T00:00:00.000Z",
    });
    expect(() => loadConfig({ OUTBOUND_MODE: "live" }))
      .toThrow(/MAIL_CUTOVER_NOT_BEFORE/);
    expect(() => loadConfig({
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-17",
    })).toThrow(/MAIL_CUTOVER_NOT_BEFORE/);
    expect(() => loadConfig({
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-02-30T00:00:00.000Z",
    })).toThrow(/MAIL_CUTOVER_NOT_BEFORE/);
    expect(() => loadConfig({ OUTBOUND_MODE: "invalid" }))
      .toThrow(/OUTBOUND_MODE/);
    expect(() => loadConfig({ AI_PROVIDER: "deepseek" })).toThrow(/DEEPSEEK_API_KEY/);
    expect(loadConfig({ AI_PROVIDER: "deepseek", DEEPSEEK_API_KEY: "test-key" }).aiProvider)
      .toBe("deepseek");
    expect(() => loadConfig({
      APP_ENV: "production",
      PUBLIC_ORIGIN: "https://calls.yino.au",
      AI_PROVIDER: "deepseek",
      DEEPSEEK_API_KEY: "test-key",
    })).toThrow(/WEBHOOK_AUTH/);
    expect(() => loadConfig({
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-17T00:00:00.000Z",
      WEBHOOK_AUTH_REQUIRED: "true",
      WEBHOOK_AUTH_TOKEN: "test-token",
    })).toThrow(/AI_PROVIDER/);
    expect(loadConfig({
      APP_ENV: "production",
      PUBLIC_ORIGIN: "https://calls.yino.au",
      AI_PROVIDER: "deepseek",
      DEEPSEEK_API_KEY: "test-key",
      VAPI_API_KEY: "vapi-key",
      WEBHOOK_AUTH_REQUIRED: "true",
      WEBHOOK_AUTH_TOKEN: "0123456789abcdef0123456789abcdef",
      OUTBOUND_MODE: "shadow",
    }).appEnvironment).toBe("production");
  });
});
