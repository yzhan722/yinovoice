import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import type { MailOutboxInput } from "../src/outbound/outbox.js";
import { profileRegistry } from "../src/profiles/profiles.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import {
  MailWorker,
  readConfinedHtmlFile,
  type MailWorkerStore,
} from "../tools/mail/mail-worker.js";
import {
  type RecipientConfig,
  loadRecipientConfig,
  resolveRecipientEnvelope,
} from "../tools/mail/recipient-config.js";
import {
  createGmailTransport,
  verifyGmailSmtp,
  type MailMessage,
} from "../tools/mail/smtp-transport.js";
import { loadMailWorkerEnvironment } from "../tools/mail-worker-entrypoint.js";
import { verifySmtpMain } from "../tools/verify-smtp-entrypoint.js";
import { YINO_LOGO_CONTENT_ID } from "../src/reports/email-inline-logo.js";
import { YINO_LOGO_DATA_URI } from "../src/reports/yino-logo.js";
import { tempDatabase, tempDirectory } from "./fixtures.js";

const FIXED_SENDER = "yinoagent@gmail.com";
const LUCAPLUS_ROLES = {
  "customer-report-primary": ["primary@example.test"],
  "customer-report-cc": ["cc@example.test"],
  "customer-report-support": ["support@example.test"],
  "quality-report-internal": ["quality@example.test"],
};
const INP_ROLES = {
  "customer-report-primary": ["inp-primary@example.test"],
  "customer-report-cc": ["inp-cc@example.test"],
  "quality-report-internal": ["inp-quality@example.test"],
};
const VALID_RECIPIENT_CONFIG = {
  sender: FIXED_SENDER,
  profiles: {
    lucaplus: { roles: LUCAPLUS_ROLES },
    "inp-group": { roles: INP_ROLES },
  },
} as const satisfies RecipientConfig;

