import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_TRIAL_CALL_ID,
  LUCAPLUS_MIA_ASSISTANT_ID,
  TrialError,
  fetchLucaPlusCall,
  mapVapiCallToEndOfCallEnvelope,
  parseTrialCallId,
} from "../tools/pull-lucaplus-call.js";

const CALL_ID = "019ffebb-795d-711f-ae46-1674252cc39c";

function baseCall(overrides: Record<string, unknown> = {}) {
  return {
    id: CALL_ID,
    assistantId: LUCAPLUS_MIA_ASSISTANT_ID,
    startedAt: "2026-08-14T05:25:27.230Z",
    endedAt: "2026-08-14T05:26:54.553Z",
    transcript: "AI: Hello. User: I need a quote.",
    summary: "Caller asked for a quote.",
    recordingUrl: "https://example.invalid/rec.wav",
    artifact: {
      recordingUrl: "https://example.invalid/artifact.wav",
      transcript: "artifact transcript",
      variableValues: {
        "phoneNumber.twilioAuthToken": "secret-token",
        "phoneNumber.twilioAccountSid": "ACsecret",
      },
      variables: { "transport.accountSid": "ACsecret" },
    },
    customer: { number: "+61400000000" },
    transport: { accountSid: "ACsecret", callToken: "tokensecret" },
    costs: [{ amount: 1 }],
    monitor: { listenUrl: "wss://example.invalid/listen" },
    analysis: { summary: "analysis summary" },
    ...overrides,
  };
}

describe("parseTrialCallId", () => {
  it("defaults to the spec call id", () => {
    expect(parseTrialCallId(undefined)).toBe(CALL_ID);
    expect(DEFAULT_TRIAL_CALL_ID).toBe(CALL_ID);
  });

  it("accepts a UUID override", () => {
    expect(parseTrialCallId("11111111-1111-1111-1111-111111111111")).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
  });

  it("rejects a non-UUID override", () => {
    expect(() => parseTrialCallId("latest")).toThrow(TrialError);
    try {
      parseTrialCallId("latest");
    } catch (error) {
      expect(error).toMatchObject({
        code: "trial_mapping_failed",
        message: "trial_mapping_failed",
      });
    }
  });
});

const PRESIGNED_MONO =
  "https://recordings.example.invalid/mono.wav?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=mono&X-Amz-Expires=1800";
const PRESIGNED_STEREO =
  "https://recordings.example.invalid/stereo.wav?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=stereo&X-Amz-Expires=1800";

describe("mapVapiCallToEndOfCallEnvelope", () => {
  it("maps only the allowed fields and prefers presignedMonoUrl over unsigned recording URLs", () => {
    const envelope = mapVapiCallToEndOfCallEnvelope(
      baseCall({
        artifact: {
          recordingUrl: "https://example.invalid/artifact.wav",
          stereoRecordingUrl: "https://example.invalid/stereo.wav",
          presignedMonoUrl: PRESIGNED_MONO,
          presignedStereoUrl: PRESIGNED_STEREO,
          transcript: "artifact transcript",
          variableValues: {
            "phoneNumber.twilioAuthToken": "secret-token",
            "phoneNumber.twilioAccountSid": "ACsecret",
          },
          variables: { "transport.accountSid": "ACsecret" },
        },
      }),
    );
    expect(envelope).toEqual({
      message: {
        type: "end-of-call-report",
        timestamp: Date.parse("2026-08-14T05:26:54.553Z"),
        call: {
          id: CALL_ID,
          assistantId: LUCAPLUS_MIA_ASSISTANT_ID,
        },
        startedAt: "2026-08-14T05:25:27.230Z",
        endedAt: "2026-08-14T05:26:54.553Z",
        transcript: "AI: Hello. User: I need a quote.",
        summary: "Caller asked for a quote.",
        artifact: { recordingUrl: PRESIGNED_MONO },
      },
    });
    const json = JSON.stringify(envelope);
    expect(json).not.toContain("secret-token");
    expect(json).not.toContain("ACsecret");
    expect(json).not.toContain("tokensecret");
    expect(json).not.toContain("+61400000000");
    expect(json).not.toContain("variableValues");
    expect(json).not.toContain("https://example.invalid/artifact.wav");
    expect(json).not.toContain("https://example.invalid/rec.wav");
  });

  it("falls back to presignedStereoUrl when mono is missing", () => {
    const envelope = mapVapiCallToEndOfCallEnvelope(
      baseCall({
        artifact: {
          recordingUrl: "https://example.invalid/artifact.wav",
          presignedStereoUrl: PRESIGNED_STEREO,
        },
      }),
    );
    expect(envelope.message.artifact).toEqual({ recordingUrl: PRESIGNED_STEREO });
  });

  it("falls back to artifact transcript and analysis.summary without using unsigned recording URLs", () => {
    const envelope = mapVapiCallToEndOfCallEnvelope(
      baseCall({
        transcript: "",
        summary: "",
        artifact: {
          transcript: "from artifact",
          recordingUrl: "https://example.invalid/artifact.wav",
        },
      }),
    );
    expect(envelope.message.transcript).toBe("from artifact");
    expect(envelope.message.summary).toBe("analysis summary");
    expect(envelope.message.artifact).toBeUndefined();
  });

  it("omits recording when only unsigned or non-https URLs exist", () => {
    const envelope = mapVapiCallToEndOfCallEnvelope(
      baseCall({
        recordingUrl: "https://example.invalid/rec.wav",
        artifact: {
          recordingUrl: "https://example.invalid/artifact.wav",
          stereoRecordingUrl: "https://example.invalid/stereo.wav",
          presignedMonoUrl: "http://insecure.invalid/mono.wav?X-Amz-Signature=x",
        },
      }),
    );
    expect(envelope.message.artifact).toBeUndefined();
  });

  it("rejects a non-LucaPlus-Mia assistant", () => {
    expect(() =>
      mapVapiCallToEndOfCallEnvelope(
        baseCall({ assistantId: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
      ),
    ).toThrow(TrialError);
    try {
      mapVapiCallToEndOfCallEnvelope(
        baseCall({ assistantId: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
      );
    } catch (error) {
      expect(error).toMatchObject({
        code: "trial_call_not_lucaplus",
        message: "trial_call_not_lucaplus",
      });
    }
  });
});

describe("fetchLucaPlusCall", () => {
  it("GETs api.vapi.ai/call/{id} with the bearer key and returns JSON", async () => {
    const call = baseCall();
    const fetchFn = vi.fn(
      async () => new Response(JSON.stringify(call), { status: 200 }),
    );
    await expect(
      fetchLucaPlusCall(CALL_ID, "vapi-test-key", fetchFn as unknown as typeof fetch),
    ).resolves.toEqual(call);
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
  });

  it("maps HTTP failure to trial_call_fetch_failed without leaking the body", async () => {
    const fetchFn = vi.fn(
      async () => new Response("injected-vapi-secret", { status: 500 }),
    );
    try {
      await fetchLucaPlusCall(
        CALL_ID,
        "vapi-test-key",
        fetchFn as unknown as typeof fetch,
      );
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(TrialError);
      expect(error).toMatchObject({
        code: "trial_call_fetch_failed",
        message: "trial_call_fetch_failed",
      });
      expect(`${String(error)}\n${(error as Error).stack ?? ""}`).not.toContain(
        "injected-vapi-secret",
      );
    }
  });
});
