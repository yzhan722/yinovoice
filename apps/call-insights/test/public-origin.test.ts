import { describe, expect, it } from "vitest";
import { assertPublicOrigin } from "../src/domain/public-origin.js";

describe("assertPublicOrigin", () => {
  it("accepts the local rating origin and https origins that are not n8n.cloud", () => {
    expect(assertPublicOrigin("http://127.0.0.1:3210")).toBe("http://127.0.0.1:3210");
    expect(assertPublicOrigin("http://127.0.0.1:3210/")).toBe("http://127.0.0.1:3210");
    expect(assertPublicOrigin("https://calls.example.invalid")).toBe(
      "https://calls.example.invalid",
    );
    expect(assertPublicOrigin("https://calls.example.invalid/")).toBe(
      "https://calls.example.invalid",
    );
  });

  it("rejects n8n.cloud, non-loopback http, credentials, and paths", () => {
    expect(() => assertPublicOrigin("https://evil.example")).not.toThrow();
    expect(() => assertPublicOrigin("http://evil.example")).toThrow(/public origin/i);
    expect(() => assertPublicOrigin("https://yinoagent.app.n8n.cloud")).toThrow(
      /n8n\.cloud/,
    );
    expect(() => assertPublicOrigin("https://n8n.cloud")).toThrow(/n8n\.cloud/);
    expect(() => assertPublicOrigin("https://user:pass@calls.example.invalid")).toThrow(
      /public origin/i,
    );
    expect(() => assertPublicOrigin("https://calls.example.invalid/v1")).toThrow(
      /public origin/i,
    );
    expect(() => assertPublicOrigin("javascript:alert(1)")).toThrow(/public origin/i);
  });
});
