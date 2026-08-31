import { existsSync, rmSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { DatabaseSync } from "node:sqlite";
import { ArtifactPathSegmentSchema } from "../src/domain/schemas.js";

const DEFAULT_RETENTION_DAYS = 90;

export interface RuntimeRetentionOptions {
  databasePath: string;
  artifactDirectory: string;
  now?: Date;
  retentionDays?: number;
}

export interface RuntimeRetentionResult {
  callsRemoved: number;
  artifactDirectoriesRemoved: number;
  outboxRowsScrubbed: number;
}

interface ExpiredCall {
  profile: string;
  callId: string;
}

export function retainRuntime(
  options: RuntimeRetentionOptions,
): RuntimeRetentionResult {
  const now = options.now ?? new Date();
  const retentionDays = options.retentionDays ?? DEFAULT_RETENTION_DAYS;
  if (
    !Number.isFinite(now.getTime()) ||
    !Number.isSafeInteger(retentionDays) ||
    retentionDays < 1
  ) {
    throw new Error("runtime_retention_invalid");
  }
  const cutoff = new Date(
    now.getTime() - retentionDays * 24 * 60 * 60 * 1_000,
  ).toISOString();
  const database = new DatabaseSync(options.databasePath);
  try {
    database.exec("PRAGMA busy_timeout = 5000");
    const scrubOutbox = database.prepare(
      `UPDATE mail_outbox
       SET subject = '', html_path = '', recipient_roles_json = '[]',
           status = CASE
             WHEN status IN ('pending', 'sending') THEN 'failed'
             ELSE status
           END,
           next_attempt_at = NULL, last_error = NULL,
           provider_message_id = NULL
       WHERE profile = ? AND call_id = ?`,
    );
    const deleteRatings = database.prepare(
      "DELETE FROM ratings WHERE profile = ? AND call_id = ?",
    );
    const deleteAnalyses = database.prepare(
      "DELETE FROM analyses WHERE profile = ? AND call_id = ?",
    );
    const deleteJobs = database.prepare(
      "DELETE FROM jobs WHERE profile = ? AND call_id = ?",
    );
    const deleteEvents = database.prepare(
      "DELETE FROM events WHERE profile = ? AND call_id = ?",
    );
    const deleteCalls = database.prepare(
      "DELETE FROM calls WHERE profile = ? AND call_id = ?",
    );

    let callsRemoved = 0;
    let artifactDirectoriesRemoved = 0;
    let outboxRowsScrubbed = 0;
    for (;;) {
      database.exec("BEGIN IMMEDIATE");
      try {
      const expired = database
        .prepare(
          `SELECT profile, call_id
           FROM calls
           WHERE received_at < ?
             AND NOT EXISTS (
               SELECT 1 FROM jobs
               WHERE jobs.profile = calls.profile
                 AND jobs.call_id = calls.call_id
                 AND jobs.status IN ('pending', 'running')
                 AND jobs.updated_at >= ?
             )
             AND NOT EXISTS (
               SELECT 1 FROM mail_outbox
               WHERE mail_outbox.profile = calls.profile
                 AND mail_outbox.call_id = calls.call_id
                 AND mail_outbox.status IN ('pending', 'sending')
                 AND mail_outbox.updated_at >= ?
             )
           ORDER BY profile, call_id
           LIMIT 25`,
        )
        .all(cutoff, cutoff, cutoff)
        .map((row): ExpiredCall => {
          const profile = row.profile;
          const callId = row.call_id;
          if (
            typeof profile !== "string" ||
            typeof callId !== "string" ||
            !ArtifactPathSegmentSchema.safeParse(profile).success ||
            !ArtifactPathSegmentSchema.safeParse(callId).success
          ) {
            throw new Error("runtime_retention_invalid");
          }
          return { profile, callId };
        });
      if (expired.length === 0) {
        database.exec("COMMIT");
        break;
      }

      const artifactRoot = resolve(options.artifactDirectory);
      for (const call of expired) {
        const directory = resolve(
          artifactRoot,
          call.profile,
          call.callId,
        );
        const relativeDirectory = relative(artifactRoot, directory);
        if (
          relativeDirectory.startsWith("..") ||
          isAbsolute(relativeDirectory)
        ) {
          throw new Error("runtime_retention_invalid");
        }
        if (existsSync(directory)) {
          rmSync(directory, { recursive: true, force: true });
          artifactDirectoriesRemoved += 1;
        }
      }

      for (const call of expired) {
        const parameters = [call.profile, call.callId] as const;
        outboxRowsScrubbed += Number(
          scrubOutbox.run(...parameters).changes,
        );
        deleteRatings.run(...parameters);
        deleteAnalyses.run(...parameters);
        deleteJobs.run(...parameters);
        deleteEvents.run(...parameters);
        deleteCalls.run(...parameters);
      }
      database.exec("COMMIT");
      callsRemoved += expired.length;
      } catch (error) {
        if (database.isTransaction) {
          database.exec("ROLLBACK");
        }
        throw error;
      }
    }
    return {
      callsRemoved,
      artifactDirectoriesRemoved,
      outboxRowsScrubbed,
    };
  } finally {
    database.close();
  }
}

function isEntrypoint(): boolean {
  const entry = process.argv[1];
  return entry !== undefined &&
    import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isEntrypoint()) {
  try {
    const databasePath = process.env.SQLITE_PATH?.trim();
    const artifactDirectory = process.env.ARTIFACT_DIRECTORY?.trim();
    if (!databasePath || !artifactDirectory) {
      throw new Error("runtime_retention_invalid");
    }
    console.log(JSON.stringify(retainRuntime({
      databasePath,
      artifactDirectory,
    })));
  } catch {
    process.exitCode = 1;
    console.error("runtime_retention_failed");
  }
}
