import { describe, expect, it } from "vitest";
import * as serverRuntime from "../src/api/server.js";
import {
  INP_CHINESE_ASSISTANT_ID,
  INP_ENGLISH_ASSISTANT_ID,
} from "../src/integrations/vapi-call-mapper.js";
import {
  createApiHarness,
  createApiHarnessWithCompletedCall,
  sanitizedEndOfCallEnvelope,
  sanitizedStatusUpdateEnvelope,
} from "./fixtures.js";

const PRIVATE_FRAGMENTS = [
  "Customer: I need an invoice workflow.",
  "Customer asked about invoice automation.",
  "https://example.invalid/recordings/demo.mp3",
  "+61000000000",
  "raw provider response",
  "worker-test-secret",
] as const;

type TestSignal = "SIGINT" | "SIGTERM";

class InjectedSignalSource {
  private readonly listeners = new Map<TestSignal, Set<() => void>>();

  on(signal: TestSignal, listener: () => void): void {
    const listeners = this.listeners.get(signal) ?? new Set<() => void>();
    listeners.add(listener);
    this.listeners.set(signal, listeners);
  }

  off(signal: TestSignal, listener: () => void): void {
    this.listeners.get(signal)?.delete(listener);
  }

  emit(signal: TestSignal): void {
    for (const listener of [...(this.listeners.get(signal) ?? [])]) {
      listener();
    }
  }

