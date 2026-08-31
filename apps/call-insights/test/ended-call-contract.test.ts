import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { normalizeEndedCall } from "../src/application/normalize-ended-call.js";
import { lucaplusProfile } from "./fixtures.js";

const FIXTURES = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../packages/contracts/ended-call/fixtures",
);

function loadFixture(name: string): unknown {
  return JSON.parse(readFileSync(join(FIXTURES, name), "utf8"));
}

describe("shared ended-call v1 fixtures", () => {
  it("accepts the valid yino fixture", () => {
    const body = loadFixture("valid-yino-ended-call.json");
    const event = normalizeEndedCall(
      lucaplusProfile,
      body,
      new Date("2026-08-31T10:05:00.000Z"),
    );
    expect(event.action).toBe("analyze");
    expect(event.call?.channel).toBe("yino");
    expect(event.call?.recordingUrl).toBeNull();
    expect(event.call?.durationSeconds).toBe(252);
  });

  it("rejects empty content, extra fields, and non-UTC timestamps", () => {
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        loadFixture("invalid-empty-content.json"),
        new Date(),
      ),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        loadFixture("invalid-extra-field.json"),
        new Date(),
      ),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        loadFixture("invalid-timestamp.json"),
        new Date(),
      ),
    ).toThrow();
  });
});