describe("recipient config", () => {
  it("loads a private checksummed role map and preserves To/CC semantics", async () => {
    const harness = recipientHarness(VALID_RECIPIENT_CONFIG);

    const config = await loadRecipientConfig(
      "/run/secrets/mail-recipients.json",
      harness.checksum,
      profileRegistry,
      harness.dependencies,
    );

    expect(resolveRecipientEnvelope(config, "lucaplus", [
      "customer-report-primary",
      "customer-report-cc",
      "customer-report-support",
    ])).toEqual({
      to: ["primary@example.test"],
      cc: ["cc@example.test", "support@example.test"],
    });
    expect(resolveRecipientEnvelope(config, "inp-group", [
      "customer-report-primary",
      "customer-report-cc",
    ])).toEqual({
      to: ["inp-primary@example.test"],
      cc: ["inp-cc@example.test"],
    });
    expect(resolveRecipientEnvelope(config, "lucaplus", [
      "quality-report-internal",
    ])).toEqual({
      to: ["quality@example.test"],
      cc: [],
    });
  });

  it("rejects group/world-readable recipient files before reading contents", async () => {
    const harness = recipientHarness(VALID_RECIPIENT_CONFIG);
    harness.stat.mockResolvedValueOnce({
      mode: 0o100640,
      uid: 1000,
      isFile: () => true,
    });

    await expect(loadRecipientConfig(
      "/run/secrets/mail-recipients.json",
      harness.checksum,
      profileRegistry,
      harness.dependencies,
    )).rejects.toThrow("recipient_config_permissions_invalid");
    expect(harness.readFile).not.toHaveBeenCalled();
    expect(harness.close).toHaveBeenCalledTimes(1);
  });

  it("rejects a private file not owned by the service account", async () => {
    const harness = recipientHarness(VALID_RECIPIENT_CONFIG);
    harness.stat.mockResolvedValueOnce({
      mode: 0o100600,
      uid: 0,
      isFile: () => true,
    });

    await expect(loadRecipientConfig(
      "/run/secrets/mail-recipients.json",
      harness.checksum,
      profileRegistry,
      harness.dependencies,
    )).rejects.toThrow("recipient_config_permissions_invalid");
    expect(harness.readFile).not.toHaveBeenCalled();
  });

  it.each([
    {
      name: "missing required role",
      config: {
        sender: FIXED_SENDER,
        profiles: {
          ...VALID_RECIPIENT_CONFIG.profiles,
          lucaplus: {
            roles: {
              ...LUCAPLUS_ROLES,
              "quality-report-internal": undefined,
            },
          },
        },
      },
    },
    {
      name: "unknown role",
      config: {
        sender: FIXED_SENDER,
        profiles: {
          ...VALID_RECIPIENT_CONFIG.profiles,
          lucaplus: {
            roles: {
              ...LUCAPLUS_ROLES,
              unexpected: ["x@example.test"],
            },
          },
        },
      },
    },
    {
      name: "empty address list",
      config: {
        sender: FIXED_SENDER,
        profiles: {
          ...VALID_RECIPIENT_CONFIG.profiles,
          lucaplus: {
            roles: { ...LUCAPLUS_ROLES, "customer-report-primary": [] },
          },
        },
      },
    },
    {
      name: "duplicate address",
      config: {
        sender: FIXED_SENDER,
        profiles: {
          ...VALID_RECIPIENT_CONFIG.profiles,
          lucaplus: {
            roles: {
              ...LUCAPLUS_ROLES,
              "customer-report-cc": ["primary@example.test"],
            },
          },
        },
      },
    },
    {
      name: "header injection",
      config: {
        sender: FIXED_SENDER,
        profiles: {
          ...VALID_RECIPIENT_CONFIG.profiles,
          lucaplus: {
            roles: {
              ...LUCAPLUS_ROLES,
              "customer-report-primary": [
                "primary@example.test\r\nBcc: attacker@example.test",
              ],
            },
          },
        },
      },
    },
    {
      name: "wrong sender",
      config: {
        sender: "other@example.test",
        profiles: VALID_RECIPIENT_CONFIG.profiles,
      },
    },
  ])("rejects $name without exposing recipient data", async ({ config }) => {
    const harness = recipientHarness(config);

    await expect(loadRecipientConfig(
      "/run/secrets/mail-recipients.json",
      harness.checksum,
      profileRegistry,
      harness.dependencies,
    )).rejects.toThrow("recipient_config_invalid");
  });

  it("ignores a checksum mismatch and still loads recipients", async () => {
    const harness = recipientHarness(VALID_RECIPIENT_CONFIG);

    const config = await loadRecipientConfig(
      "/run/secrets/mail-recipients.json",
      "0".repeat(64),
      profileRegistry,
      harness.dependencies,
    );
    expect(resolveRecipientEnvelope(config, "inp-group", [
      "customer-report-primary",
    ])).toEqual({
      to: ["inp-primary@example.test"],
      cc: [],
    });
  });
});

describe("Gmail SMTP adapter", () => {
  it("uses only the fixed Gmail TLS endpoint and sender account", () => {
    const transport = {
      verify: vi.fn(async () => undefined),
      sendMail: vi.fn(async () => ({ messageId: "provider-id" })),
      close: vi.fn(),
    };
    const createTransport = vi.fn(() => transport);

    expect(createGmailTransport(" app password ", createTransport)).toBe(
      transport,
    );
    expect(createTransport).toHaveBeenCalledWith({
      host: "smtp.gmail.com",
      port: 465,
      secure: true,
      auth: {
        user: FIXED_SENDER,
        pass: "apppassword",
      },
    });
  });

  it("verify-only never calls sendMail and always closes the transport", async () => {
    const transport = {
      verify: vi.fn(async () => undefined),
      sendMail: vi.fn(async () => ({ messageId: "must-not-send" })),
      close: vi.fn(),
    };
    const createTransport = vi.fn(() => transport);

    await expect(verifyGmailSmtp("app-password", createTransport))
      .resolves.toBeUndefined();
    expect(transport.verify).toHaveBeenCalledTimes(1);
    expect(transport.sendMail).not.toHaveBeenCalled();
    expect(transport.close).toHaveBeenCalledTimes(1);
  });
});

