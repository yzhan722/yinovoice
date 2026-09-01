import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import {
  assertEmailTestEnvironment,
  emailTestMain,
  fixedEmailTestErrorCode,
  generateFictionalLucaPlusReport,
  type TestMailTransport,
} from "./send-test-email.js";

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return (
    entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href
  );
}

if (isEntrypoint()) {
  void (async (): Promise<number> => {
    try {
      assertEmailTestEnvironment(process.env);
    } catch (error) {
      console.error(fixedEmailTestErrorCode(error));
      return 1;
    }

    try {
      const nodemailer = await import("nodemailer");
      return await emailTestMain(process.env, {
        createTransport: (options: unknown): TestMailTransport =>
          nodemailer.default.createTransport(options as never),
        generateReport: generateFictionalLucaPlusReport,
      });
    } catch {
      console.error("email_test_send_failed");
      return 1;
    }
  })().then(
    (exitCode) => {
      process.exitCode = exitCode;
    },
    () => {
      console.error("email_test_send_failed");
      process.exitCode = 1;
    },
  );
}
