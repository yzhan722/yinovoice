import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { verifyGmailSmtp } from "./mail/smtp-transport.js";

type LineWriter = (line: string) => void;

export interface VerifySmtpDependencies {
  verify(password: string): Promise<void>;
}

const DEFAULT_DEPENDENCIES: VerifySmtpDependencies = {
  verify: verifyGmailSmtp,
};

export async function verifySmtpMain(
  env: NodeJS.ProcessEnv = process.env,
  dependencies: VerifySmtpDependencies = DEFAULT_DEPENDENCIES,
  writeLine: LineWriter = console.log,
  writeError: LineWriter = console.error,
): Promise<number> {
  const password = env.GMAIL_APP_PASSWORD;
  if (!password?.replace(/\s/g, "")) {
    writeError("smtp_verify_failed");
    return 1;
  }
  try {
    await dependencies.verify(password);
    writeLine("smtp_verify_ok");
    return 0;
  } catch {
    writeError("smtp_verify_failed");
    return 1;
  }
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isEntrypoint()) {
  void verifySmtpMain().then((exitCode) => {
    process.exitCode = exitCode;
  });
}
