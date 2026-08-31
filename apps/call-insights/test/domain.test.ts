import { describe, expect, it } from "vitest";
import { QualityAnalysisSchema } from "../src/domain/schemas.js";
import { loadProfile } from "../src/profiles/profiles.js";
import { normalizeVapiEvent } from "../src/application/normalize-vapi-event.js";

describe("profiles", () => {
  it("loads known profiles and rejects unknown slugs", () => {
    expect(loadProfile("lucaplus")?.displayName).toBe("LucaPlus");
    expect(loadProfile("inp-group")?.displayName).toBe("INP Group");
    expect(loadProfile("unknown")).toBeNull();
  });
});

describe("QualityAnalysisSchema", () => {
  it("rejects scores outside 0..10", () => {
    const validQuality = {
      score: 8,
      strengths: ["Clear greeting"],
      weaknesses: ["Missed follow-up"],
      suggestions: ["Confirm next steps"],
      shouldUpdatePrompt: false,
      summary: "Solid call with a minor follow-up gap.",
    };
    expect(() =>
      QualityAnalysisSchema.parse({ ...validQuality, score: 11 }),
    ).toThrow();
    expect(() =>
      QualityAnalysisSchema.parse({ ...validQuality, score: -1 }),
    ).toThrow();
  });
});

describe("normalizeVapiEvent", () => {
  it("normalizes direct and n8n envelopes identically", () => {
    const profile = loadProfile("lucaplus");
    expect(profile).not.toBeNull();
    const message = {
      type: "end-of-call-report",
      timestamp: 1786600000000,
      call: { id: "call_demo_001" },
      startedAt: "2026-08-13T01:00:00.000Z",
      endedAt: "2026-08-13T01:02:30.000Z",
      transcript: "Customer: I need an invoice workflow.",
      summary: "Customer asked about invoice automation.",
      artifact: {
        recordingUrl: "https://example.invalid/recordings/demo.mp3",
        presignedMonoUrl:
          "https://recordings.example.invalid/mono.wav?X-Amz-Signature=mono",
      },
    };
    const direct = normalizeVapiEvent(profile!, { message }, new Date("2026-08-13T02:00:00Z"));
    const replay = normalizeVapiEvent(
      profile!,
      { body: { message } },
      new Date("2026-08-13T02:00:00Z"),
    );
    expect(replay).toEqual(direct);
    expect(direct.call?.durationSeconds).toBe(150);
    expect(direct.call?.callId).toBe("call_demo_001");
    expect(direct.call?.recordingUrl).toBe(
      "https://recordings.example.invalid/mono.wav?X-Amz-Signature=mono",
    );
  });

  it("selects presignedStereoUrl and ignores unsigned recording URLs", () => {
    const profile = loadProfile("lucaplus")!;
    const event = normalizeVapiEvent(
      profile,
      {
        message: {
          type: "end-of-call-report",
          timestamp: 1786600000000,
          call: { id: "call_demo_001" },
          startedAt: "2026-08-13T01:00:00.000Z",
          endedAt: "2026-08-13T01:02:30.000Z",
          transcript: "Customer: I need an invoice workflow.",
          summary: "Customer asked about invoice automation.",
          artifact: {
            recordingUrl: "https://example.invalid/recordings/demo.mp3",
            stereoRecordingUrl: "https://example.invalid/recordings/stereo.mp3",
            presignedStereoUrl:
              "https://recordings.example.invalid/stereo.wav?X-Amz-Signature=stereo",
          },
        },
      },
      new Date("2026-08-13T02:00:00Z"),
    );
    expect(event.call?.recordingUrl).toBe(
      "https://recordings.example.invalid/stereo.wav?X-Amz-Signature=stereo",
    );
  });

  it("omits unsigned recording URLs from the normalized call", () => {
    const profile = loadProfile("lucaplus")!;
    const event = normalizeVapiEvent(
      profile,
      {
        message: {
          type: "end-of-call-report",
          timestamp: 1786600000000,
          call: { id: "call_demo_001" },
          startedAt: "2026-08-13T01:00:00.000Z",
          endedAt: "2026-08-13T01:02:30.000Z",
          transcript: "Customer: I need an invoice workflow.",
          summary: "Customer asked about invoice automation.",
          artifact: { recordingUrl: "https://example.invalid/recordings/demo.mp3" },
        },
      },
      new Date("2026-08-13T02:00:00Z"),
    );
    expect(event.call?.recordingUrl).toBeNull();
  });

  it("keeps a mapped playback URL stored on artifact.recordingUrl when it is already presigned", () => {
    const profile = loadProfile("lucaplus")!;
    const presigned =
      "https://recordings.example.invalid/mono.wav?X-Amz-Signature=mapped";
    const event = normalizeVapiEvent(
      profile,
      {
        message: {
          type: "end-of-call-report",
          timestamp: 1786600000000,
          call: { id: "call_demo_001" },
          startedAt: "2026-08-13T01:00:00.000Z",
          endedAt: "2026-08-13T01:02:30.000Z",
          transcript: "Customer: I need an invoice workflow.",
          summary: "Customer asked about invoice automation.",
          artifact: { recordingUrl: presigned },
        },
      },
      new Date("2026-08-13T02:00:00Z"),
    );
    expect(event.call?.recordingUrl).toBe(presigned);
  });

  it("rejects report events without call.id", () => {
    const profile = loadProfile("inp-group")!;
    expect(() =>
      normalizeVapiEvent(
        profile,
        { message: { type: "end-of-call-report", timestamp: 1, call: {} } },
        new Date(),
      ),
    ).toThrow(/call\.id/);
  });

  it.each(["", ".", "..", "foo/bar", "foo\\bar", "call id", "call\0id"])(
    "rejects artifact-unsafe call id %j",
    (callId) => {
      const profile = loadProfile("lucaplus")!;
      expect(() =>
        normalizeVapiEvent(
          profile,
          {
            message: {
              type: "end-of-call-report",
              timestamp: 1786600000000,
              call: { id: callId },
              startedAt: "2026-08-13T01:00:00.000Z",
              endedAt: "2026-08-13T01:02:30.000Z",
              transcript: "Customer: fictional request.",
            },
          },
          new Date("2026-08-13T02:00:00Z"),
        ),
      ).toThrow(/call\.id/i);
    },
  );

  it("marks status updates as skipped data", () => {
    const profile = loadProfile("lucaplus")!;
    const result = normalizeVapiEvent(
      profile,
      {
        message: {
          type: "status-update",
          timestamp: 1786600000000,
          call: { id: "call_demo_002" },
          status: "in-progress",
        },
      },
      new Date("2026-08-13T02:00:00Z"),
    );
    expect(result.action).toBe("skip");
    expect(result.call).toBeNull();
  });
});