describe("MailWorker", () => {
  it("sends current profile CC even when the queued roles are stale", async () => {
    const harness = mailWorkerHarness();
    try {
      harness.enqueue({
        profile: "inp-group",
        kind: "customer",
        callId: "call_inp_stale_roles",
        recipientRoles: ["customer-report-primary"],
        messageId: "<inp-stale@calls.yino.au>",
      });

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.sendMail).toHaveBeenCalledWith({
        from: FIXED_SENDER,
        to: ["inp-primary@example.test"],
        cc: ["inp-cc@example.test"],
        subject: "Call Report",
        html: "<html>safe report</html>",
        messageId: "<inp-stale@calls.yino.au>",
      });
    } finally {
      harness.close();
    }
  });

  it("sends INP customer reports To primary and CC the cc role", async () => {
    const harness = mailWorkerHarness();
    try {
      harness.enqueue({
        profile: "inp-group",
        kind: "customer",
        callId: "call_inp_cc",
        messageId: "<inp-customer@calls.yino.au>",
      });

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.sendMail).toHaveBeenCalledWith({
        from: FIXED_SENDER,
        to: ["inp-primary@example.test"],
        cc: ["inp-cc@example.test"],
        subject: "Call Report",
        html: "<html>safe report</html>",
        messageId: "<inp-customer@calls.yino.au>",
      });
    } finally {
      harness.close();
    }
  });

  it("sends both report kinds with mapped recipients and marks them sent", async () => {
    const harness = mailWorkerHarness();
    try {
      const customer = harness.enqueue({
        kind: "customer",
        recipientRoles: [
          "customer-report-primary",
          "customer-report-cc",
          "customer-report-support",
        ],
        messageId: "<customer@calls.yino.au>",
      });
      const quality = harness.enqueue({
        kind: "quality",
        recipientRoles: ["quality-report-internal"],
        messageId: "<quality@calls.yino.au>",
      });

      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(true);
      expect(await harness.worker.runOnce()).toBe(false);

      expect(harness.sendMail).toHaveBeenNthCalledWith(1, {
        from: FIXED_SENDER,
        to: ["primary@example.test"],
        cc: ["cc@example.test", "support@example.test"],
        subject: "Call Report",
        html: "<html>safe report</html>",
        messageId: "<customer@calls.yino.au>",
      });
      expect(harness.sendMail).toHaveBeenNthCalledWith(2, {
        from: FIXED_SENDER,
        to: ["quality@example.test"],
        subject: "Call Report",
        html: "<html>safe report</html>",
        messageId: "<quality@calls.yino.au>",
      });
      expect(harness.store.getMail(customer.outboxId)).toMatchObject({
        status: "sent",
        providerMessageId: "provider-message-id",
      });
      expect(harness.store.getMail(quality.outboxId)).toMatchObject({
        status: "sent",
        providerMessageId: "provider-message-id",
      });
    } finally {
      harness.close();
    }
  });

  it("inlines both customer-report logos as one CID PNG before SMTP", async () => {
    const harness = mailWorkerHarness();
    try {
      harness.readHtml.mockResolvedValue(
        `<html><img src="${YINO_LOGO_DATA_URI}" alt="header"><img src="${YINO_LOGO_DATA_URI}" alt="footer"></html>`,
      );
      harness.enqueue({
        kind: "customer",
        recipientRoles: [
          "customer-report-primary",
          "customer-report-cc",
          "customer-report-support",
        ],
        messageId: "<customer-logo@calls.yino.au>",
      });

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.sendMail).toHaveBeenCalledTimes(1);
      const message = harness.sendMail.mock.calls[0]?.[0];
      expect(message?.html).not.toContain("data:image/png;base64,");
      expect(message?.html.match(/src="cid:yino-logo@calls\.yino\.au"/g)).toHaveLength(
        2,
      );
      expect(message?.attachments).toEqual([
        expect.objectContaining({
          filename: "yino-logo.png",
          cid: YINO_LOGO_CONTENT_ID,
          contentType: "image/png",
          contentDisposition: "inline",
        }),
      ]);
      expect(Buffer.isBuffer(message?.attachments?.[0]?.content)).toBe(true);
    } finally {
      harness.close();
    }
  });

  it("retries explicit temporary SMTP rejections with bounded backoff", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue();
      harness.sendMail.mockRejectedValueOnce(
        Object.assign(new Error("private SMTP detail"), {
          responseCode: 421,
        }),
      );

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "pending",
        attempts: 1,
        nextAttemptAt: "2026-08-17T00:01:00.000Z",
        lastError: "smtp_temporary_failure",
      });
      expect(harness.logs).toEqual([{
        outboxId: queued.outboxId,
        profile: "lucaplus",
        callId: "call_mail_worker",
        kind: "customer",
        errorCategory: "smtp_temporary_failure",
      }]);
      expect(JSON.stringify(harness.logs)).not.toContain("private SMTP detail");
    } finally {
      harness.close();
    }
  });

  it("marks an ambiguous SMTP timeout uncertain without retrying", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue();
      harness.sendMail.mockRejectedValueOnce(
        Object.assign(new Error("private SMTP detail"), {
          code: "ETIMEDOUT",
        }),
      );

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "uncertain",
        attempts: 1,
        nextAttemptAt: null,
        lastError: "mail_delivery_uncertain",
      });
      expect(harness.sendMail).toHaveBeenCalledTimes(1);
    } finally {
      harness.close();
    }
  });

  it("blocks a restored pending row completed before cutover", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue();
      const worker = new MailWorker({
        ...harness.workerOptions,
        resolveCallEndedAt: () => "2026-08-15T23:59:59.999Z",
      });

      expect(await worker.runOnce()).toBe(true);
      expect(harness.sendMail).not.toHaveBeenCalled();
      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        lastError: "mail_cutover_blocked",
      });
    } finally {
      harness.close();
    }
  });

  it.each([
    Object.assign(new Error("private auth failure"), { code: "EAUTH" }),
    Object.assign(new Error("private mailbox failure"), { responseCode: 550 }),
  ])("does not retry permanent SMTP failures", async (smtpError) => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue();
      harness.sendMail.mockRejectedValueOnce(smtpError);

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        attempts: 1,
        nextAttemptAt: null,
        lastError: "smtp_permanent_failure",
      });
    } finally {
      harness.close();
    }
  });

  it("stops retrying after the fifth delivery attempt", async () => {
    let now = new Date("2026-08-17T00:00:00.000Z");
    const harness = mailWorkerHarness(() => now);
    try {
      const queued = harness.enqueue();
      harness.sendMail.mockRejectedValue(
        Object.assign(new Error("private temporary rejection"), {
          responseCode: 421,
        }),
      );

      for (const next of [
        "2026-08-17T00:01:00.000Z",
        "2026-08-17T00:06:00.000Z",
        "2026-08-17T00:21:00.000Z",
        "2026-08-17T01:21:00.000Z",
      ]) {
        expect(await harness.worker.runOnce()).toBe(true);
        now = new Date(next);
      }
      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        attempts: 5,
        lastError: "smtp_retry_exhausted",
      });
      expect(harness.sendMail).toHaveBeenCalledTimes(5);
    } finally {
      harness.close();
    }
  });

  it("marks delivery uncertain when SMTP succeeds but sent persistence fails", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue();
      const workerStore: MailWorkerStore = {
        recordMailWorkerHeartbeat:
          harness.store.recordMailWorkerHeartbeat.bind(harness.store),
        recoverStaleSendingMail:
          harness.store.recoverStaleSendingMail.bind(harness.store),
        claimNextMail: harness.store.claimNextMail.bind(harness.store),
        markMailSent: () => {
          throw new Error("private database failure");
        },
        retryMail: harness.store.retryMail.bind(harness.store),
        markMailFailed: harness.store.markMailFailed.bind(harness.store),
        markMailUncertain: harness.store.markMailUncertain.bind(harness.store),
      };
      const worker = new MailWorker({
        ...harness.workerOptions,
        store: workerStore,
      });

      expect(await worker.runOnce()).toBe(true);

      expect(harness.sendMail).toHaveBeenCalledTimes(1);
      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "uncertain",
        attempts: 1,
        lastError: "mail_delivery_uncertain",
      });
    } finally {
      harness.close();
    }
  });

  it("rejects outbox artifact paths outside the configured artifact root", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue({
        htmlPath: resolve("package.json"),
      });

      expect(await harness.worker.runOnce()).toBe(true);

      expect(harness.readHtml).not.toHaveBeenCalled();
      expect(harness.sendMail).not.toHaveBeenCalled();
      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        lastError: "mail_artifact_unavailable",
      });
    } finally {
      harness.close();
    }
  });

  it("sends a quality report using current roles when queued roles are stale", async () => {
    const harness = mailWorkerHarness();
    try {
      const queued = harness.enqueue({
        kind: "quality",
        recipientRoles: ["customer-report-primary"],
        messageId: "<stale-quality@calls.yino.au>",
      });

      expect(await harness.worker.runOnce()).toBe(true);
      expect(harness.sendMail).toHaveBeenCalledWith({
        from: FIXED_SENDER,
        to: ["quality@example.test"],
        subject: "Call Report",
        html: "<html>safe report</html>",
        messageId: "<stale-quality@calls.yino.au>",
      });
      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "sent",
      });
    } finally {
      harness.close();
    }
  });

  it("rejects traversal segments and physically escaped artifact parents", async () => {
    const traversal = mailWorkerHarness();
    try {
      const queued = traversal.enqueue({
        callId: "..",
        htmlPath: resolve(
          traversal.workerOptions.artifactDirectory,
          "..",
          "customer-report.html",
        ),
      });
      expect(await traversal.worker.runOnce()).toBe(true);
      expect(traversal.readHtml).not.toHaveBeenCalled();
      expect(traversal.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        lastError: "mail_artifact_unavailable",
      });
    } finally {
      traversal.close();
    }

    const escaped = mailWorkerHarness();
    try {
      const queued = escaped.enqueue();
      const worker = new MailWorker({
        ...escaped.workerOptions,
        canonicalPath: vi.fn(async (path: string) =>
          path === escaped.workerOptions.artifactDirectory
            ? resolve(path)
            : resolve("outside", "customer-report.html")
        ),
      });
      expect(await worker.runOnce()).toBe(true);
      expect(escaped.readHtml).not.toHaveBeenCalled();
      expect(escaped.store.getMail(queued.outboxId)).toMatchObject({
        status: "failed",
        lastError: "mail_artifact_unavailable",
      });
    } finally {
      escaped.close();
    }
  });

  it("binds the physical containment check to the opened artifact", async () => {
    const root = tempDirectory();
    try {
      const artifactPath = join(root.path, "customer-report.html");
      writeFileSync(artifactPath, "<html>safe</html>", "utf8");

      await expect(readConfinedHtmlFile(
        artifactPath,
        resolve(root.path, "different-report.html"),
      )).rejects.toThrow("artifact unavailable");
    } finally {
      root.close();
    }
  });

  it("periodically moves mail left sending past its lease to uncertain", async () => {
    let now = new Date("2026-08-17T00:00:00.000Z");
    const harness = mailWorkerHarness(() => now);
    try {
      const queued = harness.enqueue();
      expect(harness.store.claimNextMail(now.toISOString())?.outboxId)
        .toBe(queued.outboxId);
      now = new Date("2026-08-17T00:15:00.001Z");

      expect(await harness.worker.runOnce()).toBe(false);

      expect(harness.store.getMail(queued.outboxId)).toMatchObject({
        status: "uncertain",
        lastError: "mail_delivery_uncertain",
      });
    } finally {
      harness.close();
    }
  });

  it("records an idle heartbeat that degrades only after two minutes", async () => {
    const now = new Date("2026-08-17T00:00:00.000Z");
    const harness = mailWorkerHarness(() => now);
    try {
      expect(await harness.worker.runOnce()).toBe(false);
      expect(
        harness.store.getOperationalSummary(
          new Date("2026-08-17T00:02:00.000Z"),
        ).mailWorker,
      ).toEqual({ status: "ok" });
      expect(
        harness.store.getOperationalSummary(
          new Date("2026-08-17T00:02:00.001Z"),
        ).mailWorker,
      ).toEqual({ status: "degraded" });
    } finally {
      harness.close();
    }
  });

  it("does not refresh the heartbeat when a mail cycle crashes", async () => {
    const harness = mailWorkerHarness();
    const recordMailWorkerHeartbeat = vi.fn();
    const failedStore: MailWorkerStore = {
      recordMailWorkerHeartbeat,
      recoverStaleSendingMail: () => {
        throw new Error("private database failure");
      },
      claimNextMail: harness.store.claimNextMail.bind(harness.store),
      markMailSent: harness.store.markMailSent.bind(harness.store),
      retryMail: harness.store.retryMail.bind(harness.store),
      markMailFailed: harness.store.markMailFailed.bind(harness.store),
      markMailUncertain: harness.store.markMailUncertain.bind(harness.store),
    };
    const worker = new MailWorker({
      ...harness.workerOptions,
      store: failedStore,
    });
    try {
      await expect(worker.runOnce()).rejects.toThrow();
      expect(recordMailWorkerHeartbeat).not.toHaveBeenCalled();
    } finally {
      harness.close();
    }
  });
});

