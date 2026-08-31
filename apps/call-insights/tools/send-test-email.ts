import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { MockAiProvider } from "../src/ai/mock-provider.js";
import {
  createReplayRuntime,
  runReplay,
  type ReplayRuntime,
} from "../src/cli/replay.js";
import { inlineYinoLogoForSmtp } from "../src/reports/email-inline-logo.js";

export const TEST_EMAIL_CONFIRMATION = "SEND 867542127@qq.com";
export const TEST_EMAIL_FROM = "yinoagent@gmail.com";
export const TEST_EMAIL_TO = "867542127@qq.com";
export const TEST_EMAIL_SUBJECT = "[LOCAL TEST] LucaPlus Customer Call Report";

const FICTIONAL_LUCAPLUS_FIXTURE = fileURLToPath(
  new URL("../fixtures/vapi/end-of-call.json", import.meta.url),
);
const REPORT_TEMP_PREFIX = "vapi-call-insights-email-";

export interface TestMailMessage {
  from: typeof TEST_EMAIL_FROM;
  to: typeof TEST_EMAIL_TO;
  subject: typeof TEST_EMAIL_SUBJECT;
  html: string;
  attachments?: ReturnType<typeof inlineYinoLogoForSmtp>["attachments"];
}

export interface TestMailTransport {
  verify(): Promise<unknown>;
  sendMail(message: TestMailMessage): Promise<{ messageId?: string }>;
  close(): void;
}

export interface GeneratedTestReport {
  html: string;
  cleanup(): Promise<void>;
}

export interface SendTestEmailDependencies {
  createTransport(options: unknown): TestMailTransport;
  generateReport(): Promise<GeneratedTestReport>;
}

export class EmailTestError extends Error {
  constructor(
    readonly code:
      | "email_test_not_confirmed"
      | "email_test_credentials_missing"
      | "email_test_report_generation_failed"
      | "email_test_send_failed"
      | "email_test_cleanup_failed",
  ) {
    super(code);
  }
}

