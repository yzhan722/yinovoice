import { createHash } from "node:crypto";
import { join } from "node:path";
import type { Call, CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import type { ArtifactResult } from "../reports/artifact-writer.js";
import {
  renderCustomerReportSubject,
  renderQualityReportSubject,
} from "../reports/html.js";
import type { SqliteStore } from "../storage/sqlite-store.js";
import type { MailKind } from "./outbox.js";

export type OutboundMode = "off" | "shadow" | "live";

export interface CompletedReportInput {
  profile: ClientProfile;
  call: Call;
  analysis: CallAnalysis;
  quality: QualityAnalysis;
  artifacts: ArtifactResult;
}

export interface OutboxPlanningSink {
  plan(input: CompletedReportInput): void;
}

export interface OutboxPlannerOptions {
  mode: OutboundMode;
  cutoverNotBefore: string | null;
}

const UTC_TIMESTAMP_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;

export const OFF_OUTBOX_PLANNER: OutboxPlanningSink = {
  plan(): void {},
};

export class OutboxPlanner implements OutboxPlanningSink {
  private readonly cutoverTimestamp: number | null;

  constructor(
    private readonly store: SqliteStore,
    private readonly options: OutboxPlannerOptions,
  ) {
    if (options.mode === "live") {
      if (
        !options.cutoverNotBefore ||
        !UTC_TIMESTAMP_PATTERN.test(options.cutoverNotBefore)
      ) {
        throw new Error("live outbound mode requires a UTC cutover timestamp");
      }
      const timestamp = Date.parse(options.cutoverNotBefore);
      if (
        !Number.isFinite(timestamp) ||
        new Date(timestamp).toISOString() !== options.cutoverNotBefore
      ) {
        throw new Error("live outbound mode requires a valid cutover timestamp");
      }
      this.cutoverTimestamp = timestamp;
      this.store.initializeRuntimeMailCutover(options.cutoverNotBefore);
    } else {
      this.cutoverTimestamp = null;
    }
  }

  plan(input: CompletedReportInput): void {
    if (this.options.mode === "off") {
      return;
    }
    if (input.call.channel === "yino" && input.profile.mailEnabled !== true) {
      return;
    }
    const status = this.shouldDispatch(input.call.endedAt)
      ? "pending"
      : "suppressed";
    this.store.enqueueMailBatch([
      {
        profile: input.profile.slug,
        callId: input.call.callId,
        kind: "customer",
        subject: renderCustomerReportSubject(input.analysis),
        htmlPath: join(input.artifacts.directory, "customer-report.html"),
        recipientRoles: [...input.profile.legacyCustomerReportRecipients],
        messageId: deterministicMessageId(
          input.profile.slug,
          input.call.callId,
          "customer",
        ),
        status,
        nextAttemptAt: null,
      },
      {
        profile: input.profile.slug,
        callId: input.call.callId,
        kind: "quality",
        subject: renderQualityReportSubject(
          input.profile,
          input.analysis,
          input.quality,
        ),
        htmlPath: join(input.artifacts.directory, "quality-report.html"),
        recipientRoles: [...input.profile.legacyQualityReportRecipients],
        messageId: deterministicMessageId(
          input.profile.slug,
          input.call.callId,
          "quality",
        ),
        status,
        nextAttemptAt: null,
      },
    ]);
  }

  private shouldDispatch(endedAt: string): boolean {
    return this.options.mode === "live" &&
      this.cutoverTimestamp !== null &&
      Date.parse(endedAt) >= this.cutoverTimestamp;
  }
}

function deterministicMessageId(
  profile: string,
  callId: string,
  kind: MailKind,
): string {
  const digest = createHash("sha256")
    .update(`${profile}|${callId}|${kind}`)
    .digest("hex");
  return `<${digest}@calls.yino.au>`;
}
