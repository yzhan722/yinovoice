import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_TRIAL_CALL_ID,
  LUCAPLUS_MIA_ASSISTANT_ID,
  TrialError,
} from "../tools/pull-lucaplus-call.js";
import {
  TRIAL_EMAIL_FROM,
  TRIAL_EMAIL_TO,
  TRIAL_RECORDING_ATTACHED_NOTE,
  assertTrialEmailEnvironment,
  generateLucaPlusTrialReports,
  isSafeTrialRecordingAttachment,
  isSafeTrialReportHtml,
  sendTrialEmail,
  type GeneratedTrialReport,
  type TrialEmailDependencies,
  type TrialMailMessage,
  type TrialMailTransport,
  type TrialReportDependencies,
} from "../tools/send-trial-email.js";

const CALL_ID = DEFAULT_TRIAL_CALL_ID;
const TEST_PASSWORD = "test-password";
const CUSTOMER_HTML = "<h1>LucaPlus</h1><p>+61400000000 asked for a quote.</p>";
const QUALITY_HTML = "<h1>quality</h1><p>Score: 8</p>";
const CUSTOMER_SUBJECT = "Call Report for Demo Customer 2026-08-13 11:00 AEST";
const QUALITY_SUBJECT = "[质量分析] Luca AI 评分: 8/10 - Demo Customer";
const TRIAL_MESSAGES = [
  { subject: CUSTOMER_SUBJECT, html: CUSTOMER_HTML },
  { subject: QUALITY_SUBJECT, html: QUALITY_HTML },
] as const;
const PRESIGNED_MONO =
  "https://recordings.example.invalid/mono.wav?X-Amz-Signature=test";
const WAV_BYTES = Buffer.from("RIFF\0\0\0\0WAVEfmt ");
const RECORDING_ATTACHMENT = {
  filename: "recording.wav",
  content: WAV_BYTES,
  contentType: "audio/wav",
} as const;

function confirmedEnvironment(
  overrides: NodeJS.ProcessEnv = {},
): NodeJS.ProcessEnv {
  return {
    REAL_EMAIL_TEST_CONFIRM: "SEND 867542127@qq.com",
    GMAIL_TEST_APP_PASSWORD: TEST_PASSWORD,
    VAPI_API_KEY: "vapi-test-key",
    AI_PROVIDER: "deepseek",
    DEEPSEEK_API_KEY: "sk-test-deepseek",
    ...overrides,
  };
}

function vapiCall(overrides: Record<string, unknown> = {}) {
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
      variableValues: {
        "phoneNumber.twilioAuthToken": "secret-token",
      },
    },
    ...overrides,
  };
}

function createEmailHarness() {
  const verify = vi.fn(async (): Promise<unknown> => undefined);
  const sendMail = vi.fn(
    async (_message: TrialMailMessage): Promise<{ messageId?: string }> => ({
      messageId: "test-message-id",
    }),
  );
  const close = vi.fn((): void => undefined);
  const cleanup = vi.fn(async (): Promise<void> => undefined);
  const createTransport = vi.fn(
    (_options: unknown): TrialMailTransport => ({ verify, sendMail, close }),
  );
  const generateReports = vi.fn(
    async (): Promise<GeneratedTrialReport> => ({
      messages: [...TRIAL_MESSAGES],
      cleanup,
    }),
  );
  const dependencies = {
    createTransport,
    generateReports,
  } satisfies TrialEmailDependencies;
  return {
    dependencies,
    createTransport,
    generateReports,
    verify,
    sendMail,
    close,
    cleanup,
  };
}

async function expectTrialError(
  operation: () => Promise<unknown>,
  code: TrialError["code"],
  forbiddenText: readonly string[] = [],
): Promise<void> {
  try {
    await operation();
    expect.unreachable();
  } catch (error) {
    expect(error).toBeInstanceOf(TrialError);
    expect(error).toMatchObject({ code, message: code });
    const visible = `${String(error)}\n${(error as Error).stack ?? ""}`;
    for (const text of forbiddenText) {
      expect(visible).not.toContain(text);
    }
  }
}

describe("assertTrialEmailEnvironment", () => {
  it("rejects the wrong confirmation before any other check", () => {
    expect(() =>
      assertTrialEmailEnvironment(
        confirmedEnvironment({ REAL_EMAIL_TEST_CONFIRM: "wrong" }),
      ),
    ).toThrow(expect.objectContaining({ code: "trial_not_confirmed" }));
  });

  it.each(["GMAIL_TEST_APP_PASSWORD", "VAPI_API_KEY", "DEEPSEEK_API_KEY"])(
    "rejects a missing %s",
    (key) => {
      expect(() =>
        assertTrialEmailEnvironment(confirmedEnvironment({ [key]: "" })),
      ).toThrow(expect.objectContaining({ code: "trial_credentials_missing" }));
    },
  );

  it("rejects a provider other than deepseek", () => {
    expect(() =>
      assertTrialEmailEnvironment(confirmedEnvironment({ AI_PROVIDER: "mock" })),
    ).toThrow(expect.objectContaining({ code: "trial_credentials_missing" }));
  });
});

