import { describe, expect, it, vi } from "vitest";
import { existsSync } from "node:fs";
import { MockAiProvider } from "../src/ai/mock-provider.js";
import {
  INP_ENGLISH_ASSISTANT_ID,
  LUCAPLUS_MIA_ASSISTANT_ID,
  VapiCallMappingError,
  mapVapiCallToEndOfCallEnvelope,
} from "../src/integrations/vapi-call-mapper.js";
import {
  VapiCallFetchError,
  listVapiCalls,
} from "../src/integrations/vapi-client.js";
import {
  runShadowReplayCommand,
  type ShadowReplayDependencies,
} from "../tools/shadow-replay.js";
import {
  createShadowReplayRuntime,
  shadowReplayMain,
} from "../tools/shadow-replay-entrypoint.js";

const PRIVATE_FRAGMENTS = [
  "private-call-id",
  "Customer private transcript",
  "Private Customer",
  "private@example.test",
  "https://recordings.example.test/private.wav",
  "C:\\private\\shadow-work",
] as const;

function vapiCall(
  assistantId: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: "019ffebb-795d-711f-ae46-1674252cc39c",
    assistantId,
    startedAt: "2026-08-14T05:25:27.230Z",
    endedAt: "2026-08-14T05:26:54.553Z",
    transcript: "AI: Hello. User: I need a quote.",
    summary: "Caller asked for a quote.",
    artifact: {
      recordingUrl:
        "https://recordings.example.invalid/artifact.wav?X-Amz-Signature=test",
    },
    ...overrides,
  };
}