const MAX_CANONICALIZATION_ROUNDS = 4;
const NAMED_HTML_ENTITIES: Readonly<Record<string, string>> = {
  amp: "&",
  apos: "'",
  colon: ":",
  commat: "@",
  equals: "=",
  gt: ">",
  hyphen: "-",
  lpar: "(",
  lowbar: "_",
  lt: "<",
  nbsp: " ",
  newline: "\n",
  num: "#",
  percnt: "%",
  period: ".",
  plus: "+",
  quot: '"',
  rpar: ")",
  sol: "/",
  tab: "\t",
};
const ALLOWED_FICTIONAL_MAILBOX_PATTERN =
  /[A-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+invalid/gi;
const ASCII_MAILBOX_ADJACENCY_PATTERN =
  /[A-Z0-9.!#$%&'*+/=?^_`{|}~@-]/i;
const HOST_PATTERN = /\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b/gi;
const ENCODED_DANGEROUS_TOKEN_PATTERN =
  /%[0-9a-f]{2}|&#(?:\d{1,7}|x[0-9a-f]{1,6});?|&(?:amp|apos|colon|commat|equals|gt|hyphen|lpar|lowbar|lt|nbsp|newline|num|percnt|period|plus|quot|rpar|sol|tab);?/i;
const UNSAFE_TEXT_PATTERNS = [
  /\bpinData\b/i,
  /\bcredential(?:s|[_\s-]*(?:id|key|secret|token))?\b/i,
  /\bapi[_\s-]*key\b/i,
  /\+61[\s().-]*[23478](?:[\s().-]*\d){8}\b/,
] as const;

function decodePercentEncoding(value: string): string {
  return value.replace(/(?:%[0-9a-f]{2})+/gi, (encoded) => {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded.replace(/%([0-9a-f]{2})/gi, (_match, hex: string) =>
        String.fromCharCode(Number.parseInt(hex, 16)),
      );
    }
  });
}

function decodeHtmlEntities(value: string): string {
  return value.replace(
    /&(?:#(\d{1,7})|#x([0-9a-f]{1,6})|([a-z][a-z0-9]+));?/gi,
    (entity, decimal: string | undefined, hex: string | undefined, named: string | undefined) => {
      if (named !== undefined) {
        return NAMED_HTML_ENTITIES[named.toLowerCase()] ?? entity;
      }

      const codePoint = Number.parseInt(decimal ?? hex ?? "", decimal ? 10 : 16);
      if (
        !Number.isInteger(codePoint) ||
        codePoint <= 0 ||
        codePoint > 0x10ffff ||
        (codePoint >= 0xd800 && codePoint <= 0xdfff)
      ) {
        return entity;
      }
      return String.fromCodePoint(codePoint);
    },
  );
}

function mapIdnaDotSeparators(value: string): string {
  return value.replace(/[\u3002\uff0e\uff61]/g, ".");
}

function canonicalizationPass(value: string): string {
  const normalized = mapIdnaDotSeparators(value.normalize("NFKC"));
  return mapIdnaDotSeparators(
    decodeHtmlEntities(decodePercentEncoding(normalized)).normalize("NFKC"),
  );
}

function canonicalizeReportText(value: string): string {
  let canonical = value;
  for (let round = 0; round < MAX_CANONICALIZATION_ROUNDS; round += 1) {
    const next = canonicalizationPass(canonical);
    if (next === canonical) {
      canonical = next;
      break;
    }
    canonical = next;
  }

  if (
    canonicalizationPass(canonical) !== canonical ||
    ENCODED_DANGEROUS_TOKEN_PATTERN.test(canonical)
  ) {
    throw new Error("canonicalization did not converge");
  }
  return canonical;
}

function inspectableReportText(html: string): string[] {
  const canonicalRawHtml = canonicalizeReportText(html);
  const withoutComments = canonicalRawHtml.replace(/<!--[\s\S]*?-->/g, "");
  const attributeValues: string[] = [];
  for (const tag of withoutComments.match(/<[^>]*>/g) ?? []) {
    const attributePattern =
      /\s[^\s"'<>/=]+\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/g;
    let match: RegExpExecArray | null;
    while ((match = attributePattern.exec(tag)) !== null) {
      attributeValues.push(match[1] ?? match[2] ?? match[3] ?? "");
    }
  }

  const visibleText = withoutComments.replace(/<[^>]*>/g, "");
  return [
    canonicalRawHtml,
    ...[visibleText, ...attributeValues].map(canonicalizeReportText),
  ];
}

function isMailboxAdjacent(character: string | undefined): boolean {
  if (character === undefined) {
    return false;
  }
  return (
    character.codePointAt(0)! > 0x7f ||
    ASCII_MAILBOX_ADJACENCY_PATTERN.test(character)
  );
}

function containsUnsafeEmail(text: string): boolean {
  const atPositions: number[] = [];
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "@") {
      atPositions.push(index);
    }
  }
  if (atPositions.length === 0) {
    return false;
  }

  const allowedAtPositions = new Set<number>();
  for (const match of text.matchAll(ALLOWED_FICTIONAL_MAILBOX_PATTERN)) {
    const mailbox = match[0];
    const start = match.index;
    const end = start + mailbox.length;
    if (
      isMailboxAdjacent(text[start - 1]) ||
      isMailboxAdjacent(text[end])
    ) {
      continue;
    }

    const atOffset = mailbox.indexOf("@");
    const domain = mailbox.slice(atOffset + 1).toLowerCase();
    if (domain.split(".").some((label) => label.startsWith("xn--"))) {
      continue;
    }
    allowedAtPositions.add(start + atOffset);
  }

  return atPositions.some((position) => !allowedAtPositions.has(position));
}

function containsN8nCloudHost(text: string): boolean {
  return (text.match(HOST_PATTERN) ?? []).some((candidate) => {
    const host = candidate.toLowerCase();
    return host === "n8n.cloud" || host.endsWith(".n8n.cloud");
  });
}

function isSafeTestReportHtml(html: string): boolean {
  return inspectableReportText(html).every(
    (text) =>
      !UNSAFE_TEXT_PATTERNS.some((pattern) => pattern.test(text)) &&
      !containsUnsafeEmail(text) &&
      !containsN8nCloudHost(text),
  );
}

export function assertEmailTestEnvironment(environment: NodeJS.ProcessEnv): void {
  if (environment.REAL_EMAIL_TEST_CONFIRM !== TEST_EMAIL_CONFIRMATION) {
    throw new EmailTestError("email_test_not_confirmed");
  }

  if (!environment.GMAIL_TEST_APP_PASSWORD?.trim()) {
    throw new EmailTestError("email_test_credentials_missing");
  }
}

export function fixedEmailTestErrorCode(error: unknown): EmailTestError["code"] {
  return error instanceof EmailTestError
    ? error.code
    : "email_test_send_failed";
}

function temporaryDirectoryCleanup(rootPath: string): () => Promise<void> {
  let cleanupPromise: Promise<void> | undefined;
  return async (): Promise<void> => {
    cleanupPromise ??= rm(rootPath, { recursive: true, force: true });
    await cleanupPromise;
  };
}

export async function generateFictionalLucaPlusReport(): Promise<GeneratedTestReport> {
  const rootPath = resolve(
    await mkdtemp(join(tmpdir(), REPORT_TEMP_PREFIX)),
  );
  const databasePath = resolve(rootPath, "database", "email-test.sqlite");
  const artifactPath = resolve(rootPath, "artifacts");
  const cleanup = temporaryDirectoryCleanup(rootPath);
  const args = [
    "--profile",
    "lucaplus",
    "--file",
    FICTIONAL_LUCAPLUS_FIXTURE,
    "--wait",
    "--database",
    databasePath,
    "--artifacts",
    artifactPath,
  ] as const;
  let runtime: ReplayRuntime | null = null;
  let generated = false;

  try {
    runtime = createReplayRuntime(
      args,
      { AI_PROVIDER: "mock" },
      { provider: new MockAiProvider() },
    );
    const result = await runReplay(args, runtime.dependencies);
    if (result.status !== "succeeded" || result.files.length !== 4) {
      throw new Error("fictional_report_generation_failed");
    }

    const customerReportPaths = result.files.filter(
      (path) => basename(path) === "customer-report.html",
    );
    if (customerReportPaths.length !== 1) {
      throw new Error("fictional_report_artifact_invalid");
    }

    const html = await readFile(customerReportPaths[0]!, "utf8");
    await runtime.close();
    runtime = null;
    generated = true;
    return { html, cleanup };
  } finally {
    if (!generated) {
      let cleanupError: unknown;
      try {
        await runtime?.close();
      } catch (error) {
        cleanupError = error;
      }
      try {
        await cleanup();
      } catch (error) {
        cleanupError ??= error;
      }
      if (cleanupError !== undefined) {
        throw cleanupError;
      }
    }
  }
}

export async function sendTestEmail(
  environment: NodeJS.ProcessEnv,
  dependencies: SendTestEmailDependencies,
): Promise<{ status: "sent"; messageId: string | null }> {
  assertEmailTestEnvironment(environment);
  const password = environment.GMAIL_TEST_APP_PASSWORD!;

  let report: unknown;
  try {
    report = await dependencies.generateReport();
  } catch {
    throw new EmailTestError("email_test_report_generation_failed");
  }

  let cleanupReport: (() => Promise<void>) | undefined;
  let transport: TestMailTransport | undefined;
  try {
    let reportHtml: string;
    try {
      if (typeof report !== "object" || report === null) {
        throw new Error("invalid report");
      }

      const cleanup = Reflect.get(report, "cleanup");
      if (typeof cleanup !== "function") {
        throw new Error("invalid report cleanup");
      }
      cleanupReport = async () => {
        await Reflect.apply(cleanup, report, []);
      };

      const html = Reflect.get(report, "html");
      if (typeof html !== "string" || !isSafeTestReportHtml(html)) {
        throw new Error("invalid report html");
      }
      reportHtml = html;
    } catch {
      throw new EmailTestError("email_test_report_generation_failed");
    }

    try {
      transport = dependencies.createTransport({
        host: "smtp.gmail.com",
        port: 465,
        secure: true,
        auth: {
          user: TEST_EMAIL_FROM,
          pass: password,
        },
        tls: {
          minVersion: "TLSv1.2",
          servername: "smtp.gmail.com",
        },
      });
      await transport.verify();
      const inlined = inlineYinoLogoForSmtp(reportHtml);
      const response = await transport.sendMail({
        from: TEST_EMAIL_FROM,
        to: TEST_EMAIL_TO,
        subject: TEST_EMAIL_SUBJECT,
        html: inlined.html,
        ...(inlined.attachments.length > 0
          ? { attachments: inlined.attachments }
          : {}),
      });
      return {
        status: "sent",
        messageId: response.messageId ?? null,
      };
    } catch {
      throw new EmailTestError("email_test_send_failed");
    }
  } finally {
    let cleanupFailed = false;
    try {
      transport?.close();
    } catch {
      cleanupFailed = true;
    }
    if (cleanupReport !== undefined) {
      try {
        await cleanupReport();
      } catch {
        cleanupFailed = true;
      }
    }
    if (cleanupFailed) {
      throw new EmailTestError("email_test_cleanup_failed");
    }
  }
}

type LineWriter = (line: string) => void;

export async function emailTestMain(
  environment: NodeJS.ProcessEnv,
  dependencies: SendTestEmailDependencies,
  writeLine: LineWriter = console.log,
  writeError: LineWriter = console.error,
): Promise<number> {
  try {
    await sendTestEmail(environment, dependencies);
  } catch (error) {
    writeError(fixedEmailTestErrorCode(error));
    return 1;
  }

  writeLine('{"status":"sent"}');
  return 0;
}