describe("isSafeTrialReportHtml", () => {
  it("allows phones and local rating links", () => {
    expect(
      isSafeTrialReportHtml(
        `${CUSTOMER_HTML}<a href="http://127.0.0.1:3210/rating?score=5&call_id=${CALL_ID}&profile=lucaplus">Rate 5</a>`,
      ),
    ).toBe(true);
  });

  it("rejects customer-domain mailto links and leaked secrets", () => {
    expect(
      isSafeTrialReportHtml('<a href="mailto:ray@lucaplus.com">x</a>'),
    ).toBe(false);
    expect(isSafeTrialReportHtml("pinData")).toBe(false);
    expect(isSafeTrialReportHtml("https://yinoagent.app.n8n.cloud/webhook/x")).toBe(
      false,
    );
    expect(isSafeTrialReportHtml("sk-live-secret")).toBe(false);
    expect(isSafeTrialReportHtml("VAPI_API_KEY")).toBe(false);
  });
});

describe("isSafeTrialRecordingAttachment", () => {
  it("accepts a bounded WAV payload and rejects other shapes", () => {
    expect(isSafeTrialRecordingAttachment(RECORDING_ATTACHMENT)).toBe(true);
    expect(
      isSafeTrialRecordingAttachment({
        ...RECORDING_ATTACHMENT,
        filename: "secret.wav",
      }),
    ).toBe(false);
    expect(
      isSafeTrialRecordingAttachment({
        ...RECORDING_ATTACHMENT,
        contentType: "application/octet-stream",
      }),
    ).toBe(false);
    expect(
      isSafeTrialRecordingAttachment({
        ...RECORDING_ATTACHMENT,
        content: Buffer.from("not-a-wav"),
      }),
    ).toBe(false);
    expect(
      isSafeTrialRecordingAttachment({
        ...RECORDING_ATTACHMENT,
        path: "https://example.invalid/rec.wav",
      }),
    ).toBe(false);
  });
});

describe("generateLucaPlusTrialReports", () => {
  it("maps a LucaPlus call and never forwards Twilio secrets into analysis or HTML", async () => {
    const fetchFn = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify(vapiCall()), { status: 200 }),
    );
    const analyzeEnvelope = vi.fn(
      async (envelope: unknown, paths: { envelopePath: string }) => {
        const { readFile } = await import("node:fs/promises");
        const written = await readFile(paths.envelopePath, "utf8");
        expect(written).not.toContain("secret-token");
        expect(JSON.parse(written)).toEqual(envelope);
        expect(JSON.stringify(envelope)).not.toContain("secret-token");
        return {
          customerHtml: CUSTOMER_HTML,
          qualityHtml: QUALITY_HTML,
          customerName: "Demo Customer",
          localCallTime: "2026-08-13 11:00 AEST",
          score: 8,
        };
      },
    );
    const dependencies = {
      fetchFn,
      analyzeEnvelope,
    } satisfies TrialReportDependencies;

    const report = await generateLucaPlusTrialReports(
      confirmedEnvironment(),
      dependencies,
    );
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(String(fetchFn.mock.calls[0]?.[0])).toBe(
      `https://api.vapi.ai/call/${CALL_ID}`,
    );
    expect(report.messages).toEqual([
      { subject: CUSTOMER_SUBJECT, html: CUSTOMER_HTML },
      { subject: QUALITY_SUBJECT, html: QUALITY_HTML },
    ]);
    expect(report.recordingAttachment).toBeUndefined();
    expect(report.messages.some((message) => message.html.includes("secret-token"))).toBe(
      false,
    );
    expect(analyzeEnvelope).toHaveBeenCalledTimes(1);
    await report.cleanup();
  });

  it("rejects a non-LucaPlus assistant before analysis", async () => {
    const fetchFn = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(
          JSON.stringify(
            vapiCall({ assistantId: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
          ),
          { status: 200 },
        ),
    );
    const analyzeEnvelope = vi.fn();
    await expectTrialError(
      () =>
        generateLucaPlusTrialReports(confirmedEnvironment(), {
          fetchFn,
          analyzeEnvelope,
        }),
      "trial_call_not_lucaplus",
    );
    expect(analyzeEnvelope).not.toHaveBeenCalled();
  });

  it("downloads the presigned WAV after mapping and never fetches it with the VAPI bearer key", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === `https://api.vapi.ai/call/${CALL_ID}`) {
        return new Response(
          JSON.stringify(
            vapiCall({
              artifact: {
                presignedMonoUrl: PRESIGNED_MONO,
                recordingUrl: "https://example.invalid/artifact.wav",
                variableValues: {
                  "phoneNumber.twilioAuthToken": "secret-token",
                },
              },
            }),
          ),
          { status: 200 },
        );
      }
      if (url === PRESIGNED_MONO) {
        expect(init?.headers).toBeUndefined();
        return new Response(WAV_BYTES, {
          status: 200,
          headers: { "content-type": "audio/wav" },
        });
      }
      return new Response("unexpected", { status: 500 });
    });
    const analyzeEnvelope = vi.fn(async () => ({
      customerHtml: CUSTOMER_HTML,
      qualityHtml: QUALITY_HTML,
      customerName: "Demo Customer",
      localCallTime: "2026-08-13 11:00 AEST",
      score: 8,
    }));

    const report = await generateLucaPlusTrialReports(confirmedEnvironment(), {
      fetchFn: fetchFn as unknown as typeof fetch,
      analyzeEnvelope,
    });
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(String(fetchFn.mock.calls[1]?.[0])).toBe(PRESIGNED_MONO);
    expect(report.recordingAttachment).toEqual(RECORDING_ATTACHMENT);
    expect(report.messages[0]?.html).toContain(TRIAL_RECORDING_ATTACHED_NOTE);
    expect(JSON.stringify(report.messages)).not.toContain("secret-token");
    await report.cleanup();
  });
});

