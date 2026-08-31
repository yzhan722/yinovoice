import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import {
  createReplayRuntime,
  runReplay,
  type ReplayRuntime,
} from "../src/cli/replay.js";
import { isPresignedHttpsPlaybackUrl } from "../src/domain/recording-url.js";
import { loadProfile } from "../src/profiles/profiles.js";
import { inlineYinoLogoForSmtp } from "../src/reports/email-inline-logo.js";
import {
  renderCustomerReportSubject,
  renderQualityReportSubject,
} from "../src/reports/html.js";
import {
  type EndOfCallEnvelope,
  TrialError,
  fetchLucaPlusCall,
  mapVapiCallToEndOfCallEnvelope,
  parseTrialCallId,
} from "./pull-lucaplus-call.js";

export const TRIAL_EMAIL_CONFIRMATION = "SEND 867542127@qq.com";
export const TRIAL_EMAIL_FROM = "yinoagent@gmail.com";
export const TRIAL_EMAIL_TO = "867542127@qq.com";
export const TRIAL_RECORDING_ATTACHED_NOTE =
  "A WAV recording is attached to this email.";
export const TRIAL_RECORDING_FILENAME = "recording.wav";
const MAX_RECORDING_BYTES = 20 * 1024 * 1024;

const REPORT_TEMP_PREFIX = "vapi-call-insights-trial-";

export interface TrialRecordingAttachment {
  filename: typeof TRIAL_RECORDING_FILENAME;
  content: Buffer;
  contentType: "audio/wav";
}

export interface TrialMailMessage {
  from: typeof TRIAL_EMAIL_FROM;
  to: typeof TRIAL_EMAIL_TO;
  subject: string;
  html: string;
  attachments?: Array<
    TrialRecordingAttachment | ReturnType<typeof inlineYinoLogoForSmtp>["attachments"][number]
  >;
}

export interface TrialMailTransport {
  verify(): Promise<unknown>;
  sendMail(message: TrialMailMessage): Promise<{ messageId?: string }>;
  close(): void;
}

export interface TrialReportMessage {
  subject: string;
  html: string;
}

export interface GeneratedTrialReport {
  messages: TrialReportMessage[];
  recordingAttachment?: TrialRecordingAttachment;
  cleanup(): Promise<void>;
}

export interface TrialEmailDependencies {
  createTransport(options: unknown): TrialMailTransport;
  generateReports(): Promise<GeneratedTrialReport>;
}

export interface TrialReportPaths {
  databasePath: string;
  artifactPath: string;
  envelopePath: string;
}

export interface TrialReportDependencies {
  fetchFn: typeof fetch;
  analyzeEnvelope(
    envelope: EndOfCallEnvelope,
    paths: TrialReportPaths,
  ): Promise<TrialAnalysisReports>;
}