describe("mail process entrypoints", () => {
  it("requires all isolated mail secrets and paths", () => {
    expect(loadMailWorkerEnvironment({
      SQLITE_PATH: "/var/lib/vapi-call-insights/runtime.sqlite",
      ARTIFACT_DIRECTORY: "/var/lib/vapi-call-insights/artifacts",
      MAIL_RECIPIENT_CONFIG_PATH: "/run/secrets/mail-recipients.json",
      MAIL_RECIPIENT_CONFIG_SHA256: "a".repeat(64),
      GMAIL_APP_PASSWORD: " app password ",
      OUTBOUND_MODE: "live",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-16T00:00:00.000Z",
      SMTP_HOST: "attacker.example.test",
    })).toEqual({
      sqlitePath: "/var/lib/vapi-call-insights/runtime.sqlite",
      artifactDirectory: "/var/lib/vapi-call-insights/artifacts",
      recipientConfigPath: "/run/secrets/mail-recipients.json",
      profilesDirectory: null,
      gmailAppPassword: " app password ",
      outboundMode: "live",
      mailCutoverNotBefore: "2026-08-16T00:00:00.000Z",
    });
    expect(() => loadMailWorkerEnvironment({}))
      .toThrow("mail_worker_configuration_invalid");
    expect(() => loadMailWorkerEnvironment({
      SQLITE_PATH: "/tmp/runtime.sqlite",
      ARTIFACT_DIRECTORY: "/tmp/artifacts",
      MAIL_RECIPIENT_CONFIG_PATH: "/tmp/recipients.json",
      MAIL_RECIPIENT_CONFIG_SHA256: "a".repeat(64),
      GMAIL_APP_PASSWORD: "app-password",
      OUTBOUND_MODE: "shadow",
      MAIL_CUTOVER_NOT_BEFORE: "2026-08-16T00:00:00.000Z",
    })).toThrow("mail_worker_configuration_invalid");
  });

  it("runs SMTP verification without exposing errors or invoking a sender", async () => {
    const output: string[] = [];
    const errors: string[] = [];
    const verify = vi.fn(async () => undefined);

    await expect(verifySmtpMain(
      { GMAIL_APP_PASSWORD: "app-password" },
      { verify },
      (line) => output.push(line),
      (line) => errors.push(line),
    )).resolves.toBe(0);

    expect(verify).toHaveBeenCalledWith("app-password");
    expect(output).toEqual(["smtp_verify_ok"]);
    expect(errors).toEqual([]);
  });

  it("reports only a fixed SMTP verification failure", async () => {
    const output: string[] = [];
    const errors: string[] = [];

    await expect(verifySmtpMain(
      { GMAIL_APP_PASSWORD: "private-app-password" },
      {
        verify: async () => {
          throw new Error("private SMTP response");
        },
      },
      (line) => output.push(line),
      (line) => errors.push(line),
    )).resolves.toBe(1);

    expect(output).toEqual([]);
    expect(errors).toEqual(["smtp_verify_failed"]);
    expect(JSON.stringify(errors)).not.toContain("private");
  });
});

