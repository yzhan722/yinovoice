import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { lstat } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  renderCustomerReport,
  renderCustomerReportSubject,
  renderQualityReport,
  renderQualityReportSubject,
  renderRatingConfirmation,
  renderRatingSavedHtml,
} from "../src/reports/html.js";
import {
  ArtifactWriter,
  type ArtifactWriterDependencies,
} from "../src/reports/artifact-writer.js";
import {
  inpGroupProfile,
  lucaplusProfile,
  makeAnalysis,
  makeCall,
  makeQuality,
  tempDirectory,
} from "./fixtures.js";

const RATING_BASE = "http://127.0.0.1:3210";

function dataPngImageCount(html: string): number {
  return html.match(/<img\b[^>]*\bsrc="data:image\/png;base64,[A-Za-z0-9+/]+=*"[\s>]/gi)?.length ?? 0;
}

describe("reports", () => {
  it("uses n8n subjects for the customer and quality emails", () => {
    expect(renderCustomerReportSubject(makeAnalysis())).toBe(
      "Call Report for Demo Customer 2026-08-13 11:00 AEST",
    );
    expect(
      renderQualityReportSubject(lucaplusProfile, makeAnalysis(), makeQuality()),
    ).toBe("[质量分析] Luca AI 评分: 8/10 - Demo Customer");
    expect(
      renderQualityReportSubject(inpGroupProfile, makeAnalysis(), {
        ...makeQuality(),
        score: 7.5,
      }),
    ).toBe("[质量分析] INP AI 评分: 7.5/10 - Demo Customer");
    expect(
      renderCustomerReportSubject({
        ...makeAnalysis(),
        customerName: "A\r\nB",
        localCallTime: "C\nD",
      }),
    ).toBe("Call Report for A B C D");
  });

  it("escapes dynamic HTML and creates local rating links", () => {
    const call = { ...makeCall(), transcript: "<script>alert(1)</script>" };
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call,
      analysis: {
        ...makeAnalysis(),
        customerName: "<b>Injected</b>",
        formattedTranscript: "<script>alert(1)</script>",
      },
      ratingBaseUrl: RATING_BASE,
    });
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("&lt;b&gt;Injected&lt;/b&gt;");
    expect(html).toContain("call_id=call_demo_001");
    expect(html).toContain("profile=lucaplus");
    expect(html).toContain("AI Call Report");
    expect(html).toContain("How did your agent perform?");
    expect(html).toContain("Best regards,");
    expect(html).toContain("The Yino Digital Receptionist");
    expect(html).toContain("Scale Faster, Staff Lighter.");
    expect(html).toContain("www.yino.au");
    expect(html).toContain("#e4e84d");
    expect(html).toContain("Play recording");
    expect(html).toContain("invoice automation");
    expect(html).toContain("Customer asked about invoice automation.");
    expect(html).toContain("Avenir Next");
    expect(html).not.toContain("Palatino");
    expect(html).not.toContain("Fraunces");
    expect(html).not.toContain("Iowan");
    expect(html).not.toContain("font-style: italic");
    expect(html).not.toContain("Montserrat");
    expect(html).not.toContain("fonts.googleapis.com");
    expect(html).not.toContain("font/woff2");
    expect(html).not.toContain("★");
    expect(html).not.toContain("Poor");
    expect(html).not.toContain("Excellent");
    expect(html).not.toContain('method="post"');
    for (const score of [1, 2, 3, 4, 5]) {
      expect(html).toContain(
        `href="${RATING_BASE}/rating?score=${score}&amp;call_id=call_demo_001&amp;profile=lucaplus"`,
      );
    }
    expect(dataPngImageCount(html)).toBe(1);
    expect(html).not.toMatch(/<img\b[^>]*\bsrc="https?:/i);
    expect(html).not.toContain("n8n.cloud");
    expect(html).not.toContain("mailto:");
    expect(html).not.toContain("javascript:");
    expect(() =>
      renderCustomerReport({
        profile: lucaplusProfile,
        call,
        analysis: makeAnalysis(),
        ratingBaseUrl: "http://evil.example",
      }),
    ).toThrow(/public origin/i);
    expect(() =>
      renderCustomerReport({
        profile: lucaplusProfile,
        call,
        analysis: makeAnalysis(),
        ratingBaseUrl: "https://yinoagent.app.n8n.cloud",
      }),
    ).toThrow(/n8n\.cloud/);
  });

  it("uses readable system sans on rating capture and saved pages", () => {
    const capture = renderRatingConfirmation("lucaplus", "call_demo_001", 4);
    expect(capture).toContain("Saving rating");
    expect(capture).toContain('method="post"');
    expect(capture).toContain("yino-rate");
    expect(capture).toContain(".submit(");
    expect(capture).toContain("file:");
    expect(capture).not.toContain("Confirm rating");
    expect(capture).not.toContain(">Confirm<");
    expect(capture).not.toContain("Rating saved");
    expect(capture).toContain("Avenir Next");
    expect(capture).not.toContain("font/woff2");
    expect(capture).not.toContain("Fraunces");
    expect(capture).not.toContain("Outfit");
    expect(capture).not.toContain("font-style: italic");
    expect(capture).not.toContain("fonts.googleapis.com");
    const saved = renderRatingSavedHtml();
    expect(saved).toContain("Rating saved");
    expect(saved).toContain("Avenir Next");
    expect(saved).not.toContain("Fraunces");
    expect(saved).not.toContain("Outfit");
    expect(saved).not.toContain("font/woff2");
    expect(saved).toContain("You can close this page.");
  });

  it("puts a readable summary above topics and recording", () => {
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      ratingBaseUrl: RATING_BASE,
    });
    const summaryAt = html.indexOf(">Summary<");
    const topicsAt = html.indexOf(">Topics<");
    const recordingAt = html.indexOf("Play recording");
    const transcriptAt = html.indexOf(">Transcript<");
    expect(summaryAt).toBeGreaterThan(0);
    expect(topicsAt).toBeGreaterThan(summaryAt);
    expect(recordingAt).toBeGreaterThan(topicsAt);
    expect(transcriptAt).toBeGreaterThan(recordingAt);
    expect(html).toContain("border-left: 3px solid #e4e84d");
    expect(html).toContain("Customer asked about invoice automation.");
  });

  it("centers the customer-report logo and AI Call Report eyebrow", () => {
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      ratingBaseUrl: RATING_BASE,
    });
    expect(html).toContain('<td align="center" style="padding-bottom: 18px;">');
    expect(html).toContain("margin: 0 auto");
    expect(html).toMatch(/text-align: center;[^"]*">AI Call Report</);
  });

  it("links recordings through the stable local /recording route instead of expiring VAPI URLs", () => {
    const recordingHref = `${RATING_BASE}/recording?call_id=call_demo_001&amp;profile=lucaplus`;
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call: { ...makeCall(), recordingUrl: "javascript:alert(1)" },
      analysis: makeAnalysis(),
      ratingBaseUrl: RATING_BASE,
    });
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("alert(1)");
    expect(html).toContain("Play recording");
    expect(html).toContain(`href="${recordingHref}"`);
    expect(html).not.toContain(`>${recordingHref}<`);

    const httpHtml = renderCustomerReport({
      profile: lucaplusProfile,
      call: { ...makeCall(), recordingUrl: "http://example.invalid/recordings/demo.mp3" },
      analysis: makeAnalysis(),
      ratingBaseUrl: RATING_BASE,
    });
    expect(httpHtml).not.toContain("http://example.invalid/recordings/demo.mp3");
    expect(httpHtml).toContain(`href="${recordingHref}"`);

    const unsignedHtml = renderCustomerReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      ratingBaseUrl: RATING_BASE,
    });
    expect(unsignedHtml).not.toContain("https://example.invalid/recordings/demo.mp3");
    expect(unsignedHtml).toContain("Play recording");
    expect(unsignedHtml).toContain(`href="${recordingHref}"`);

    const presigned =
      "https://recordings.example.invalid/mono.wav?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc&X-Amz-Expires=1800";
    const publicOrigin = "https://calls.example.invalid";
    const presignedHtml = renderCustomerReport({
      profile: lucaplusProfile,
      call: { ...makeCall(), recordingUrl: presigned },
      analysis: makeAnalysis(),
      ratingBaseUrl: publicOrigin,
    });
    expect(presignedHtml).not.toContain("X-Amz-Signature");
    expect(presignedHtml).not.toContain("recordings.example.invalid");
    expect(presignedHtml).toContain(
      `href="${publicOrigin}/recording?call_id=call_demo_001&amp;profile=lucaplus"`,
    );
    expect(presignedHtml).toContain(
      `href="${publicOrigin}/rating?score=5&amp;call_id=call_demo_001&amp;profile=lucaplus"`,
    );
    expect(presignedHtml).toContain("Play recording");
  });

  it("hides empty summary, missing recording, and unknown contact", () => {
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call: {
        ...makeCall(),
        summary: "  ",
        recordingUrl: null,
      },
      analysis: {
        ...makeAnalysis(),
        contactInfo: "Not mentioned",
        formattedTranscript:
          "user: hello there\nassistant: I can help with that.",
      },
      ratingBaseUrl: RATING_BASE,
    });
    expect(html).not.toContain("Play recording");
    expect(html).not.toContain("Summary");
    expect(html).not.toContain("Not mentioned");
    expect(html).toContain("hello there");
    expect(html).toContain("I can help with that.");
    expect(html).toContain("2 min 30s");
  });

  it("escapes quality report fields and includes prompt recommendation", () => {
    const html = renderQualityReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: { ...makeAnalysis(), customerName: "<img src=x>" },
      quality: {
        ...makeQuality(),
        strengths: ["<script>steal()</script>"],
        shouldUpdatePrompt: true,
      },
    });
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;steal()&lt;/script&gt;");
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).toContain("8/10");
    expect(html).toContain("📊 AI客服质量分析报告");
    expect(html).toContain("✅ 优点");
    expect(html).toContain("❌ 问题");
    expect(html).toContain("💡 改进建议");
    expect(html).toContain("⚠️ 建议更新Prompt");
    expect(html).toContain("Yino AI Quality Monitor");
    expect(html).toContain("#d4edda");
    expect(html).toContain("Solid call with minor follow-up gap.");
    expect(html).toContain("Confirm next steps");
    expect(html).not.toContain("mailto:");
    expect(html).not.toMatch(/<img\b/i);
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("n8n.cloud");
  });

  it("atomically writes exactly four artifacts", async () => {
    const root = tempDirectory();
    const writer = new ArtifactWriter(root.path);
    const result = await writer.write({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      quality: makeQuality(),
      provider: "mock",
      generatedAt: "2026-08-13T04:00:00Z",
    });
    expect(result.files.sort()).toEqual([
      "call.json",
      "customer-report.html",
      "manifest.json",
      "quality-report.html",
    ]);
    expect(root.findFiles("*.tmp")).toEqual([]);
    const directory = join(root.path, "lucaplus", "call_demo_001");
    expect(result.directory).toBe(directory);
    expect(readdirSync(directory).sort()).toEqual([
      "call.json",
      "customer-report.html",
      "manifest.json",
      "quality-report.html",
    ]);

    const manifest = JSON.parse(readFileSync(join(directory, "manifest.json"), "utf8"));
    expect(manifest.schemaVersion).toBe(1);
    expect(manifest.provider).toBe("mock");
    expect(manifest.generatedAt).toBe("2026-08-13T04:00:00Z");
    expect(manifest.profile).toBe("lucaplus");
    expect(manifest.callId).toBe("call_demo_001");
    expect(manifest.files).toEqual([
      "call.json",
      "customer-report.html",
      "quality-report.html",
      "manifest.json",
    ]);
    expect(manifest.legacyCustomerReportRecipients).toEqual(
      lucaplusProfile.legacyCustomerReportRecipients,
    );
    expect(manifest.legacyQualityReportRecipients).toEqual(
      lucaplusProfile.legacyQualityReportRecipients,
    );
    expect(manifest.outboundMail).toEqual({
      dispatch: "disabled",
      customer: {
        subject: "Call Report for Demo Customer 2026-08-13 11:00 AEST",
        recipientRoles: lucaplusProfile.legacyCustomerReportRecipients,
        htmlFile: "customer-report.html",
      },
      quality: {
        subject: "[质量分析] Luca AI 评分: 8/10 - Demo Customer",
        recipientRoles: lucaplusProfile.legacyQualityReportRecipients,
        htmlFile: "quality-report.html",
      },
    });
    expect(JSON.stringify(manifest)).not.toContain("@");
    expect(JSON.stringify(manifest)).not.toMatch(/api[_-]?key/i);

    const customerHtml = readFileSync(join(directory, "customer-report.html"), "utf8");
    const qualityHtml = readFileSync(join(directory, "quality-report.html"), "utf8");
    expect(customerHtml).toContain(
      `${RATING_BASE}/recording?call_id=call_demo_001&amp;profile=lucaplus`,
    );
    expect(customerHtml).not.toContain("X-Amz-Signature");
    expect(customerHtml).toContain("AI Call Report");
    expect(qualityHtml).toContain("📊 AI客服质量分析报告");
    expect(dataPngImageCount(customerHtml)).toBe(1);
    expect(qualityHtml).not.toMatch(/<img\b/i);
    for (const html of [customerHtml, qualityHtml]) {
      expect(html).not.toContain("<script>");
      expect(html).not.toContain("mailto:");
      expect(html).not.toMatch(/<img\b[^>]*\bsrc="https?:/i);
      expect(html).not.toContain("javascript:");
      expect(html).not.toContain("n8n.cloud");
    }
    root.close();
  });

  it("removes writer-owned crash leftovers before publishing a new manifest", async () => {
    const root = tempDirectory();
    const directory = join(root.path, "lucaplus", "call_demo_001");
    const ownedLeftovers = [
      "call.json.11111111-1111-4111-8111-111111111111.tmp",
      "manifest.json.22222222-2222-4222-8222-222222222222.tmp",
    ];
    const unrelatedTemp = "operator-note.tmp";
    mkdirSync(directory, { recursive: true });
    for (const filename of ownedLeftovers) {
      writeFileSync(join(directory, filename), "crash-leftover", "utf8");
    }
    writeFileSync(join(directory, unrelatedTemp), "leave-me", "utf8");

    try {
      await new ArtifactWriter(root.path).write({
        profile: lucaplusProfile,
        call: makeCall(),
        analysis: makeAnalysis(),
        quality: makeQuality(),
        provider: "mock",
        generatedAt: "2026-08-13T04:00:00Z",
      });

      expect(existsSync(join(directory, "manifest.json"))).toBe(true);
      for (const filename of ownedLeftovers) {
        expect(existsSync(join(directory, filename))).toBe(false);
      }
      expect(readFileSync(join(directory, unrelatedTemp), "utf8")).toBe("leave-me");
      expect(
        readdirSync(directory).filter((name) =>
          /^(?:call\.json|customer-report\.html|quality-report\.html|manifest\.json)\.[0-9a-f-]+\.tmp$/i
            .test(name)),
      ).toEqual([]);
    } finally {
      root.close();
    }
  });

  it("writes only non-address role labels for both default Profiles", async () => {
    const root = tempDirectory();
    const expectedLabels = {
      lucaplus: {
        customer: [
          "customer-report-primary",
          "customer-report-cc",
          "customer-report-support",
        ],
        quality: ["quality-report-internal"],
      },
      "inp-group": {
        customer: ["customer-report-primary", "customer-report-cc"],
        quality: ["quality-report-internal"],
      },
    } as const;

    try {
      for (const profile of [lucaplusProfile, inpGroupProfile]) {
        await new ArtifactWriter(root.path).write({
          profile,
          call: makeCall({ profile: profile.slug }),
          analysis: makeAnalysis(),
          quality: makeQuality(),
          provider: "mock",
          generatedAt: "2026-08-13T04:00:00Z",
        });
        const directory = join(root.path, profile.slug, "call_demo_001");
        const manifest = JSON.parse(
          readFileSync(join(directory, "manifest.json"), "utf8"),
        );
        expect(manifest.legacyCustomerReportRecipients).toEqual(
          expectedLabels[profile.slug as keyof typeof expectedLabels].customer,
        );
        expect(manifest.legacyQualityReportRecipients).toEqual(
          expectedLabels[profile.slug as keyof typeof expectedLabels].quality,
        );
        expect(JSON.stringify(manifest)).not.toContain("@");

        const generatedText = readdirSync(directory)
          .map((filename) => readFileSync(join(directory, filename), "utf8"))
          .join("\n");
        const emailLikeValues =
          generatedText.match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) ?? [];
        expect(emailLikeValues.every((value) => value.endsWith(".invalid"))).toBe(true);
      }
    } finally {
      root.close();
    }
  });

  it("removes an old manifest before a rewrite can fail", async () => {
    const root = tempDirectory();
    const input = {
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      quality: makeQuality(),
      provider: "mock" as const,
      generatedAt: "2026-08-13T04:00:00Z",
    };
    const manifestPath = join(
      root.path,
      "lucaplus",
      "call_demo_001",
      "manifest.json",
    );
    try {
      await new ArtifactWriter(root.path).write(input);
      expect(existsSync(manifestPath)).toBe(true);

      let rewriteStarted = false;
      const crashingWriter = new ArtifactWriter(root.path, {
        beforeFileWrite(_directory: string, filename: string): void {
          if (filename !== "call.json") {
            return;
          }
          rewriteStarted = true;
          if (existsSync(manifestPath)) {
            throw new Error("stale manifest survived into rewrite");
          }
          throw new Error("simulated crash after manifest invalidation");
        },
      });

      await expect(
        crashingWriter.write({
          ...input,
          generatedAt: "2026-08-13T05:00:00Z",
        }),
      ).rejects.toThrow("simulated crash after manifest invalidation");
      expect(rewriteStarted).toBe(true);
      expect(existsSync(manifestPath)).toBe(false);
    } finally {
      root.close();
    }
  });

  it("rejects path separators and traversal in profile and call id", async () => {
    const root = tempDirectory();
    const writer = new ArtifactWriter(root.path);
    const base = {
      analysis: makeAnalysis(),
      quality: makeQuality(),
      provider: "mock" as const,
      generatedAt: "2026-08-13T04:00:00Z",
    };
    const escapedSibling = join(root.path, "..", "evil-escape");

    await expect(
      writer.write({
        ...base,
        profile: { ...lucaplusProfile, slug: "../evil-escape" },
        call: makeCall(),
      }),
    ).rejects.toThrow(/invalid|separator|traversal/i);
    expect(existsSync(escapedSibling)).toBe(false);

    await expect(
      writer.write({
        ...base,
        profile: lucaplusProfile,
        call: makeCall({ callId: "foo/bar" }),
      }),
    ).rejects.toThrow(/invalid|separator|traversal/i);

    await expect(
      writer.write({
        ...base,
        profile: lucaplusProfile,
        call: makeCall({ callId: "foo\\bar" }),
      }),
    ).rejects.toThrow(/invalid|separator|traversal/i);

    await expect(
      writer.write({
        ...base,
        profile: lucaplusProfile,
        call: makeCall({ callId: ".." }),
      }),
    ).rejects.toThrow(/invalid|separator|traversal/i);

    expect(root.findFiles(".json")).toEqual([]);
    expect(root.findFiles(".html")).toEqual([]);
    expect(existsSync(escapedSibling)).toBe(false);
    root.close();
  });

  it("removes temporary files and omits manifest after a write failure", async () => {
    const root = tempDirectory();
    const dest = join(root.path, "lucaplus", "call_demo_001");
    mkdirSync(join(dest, "customer-report.html"), { recursive: true });
    const writer = new ArtifactWriter(root.path);
    await expect(
      writer.write({
        profile: lucaplusProfile,
        call: makeCall(),
        analysis: makeAnalysis(),
        quality: makeQuality(),
        provider: "mock",
        generatedAt: "2026-08-13T04:00:00Z",
      }),
    ).rejects.toThrow();
    expect(root.findFiles("*.tmp")).toEqual([]);
    expect(existsSync(join(dest, "manifest.json"))).toBe(false);
    expect(existsSync(join(dest, "quality-report.html"))).toBe(false);
    root.close();
  });

  it("rejects a real directory link ancestor without deleting or writing outside root", async () => {
    const root = tempDirectory();
    const outside = tempDirectory();
    const artifactRoot = join(root.path, "artifacts");
    const linkedProfile = join(artifactRoot, "lucaplus");
    const outsideCall = join(outside.path, "call_demo_001");
    mkdirSync(artifactRoot, { recursive: true });
    mkdirSync(outsideCall, { recursive: true });
    const outsideManifest = join(outsideCall, "manifest.json");
    writeFileSync(outsideManifest, "outside-marker", "utf8");

    let linkCreated = false;
    try {
      symlinkSync(outside.path, linkedProfile, process.platform === "win32" ? "junction" : "dir");
      linkCreated = true;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "EPERM" && code !== "EACCES" && code !== "ENOTSUP") {
        throw error;
      }
    }

    try {
      if (!linkCreated) {
        return;
      }
      const writer = new ArtifactWriter(artifactRoot);
      await expect(
        writer.write({
          profile: lucaplusProfile,
          call: makeCall(),
          analysis: makeAnalysis(),
          quality: makeQuality(),
          provider: "mock",
          generatedAt: "2026-08-13T04:00:00Z",
        }),
      ).rejects.toThrow(/link|contain|physical|reparse/i);
      expect(readFileSync(outsideManifest, "utf8")).toBe("outside-marker");
      expect(readdirSync(outsideCall)).toEqual(["manifest.json"]);
    } finally {
      root.close();
      outside.close();
    }
  });

  it("uses the filesystem seam to reject a reparse ancestor before any write", async () => {
    const root = tempDirectory();
    const artifactRoot = join(root.path, "artifacts");
    const profilePath = join(artifactRoot, "lucaplus");
    mkdirSync(profilePath, { recursive: true });
    let beforeFileWriteCalls = 0;
    const dependencies = {
      beforeFileWrite(): void {
        beforeFileWriteCalls += 1;
      },
      lstat: async (path: string) => {
        const stats = await lstat(path);
        return path === profilePath
          ? ({
              ...stats,
              isSymbolicLink: () => true,
            } as Awaited<ReturnType<typeof lstat>>)
          : stats;
      },
    } as unknown as ArtifactWriterDependencies;

    try {
      await expect(
        new ArtifactWriter(artifactRoot, dependencies).write({
          profile: lucaplusProfile,
          call: makeCall(),
          analysis: makeAnalysis(),
          quality: makeQuality(),
          provider: "mock",
          generatedAt: "2026-08-13T04:00:00Z",
        }),
      ).rejects.toThrow(/link|contain|physical|reparse/i);
      expect(beforeFileWriteCalls).toBe(0);
      expect(readdirSync(profilePath)).toEqual([]);
    } finally {
      root.close();
    }
  });

  it.each([
    {
      name: "partial",
      filenames: [
        "call.json",
        "customer-report.html",
        "quality-report.html",
      ],
    },
    {
      name: "extra",
      filenames: [
        "call.json",
        "customer-report.html",
        "quality-report.html",
        "manifest.json",
        "unexpected.txt",
      ],
    },
  ])("rejects a $name artifact set during discovery", async ({ filenames }) => {
    const root = tempDirectory();
    const directory = join(root.path, "lucaplus", "call_demo_001");
    mkdirSync(directory, { recursive: true });
    for (const filename of filenames) {
      writeFileSync(join(directory, filename), filename, "utf8");
    }

    try {
      await expect(
        new ArtifactWriter(root.path).listFiles("lucaplus", "call_demo_001"),
      ).rejects.toThrow(/artifact.*discovery|artifact.*set/i);
    } finally {
      root.close();
    }
  });

  it("rejects a symlink-like artifact through the filesystem seam", async () => {
    const root = tempDirectory();
    const directory = join(root.path, "lucaplus", "call_demo_001");
    const linkedFile = join(directory, "manifest.json");
    mkdirSync(directory, { recursive: true });
    for (const filename of [
      "call.json",
      "customer-report.html",
      "quality-report.html",
      "manifest.json",
    ]) {
      writeFileSync(join(directory, filename), filename, "utf8");
    }
    const dependencies = {
      lstat: async (path: string) => {
        const stats = await lstat(path);
        return path === linkedFile
          ? ({
              ...stats,
              isSymbolicLink: () => true,
            } as Awaited<ReturnType<typeof lstat>>)
          : stats;
      },
    } as unknown as ArtifactWriterDependencies;

    try {
      await expect(
        new ArtifactWriter(root.path, dependencies).listFiles(
          "lucaplus",
          "call_demo_001",
        ),
      ).rejects.toThrow(/artifact.*discovery|artifact.*physical/i);
    } finally {
      root.close();
    }
  });
});