export interface TrialAnalysisReports {
  customerHtml: string;
  qualityHtml: string;
  customerName: string;
  localCallTime: string;
  score: number;
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
const HOST_PATTERN = /\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b/gi;
const ENCODED_DANGEROUS_TOKEN_PATTERN =
  /%[0-9a-f]{2}|&#(?:\d{1,7}|x[0-9a-f]{1,6});?|&(?:amp|apos|colon|commat|equals|gt|hyphen|lpar|lowbar|lt|nbsp|newline|num|percnt|period|plus|quot|rpar|sol|tab);?/i;
const FORBIDDEN_MAILBOX_PATTERN =
  /(?:^|[^A-Z0-9.!#$%&'*+/=?^_`{|}~-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:lucaplus\.com|inpgroup\.com\.au)\b/i;
const UNSAFE_TEXT_PATTERNS = [
  /\bpinData\b/i,
  /\bVAPI_API_KEY\b/,
  /\bsk-[A-Za-z0-9_-]+/,
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

function containsN8nCloudHost(text: string): boolean {
  return (text.match(HOST_PATTERN) ?? []).some((candidate) => {
    const host = candidate.toLowerCase();
    return host === "n8n.cloud" || host.endsWith(".n8n.cloud");
  });
}

function containsForbiddenRecipientMailbox(text: string): boolean {
  return FORBIDDEN_MAILBOX_PATTERN.test(` ${text}`);
}

export function isSafeTrialReportHtml(html: string): boolean {
  try {
    return inspectableReportText(html).every(
      (text) =>
        !UNSAFE_TEXT_PATTERNS.some((pattern) => pattern.test(text)) &&
        !containsForbiddenRecipientMailbox(text) &&
        !containsN8nCloudHost(text),
    );
  } catch {
    return false;
  }
}

export function isSafeTrialRecordingAttachment(
  attachment: unknown,
): attachment is TrialRecordingAttachment {
  if (typeof attachment !== "object" || attachment === null) {
    return false;
  }
  if (Reflect.get(attachment, "path") !== undefined) {
    return false;
  }
  if (Reflect.get(attachment, "cid") !== undefined) {
    return false;
  }
  if (Reflect.get(attachment, "href") !== undefined) {
    return false;
  }
  const filename = Reflect.get(attachment, "filename");
  const contentType = Reflect.get(attachment, "contentType");
  const content = Reflect.get(attachment, "content");
  if (filename !== TRIAL_RECORDING_FILENAME || contentType !== "audio/wav") {
    return false;
  }
  if (!Buffer.isBuffer(content)) {
    return false;
  }
  if (content.length < 12 || content.length > MAX_RECORDING_BYTES) {
    return false;
  }
  return (
    content.subarray(0, 4).toString("ascii") === "RIFF" &&
    content.subarray(8, 12).toString("ascii") === "WAVE"
  );
}

async function downloadTrialRecording(
  recordingUrl: string | undefined,
  fetchFn: typeof fetch,
): Promise<TrialRecordingAttachment | undefined> {
  if (recordingUrl === undefined || !isPresignedHttpsPlaybackUrl(recordingUrl)) {
    return undefined;
  }

  let response: Response;
  try {
    response = await fetchFn(recordingUrl, {
      method: "GET",
      redirect: "error",
    });
  } catch {
    throw new TrialError("trial_analysis_failed");
  }
  if (!response.ok) {
    try {
      await response.arrayBuffer();
    } catch {
      // Discard the body so it cannot leak into TrialError.
    }
    throw new TrialError("trial_analysis_failed");
  }

  const lengthHeader = response.headers.get("content-length");
  if (lengthHeader !== null) {
    const declared = Number.parseInt(lengthHeader, 10);
    if (Number.isFinite(declared) && declared > MAX_RECORDING_BYTES) {
      throw new TrialError("trial_analysis_failed");
    }
  }

  let content: Buffer;
  try {
    content = Buffer.from(await response.arrayBuffer());
  } catch {
    throw new TrialError("trial_analysis_failed");
  }
  const attachment: TrialRecordingAttachment = {
    filename: TRIAL_RECORDING_FILENAME,
    content,
    contentType: "audio/wav",
  };
  if (!isSafeTrialRecordingAttachment(attachment)) {
    throw new TrialError("trial_analysis_failed");
  }
  return attachment;
}

function lucaplusTrialProfile() {
  const profile = loadProfile("lucaplus");
  if (!profile) {
    throw new TrialError("trial_analysis_failed");
  }
  return profile;
}

function trialMessagesFromAnalysis(reports: TrialAnalysisReports): TrialReportMessage[] {
  if (
    typeof reports.customerHtml !== "string" ||
    typeof reports.qualityHtml !== "string" ||
    typeof reports.customerName !== "string" ||
    typeof reports.localCallTime !== "string" ||
    typeof reports.score !== "number" ||
    !Number.isFinite(reports.score)
  ) {
    throw new TrialError("trial_analysis_failed");
  }

  const analysis = {
    customerName: reports.customerName,
    contactInfo: "",
    mainTopics: [],
    formattedTranscript: "",
    localCallTime: reports.localCallTime,
  };
  return [
    {
      subject: renderCustomerReportSubject(analysis),
      html: reports.customerHtml,
    },
    {
      subject: renderQualityReportSubject(lucaplusTrialProfile(), analysis, {
        score: reports.score,
        strengths: [],
        weaknesses: [],
        suggestions: [],
        shouldUpdatePrompt: false,
        summary: "",
      }),
      html: reports.qualityHtml,
    },
  ];
}

export function assertTrialEmailEnvironment(
  environment: NodeJS.ProcessEnv,
): void {
  if (environment.REAL_EMAIL_TEST_CONFIRM !== TRIAL_EMAIL_CONFIRMATION) {
    throw new TrialError("trial_not_confirmed");
  }

  if (
    !environment.GMAIL_TEST_APP_PASSWORD?.trim() ||
    !environment.VAPI_API_KEY?.trim() ||
    !environment.DEEPSEEK_API_KEY?.trim() ||
    environment.AI_PROVIDER !== "deepseek"
  ) {
    throw new TrialError("trial_credentials_missing");
  }
}

export function fixedTrialErrorCode(error: unknown): TrialError["code"] {
  return error instanceof TrialError ? error.code : "trial_send_failed";
}

function temporaryDirectoryCleanup(rootPath: string): () => Promise<void> {
  let cleanupPromise: Promise<void> | undefined;
  return async (): Promise<void> => {
    cleanupPromise ??= rm(rootPath, { recursive: true, force: true });
    await cleanupPromise;
  };
}

export async function analyzeMappedEnvelopeWithReplay(
  envelope: EndOfCallEnvelope,
  paths: TrialReportPaths,
  environment: NodeJS.ProcessEnv,
): Promise<TrialAnalysisReports> {
  const args = [
    "--profile",
    "lucaplus",
    "--file",
    paths.envelopePath,
    "--wait",
    "--database",
    paths.databasePath,
    "--artifacts",
    paths.artifactPath,
  ] as const;
  let runtime: ReplayRuntime | null = null;

  try {
    runtime = createReplayRuntime(args, environment);
    const result = await runReplay(args, runtime.dependencies);
    if (result.status !== "succeeded" || result.files.length !== 4) {
      throw new Error("trial_report_generation_failed");
    }

    const customerReportPaths = result.files.filter(
      (path) => basename(path) === "customer-report.html",
    );
    const qualityReportPaths = result.files.filter(
      (path) => basename(path) === "quality-report.html",
    );
    if (customerReportPaths.length !== 1 || qualityReportPaths.length !== 1) {
      throw new Error("trial_report_artifact_invalid");
    }

    const customerHtml = await readFile(customerReportPaths[0]!, "utf8");
    const qualityHtml = await readFile(qualityReportPaths[0]!, "utf8");
    const stored = runtime.dependencies.store.getAnalysis(
      "lucaplus",
      envelope.message.call.id,
    );
    if (!stored) {
      throw new Error("trial_report_generation_failed");
    }
    await runtime.close();
    runtime = null;
    return {
      customerHtml,
      qualityHtml,
      customerName: stored.callAnalysis.customerName,
      localCallTime: stored.callAnalysis.localCallTime,
      score: stored.qualityAnalysis.score,
    };
  } catch (error) {
    try {
      await runtime?.close();
    } catch {
      // Keep the mapped analysis error.
    }
    if (error instanceof TrialError) {
      throw error;
    }
    throw new TrialError("trial_analysis_failed");
  }
}

export async function generateLucaPlusTrialReports(
  environment: NodeJS.ProcessEnv,
  dependencies: TrialReportDependencies,
): Promise<GeneratedTrialReport> {
  const apiKey = environment.VAPI_API_KEY?.trim();
  if (!apiKey) {
    throw new TrialError("trial_credentials_missing");
  }

  const callId = parseTrialCallId(environment.TRIAL_CALL_ID);
  const call = await fetchLucaPlusCall(callId, apiKey, dependencies.fetchFn);
  const envelope = mapVapiCallToEndOfCallEnvelope(call);

  const rootPath = resolve(await mkdtemp(join(tmpdir(), REPORT_TEMP_PREFIX)));
  const cleanup = temporaryDirectoryCleanup(rootPath);
  const paths: TrialReportPaths = {
    databasePath: resolve(rootPath, "database", "trial.sqlite"),
    artifactPath: resolve(rootPath, "artifacts"),
    envelopePath: resolve(rootPath, "envelope.json"),
  };
  let generated = false;

  try {
    await writeFile(paths.envelopePath, JSON.stringify(envelope), "utf8");
    const reports = await dependencies.analyzeEnvelope(envelope, paths);
    const messages = trialMessagesFromAnalysis(reports);
    const recordingAttachment = await downloadTrialRecording(
      envelope.message.artifact?.recordingUrl,
      dependencies.fetchFn,
    );
    if (recordingAttachment !== undefined) {
      const customer = messages[0];
      if (customer === undefined) {
        throw new TrialError("trial_analysis_failed");
      }
      customer.html = `${customer.html}\n<p>${TRIAL_RECORDING_ATTACHED_NOTE}</p>`;
      if (!isSafeTrialReportHtml(customer.html)) {
        throw new TrialError("trial_analysis_failed");
      }
    }
    generated = true;
    return {
      messages,
      ...(recordingAttachment === undefined ? {} : { recordingAttachment }),
      cleanup,
    };
  } catch (error) {
    if (!generated) {
      try {
        await cleanup();
      } catch {
        // Preserve the original mapped error.
      }
    }
    if (error instanceof TrialError) {
      throw error;
    }
    throw new TrialError("trial_analysis_failed");
  }
}

export async function sendTrialEmail(
  environment: NodeJS.ProcessEnv,
  dependencies: TrialEmailDependencies,
): Promise<{ status: "sent"; messageId: string | null }> {
  assertTrialEmailEnvironment(environment);
  const password = environment.GMAIL_TEST_APP_PASSWORD!;

  let report: unknown;
  try {
    report = await dependencies.generateReports();
  } catch (error) {
    if (error instanceof TrialError) {
      throw error;
    }
    throw new TrialError("trial_analysis_failed");
  }

  let cleanupReport: (() => Promise<void>) | undefined;
  let transport: TrialMailTransport | undefined;
  try {
    let messages: TrialMailMessage[];
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

      const rawMessages = Reflect.get(report, "messages");
      if (!Array.isArray(rawMessages) || rawMessages.length !== 2) {
        throw new Error("invalid report messages");
      }
      messages = rawMessages.map((item: unknown) => {
        if (typeof item !== "object" || item === null) {
          throw new Error("invalid report message");
        }
        const subject = Reflect.get(item, "subject");
        const html = Reflect.get(item, "html");
        if (typeof subject !== "string" || subject.length === 0) {
          throw new Error("invalid report subject");
        }
        if (typeof html !== "string" || !isSafeTrialReportHtml(html)) {
          throw new Error("invalid report html");
        }
        return {
          from: TRIAL_EMAIL_FROM,
          to: TRIAL_EMAIL_TO,
          subject,
          html,
        };
      });

      const rawAttachment = Reflect.get(report, "recordingAttachment");
      if (rawAttachment !== undefined) {
        if (!isSafeTrialRecordingAttachment(rawAttachment)) {
          throw new Error("invalid recording attachment");
        }
        const customerMessage = messages[0];
        if (customerMessage === undefined) {
          throw new Error("invalid report messages");
        }
        customerMessage.attachments = [
          {
            filename: rawAttachment.filename,
            content: rawAttachment.content,
            contentType: rawAttachment.contentType,
          },
        ];
      }
    } catch {
      throw new TrialError("trial_analysis_failed");
    }

    try {
      transport = dependencies.createTransport({
        host: "smtp.gmail.com",
        port: 465,
        secure: true,
        auth: {
          user: TRIAL_EMAIL_FROM,
          pass: password,
        },
        tls: {
          minVersion: "TLSv1.2",
          servername: "smtp.gmail.com",
        },
      });
      await transport.verify();
      let messageId: string | null = null;
      for (const message of messages) {
        const inlined = inlineYinoLogoForSmtp(message.html);
        const attachments = [
          ...inlined.attachments,
          ...(message.attachments ?? []),
        ];
        const response = await transport.sendMail({
          ...message,
          html: inlined.html,
          ...(attachments.length > 0 ? { attachments } : {}),
        });
        messageId = response.messageId ?? null;
      }
      return {
        status: "sent",
        messageId,
      };
    } catch {
      throw new TrialError("trial_send_failed");
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
      throw new TrialError("trial_cleanup_failed");
    }
  }
}

type LineWriter = (line: string) => void;

export async function trialEmailMain(
  environment: NodeJS.ProcessEnv,
  dependencies: TrialEmailDependencies,
  writeLine: LineWriter = console.log,
  writeError: LineWriter = console.error,
): Promise<number> {
  try {
    await sendTrialEmail(environment, dependencies);
  } catch (error) {
    writeError(fixedTrialErrorCode(error));
    return 1;
  }

  writeLine('{"status":"sent"}');
  return 0;
}