function recipientHarness(config: unknown) {
  const contents = Buffer.from(JSON.stringify(config), "utf8");
  const checksum = createHash("sha256").update(contents).digest("hex");
  const stat = vi.fn(async () => ({
    mode: 0o100600,
    uid: 1000,
    isFile: () => true,
  }));
  const readFile = vi.fn(async () => contents);
  const close = vi.fn(async () => undefined);
  const open = vi.fn(async () => ({ stat, readFile, close }));
  return {
    checksum,
    stat,
    readFile,
    close,
    dependencies: {
      open,
      getuid: () => 1000,
    },
  };
}

function mailWorkerHarness(clock: () => Date = () =>
  new Date("2026-08-17T00:00:00.000Z")
) {
  const database = tempDatabase();
  const store = new SqliteStore(database.path);
  const sendMail = vi.fn(async (_message: MailMessage) => ({
    messageId: "provider-message-id",
  }));
  const transport = {
    verify: vi.fn(async () => undefined),
    sendMail,
    close: vi.fn(),
  };
  const logs: unknown[] = [];
  const readHtml = vi.fn(async () => "<html>safe report</html>");
  const workerOptions = {
    store,
    profiles: profileRegistry,
    recipients: VALID_RECIPIENT_CONFIG satisfies RecipientConfig,
    transport,
    artifactDirectory: resolve("artifacts"),
    canonicalPath: vi.fn(async (path: string) => resolve(path)),
    readHtml,
    outboundMode: "live" as const,
    mailCutoverNotBefore: "2026-08-16T00:00:00.000Z",
    resolveCallEndedAt: () => "2026-08-17T00:00:00.000Z",
    clock,
    log: (entry: unknown) => logs.push(entry),
  };
  const worker = new MailWorker(workerOptions);
  return {
    store,
    worker,
    workerOptions,
    sendMail,
    readHtml,
    logs,
    enqueue(overrides: Partial<MailOutboxInput> = {}) {
      const profile = overrides.profile ?? "lucaplus";
      const callId = overrides.callId ?? "call_mail_worker";
      const kind = overrides.kind ?? "customer";
      const loadedProfile = profileRegistry.get(profile);
      const recipientRoles = overrides.recipientRoles ??
        (kind === "customer"
          ? loadedProfile?.legacyCustomerReportRecipients
          : loadedProfile?.legacyQualityReportRecipients) ??
        [];
      return store.enqueueMail({
        subject: "Call Report",
        htmlPath: overrides.htmlPath ??
          `artifacts/${profile}/${callId}/${kind}-report.html`,
        messageId: "<mail-worker@calls.yino.au>",
        status: "pending",
        nextAttemptAt: null,
        ...overrides,
        profile,
        callId,
        kind,
        recipientRoles: [...recipientRoles],
      });
    },
    close() {
      store.close();
      database.close();
    },
  };
}