describe("sendTrialEmail", () => {
  it("fails before work without the exact confirmation", async () => {
    const harness = createEmailHarness();
    await expectTrialError(
      () =>
        sendTrialEmail(
          confirmedEnvironment({ REAL_EMAIL_TEST_CONFIRM: "wrong" }),
          harness.dependencies,
        ),
      "trial_not_confirmed",
    );
    expect(harness.generateReports).not.toHaveBeenCalled();
    expect(harness.createTransport).not.toHaveBeenCalled();
  });

  it("sends the n8n customer and quality mails with the fixed envelope and no copies", async () => {
    const harness = createEmailHarness();
    const result = await sendTrialEmail(
      confirmedEnvironment(),
      harness.dependencies,
    );
    expect(result).toEqual({ status: "sent", messageId: "test-message-id" });
    expect(harness.createTransport).toHaveBeenCalledTimes(1);
    expect(harness.verify).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).toHaveBeenCalledTimes(2);
    expect(harness.sendMail.mock.calls.map((call) => call[0])).toEqual([
      {
        from: TRIAL_EMAIL_FROM,
        to: TRIAL_EMAIL_TO,
        subject: CUSTOMER_SUBJECT,
        html: CUSTOMER_HTML,
      },
      {
        from: TRIAL_EMAIL_FROM,
        to: TRIAL_EMAIL_TO,
        subject: QUALITY_SUBJECT,
        html: QUALITY_HTML,
      },
    ]);
    for (const message of harness.sendMail.mock.calls.map((call) => call[0])) {
      expect(message).not.toHaveProperty("cc");
      expect(message).not.toHaveProperty("bcc");
      expect(message).not.toHaveProperty("replyTo");
      expect(message).not.toHaveProperty("attachments");
    }
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("attaches the WAV only to the customer mail", async () => {
    const harness = createEmailHarness();
    harness.generateReports.mockResolvedValueOnce({
      messages: [
        {
          subject: CUSTOMER_SUBJECT,
          html: `${CUSTOMER_HTML}\n<p>${TRIAL_RECORDING_ATTACHED_NOTE}</p>`,
        },
        { subject: QUALITY_SUBJECT, html: QUALITY_HTML },
      ],
      recordingAttachment: RECORDING_ATTACHMENT,
      cleanup: harness.cleanup,
    });
    const result = await sendTrialEmail(
      confirmedEnvironment(),
      harness.dependencies,
    );
    expect(result).toEqual({ status: "sent", messageId: "test-message-id" });
    expect(harness.sendMail).toHaveBeenCalledTimes(2);
    expect(harness.sendMail.mock.calls[0]?.[0]).toEqual({
      from: TRIAL_EMAIL_FROM,
      to: TRIAL_EMAIL_TO,
      subject: CUSTOMER_SUBJECT,
      html: `${CUSTOMER_HTML}\n<p>${TRIAL_RECORDING_ATTACHED_NOTE}</p>`,
      attachments: [RECORDING_ATTACHMENT],
    });
    expect(harness.sendMail.mock.calls[1]?.[0]).toEqual({
      from: TRIAL_EMAIL_FROM,
      to: TRIAL_EMAIL_TO,
      subject: QUALITY_SUBJECT,
      html: QUALITY_HTML,
    });
    expect(harness.sendMail.mock.calls[1]?.[0]).not.toHaveProperty("attachments");
    expect(harness.sendMail.mock.calls[0]?.[0]).not.toHaveProperty("cc");
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps analyzer failures without leaking their text", async () => {
    const harness = createEmailHarness();
    harness.generateReports.mockRejectedValueOnce(
      new Error("injected-analysis-secret"),
    );
    await expectTrialError(
      () => sendTrialEmail(confirmedEnvironment(), harness.dependencies),
      "trial_analysis_failed",
      ["injected-analysis-secret", TEST_PASSWORD],
    );
    expect(harness.createTransport).not.toHaveBeenCalled();
  });
});
