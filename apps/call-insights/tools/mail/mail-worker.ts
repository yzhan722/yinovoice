import { constants } from "node:fs";
import { open, realpath, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { ArtifactPathSegmentSchema } from "../../src/domain/schemas.js";
import type { ProfileRegistry } from "../../src/domain/types.js";
import type { MailOutboxRecord } from "../../src/outbound/outbox.js";
import { inlineYinoLogoForSmtp } from "../../src/reports/email-inline-logo.js";
import type { SqliteStore } from "../../src/storage/sqlite-store.js";
import {
  resolveRecipientEnvelope,
  type RecipientConfig,
} from "./recipient-config.js";
import type { MailMessage, MailTransport } from "./smtp-transport.js";

const MAX_ATTEMPTS = 5;
const SENDING_LEASE_MS = 15 * 60 * 1_000;
const MAX_HTML_BYTES = 5 * 1024 * 1024;
const RETRY_DELAYS_MINUTES = [1, 5, 15, 60] as const;
const PERMANENT_SMTP_CODES = new Set([
  "EAUTH",
  "EENVELOPE",
  "EMESSAGE",
]);

type MailErrorCategory =
  | "mail_artifact_unavailable"
  | "recipient_resolution_failed"
  | "smtp_temporary_failure"
  | "smtp_permanent_failure"
  | "smtp_retry_exhausted"
  | "mail_delivery_uncertain"
  | "mail_cutover_blocked";

export interface MailWorkerStore {
  recordMailWorkerHeartbeat(at: string): void;
  recoverStaleSendingMail(staleBefore: string): number;
  claimNextMail(now: string): MailOutboxRecord | null;
  markMailSent(
    outboxId: number,
    providerMessageId: string | null,
    sentAt: string,
  ): void;
  retryMail(
    outboxId: number,
    safeError: string,
    nextAttemptAt: string,
  ): void;
  markMailFailed(outboxId: number, safeError: string): void;
  markMailUncertain(outboxId: number, safeError: string): void;
}

export interface MailWorkerLogEntry {
  outboxId: number;
  profile: string;
  callId: string;
  kind: MailOutboxRecord["kind"];
  errorCategory: MailErrorCategory;
}

export interface MailWorkerOptions {
  store: MailWorkerStore;
  profiles: ProfileRegistry;
  recipients: RecipientConfig;
  getRecipients?: () => RecipientConfig;
  transport: MailTransport;
  artifactDirectory: string;
  outboundMode: "live";
  mailCutoverNotBefore: string;
  resolveCallEndedAt(profile: string, callId: string): string | null;
  canonicalPath?: (path: string) => Promise<string>;
  readHtml?: (
    path: string,
    expectedCanonicalPath: string,
  ) => Promise<string>;
  clock?: () => Date;
  log?: (entry: MailWorkerLogEntry) => void;
}

export class MailWorker {
  private readonly readHtml: (
    path: string,
    expectedCanonicalPath: string,
  ) => Promise<string>;
  private readonly canonicalPath: (path: string) => Promise<string>;
  private readonly clock: () => Date;
  private readonly log: (entry: MailWorkerLogEntry) => void;
  private readonly cutoverTimestamp: number;

  constructor(private readonly options: MailWorkerOptions) {
    this.readHtml = options.readHtml ?? readConfinedHtmlFile;
    this.canonicalPath = options.canonicalPath ?? realpath;
    this.clock = options.clock ?? (() => new Date());
    this.log = options.log ?? (() => undefined);
    this.cutoverTimestamp = Date.parse(options.mailCutoverNotBefore);
    if (
      options.outboundMode !== "live" ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(
        options.mailCutoverNotBefore,
      ) ||
      !Number.isFinite(this.cutoverTimestamp) ||
      new Date(this.cutoverTimestamp).toISOString() !==
        options.mailCutoverNotBefore
    ) {
      throw new Error("mail_worker_configuration_invalid");
    }
  }

  async runOnce(): Promise<boolean> {
    const now = this.clock();
    this.options.store.recoverStaleSendingMail(
      new Date(now.getTime() - SENDING_LEASE_MS).toISOString(),
    );
    const mail = this.options.store.claimNextMail(
      now.toISOString(),
    );
    if (!mail) {
      return this.completeCycle(false);
    }
    if (!this.isAfterCutover(mail)) {
      this.options.store.markMailFailed(
        mail.outboxId,
        "mail_cutover_blocked",
      );
      this.logFailure(mail, "mail_cutover_blocked");
      return this.completeCycle(true);
    }

    let message: MailMessage;
    try {
      message = await this.buildMessage(mail);
    } catch (error) {
      const category: MailErrorCategory =
        error instanceof RecipientResolutionError
          ? "recipient_resolution_failed"
          : "mail_artifact_unavailable";
      this.options.store.markMailFailed(mail.outboxId, category);
      this.logFailure(mail, category);
      return this.completeCycle(true);
    }

    let providerMessageId: string | null;
    try {
      const result = await this.options.transport.sendMail(message);
      providerMessageId = typeof result.messageId === "string"
        ? result.messageId
        : null;
    } catch (error) {
      this.handleSendFailure(mail, error);
      return this.completeCycle(true);
    }

    try {
      this.options.store.markMailSent(
        mail.outboxId,
        providerMessageId,
        this.clock().toISOString(),
      );
    } catch {
      this.options.store.markMailUncertain(
        mail.outboxId,
        "mail_delivery_uncertain",
      );
      this.logFailure(mail, "mail_delivery_uncertain");
    }
    return this.completeCycle(true);
  }

  private async buildMessage(
    mail: MailOutboxRecord,
  ): Promise<MailMessage> {
    const profile = this.options.profiles.get(mail.profile);
    if (!profile) {
      throw new RecipientResolutionError();
    }
    const expectedRoles = mail.kind === "customer"
      ? profile.legacyCustomerReportRecipients
      : profile.legacyQualityReportRecipients;

    let envelope;
    try {
      envelope = resolveRecipientEnvelope(
        this.options.getRecipients?.() ?? this.options.recipients,
        mail.profile,
        expectedRoles,
      );
    } catch {
      throw new RecipientResolutionError();
    }
    if (
      !ArtifactPathSegmentSchema.safeParse(mail.profile).success ||
      !ArtifactPathSegmentSchema.safeParse(mail.callId).success
    ) {
      throw new Error("artifact unavailable");
    }
    const filename = `${mail.kind}-report.html`;
    const artifactRoot = resolve(this.options.artifactDirectory);
    const expectedPath = resolve(
      artifactRoot,
      mail.profile,
      mail.callId,
      filename,
    );
    if (resolve(mail.htmlPath) !== expectedPath) {
      throw new Error("artifact unavailable");
    }
    const canonicalRoot = await this.canonicalPath(artifactRoot);
    const canonicalExpected = resolve(
      canonicalRoot,
      mail.profile,
      mail.callId,
      filename,
    );
    const canonicalArtifact = await this.canonicalPath(expectedPath);
    if (canonicalArtifact !== canonicalExpected) {
      throw new Error("artifact unavailable");
    }
    const html = await this.readHtml(
      canonicalArtifact,
      canonicalExpected,
    );
    if (typeof html !== "string" || html.length === 0) {
      throw new Error("artifact unavailable");
    }
    const inlined = inlineYinoLogoForSmtp(html);
    return {
      from: this.options.recipients.sender,
      to: envelope.to,
      ...(envelope.cc.length > 0 ? { cc: envelope.cc } : {}),
      subject: mail.subject,
      html: inlined.html,
      messageId: mail.messageId,
      ...(inlined.attachments.length > 0
        ? { attachments: inlined.attachments }
        : {}),
    };
  }

  private handleSendFailure(
    mail: MailOutboxRecord,
    error: unknown,
  ): void {
    if (isPermanentSmtpFailure(error)) {
      this.options.store.markMailFailed(
        mail.outboxId,
        "smtp_permanent_failure",
      );
      this.logFailure(mail, "smtp_permanent_failure");
      return;
    }
    if (!isExplicitTemporarySmtpFailure(error)) {
      this.options.store.markMailUncertain(
        mail.outboxId,
        "mail_delivery_uncertain",
      );
      this.logFailure(mail, "mail_delivery_uncertain");
      return;
    }
    if (mail.attempts >= MAX_ATTEMPTS) {
      this.options.store.markMailFailed(
        mail.outboxId,
        "smtp_retry_exhausted",
      );
      this.logFailure(mail, "smtp_retry_exhausted");
      return;
    }

    const delayMinutes = RETRY_DELAYS_MINUTES[mail.attempts - 1];
    if (delayMinutes === undefined) {
      this.options.store.markMailFailed(
        mail.outboxId,
        "smtp_retry_exhausted",
      );
      this.logFailure(mail, "smtp_retry_exhausted");
      return;
    }
    const nextAttemptAt = new Date(
      this.clock().getTime() + delayMinutes * 60_000,
    ).toISOString();
    this.options.store.retryMail(
      mail.outboxId,
      "smtp_temporary_failure",
      nextAttemptAt,
    );
    this.logFailure(mail, "smtp_temporary_failure");
  }

  private isAfterCutover(mail: MailOutboxRecord): boolean {
    try {
      const endedAt = this.options.resolveCallEndedAt(
        mail.profile,
        mail.callId,
      );
      return endedAt !== null &&
        Number.isFinite(Date.parse(endedAt)) &&
        Date.parse(endedAt) >= this.cutoverTimestamp;
    } catch {
      return false;
    }
  }

  private logFailure(
    mail: MailOutboxRecord,
    errorCategory: MailErrorCategory,
  ): void {
    this.log({
      outboxId: mail.outboxId,
      profile: mail.profile,
      callId: mail.callId,
      kind: mail.kind,
      errorCategory,
    });
  }

  private completeCycle(processed: boolean): boolean {
    this.options.store.recordMailWorkerHeartbeat(
      this.clock().toISOString(),
    );
    return processed;
  }
}

class RecipientResolutionError extends Error {}

function isPermanentSmtpFailure(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const code = "code" in error && typeof error.code === "string"
    ? error.code
    : null;
  if (code !== null && PERMANENT_SMTP_CODES.has(code)) {
    return true;
  }
  const responseCode =
    "responseCode" in error && typeof error.responseCode === "number"
      ? error.responseCode
      : null;
  return responseCode !== null && responseCode >= 500 && responseCode < 600;
}

function isExplicitTemporarySmtpFailure(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const responseCode =
    "responseCode" in error && typeof error.responseCode === "number"
      ? error.responseCode
      : null;
  return responseCode !== null && responseCode >= 400 && responseCode < 500;
}

export type DefaultMailWorkerStore = Pick<
  SqliteStore,
  | "recordMailWorkerHeartbeat"
  | "recoverStaleSendingMail"
  | "claimNextMail"
  | "markMailSent"
  | "retryMail"
  | "markMailFailed"
  | "markMailUncertain"
>;

export async function readConfinedHtmlFile(
  path: string,
  expectedCanonicalPath: string,
): Promise<string> {
  const noFollow = typeof constants.O_NOFOLLOW === "number"
    ? constants.O_NOFOLLOW
    : 0;
  const handle = await open(path, constants.O_RDONLY | noFollow);
  try {
    const metadata = await handle.stat();
    if (!metadata.isFile() || metadata.size > MAX_HTML_BYTES) {
      throw new Error("artifact unavailable");
    }
    const pathMetadata = await stat(path);
    const openedCanonical = process.platform === "linux"
      ? await realpath(`/proc/self/fd/${handle.fd}`)
      : await realpath(path);
    if (
      openedCanonical !== expectedCanonicalPath ||
      pathMetadata.dev !== metadata.dev ||
      pathMetadata.ino !== metadata.ino
    ) {
      throw new Error("artifact unavailable");
    }
    const contents = Buffer.allocUnsafe(MAX_HTML_BYTES + 1);
    let total = 0;
    while (total < contents.byteLength) {
      const { bytesRead } = await handle.read(
        contents,
        total,
        contents.byteLength - total,
        total,
      );
      if (bytesRead === 0) {
        break;
      }
      total += bytesRead;
    }
    if (total > MAX_HTML_BYTES) {
      throw new Error("artifact unavailable");
    }
    return contents.subarray(0, total).toString("utf8");
  } finally {
    await handle.close();
  }
}
