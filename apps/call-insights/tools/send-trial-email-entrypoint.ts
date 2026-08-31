import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import {
  analyzeMappedEnvelopeWithReplay,
  assertTrialEmailEnvironment,
  fixedTrialErrorCode,
  generateLucaPlusTrialReports,
  trialEmailMain,
  type TrialMailTransport,
} from "./send-trial-email.js";

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
      assertTrialEmailEnvironment(process.env);
    } catch (error) {
      console.error(fixedTrialErrorCode(error));
      return 1;
    }

    try {
      const nodemailer = await import("nodemailer");
      return await trialEmailMain(process.env, {
        createTransport: (options: unknown): TrialMailTransport =>
          nodemailer.default.createTransport(options as never),
        generateReports: () =>
          generateLucaPlusTrialReports(process.env, {
            fetchFn: fetch,
            analyzeEnvelope: (envelope, paths) =>
              analyzeMappedEnvelopeWithReplay(envelope, paths, process.env),
          }),
      });
    } catch {
      console.error("trial_send_failed");
      return 1;
    }
  })().then(
    (exitCode) => {
      process.exitCode = exitCode;
    },
    () => {
      console.error("trial_send_failed");
      process.exitCode = 1;
    },
  );
}
