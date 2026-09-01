import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { profileRegistry } from "../src/profiles/profiles.js";
import { CONFIG_POLL_INTERVAL_MS } from "../src/profiles/runtime-config.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import { MailWorker, type MailWorkerLogEntry } from "./mail/mail-worker.js";
import { loadRecipientConfig } from "./mail/recipient-config.js";
import { RuntimeMailConfig } from "./mail/runtime-mail-config.js";
import { createGmailTransport } from "./mail/smtp-transport.js";

const MAIL_POLL_INTERVAL_MS = 1_000;

export interface MailWorkerEnvironment {
  sqlitePath: string;
  artifactDirectory: string;
  recipientConfigPath: string;
  profilesDirectory: string | null;
  gmailAppPassword: string;
  outboundMode: "live";
  mailCutoverNotBefore: string;
}

export interface MailWorkerRuntime {
  close(): Promise<void>;
}

export function loadMailWorkerEnvironment(
  env: NodeJS.ProcessEnv = process.env,
): MailWorkerEnvironment {
  const sqlitePath = env.SQLITE_PATH?.trim();
  const artifactDirectory = env.ARTIFACT_DIRECTORY?.trim();
  const recipientConfigPath = env.MAIL_RECIPIENT_CONFIG_PATH?.trim();
  const profilesDirectory = env.PROFILES_DIRECTORY?.trim() || null;
  const gmailAppPassword = env.GMAIL_APP_PASSWORD;
  const outboundMode = env.OUTBOUND_MODE?.trim();
  const mailCutoverNotBefore = env.MAIL_CUTOVER_NOT_BEFORE?.trim();
  if (
    !sqlitePath ||
    !artifactDirectory ||
    !recipientConfigPath ||
    !gmailAppPassword?.replace(/\s/g, "") ||
    outboundMode !== "live" ||
    !mailCutoverNotBefore ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(
      mailCutoverNotBefore,
    ) ||
    !Number.isFinite(Date.parse(mailCutoverNotBefore)) ||
    new Date(Date.parse(mailCutoverNotBefore)).toISOString() !==
      mailCutoverNotBefore
  ) {
    throw new Error("mail_worker_configuration_invalid");
  }
  return {
    sqlitePath,
    artifactDirectory,
    recipientConfigPath,
    profilesDirectory,
    gmailAppPassword,
    outboundMode,
    mailCutoverNotBefore,
  };
}

export async function createMailWorkerRuntime(
  env: NodeJS.ProcessEnv = process.env,
  writeLine: (line: string) => void = console.log,
  writeError: (line: string) => void = console.error,
): Promise<MailWorkerRuntime> {
  const config = loadMailWorkerEnvironment(env);
  if (config.sqlitePath !== ":memory:") {
    mkdirSync(dirname(resolve(config.sqlitePath)), { recursive: true });
  }
  const store = new SqliteStore(config.sqlitePath);
  let transport: ReturnType<typeof createGmailTransport> | null = null;
  try {
    store.assertRuntimeMailCutover(config.mailCutoverNotBefore);
    const mailConfig = config.profilesDirectory
      ? new RuntimeMailConfig({
        profilesDirectory: config.profilesDirectory,
        recipientsPath: config.recipientConfigPath,
      })
      : null;
    if (mailConfig && !await mailConfig.load()) {
      throw new Error("mail_worker_configuration_invalid");
    }
    const recipients = mailConfig
      ? mailConfig.getRecipients()
      : await loadRecipientConfig(
        config.recipientConfigPath,
        undefined,
        profileRegistry,
      );
    const profiles = mailConfig?.profiles ?? profileRegistry;
    transport = createGmailTransport(config.gmailAppPassword);
    await transport.verify();
    const worker = new MailWorker({
      store,
      profiles,
      recipients,
      ...(mailConfig
        ? { getRecipients: () => mailConfig.getRecipients() }
        : {}),
      transport,
      artifactDirectory: config.artifactDirectory,
      outboundMode: config.outboundMode,
      mailCutoverNotBefore: config.mailCutoverNotBefore,
      resolveCallEndedAt: (profile, callId) =>
        store.getCall(profile, callId)?.endedAt ?? null,
      log: (entry: MailWorkerLogEntry) => writeLine(JSON.stringify(entry)),
    });

    let active: Promise<void> | null = null;
    let closed = false;
    const tick = (): void => {
      if (closed || active) {
        return;
      }
      active = worker.runOnce()
        .then(() => undefined)
        .catch(() => writeError("mail_worker_iteration_failed"))
        .finally(() => {
          active = null;
        });
    };
    const timer = setInterval(tick, MAIL_POLL_INTERVAL_MS);
    const configTimer = mailConfig
      ? setInterval(() => {
        void mailConfig.load().catch(() => undefined);
      }, CONFIG_POLL_INTERVAL_MS)
      : null;
    tick();

    return {
      async close(): Promise<void> {
        if (closed) {
          return;
        }
        closed = true;
        clearInterval(timer);
        if (configTimer) {
          clearInterval(configTimer);
        }
        await active?.catch(() => undefined);
        transport?.close();
        store.close();
      },
    };
  } catch {
    transport?.close();
    store.close();
    throw new Error("mail_worker_initialization_failed");
  }
}

export async function mailWorkerMain(
  env: NodeJS.ProcessEnv = process.env,
  writeLine: (line: string) => void = console.log,
  writeError: (line: string) => void = console.error,
): Promise<number> {
  let runtime: MailWorkerRuntime;
  try {
    runtime = await createMailWorkerRuntime(env, writeLine, writeError);
  } catch {
    writeError("mail_worker_start_failed");
    return 1;
  }

  await new Promise<void>((resolveShutdown) => {
    const handleSignal = (): void => {
      process.off("SIGINT", handleSignal);
      process.off("SIGTERM", handleSignal);
      resolveShutdown();
    };
    process.on("SIGINT", handleSignal);
    process.on("SIGTERM", handleSignal);
  });
  try {
    await runtime.close();
    return 0;
  } catch {
    writeError("mail_worker_shutdown_failed");
    return 1;
  }
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isEntrypoint()) {
  void mailWorkerMain().then((exitCode) => {
    process.exitCode = exitCode;
  });
}