describe("VAPI call mapper", () => {
  it.each([
    ["lucaplus", LUCAPLUS_MIA_ASSISTANT_ID],
    ["inp-group", INP_ENGLISH_ASSISTANT_ID],
  ] as const)("maps only the fixed %s assistant", (profile, assistantId) => {
    const envelope = mapVapiCallToEndOfCallEnvelope(
      profile,
      vapiCall(assistantId),
    );

    expect(envelope).toEqual({
      message: {
        type: "end-of-call-report",
        timestamp: Date.parse("2026-08-14T05:26:54.553Z"),
        call: {
          id: "019ffebb-795d-711f-ae46-1674252cc39c",
          assistantId,
        },
        startedAt: "2026-08-14T05:25:27.230Z",
        endedAt: "2026-08-14T05:26:54.553Z",
        transcript: "AI: Hello. User: I need a quote.",
        summary: "Caller asked for a quote.",
        artifact: {
          recordingUrl:
            "https://recordings.example.invalid/artifact.wav?X-Amz-Signature=test",
        },
      },
    });
  });

  it.each([
    {
      name: "wrong assistant",
      call: vapiCall("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    },
    {
      name: "missing endedAt",
      call: vapiCall(LUCAPLUS_MIA_ASSISTANT_ID, { endedAt: undefined }),
    },
    {
      name: "no transcript or summary",
      call: vapiCall(LUCAPLUS_MIA_ASSISTANT_ID, {
        transcript: "",
        summary: "",
      }),
    },
  ])("rejects $name with a fixed mapping error", ({ call }) => {
    expect(() => mapVapiCallToEndOfCallEnvelope("lucaplus", call))
      .toThrow(VapiCallMappingError);
  });
});

describe("VAPI call listing", () => {
  it("uses the fixed API endpoint and assistant filter", async () => {
    const fetchFn = vi.fn(async (
      _input: RequestInfo | URL,
      _init?: RequestInit,
    ) =>
      new Response(JSON.stringify([{ id: "call-list-item" }]), {
        status: 200,
      })
    );

    await expect(listVapiCalls(
      "private-api-key",
      LUCAPLUS_MIA_ASSISTANT_ID,
      10,
      fetchFn,
    )).resolves.toEqual([{ id: "call-list-item" }]);

    const [requestUrl, init] = fetchFn.mock.calls[0]!;
    const url = new URL(String(requestUrl));
    expect(`${url.origin}${url.pathname}`).toBe("https://api.vapi.ai/call");
    expect(url.searchParams.get("assistantId")).toBe(
      LUCAPLUS_MIA_ASSISTANT_ID,
    );
    expect(url.searchParams.get("limit")).toBe("10");
    expect(new Headers(init?.headers).get("authorization"))
      .toBe("Bearer private-api-key");
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });

  it("discards upstream bodies behind a fixed error", async () => {
    const fetchFn = vi.fn(async (
      _input: RequestInfo | URL,
      _init?: RequestInit,
    ) =>
      new Response("private upstream response", { status: 500 })
    );

    await expect(listVapiCalls(
      "private-api-key",
      LUCAPLUS_MIA_ASSISTANT_ID,
      10,
      fetchFn,
    )).rejects.toBeInstanceOf(VapiCallFetchError);
  });
});

describe("shadow replay orchestration", () => {
  it("selects valid calls for both profiles and prints only aggregate counts", async () => {
    const processed: Array<{ profile: string; envelope: unknown }> = [];
    const output: string[] = [];
    const dependencies: ShadowReplayDependencies = {
      async listCalls(_assistantId, _limit) {
        return [
          {
            id: "invalid-call",
            createdAt: "2026-08-17T00:00:00.000Z",
            endedAt: "2026-08-17T00:01:00.000Z",
          },
          {
            id: "private-call-id",
            createdAt: "2026-08-16T00:00:00.000Z",
            endedAt: "2026-08-16T00:01:00.000Z",
          },
        ];
      },
      async fetchCall(callId) {
        if (callId === "invalid-call") {
          return vapiCall("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", {
            id: callId,
          });
        }
        const assistantId = processed.length === 0
          ? LUCAPLUS_MIA_ASSISTANT_ID
          : INP_ENGLISH_ASSISTANT_ID;
        return vapiCall(assistantId, {
          id: callId,
          transcript: PRIVATE_FRAGMENTS[1],
          summary: "Private Customer private@example.test",
          artifact: { recordingUrl: PRIVATE_FRAGMENTS[4] },
        });
      },
      async processEnvelope(profile, envelope) {
        processed.push({ profile, envelope });
      },
      countSuppressedMail: () => 4,
    };

    const result = await runShadowReplayCommand(
      ["--per-profile", "1"],
      dependencies,
      (line) => output.push(line),
    );

    expect(result).toEqual({
      status: "succeeded",
      profiles: { lucaplus: 1, "inp-group": 1 },
      suppressedMail: 4,
    });
    expect(processed.map(({ profile }) => profile)).toEqual([
      "lucaplus",
      "inp-group",
    ]);
    expect(output).toEqual([
      '{"status":"succeeded","profiles":{"lucaplus":1,"inp-group":1},"suppressedMail":4}',
    ]);
    for (const fragment of PRIVATE_FRAGMENTS) {
      expect(output[0]).not.toContain(fragment);
    }
  });

  it("runs an isolated shadow pipeline even when the environment requests live mail", async () => {
    const lucaCallId = "11111111-1111-4111-8111-111111111111";
    const inpCallId = "22222222-2222-4222-8222-222222222222";
    const vapiFetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === "/call") {
        const callId = url.searchParams.get("assistantId") ===
            LUCAPLUS_MIA_ASSISTANT_ID
          ? lucaCallId
          : inpCallId;
        return new Response(JSON.stringify([{
          id: callId,
          createdAt: "2026-08-17T00:00:00.000Z",
          endedAt: "2026-08-17T00:01:00.000Z",
        }]), {
          status: 200,
        });
      }
      const callId = decodeURIComponent(url.pathname.slice("/call/".length));
      const assistantId = callId === lucaCallId
        ? LUCAPLUS_MIA_ASSISTANT_ID
        : INP_ENGLISH_ASSISTANT_ID;
      return new Response(JSON.stringify(vapiCall(assistantId, {
        id: callId,
      })), { status: 200 });
    });
    const runtime = createShadowReplayRuntime({
      VAPI_API_KEY: "private-vapi-key",
      DEEPSEEK_API_KEY: "private-deepseek-key",
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2000-01-01T00:00:00.000Z",
      PUBLIC_ORIGIN: "https://calls.yino.au",
    }, {
      provider: new MockAiProvider(),
      vapiFetch,
    });
    const workRoot = runtime.workRoot;
    try {
      await expect(runShadowReplayCommand(
        ["--per-profile", "1"],
        runtime.dependencies,
        () => undefined,
      )).resolves.toEqual({
        status: "succeeded",
        profiles: { lucaplus: 1, "inp-group": 1 },
        suppressedMail: 4,
      });
      expect(runtime.dependencies.countSuppressedMail()).toBe(4);
      expect(existsSync(workRoot)).toBe(true);
    } finally {
      await runtime.close();
    }
    expect(existsSync(workRoot)).toBe(false);
  });

  it("entrypoint reports only a fixed failure and always closes runtime", async () => {
    const close = vi.fn(async () => undefined);
    const output: string[] = [];
    const errors: string[] = [];
    const exitCode = await shadowReplayMain(
      ["--per-profile", "1"],
      {
        VAPI_API_KEY: "private-vapi-key",
        DEEPSEEK_API_KEY: "private-deepseek-key",
      },
      (line) => output.push(line),
      (line) => errors.push(line),
      () => ({
        workRoot: "C:\\private\\shadow-work",
        dependencies: {
          listCalls: async () => {
            throw new Error(PRIVATE_FRAGMENTS.join(" | "));
          },
          fetchCall: async () => null,
          processEnvelope: async () => undefined,
          countSuppressedMail: () => 0,
        },
        close,
      }),
    );

    expect(exitCode).toBe(1);
    expect(output).toEqual([]);
    expect(errors).toEqual(["shadow_replay_failed"]);
    expect(close).toHaveBeenCalledTimes(1);
    for (const fragment of PRIVATE_FRAGMENTS) {
      expect(JSON.stringify(errors)).not.toContain(fragment);
    }
  });

  it("does not print success when private-work cleanup fails", async () => {
    const output: string[] = [];
    const errors: string[] = [];
    const dependencies: ShadowReplayDependencies = {
      listCalls: async (assistantId) => [{
        id: assistantId === LUCAPLUS_MIA_ASSISTANT_ID ? "luca" : "inp",
        createdAt: "2026-08-17T00:00:00.000Z",
        endedAt: "2026-08-17T00:01:00.000Z",
      }],
      fetchCall: async (callId) =>
        vapiCall(
          callId === "luca"
            ? LUCAPLUS_MIA_ASSISTANT_ID
            : INP_ENGLISH_ASSISTANT_ID,
          { id: callId },
        ),
      processEnvelope: async () => undefined,
      countSuppressedMail: () => 4,
    };
    const exitCode = await shadowReplayMain(
      ["--per-profile", "1"],
      {
        VAPI_API_KEY: "private-vapi-key",
        DEEPSEEK_API_KEY: "private-deepseek-key",
      },
      (line) => output.push(line),
      (line) => errors.push(line),
      () => ({
        workRoot: "C:\\private\\shadow-work",
        dependencies,
        close: async () => {
          throw new Error("private cleanup failure");
        },
      }),
    );

    expect(exitCode).toBe(1);
    expect(output).toEqual([]);
    expect(errors).toEqual(["shadow_replay_shutdown_failed"]);
  });

  it("forces the default provider factory to DeepSeek", async () => {
    const createProvider = vi.fn(() => new MockAiProvider());
    const runtime = createShadowReplayRuntime({
      VAPI_API_KEY: "private-vapi-key",
      DEEPSEEK_API_KEY: "private-deepseek-key",
      AI_PROVIDER: "mock",
      OUTBOUND_MODE: "live",
      PUBLIC_ORIGIN: "https://calls.yino.au",
    }, {
      createProvider,
      vapiFetch: async () => new Response("[]", { status: 200 }),
    });
    try {
      expect(createProvider).toHaveBeenCalledWith({
        aiProvider: "deepseek",
        deepseekApiKey: "private-deepseek-key",
      });
    } finally {
      await runtime.close();
    }
  });

  it("searches beyond the initial small window for valid ended calls", async () => {
    const processed: string[] = [];
    const fetched: string[] = [];
    const dependencies: ShadowReplayDependencies = {
      async listCalls(assistantId, limit) {
        const prefix = assistantId === LUCAPLUS_MIA_ASSISTANT_ID
          ? "luca"
          : "inp";
        return Array.from({ length: 20 }, (_, index) => ({
          id: `${prefix}-${index}`,
          createdAt: `2026-08-${String(20 - index).padStart(2, "0")}T00:00:00.000Z`,
          ...(index === 19
            ? { endedAt: "2026-08-01T00:01:00.000Z" }
            : {}),
        })).slice(0, limit);
      },
      async fetchCall(callId) {
        fetched.push(callId);
        const assistantId = callId.startsWith("luca")
          ? LUCAPLUS_MIA_ASSISTANT_ID
          : INP_ENGLISH_ASSISTANT_ID;
        return vapiCall(assistantId, { id: callId });
      },
      async processEnvelope(profile) {
        processed.push(profile);
      },
      countSuppressedMail: () => 4,
    };

    await expect(runShadowReplayCommand(
      ["--per-profile", "1"],
      dependencies,
      () => undefined,
    )).resolves.toMatchObject({ status: "succeeded" });
    expect(processed).toEqual(["lucaplus", "inp-group"]);
    expect(fetched).toEqual(["luca-19", "inp-19"]);
  });

  it("does not request irrelevant older pages after enough recent calls succeed", async () => {
    const listCalls = vi.fn(async (
      assistantId: string,
      _limit: number,
      createdAtLt?: string,
    ) => {
      if (createdAtLt !== undefined) {
        throw new Error("irrelevant older page failed");
      }
      const prefix = assistantId === LUCAPLUS_MIA_ASSISTANT_ID
        ? "luca"
        : "inp";
      return Array.from({ length: 100 }, (_, index) => ({
        id: `${prefix}-${index}`,
        createdAt: `2026-08-17T00:${String(59 - (index % 60)).padStart(2, "0")}:00.000Z`,
        ...(index === 0
          ? { endedAt: "2026-08-17T01:00:00.000Z" }
          : {}),
      }));
    });
    const dependencies: ShadowReplayDependencies = {
      listCalls,
      fetchCall: async (callId) =>
        vapiCall(
          callId.startsWith("luca")
            ? LUCAPLUS_MIA_ASSISTANT_ID
            : INP_ENGLISH_ASSISTANT_ID,
          { id: callId },
        ),
      processEnvelope: async () => undefined,
      countSuppressedMail: () => 4,
    };

    await expect(runShadowReplayCommand(
      ["--per-profile", "1"],
      dependencies,
      () => undefined,
    )).resolves.toMatchObject({ status: "succeeded" });
    expect(listCalls).toHaveBeenCalledTimes(2);
    expect(listCalls.mock.calls.every((call) => call[2] === undefined))
      .toBe(true);
  });
});
