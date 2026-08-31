import { describe, expect, it } from "vitest";
import { flattenContactInfo } from "../src/ai/flatten-contact-info.js";

describe("flattenContactInfo", () => {
  it("leaves strings unchanged", () => {
    expect(flattenContactInfo("demo@example.invalid")).toBe(
      "demo@example.invalid",
    );
  });

  it("flattens objects in UTF-16 key order", () => {
    expect(flattenContactInfo({
      phone: "+61 400 000 000",
      email: "demo@example.invalid",
    })).toBe("email: demo@example.invalid; phone: +61 400 000 000");
  });

  it("stringifies nested objects and arrays", () => {
    expect(flattenContactInfo({
      extra: { city: "Sydney" },
    })).toBe('extra: {"city":"Sydney"}');
  });

  it("joins arrays and stringifies primitives", () => {
    expect(flattenContactInfo(["a", 2, true])).toBe("a; 2; true");
    expect(flattenContactInfo(4)).toBe("4");
    expect(flattenContactInfo(false)).toBe("false");
  });

  it("turns empty, null, and undefined into an empty string", () => {
    expect(flattenContactInfo({})).toBe("");
    expect(flattenContactInfo(null)).toBe("");
    expect(flattenContactInfo(undefined)).toBe("");
  });
});