  listenerCount(signal: TestSignal): number {
    return this.listeners.get(signal)?.size ?? 0;
  }
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

type ShutdownInstaller = (
  runtime: Parameters<typeof serverRuntime.closeRuntime>[0],
  signals: InjectedSignalSource,
  onFailure: () => void,
) => {
  shutdown(): Promise<void>;
};

function installInjectedSignalShutdown(
  runtime: Parameters<typeof serverRuntime.closeRuntime>[0],
  signals: InjectedSignalSource,
): ReturnType<ShutdownInstaller> {
  const installer = (
    serverRuntime as typeof serverRuntime & {
      installSignalShutdown?: ShutdownInstaller;
    }
  ).installSignalShutdown;
  expect(installer).toBeTypeOf("function");
  return installer!(runtime, signals, () => undefined);
}

describe("local API", () => {
  it("requires the configured bearer token only on VAPI webhook routes", async () => {
    const harness = createApiHarness({
      webhookAuth: {
        required: true,
        token: "correct-test-token",
      },
    });
    try {
      const missing = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });
      const wrong = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        headers: { authorization: "Bearer wrong-test-token" },
        payload: sanitizedEndOfCallEnvelope,
      });
      const accepted = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        headers: { authorization: "Bearer correct-test-token" },
        payload: sanitizedEndOfCallEnvelope,
      });
      const health = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(missing.statusCode).toBe(401);
      expect(missing.json()).toEqual({ error: "unauthorized" });
      expect(wrong.statusCode).toBe(401);
      expect(wrong.json()).toEqual({ error: "unauthorized" });
      expect(accepted.statusCode).toBe(202);
      expect(health.statusCode).toBe(200);
      expect(missing.body).not.toContain("correct-test-token");
      expect(wrong.body).not.toContain("wrong-test-token");
    } finally {
      await harness.close();
    }
  });

  it("accepts VAPI envelopes larger than Fastify's default one MiB limit", async () => {
    const harness = createApiHarness();
    try {
      const payload = structuredClone(sanitizedStatusUpdateEnvelope) as {
        message: Record<string, unknown>;
      };
      payload.message.unusedPadding = "x".repeat(2 * 1024 * 1024);

      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/inp-group",
        payload,
      });

      expect(response.statusCode).toBe(202);
      expect(response.json()).toEqual({
        status: "skipped",
        callId: "call_demo_001",
        jobId: null,
      });
    } finally {
      await harness.close();
    }
  });

  it("accepts reports without echoing private request data", async () => {
    const harness = createApiHarness();
    try {
      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });

      expect(response.statusCode).toBe(202);
      expect(response.json()).toEqual({
        status: "accepted",
        callId: "call_demo_001",
        jobId: 1,
      });
      for (const fragment of PRIVATE_FRAGMENTS.slice(0, 4)) {
        expect(response.body).not.toContain(fragment);
      }
      expect(response.body).not.toContain("transcript");
      expect(response.body).not.toContain("summary");
      expect(response.body).not.toContain("recordingUrl");
    } finally {
      await harness.close();
    }
  });

  it("rejects a report sent to a profile other than its assistant", async () => {
    const harness = createApiHarness();
    const payload = structuredClone(sanitizedEndOfCallEnvelope) as {
      message: { call: { assistantId: string } };
    };
    payload.message.call.assistantId = INP_ENGLISH_ASSISTANT_ID;
    try {
      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload,
      });

      expect(response.statusCode).toBe(400);
      expect(response.json()).toEqual({ error: "invalid_request" });
      expect(harness.store.countCalls()).toBe(0);
      expect(harness.store.countJobs()).toBe(0);
    } finally {
      await harness.close();
    }
  });

  it("accepts INP-Chinese hangup reports on the INP webhook", async () => {
    const harness = createApiHarness();
    const payload = structuredClone(sanitizedEndOfCallEnvelope) as {
      message: { call: { id: string; assistantId: string } };
    };
    payload.message.call.id = "call_inp_chinese_001";
    payload.message.call.assistantId = INP_CHINESE_ASSISTANT_ID;
    try {
      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/inp-group",
        payload,
      });

      expect(response.statusCode).toBe(202);
      expect(response.json()).toEqual({
        status: "accepted",
        callId: "call_inp_chinese_001",
        jobId: 1,
      });
      expect(harness.store.countCalls()).toBe(1);
    } finally {
      await harness.close();
    }
  });

  it("returns 200 for a duplicate report without creating another job", async () => {
    const harness = createApiHarness();
    try {
      await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });
      const duplicate = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });

      expect(duplicate.statusCode).toBe(200);
      expect(duplicate.json()).toEqual({
        status: "duplicate",
        callId: "call_demo_001",
        jobId: 1,
      });
      expect(harness.store.countJobs()).toBe(1);
    } finally {
      await harness.close();
    }
  });

  it("returns skipped and HTTP 202 for repeated skipped events", async () => {
    const harness = createApiHarness();
    try {
      const first = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/inp-group",
        payload: sanitizedStatusUpdateEnvelope,
      });
      const duplicate = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/inp-group",
        payload: sanitizedStatusUpdateEnvelope,
      });

      expect(first.statusCode).toBe(202);
      expect(first.json()).toEqual({
        status: "skipped",
        callId: "call_demo_001",
        jobId: null,
      });
      expect(duplicate.statusCode).toBe(202);
      expect(duplicate.json()).toEqual({
        status: "skipped",
        callId: "call_demo_001",
        jobId: null,
      });
      expect(harness.store.countJobs()).toBe(0);
    } finally {
      await harness.close();
    }
  });

  it("rejects artifact-unsafe call ids before writing event metadata", async () => {
    const harness = createApiHarness();
    try {
      for (const callId of ["", ".", "..", "foo/bar", "foo\\bar", "call id"]) {
        const payload = structuredClone(sanitizedEndOfCallEnvelope) as {
          message: { call: { id: string } };
        };
        payload.message.call.id = callId;
        const response = await harness.app.inject({
          method: "POST",
          url: "/v1/vapi/lucaplus",
          payload,
        });

        expect(response.statusCode).toBe(400);
        expect(response.json()).toEqual({ error: "invalid_request" });
      }
      expect(harness.store.countEvents()).toBe(0);
      expect(harness.store.countCalls()).toBe(0);
      expect(harness.store.countJobs()).toBe(0);
    } finally {
      await harness.close();
    }
  });

  it("returns fixed not-found responses for unknown profiles and routes", async () => {
    const harness = createApiHarness();
    try {
      const unknownProfile = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/unknown",
        payload: sanitizedEndOfCallEnvelope,
      });
      const unknownRoute = await harness.app.inject({
        method: "GET",
        url: "/private/Demo%20Customer",
      });

      expect(unknownProfile.statusCode).toBe(404);
      expect(unknownProfile.json()).toEqual({ error: "not_found" });
      expect(unknownRoute.statusCode).toBe(404);
      expect(unknownRoute.json()).toEqual({ error: "not_found" });
      expect(unknownRoute.body).not.toContain("Demo");
      expect(unknownRoute.body).not.toContain("private");
    } finally {
      await harness.close();
    }
  });

  it("returns a fixed validation error without echoing invalid payload data", async () => {
    const harness = createApiHarness();
    try {
      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: {
          message: {
            type: "end-of-call-report",
            timestamp: "worker-test-secret",
            transcript: PRIVATE_FRAGMENTS[0],
            summary: PRIVATE_FRAGMENTS[1],
            artifact: { recordingUrl: PRIVATE_FRAGMENTS[2] },
          },
        },
      });

      expect(response.statusCode).toBe(400);
      expect(response.json()).toEqual({ error: "invalid_request" });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(response.body).not.toContain(fragment);
      }
    } finally {
      await harness.close();
    }
  });

  it("returns a fixed internal error without echoing storage exceptions or payload data", async () => {
    const harness = createApiHarness();
    try {
      harness.store.close();
      const response = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });

      expect(response.statusCode).toBe(500);
      expect(response.json()).toEqual({ error: "internal_error" });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(response.body).not.toContain(fragment);
      }
    } finally {
      await harness.close();
    }
  });

  it("rejects non-integer and out-of-range ratings without persistence", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      for (const score of [0, 6, 1.5, "5", null]) {
        const response = await harness.app.inject({
          method: "POST",
          url: "/v1/ratings",
          payload: {
            profile: "lucaplus",
            callId: "call_demo_001",
            score,
          },
        });
        expect(response.statusCode).toBe(400);
        expect(response.json()).toEqual({ error: "invalid_request" });
      }
      expect(harness.store.countRatings()).toBe(0);
    } finally {
      await harness.close();
    }
  });

  it("rejects ratings for an unknown profile or call", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      const unknownProfile = await harness.app.inject({
        method: "POST",
        url: "/v1/ratings",
        payload: {
          profile: "unknown",
          callId: "call_demo_001",
          score: 4,
        },
      });
      const unknownCall = await harness.app.inject({
        method: "POST",
        url: "/v1/ratings",
        payload: {
          profile: "lucaplus",
          callId: "call_demo_missing",
          score: 4,
        },
      });

      expect(unknownProfile.statusCode).toBe(404);
      expect(unknownProfile.json()).toEqual({ error: "not_found" });
      expect(unknownCall.statusCode).toBe(404);
      expect(unknownCall.json()).toEqual({ error: "not_found" });
      expect(harness.store.countRatings()).toBe(0);
    } finally {
      await harness.close();
    }
  });

  it("saves an email-link rating only after POST, while GET auto-submits the form", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      const first = await harness.app.inject({
        method: "POST",
        url: "/v1/ratings",
        payload: {
          profile: "lucaplus",
          callId: "call_demo_001",
          score: 2,
        },
      });
      expect(first.statusCode).toBe(200);
      expect(first.json()).toEqual({
        status: "rated",
        profile: "lucaplus",
        callId: "call_demo_001",
        score: 2,
        ratedAt: "2026-08-13T09:30:00.000Z",
      });

      const confirmation = await harness.app.inject({
        method: "GET",
        url: "/rating?profile=lucaplus&call_id=call_demo_001&score=5",
      });

      expect(confirmation.statusCode).toBe(200);
      expect(confirmation.headers["content-type"]).toContain("text/html");
      expect(confirmation.headers["cache-control"]).toContain("no-store");
      expect(confirmation.body).toContain("Saving rating");
      expect(confirmation.body).toContain('method="post"');
      expect(confirmation.body).toContain(".submit(");
      expect(confirmation.body).not.toContain("Confirm rating");
      expect(harness.store.getRating("lucaplus", "call_demo_001")?.score)
        .toBe(2);

      const updated = await harness.app.inject({
        method: "POST",
        url: "/rating?profile=lucaplus&call_id=call_demo_001&score=5",
      });
      expect(updated.statusCode).toBe(200);
      expect(updated.body).toContain("Rating saved");
      expect(updated.body).not.toContain("call_demo_001");
      expect(harness.store.countRatings()).toBe(1);
      expect(harness.store.getRating("lucaplus", "call_demo_001")).toEqual({
        profile: "lucaplus",
        callId: "call_demo_001",
        score: 5,
        ratedAt: "2026-08-13T09:30:00.000Z",
      });
    } finally {
      await harness.close();
    }
  });

  it("refreshes recordings through GET /recording without exposing VAPI JSON", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      const missing = await harness.app.inject({
        method: "GET",
        url: "/recording",
      });
      expect(missing.statusCode).toBe(400);
      expect(missing.json()).toEqual({ error: "invalid_request" });

      const unknown = await harness.app.inject({
        method: "GET",
        url: "/recording?profile=lucaplus&call_id=missing-call",
      });
      expect(unknown.statusCode).toBe(404);
      expect(unknown.json()).toEqual({ error: "not_found" });

      const unavailable = await harness.app.inject({
        method: "GET",
        url: "/recording?profile=lucaplus&call_id=call_demo_001",
      });
      expect(unavailable.statusCode).toBe(503);
      expect(unavailable.json()).toEqual({ error: "recording_unavailable" });
      expect(unavailable.body).not.toContain("invoice");
      expect(unavailable.headers.location).toBeUndefined();
    } finally {
      await harness.close();
    }
  });

  it("302s /recording to a fresh presigned URL from a VAPI GET", async () => {
    const harness = await createApiHarnessWithCompletedCall({
      recordingRedirect: {
        apiKey: "vapi-test-key",
        fetchCall: async () => ({
          artifact: {
            presignedMonoUrl:
              "https://recordings.example.invalid/mono.wav?X-Amz-Signature=fresh",
          },
          transcript: "must-not-leak",
        }),
      },
    });
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/recording?profile=lucaplus&call_id=call_demo_001",
      });
      expect(response.statusCode).toBe(302);
      expect(response.headers.location).toBe(
        "https://recordings.example.invalid/mono.wav?X-Amz-Signature=fresh",
      );
      expect(response.body).not.toContain("must-not-leak");
      expect(response.body).not.toContain("invoice");
    } finally {
      await harness.close();
    }
  });

  it("binds Fastify using LISTEN_HOST without treating HOST as public", () => {
    expect(serverRuntime.listenOptions({ host: "127.0.0.1", port: 3210 })).toEqual({
      host: "127.0.0.1",
      port: 3210,
    });
    expect(serverRuntime.listenOptions({ host: "0.0.0.0", port: 3210 })).toEqual({
      host: "0.0.0.0",
      port: 3210,
    });
  });

  it("returns job status with a fixed error category", async () => {
    const harness = createApiHarness();
    try {
      const accepted = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });
      const jobId = accepted.json<{ jobId: number }>().jobId;

      const pending = await harness.app.inject({
        method: "GET",
        url: `/v1/jobs/${jobId}`,
      });
      expect(pending.statusCode).toBe(200);
      expect(pending.json()).toEqual({
        jobId,
        profile: "lucaplus",
        callId: "call_demo_001",
        status: "pending",
        attempts: 0,
        error: null,
      });

      expect(harness.store.claimNextJob()?.jobId).toBe(jobId);
      harness.store.failJob(jobId, PRIVATE_FRAGMENTS.join(" | "));
      const failed = await harness.app.inject({
        method: "GET",
        url: `/v1/jobs/${jobId}`,
      });
      expect(failed.statusCode).toBe(200);
      expect(failed.json()).toEqual({
        jobId,
        profile: "lucaplus",
        callId: "call_demo_001",
        status: "failed",
        attempts: 1,
        error: "analysis_job_failed",
      });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(failed.body).not.toContain(fragment);
      }
      const retried = await harness.app.inject({
        method: "POST",
        url: `/v1/jobs/${jobId}/retry`,
      });
      expect(retried.statusCode).toBe(202);
      expect(retried.json()).toEqual({
        jobId,
        status: "pending",
      });
    } finally {
      await harness.close();
    }
  });

  it("maps malformed and unknown job identifiers to fixed errors", async () => {
    const harness = createApiHarness();
    try {
      const malformed = await harness.app.inject({
        method: "GET",
        url: "/v1/jobs/not-a-number",
      });
      const unknown = await harness.app.inject({
        method: "GET",
        url: "/v1/jobs/999",
      });

      expect(malformed.statusCode).toBe(400);
      expect(malformed.json()).toEqual({ error: "invalid_request" });
      expect(unknown.statusCode).toBe(404);
      expect(unknown.json()).toEqual({ error: "not_found" });
    } finally {
      await harness.close();
    }
  });

  it("returns a completed call and its structured analysis", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/v1/calls/lucaplus/call_demo_001",
      });
      const missing = await harness.app.inject({
        method: "GET",
        url: "/v1/calls/lucaplus/call_demo_missing",
      });

      expect(response.statusCode).toBe(200);
      expect(response.json()).toMatchObject({
        call: {
          profile: "lucaplus",
          callId: "call_demo_001",
          transcript: "Customer: I need an invoice workflow.",
        },
        analysis: {
          profile: "lucaplus",
          callId: "call_demo_001",
          provider: "mock",
          callAnalysis: {
            customerName: "Demo Customer",
            mainTopics: ["invoice automation"],
          },
          qualityAnalysis: {
            score: 8,
          },
        },
      });
      expect(missing.statusCode).toBe(404);
      expect(missing.json()).toEqual({ error: "not_found" });
    } finally {
      await harness.close();
    }
  });

  it("reports only safe queue counts and success timestamps", async () => {
    const harness = createApiHarness();
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({
        queues: {
          analysis: { pending: 0, running: 0, failed: 0 },
          mail: {
            suppressed: 0,
            pending: 0,
            sending: 0,
            failed: 0,
            uncertain: 0,
          },
        },
        lastSuccess: { analysis: null, mail: null },
        mailWorker: { status: "ok" },
        config: {
          status: "ok",
          profileCount: 2,
          lastLoadedAt: null,
          lastErrorAt: null,
        },
      });
    } finally {
      await harness.close();
    }
  });

  it("degrades live-mail health until a worker heartbeat exists", async () => {
    const harness = createApiHarness({ mailExpected: true });
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(503);
      expect(response.json().mailWorker).toEqual({ status: "degraded" });
    } finally {
      await harness.close();
    }
  });

  it("degrades health when the live profile snapshot failed to reload", async () => {
    const harness = createApiHarness({
      configHealth: {
        getHealth: () => ({
          status: "degraded",
          profileCount: 2,
          lastLoadedAt: "2026-08-25T00:00:00.000Z",
          lastErrorAt: "2026-08-25T00:00:03.000Z",
        }),
      },
    });
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });
      expect(response.statusCode).toBe(503);
      expect(response.json().config).toEqual({
        status: "degraded",
        profileCount: 2,
        lastLoadedAt: "2026-08-25T00:00:00.000Z",
        lastErrorAt: "2026-08-25T00:00:03.000Z",
      });
    } finally {
      await harness.close();
    }
  });

  it("exposes a dependency-independent liveness probe", async () => {
    const harness = createApiHarness();
    try {
      harness.store.close();
      const response = await harness.app.inject({
        method: "GET",
        url: "/livez",
      });

      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({ status: "ok" });
    } finally {
      await harness.close();
    }
  });

  it("reports only a fixed Worker failure category and timestamp", async () => {
    const healthException = PRIVATE_FRAGMENTS.join(" | ");
    const workerHealth = {
      getHealth: () => ({
        status: "degraded" as const,
        lastFailure: {
          category: "worker_cycle_failed" as const,
          at: "2026-08-13T09:00:00.000Z",
          message: healthException,
        },
        exception: healthException,
      }),
    };
    const harness = createApiHarness({ workerHealth });
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(503);
      expect(response.json()).toEqual({
        queues: {
          analysis: { pending: 0, running: 0, failed: 0 },
          mail: {
            suppressed: 0,
            pending: 0,
            sending: 0,
            failed: 0,
            uncertain: 0,
          },
        },
        lastSuccess: { analysis: null, mail: null },
        mailWorker: { status: "ok" },
        config: {
          status: "ok",
          profileCount: 2,
          lastLoadedAt: null,
          lastErrorAt: null,
        },
      });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(response.body).not.toContain(fragment);
      }
    } finally {
      await harness.close();
    }
  });

  it("degrades after a recorded mail heartbeat is older than two minutes", async () => {
    const harness = createApiHarness();
    try {
      harness.store.recordMailWorkerHeartbeat(
        "2026-08-13T08:57:59.999Z",
      );
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(503);
      expect(response.json().mailWorker).toEqual({ status: "degraded" });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(response.body).not.toContain(fragment);
      }
    } finally {
      await harness.close();
    }
  });

  it("summarizes a completed private call without exposing its contents", async () => {
    const harness = await createApiHarnessWithCompletedCall();
    try {
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(200);
      expect(response.json()).toMatchObject({
        queues: {
          analysis: { pending: 0, running: 0, failed: 0 },
        },
        lastSuccess: {
          analysis: expect.stringMatching(
            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
          ),
          mail: null,
        },
      });
      for (const fragment of PRIVATE_FRAGMENTS) {
        expect(response.body).not.toContain(fragment);
      }
      expect(response.body).not.toMatch(/subject|last_error/i);
    } finally {
      await harness.close();
    }
  });

  it("returns a fixed degraded summary when operational storage is unavailable", async () => {
    const harness = createApiHarness();
    try {
      harness.store.close();
      const response = await harness.app.inject({
        method: "GET",
        url: "/health",
      });

      expect(response.statusCode).toBe(503);
      expect(response.json()).toEqual({
        queues: {
          analysis: { pending: 0, running: 0, failed: 0 },
          mail: {
            suppressed: 0,
            pending: 0,
            sending: 0,
            failed: 0,
            uncertain: 0,
          },
        },
        lastSuccess: { analysis: null, mail: null },
        mailWorker: { status: "degraded" },
        config: {
          status: "ok",
          profileCount: 2,
          lastLoadedAt: null,
          lastErrorAt: null,
        },
      });
    } finally {
      await harness.close();
    }
  });
});

