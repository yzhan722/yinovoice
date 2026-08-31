import { readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { describe, expect, it, vi } from "vitest";
import {
  EmailTestError,
  emailTestMain,
  generateFictionalLucaPlusReport,
  sendTestEmail,
  type GeneratedTestReport,
  type SendTestEmailDependencies,
  type TestMailMessage,
  type TestMailTransport,
} from "../tools/send-test-email.js";

const SAFE_HTML =
  "<html><body>Fictional LucaPlus report for demo@example.invalid</body></html>";
const TEST_PASSWORD = "test-password";
const REPORT_TEMP_PREFIX = "vapi-call-insights-email-";

async function reportTemporaryDirectories(): Promise<string[]> {
  return (await readdir(tmpdir()))
    .filter((entry) => entry.startsWith(REPORT_TEMP_PREFIX))
    .sort();
}

function confirmedEnvironment(
  password: string | undefined,
): NodeJS.ProcessEnv {
  const environment: NodeJS.ProcessEnv = {
    REAL_EMAIL_TEST_CONFIRM: "SEND 867542127@qq.com",
  };
  if (password !== undefined) {
    environment.GMAIL_TEST_APP_PASSWORD = password;
  }
  return environment;
}

function createHarness() {
  const verify = vi.fn(async (): Promise<unknown> => undefined);
  const sendMail = vi.fn(
    async (_message: TestMailMessage): Promise<{ messageId?: string }> => ({
      messageId: "test-message-id",
    }),
  );
  const close = vi.fn((): void => undefined);
  const cleanup = vi.fn(async (): Promise<void> => undefined);
  const createTransport = vi.fn(
    (_options: unknown): TestMailTransport => ({ verify, sendMail, close }),
  );
  const generateReport = vi.fn(
    async (): Promise<GeneratedTestReport> => ({
      html: SAFE_HTML,
      cleanup,
    }),
  );
  const dependencies = {
    createTransport,
    generateReport,
  } satisfies SendTestEmailDependencies;

  return {
    dependencies,
    createTransport,
    generateReport,
    verify,
    sendMail,
    close,
    cleanup,
  };
}

async function expectFixedError(
  operation: () => Promise<unknown>,
  code:
    | "email_test_not_confirmed"
    | "email_test_credentials_missing"
    | "email_test_report_generation_failed"
    | "email_test_send_failed"
    | "email_test_cleanup_failed",
  forbiddenText: readonly string[] = [],
): Promise<void> {
  let thrown: unknown;
  try {
    await operation();
  } catch (error) {
    thrown = error;
  }

  expect(thrown).toBeInstanceOf(EmailTestError);
  expect(thrown).toMatchObject({ code, message: code });
  expect(thrown).not.toHaveProperty("cause");
  const visibleError = `${String(thrown)}\n${(thrown as Error).stack ?? ""}`;
  for (const text of forbiddenText) {
    expect(visibleError).not.toContain(text);
  }
}

describe("sendTestEmail", () => {
  it.each([
    undefined,
    "wrong",
    "send 867542127@qq.com",
    "SEND 867542127@qq.com ",
  ])("fails before work without the exact confirmation (%s)", async (confirmation) => {
    const harness = createHarness();
    const environment: NodeJS.ProcessEnv = {
      GMAIL_TEST_APP_PASSWORD: TEST_PASSWORD,
    };
    if (confirmation !== undefined) {
      environment.REAL_EMAIL_TEST_CONFIRM = confirmation;
    }

    await expectFixedError(
      () => sendTestEmail(environment, harness.dependencies),
      "email_test_not_confirmed",
    );

    expect(harness.generateReport).not.toHaveBeenCalled();
    expect(harness.createTransport).not.toHaveBeenCalled();
  });

  it.each([undefined, "", "   "])(
    "fails before work without a nonempty application password (%s)",
    async (password) => {
      const harness = createHarness();

      await expectFixedError(
        () => sendTestEmail(confirmedEnvironment(password), harness.dependencies),
        "email_test_credentials_missing",
      );

      expect(harness.generateReport).not.toHaveBeenCalled();
      expect(harness.createTransport).not.toHaveBeenCalled();
    },
  );

  it("maps report generation errors without exposing their text", async () => {
    const harness = createHarness();
    const injectedText = "injected-report-secret";
    harness.generateReport.mockRejectedValueOnce(new Error(injectedText));

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_report_generation_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).not.toHaveBeenCalled();
  });

  it("maps an invalid generated report object to report generation failure", async () => {
    const harness = createHarness();
    harness.generateReport.mockResolvedValueOnce(null as never);

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_report_generation_failed",
      [TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).not.toHaveBeenCalled();
  });

  it.each([
    { name: "undefined", html: undefined },
    { name: "non-string", html: 42 },
  ])("maps $name report HTML and still cleans up", async ({ html }) => {
    const harness = createHarness();
    harness.generateReport.mockResolvedValueOnce({
      html,
      cleanup: harness.cleanup,
    } as unknown as GeneratedTestReport);

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_report_generation_failed",
      [TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps a throwing report HTML getter and still cleans up", async () => {
    const harness = createHarness();
    const injectedText = "injected-html-getter-secret";
    harness.generateReport.mockResolvedValueOnce({
      get html(): string {
        throw new Error(injectedText);
      },
      cleanup: harness.cleanup,
    });

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_report_generation_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps a safety predicate error and still cleans up", async () => {
    const harness = createHarness();
    const injectedText = "injected-canonicalization-secret";
    const normalize = vi
      .spyOn(String.prototype, "normalize")
      .mockImplementationOnce(() => {
        throw new Error(injectedText);
      });

    try {
      await expectFixedError(
        () =>
          sendTestEmail(
            confirmedEnvironment(TEST_PASSWORD),
            harness.dependencies,
          ),
        "email_test_report_generation_failed",
        [injectedText, TEST_PASSWORD],
      );
    } finally {
      normalize.mockRestore();
    }

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it.each([
    {
      name: "pinData marker",
      html: "<html><body>pinData</body></html>",
    },
    {
      name: "n8n host",
      html: "<html><body>yinoagent.app.n8n.cloud</body></html>",
    },
    {
      name: "credential marker",
      html: "<html><body>credentialId: cred_123</body></html>",
    },
    {
      name: "API-key marker",
      html: "<html><body>api_key=sk-test-marker</body></html>",
    },
    {
      name: "real Australian phone number",
      html: "<html><body>Call +61 412 345 678</body></html>",
    },
    {
      name: "routable email address",
      html: "<html><body>customer@example.com</body></html>",
    },
    {
      name: "routable email hidden in an HTML comment",
      html: "<html><body><!-- customer@example.com --></body></html>",
    },
    {
      name: "entity-encoded routable email hidden in an HTML comment",
      html: "<html><body><!-- customer&commat;example&period;com --></body></html>",
    },
    {
      name: "routable email in a malformed quoted attribute",
      html: '<html><body><div title="customer@example.com>">Safe</div></body></html>',
    },
    {
      name: "percent-encoded routable email in a malformed quoted attribute",
      html: '<html><body><div title="customer%40example%2ecom>">Safe</div></body></html>',
    },
    {
      name: "phone hidden in an HTML comment",
      html: "<html><body><!-- +61 412 345 678 --></body></html>",
    },
    {
      name: "entity-encoded phone hidden in an HTML comment",
      html: "<html><body><!-- &#43;61 412 345 678 --></body></html>",
    },
    {
      name: "n8n host hidden in an HTML comment",
      html: "<html><body><!-- n8n.cloud --></body></html>",
    },
    {
      name: "percent-encoded n8n host in a malformed quoted attribute",
      html: '<html><body><div title="n8n%2ecloud>">Safe</div></body></html>',
    },
    {
      name: "credential marker hidden in an HTML comment",
      html: "<html><body><!-- credentialId --></body></html>",
    },
    {
      name: "entity-encoded credential marker in a malformed quoted attribute",
      html: '<html><body><div title="credential&#73;d>">Safe</div></body></html>',
    },
    {
      name: "numeric HTML entity email",
      html: "<html><body>customer&#64;example&#46;com</body></html>",
    },
    {
      name: "named HTML entity email in an attribute",
      html: '<html><body><a href="mailto:customer&commat;example&period;com">Contact</a></body></html>',
    },
    {
      name: "numeric HTML entity phone",
      html: "<html><body>Call &#43;61 412 345 678</body></html>",
    },
    {
      name: "repeatedly percent-encoded n8n host",
      html: "<html><body>https://yinoagent%252eapp%252en8n%252ecloud</body></html>",
    },
    {
      name: "HTML-entity-wrapped repeated percent encoding",
      html: "<html><body>customer&percnt;2540example&percnt;252ecom</body></html>",
    },
    {
      name: "five-level percent-encoded routable email",
      html: "<html><body>customer%2525252540example.com</body></html>",
    },
    {
      name: "six-level percent-encoded n8n host",
      html: "<html><body>n8n%25252525252ecloud</body></html>",
    },
    {
      name: "five-level entity-encoded routable email",
      html: "<html><body>customer&amp;amp;amp;amp;commat;example.com</body></html>",
    },
    {
      name: "mixed entity and five-level percent encoding",
      html: "<html><body>customer&percnt;2525252540example.com</body></html>",
    },
    {
      name: "percent-encoded API-key marker",
      html: "<html><body>%61%70%69%5f%6b%65%79=value</body></html>",
    },
    {
      name: "NFKC-equivalent pinData marker",
      html: "<html><body>ｐｉｎＤａｔａ</body></html>",
    },
    {
      name: "NFKC-equivalent routable email",
      html: "<html><body>ｃｕｓｔｏｍｅｒ＠ｅｘａｍｐｌｅ．ｃｏｍ</body></html>",
    },
    {
      name: "overlapping fictional and routable email sequence",
      html: "<html><body>demo@example.invalid@example.com</body></html>",
    },
    {
      name: "Punycode top-level domain",
      html: "<html><body>customer@example.xn--p1ai</body></html>",
    },
    {
      name: "Punycode domain label before invalid",
      html: "<html><body>customer@xn--e1afmkfd.invalid</body></html>",
    },
    {
      name: "internationalized local part",
      html: "<html><body>客户@example.invalid</body></html>",
    },
    {
      name: "internationalized domain label",
      html: "<html><body>customer@例子.invalid</body></html>",
    },
    {
      name: "internationalized top-level domain",
      html: "<html><body>customer@example.测试</body></html>",
    },
    {
      name: "malformed mailbox without a domain",
      html: "<html><body>customer@</body></html>",
    },
    {
      name: "malformed mailbox without a local part",
      html: "<html><body>@example.com</body></html>",
    },
    {
      name: "malformed mailbox with adjacent at signs",
      html: "<html><body>customer@@example.invalid</body></html>",
    },
    {
      name: "malformed mailbox with spaces around at",
      html: "<html><body>customer @ example.com</body></html>",
    },
    {
      name: "marker split across visible HTML elements",
      html: "<html><body><span>pin</span><span>Data</span></body></html>",
    },
    {
      name: "entity-encoded credential marker in an attribute",
      html: '<html><body><div data-note="credential&#73;d: cred_123">Safe label</div></body></html>',
    },
    {
      name: "n8n host with ideographic full stop",
      html: "<html><body>n8n。cloud</body></html>",
    },
    {
      name: "n8n host with fullwidth full stop",
      html: "<html><body>n8n．cloud</body></html>",
    },
    {
      name: "n8n host with halfwidth ideographic full stop",
      html: "<html><body>n8n｡cloud</body></html>",
    },
  ])("rejects unsafe report content: $name", async ({ html }) => {
    const harness = createHarness();
    harness.generateReport.mockResolvedValueOnce({
      html,
      cleanup: harness.cleanup,
    });

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_report_generation_failed",
      [TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("allows standalone fictional addresses and longer fictional n8n-like hosts", async () => {
    const harness = createHarness();
    harness.generateReport.mockResolvedValueOnce({
      html: '<html><body><a href="mailto:demo&commat;example&period;invalid">Demo</a><a href="https://n8n.cloud.example.invalid/path">Docs</a></body></html>',
      cleanup: harness.cleanup,
    });

    await expect(
      sendTestEmail(
        confirmedEnvironment(TEST_PASSWORD),
        harness.dependencies,
      ),
    ).resolves.toEqual({ status: "sent", messageId: "test-message-id" });

    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("runs generate, safety, create, verify, send, close, and cleanup in order", async () => {
    const events: string[] = [];
    const dependencies = {
      async generateReport(): Promise<GeneratedTestReport> {
        events.push("generate");
        return {
          get html(): string {
            events.push("safety");
            return SAFE_HTML;
          },
          async cleanup(): Promise<void> {
            events.push("cleanup");
          },
        };
      },
      createTransport(): TestMailTransport {
        events.push("create");
        return {
          async verify(): Promise<void> {
            events.push("verify");
          },
          async sendMail(
            _message: TestMailMessage,
          ): Promise<{ messageId: string }> {
            events.push("send");
            return { messageId: "ordered-message-id" };
          },
          close(): void {
            events.push("close");
          },
        };
      },
    } satisfies SendTestEmailDependencies;

    await sendTestEmail(confirmedEnvironment(TEST_PASSWORD), dependencies);

    expect(events).toEqual([
      "generate",
      "safety",
      "create",
      "verify",
      "send",
      "close",
      "cleanup",
    ]);
  });

  it("sends exactly one fixed message through the fixed secure endpoint and cleans up", async () => {
    const harness = createHarness();

    const result = await sendTestEmail(
      confirmedEnvironment(TEST_PASSWORD),
      harness.dependencies,
    );

    expect(result).toEqual({ status: "sent", messageId: "test-message-id" });
    expect(harness.generateReport).toHaveBeenCalledTimes(1);
    expect(harness.createTransport).toHaveBeenCalledTimes(1);
    expect(harness.createTransport).toHaveBeenCalledWith({
      host: "smtp.gmail.com",
      port: 465,
      secure: true,
      auth: {
        user: "yinoagent@gmail.com",
        pass: TEST_PASSWORD,
      },
      tls: {
        minVersion: "TLSv1.2",
        servername: "smtp.gmail.com",
      },
    });
    expect(harness.verify).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).toHaveBeenCalledWith({
      from: "yinoagent@gmail.com",
      to: "867542127@qq.com",
      subject: "[LOCAL TEST] LucaPlus Customer Call Report",
      html: SAFE_HTML,
    });
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("normalizes a missing transport message id to null", async () => {
    const harness = createHarness();
    harness.sendMail.mockResolvedValueOnce({});

    await expect(
      sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
    ).resolves.toEqual({ status: "sent", messageId: null });

    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps transport creation failure and cleans the generated report", async () => {
    const harness = createHarness();
    const injectedText = "injected-create-transport-secret";
    harness.createTransport.mockImplementationOnce(() => {
      throw new Error(injectedText);
    });

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_send_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.verify).not.toHaveBeenCalled();
    expect(harness.sendMail).not.toHaveBeenCalled();
    expect(harness.close).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps verification failure, skips sending, closes, and cleans up", async () => {
    const harness = createHarness();
    const injectedText = "injected-smtp-verification-secret";
    harness.verify.mockRejectedValueOnce(new Error(injectedText));

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_send_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.verify).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).not.toHaveBeenCalled();
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps an EmailTestError thrown by the transport to the send category", async () => {
    const harness = createHarness();
    harness.verify.mockRejectedValueOnce(
      new EmailTestError("email_test_not_confirmed"),
    );

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_send_failed",
    );

    expect(harness.sendMail).not.toHaveBeenCalled();
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps send failure, closes, and cleans up without exposing SMTP text", async () => {
    const harness = createHarness();
    const injectedText = "injected-smtp-send-secret";
    harness.sendMail.mockRejectedValueOnce(new Error(injectedText));

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_send_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.verify).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("still cleans the report when transport close fails", async () => {
    const harness = createHarness();
    const injectedText = "injected-close-secret";
    harness.close.mockImplementationOnce(() => {
      throw new Error(injectedText);
    });

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_cleanup_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("maps report cleanup failure without exposing cleanup text", async () => {
    const harness = createHarness();
    const injectedText = "injected-cleanup-secret";
    harness.cleanup.mockRejectedValueOnce(new Error(injectedText));

    await expectFixedError(
      () => sendTestEmail(confirmedEnvironment(TEST_PASSWORD), harness.dependencies),
      "email_test_cleanup_failed",
      [injectedText, TEST_PASSWORD],
    );

    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("gives cleanup failure precedence over combined send, close, and cleanup failures", async () => {
    const harness = createHarness();
    const sendText = "injected-combined-send-secret";
    const closeText = "injected-combined-close-secret";
    const cleanupText = "injected-combined-cleanup-secret";
    harness.sendMail.mockRejectedValueOnce(new Error(sendText));
    harness.close.mockImplementationOnce(() => {
      throw new Error(closeText);
    });
    harness.cleanup.mockRejectedValueOnce(new Error(cleanupText));

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_cleanup_failed",
      [sendText, closeText, cleanupText, TEST_PASSWORD],
    );

    expect(harness.verify).toHaveBeenCalledTimes(1);
    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("gives cleanup failure precedence over a report safety failure", async () => {
    const harness = createHarness();
    const unsafeText = "pinData-injected-safety-secret";
    const cleanupText = "injected-safety-cleanup-secret";
    harness.generateReport.mockResolvedValueOnce({
      html: `<html><body>${unsafeText}</body></html>`,
      cleanup: harness.cleanup,
    });
    harness.cleanup.mockRejectedValueOnce(new Error(cleanupText));

    await expectFixedError(
      () =>
        sendTestEmail(
          confirmedEnvironment(TEST_PASSWORD),
          harness.dependencies,
        ),
      "email_test_cleanup_failed",
      [unsafeText, cleanupText, TEST_PASSWORD],
    );

    expect(harness.createTransport).not.toHaveBeenCalled();
    expect(harness.close).not.toHaveBeenCalled();
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });
});

describe("generateFictionalLucaPlusReport", () => {
  it("generates the report through the existing Mock pipeline and cleans its temporary directory", async () => {
    const before = await reportTemporaryDirectories();
    const originalFetch = globalThis.fetch;
    let fetchCalls = 0;
    let generated: GeneratedTestReport | undefined;
    globalThis.fetch = (async () => {
      fetchCalls += 1;
      throw new Error("network forbidden in fictional report generation");
    }) as typeof fetch;

    try {
      generated = await generateFictionalLucaPlusReport();
      const during = await reportTemporaryDirectories();
      const created = during.filter((entry) => !before.includes(entry));

      expect(created).toHaveLength(1);
      expect(generated.html).toContain("AI Call Report");
      expect(generated.html).toContain("Demo Customer");
      expect(generated.html).toContain("demo@example.invalid");
      expect(generated.html).not.toContain("pinData");
      expect(generated.html).not.toContain("yinoagent.app.n8n.cloud");
      expect(fetchCalls).toBe(0);
    } finally {
      globalThis.fetch = originalFetch;
      await generated?.cleanup();
    }

    expect(await reportTemporaryDirectories()).toEqual(before);
    await generated?.cleanup();
    expect(await reportTemporaryDirectories()).toEqual(before);
  });

  it("forces Mock with zero fetch calls despite ambient DeepSeek configuration", async () => {
    const before = await reportTemporaryDirectories();
    const originalFetch = globalThis.fetch;
    const originalProvider = process.env.AI_PROVIDER;
    const originalKey = process.env.DEEPSEEK_API_KEY;
    let fetchCalls = 0;
    let generated: GeneratedTestReport | undefined;
    process.env.AI_PROVIDER = "deepseek";
    process.env.DEEPSEEK_API_KEY = "synthetic-deepseek-key";
    globalThis.fetch = (async () => {
      fetchCalls += 1;
      throw new Error("network forbidden with ambient DeepSeek configuration");
    }) as typeof fetch;

    try {
      generated = await generateFictionalLucaPlusReport();

      expect(generated.html).toContain("AI Call Report");
      expect(generated.html).toContain("Demo Customer");
      expect(fetchCalls).toBe(0);
    } finally {
      globalThis.fetch = originalFetch;
      if (originalProvider === undefined) {
        delete process.env.AI_PROVIDER;
      } else {
        process.env.AI_PROVIDER = originalProvider;
      }
      if (originalKey === undefined) {
        delete process.env.DEEPSEEK_API_KEY;
      } else {
        process.env.DEEPSEEK_API_KEY = originalKey;
      }
      await generated?.cleanup();
    }

    expect(await reportTemporaryDirectories()).toEqual(before);
  });
});

describe("emailTestMain", () => {
  it("prints only the fixed sent status through fake wiring", async () => {
    const harness = createHarness();
    const lines: string[] = [];
    const errors: string[] = [];

    const result = await emailTestMain(
      confirmedEnvironment(TEST_PASSWORD),
      harness.dependencies,
      (line) => lines.push(line),
      (line) => errors.push(line),
    );

    expect(result).toBe(0);
    expect(lines).toEqual(['{"status":"sent"}']);
    expect(errors).toEqual([]);
    expect(harness.sendMail).toHaveBeenCalledTimes(1);
    expect(harness.cleanup).toHaveBeenCalledTimes(1);
  });

  it("prints only the fixed error code and does no work when confirmation is absent", async () => {
    const harness = createHarness();
    const lines: string[] = [];
    const errors: string[] = [];

    const result = await emailTestMain(
      { GMAIL_TEST_APP_PASSWORD: TEST_PASSWORD },
      harness.dependencies,
      (line) => lines.push(line),
      (line) => errors.push(line),
    );

    expect(result).toBe(1);
    expect(lines).toEqual([]);
    expect(errors).toEqual(["email_test_not_confirmed"]);
    expect(harness.generateReport).not.toHaveBeenCalled();
    expect(harness.createTransport).not.toHaveBeenCalled();
  });
});
