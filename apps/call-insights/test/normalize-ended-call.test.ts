import { describe, expect, it } from "vitest";
import { normalizeEndedCall } from "../src/application/normalize-ended-call.js";
import { lucaplusProfile } from "./fixtures.js";

const body = {
  schemaVersion: 1,
  channel: "yino",
  callId: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  eventId: "a".repeat(64),
  startedAt: "2026-08-25T03:00:00.000Z",
  endedAt: "2026-08-25T03:04:12.000Z",
  durationSeconds: 252,
  transcript: "user: hello\nassistant: hi",
  summary: "",
  recordingUrl: null,
};

describe("normalizeEndedCall", () => {
  it("accepts a yino ended-call and queues analysis", () => {
    const event = normalizeEndedCall(
      lucaplusProfile,
      body,
      new Date("2026-08-25T03:05:00.000Z"),
    );
    expect(event.action).toBe("analyze");
    expect(event.call?.channel).toBe("yino");
    expect(event.call?.callId).toBe(body.callId);
    expect(event.call?.recordingUrl).toBeNull();
    expect(event.eventId).toBe(body.eventId);
  });

  it("rejects extra keys, missing transcript+summary, and non-UTC timestamps", () => {
    expect(() =>
      normalizeEndedCall(lucaplusProfile, { ...body, extra: true }, new Date()),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        { ...body, transcript: "", summary: "" },
        new Date(),
      ),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        { ...body, startedAt: "2026-08-25T03:00:00+00:00" },
        new Date(),
      ),
    ).toThrow();
  });
});