const YINO_ENDED_CALL = {
  schemaVersion: 1,
  channel: "yino",
  callId: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  eventId: "b".repeat(64),
  startedAt: "2026-08-25T03:00:00.000Z",
  endedAt: "2026-08-25T03:04:12.000Z",
  durationSeconds: 252,
  transcript: "user: hello\nassistant: hi",
  summary: "",
  recordingUrl: null,
};

describe("yino ingest", () => {
  it("accepts a bound profile with ingest bearer and does not use the vapi webhook token", async () => {
    const harness = createApiHarness({
      ingestAuth: {
        required: true,
        token: "ingest-test-token-32-chars-minimum",
      },
      webhookAuth: {
        required: true,
        token: "vapi-webhook-token-32-chars-minimum",
      },
    });
    try {
      const denied = await harness.app.inject({
        method: "POST",
        url: "/v1/ingest/lucaplus",
        headers: {
          authorization: "Bearer vapi-webhook-token-32-chars-minimum",
        },
        payload: YINO_ENDED_CALL,
      });
      expect(denied.statusCode).toBe(401);

      const ok = await harness.app.inject({
        method: "POST",
        url: "/v1/ingest/lucaplus",
        headers: {
          authorization: "Bearer ingest-test-token-32-chars-minimum",
        },
        payload: YINO_ENDED_CALL,
      });
      expect(ok.statusCode).toBe(202);
      expect(ok.json()).toMatchObject({
        status: "accepted",
        callId: YINO_ENDED_CALL.callId,
      });
    } finally {
      await harness.close();
    }
  });

  it("returns 404 for unknown profile and 400 for empty transcript", async () => {
    const harness = createApiHarness({
      ingestAuth: {
        required: true,
        token: "ingest-test-token-32-chars-minimum",
      },
    });
    try {
      const unknown = await harness.app.inject({
        method: "POST",
        url: "/v1/ingest/unknown",
        headers: {
          authorization: "Bearer ingest-test-token-32-chars-minimum",
        },
        payload: YINO_ENDED_CALL,
      });
      expect(unknown.statusCode).toBe(404);

      const empty = await harness.app.inject({
        method: "POST",
        url: "/v1/ingest/lucaplus",
        headers: {
          authorization: "Bearer ingest-test-token-32-chars-minimum",
        },
        payload: { ...YINO_ENDED_CALL, transcript: "", summary: "" },
      });
      expect(empty.statusCode).toBe(400);
      expect(
        harness.store.getCall("lucaplus", YINO_ENDED_CALL.callId),
      ).toBeNull();
    } finally {
      await harness.close();
    }
  });

  it("returns 401 when ingest token is missing without blocking vapi webhook", async () => {
    const harness = createApiHarness({
      ingestAuth: { required: true, token: null },
    });
    try {
      const denied = await harness.app.inject({
        method: "POST",
        url: "/v1/ingest/lucaplus",
        headers: {
          authorization: "Bearer ingest-test-token-32-chars-minimum",
        },
        payload: YINO_ENDED_CALL,
      });
      expect(denied.statusCode).toBe(401);

      const vapi = await harness.app.inject({
        method: "POST",
        url: "/v1/vapi/lucaplus",
        payload: sanitizedEndOfCallEnvelope,
      });
      expect(vapi.statusCode).toBe(202);
    } finally {
      await harness.close();
    }
  });
});

