import { describe, expect, it, vi } from "vitest";
import { resolveRecordingRedirect } from "../src/application/recording-redirect.js";
import { fetchVapiCallJson, VapiCallFetchError } from "../src/integrations/vapi-client.js";
import { makeCall } from "./fixtures.js";

const CALL_ID = "019ffebb-795d-711f-ae46-1674252cc39c";
const PRESIGNED =
  "https://recordings.example.invalid/mono.wav?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc&X-Amz-Expires=1800";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("fetchVapiCallJson", () => {
  it("GETs api.vapi.ai/call/{id} and never PATCHes", async () => {
    const fetchFn = vi.fn(async () => jsonResponse({ id: CALL_ID }));
    await expect(
      fetchVapiCallJson(CALL_ID, "vapi-test-key", fetchFn as unknown as typeof fetch),
    ).resolves.toEqual({ id: CALL_ID });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith(
      `https://api.vapi.ai/call/${CALL_ID}`,
      expect.objectContaining({
        method: "GET",
        redirect: "error",
        headers: {
          authorization: "Bearer vapi-test-key",
          accept: "application/json",
        },
      }),
    );
    expect(JSON.stringify(fetchFn.mock.calls)).not.toContain("PATCH");
  });

  it("maps HTTP failure without leaking the body", async () => {
    const fetchFn = vi.fn(
      async () => new Response("injected-vapi-secret", { status: 500 }),
    );
    try {
      await fetchVapiCallJson(
        CALL_ID,
        "vapi-test-key",
        fetchFn as unknown as typeof fetch,
      );
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(VapiCallFetchError);
      expect(`${String(error)}\n${(error as Error).stack ?? ""}`).not.toContain(
        "injected-vapi-secret",
      );
    }
  });
});

describe("resolveRecordingRedirect", () => {
  it("404s without calling VAPI when the call is not in the local store", async () => {
    const fetchFn = vi.fn();
    const result = await resolveRecordingRedirect({
      profile: "lucaplus",
      callId: CALL_ID,
      getCall: () => null,
      apiKey: "vapi-test-key",
      fetchCall: async (callId) =>
        fetchVapiCallJson(callId, "vapi-test-key", fetchFn as unknown as typeof fetch),
    });
    expect(result).toEqual({ type: "error", status: 404, error: "not_found" });
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("503s without calling VAPI when the API key is missing", async () => {
    const fetchFn = vi.fn();
    const result = await resolveRecordingRedirect({
      profile: "lucaplus",
      callId: CALL_ID,
      getCall: () => makeCall({ callId: CALL_ID }),
      apiKey: null,
      fetchCall: async () => {
        fetchFn();
        throw new Error("must not fetch");
      },
    });
    expect(result).toEqual({
      type: "error",
      status: 503,
      error: "recording_unavailable",
    });
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("302s to a fresh presigned URL from the VAPI GET artifact", async () => {
    const fetchFn = vi.fn(async () =>
      jsonResponse({
        id: CALL_ID,
        artifact: {
          recordingUrl: "https://recordings.example.invalid/unsigned.wav",
          presignedMonoUrl: PRESIGNED,
        },
        transcript: "must-not-appear-in-redirect",
      }),
    );
    const result = await resolveRecordingRedirect({
      profile: "lucaplus",
      callId: CALL_ID,
      getCall: () => makeCall({ callId: CALL_ID }),
      apiKey: "vapi-test-key",
      fetchCall: async (callId) =>
        fetchVapiCallJson(callId, "vapi-test-key", fetchFn as unknown as typeof fetch),
    });
    expect(result).toEqual({ type: "redirect", location: PRESIGNED });
    expect(JSON.stringify(result)).not.toContain("must-not-appear-in-redirect");
    expect(JSON.stringify(result)).not.toContain("unsigned.wav");
  });

  it("503s when VAPI returns only an unsigned recording URL", async () => {
    const fetchFn = vi.fn(async () =>
      jsonResponse({
        id: CALL_ID,
        artifact: { recordingUrl: "https://recordings.example.invalid/unsigned.wav" },
      }),
    );
    const result = await resolveRecordingRedirect({
      profile: "lucaplus",
      callId: CALL_ID,
      getCall: () => makeCall({ callId: CALL_ID }),
      apiKey: "vapi-test-key",
      fetchCall: async (callId) =>
        fetchVapiCallJson(callId, "vapi-test-key", fetchFn as unknown as typeof fetch),
    });
    expect(result).toEqual({
      type: "error",
      status: 503,
      error: "recording_unavailable",
    });
  });
});
