import { copyFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { RuntimeProfileSource } from "../src/profiles/runtime-config.js";
import { tempDirectory } from "./fixtures.js";

const BUNDLED = fileURLToPath(new URL("../src/profiles", import.meta.url));

function seedBundled(directory: string): void {
  copyFileSync(join(BUNDLED, "lucaplus.json"), join(directory, "lucaplus.json"));
  copyFileSync(join(BUNDLED, "inp-group.json"), join(directory, "inp-group.json"));
}

const THIRD_PROFILE = {
  slug: "acme-demo",
  displayName: "Acme Demo",
  assistantName: "Acme AI",
  vapiAssistantId: "00000000-0000-4000-8000-000000000001",
  timezone: "Australia/Sydney",
  brandName: "Acme Demo",
  analysisLanguage: "en",
  qualityLanguage: "zh",
  companyAliases: ["Acme Demo"],
  legacyCustomerReportRecipients: ["customer-report-primary"],
  legacyQualityReportRecipients: ["quality-report-internal"],
};

describe("RuntimeProfileSource", () => {
  it("loads bundled-shaped profiles from a directory", async () => {
    const root = tempDirectory();
    try {
      seedBundled(root.path);
      const source = new RuntimeProfileSource({
        directory: root.path,
        clock: () => new Date("2026-08-25T00:00:00.000Z"),
      });
      expect(await source.load()).toBe(true);
      expect(source.registry.get("lucaplus")?.displayName).toBe("LucaPlus");
      expect(source.registry.get("inp-group")?.displayName).toBe("INP Group");
      expect(source.getHealth()).toEqual({
        status: "ok",
        profileCount: 2,
        lastLoadedAt: "2026-08-25T00:00:00.000Z",
        lastErrorAt: null,
      });
    } finally {
      root.close();
    }
  });

  it("picks up a third profile file without a code import", async () => {
    const root = tempDirectory();
    try {
      seedBundled(root.path);
      const source = new RuntimeProfileSource({
        directory: root.path,
        clock: () => new Date("2026-08-25T00:00:00.000Z"),
      });
      expect(await source.load()).toBe(true);
      writeFileSync(
        join(root.path, "acme-demo.json"),
        `${JSON.stringify(THIRD_PROFILE, null, 2)}\n`,
        "utf8",
      );
      expect(await source.load()).toBe(true);
      expect(source.registry.get("acme-demo")?.brandName).toBe("Acme Demo");
      expect(source.registry.list()).toHaveLength(3);
    } finally {
      root.close();
    }
  });

  it("keeps the last good snapshot when a new file is invalid", async () => {
    const root = tempDirectory();
    try {
      seedBundled(root.path);
      let now = new Date("2026-08-25T00:00:00.000Z");
      const source = new RuntimeProfileSource({
        directory: root.path,
        clock: () => now,
      });
      expect(await source.load()).toBe(true);
      writeFileSync(join(root.path, "acme-demo.json"), "{not json", "utf8");
      now = new Date("2026-08-25T00:00:03.000Z");
      expect(await source.load()).toBe(false);
      expect(source.registry.get("acme-demo")).toBeNull();
      expect(source.registry.list().map((profile) => profile.slug)).toEqual([
        "inp-group",
        "lucaplus",
      ]);
      expect(source.getHealth()).toEqual({
        status: "degraded",
        profileCount: 2,
        lastLoadedAt: "2026-08-25T00:00:00.000Z",
        lastErrorAt: "2026-08-25T00:00:03.000Z",
      });
    } finally {
      root.close();
    }
  });

  it("rejects a file whose slug does not match its name", async () => {
    const root = tempDirectory();
    try {
      seedBundled(root.path);
      const source = new RuntimeProfileSource({
        directory: root.path,
        clock: () => new Date("2026-08-25T00:00:00.000Z"),
      });
      expect(await source.load()).toBe(true);
      writeFileSync(
        join(root.path, "acme-demo.json"),
        `${JSON.stringify({ ...THIRD_PROFILE, slug: "other-slug" }, null, 2)}\n`,
        "utf8",
      );
      expect(await source.load()).toBe(false);
      expect(source.registry.get("acme-demo")).toBeNull();
      expect(source.registry.get("other-slug")).toBeNull();
    } finally {
      root.close();
    }
  });
});