describe("server shutdown", () => {
  it("stops accepting requests and cancels AI before waiting on the Worker", async () => {
    const order: string[] = [];

    await serverRuntime.closeRuntime({
      app: {
        close: async () => {
          order.push("app");
        },
      },
      provider: {
        close: () => {
          order.push("provider");
        },
      },
      worker: {
        stop: async () => {
          order.push("worker");
        },
      },
      store: {
        close: () => {
          order.push("store");
        },
      },
    });

    expect(order).toEqual(["app", "provider", "worker", "store"]);
  });

  it("routes repeated signals through one in-flight close sequence", async () => {
    const appCloseGate = deferred<void>();
    const signals = new InjectedSignalSource();
    const order: string[] = [];
    let appCloseCalls = 0;
    const controller = installInjectedSignalShutdown(
      {
        app: {
          close: async () => {
            appCloseCalls += 1;
            order.push("app");
            await appCloseGate.promise;
          },
        },
        provider: {
          close: () => {
            order.push("provider");
          },
        },
        worker: {
          stop: async () => {
            order.push("worker");
          },
        },
        store: {
          close: () => {
            order.push("store");
          },
        },
      },
      signals,
    );

    signals.emit("SIGINT");
    signals.emit("SIGTERM");
    await Promise.resolve();

    expect(appCloseCalls).toBe(1);
    expect(order).toEqual(["app"]);

    appCloseGate.resolve();
    await controller.shutdown();

    expect(order).toEqual(["app", "provider", "worker", "store"]);
  });

  it("removes signal handlers only after shutdown completion", async () => {
    const appCloseGate = deferred<void>();
    const signals = new InjectedSignalSource();
    const controller = installInjectedSignalShutdown(
      {
        app: {
          close: async () => {
            await appCloseGate.promise;
          },
        },
        provider: {
          close: () => undefined,
        },
        worker: {
          stop: async () => undefined,
        },
        store: {
          close: () => undefined,
        },
      },
      signals,
    );

    expect(signals.listenerCount("SIGINT")).toBe(1);
    expect(signals.listenerCount("SIGTERM")).toBe(1);

    signals.emit("SIGINT");
    await Promise.resolve();

    expect(signals.listenerCount("SIGINT")).toBe(1);
    expect(signals.listenerCount("SIGTERM")).toBe(1);

    appCloseGate.resolve();
    await controller.shutdown();

    expect(signals.listenerCount("SIGINT")).toBe(0);
    expect(signals.listenerCount("SIGTERM")).toBe(0);
  });
});
