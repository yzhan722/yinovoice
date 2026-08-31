import { createHash } from "node:crypto";
import { EndedCallIngestSchema } from "../domain/schemas.js";
import type { ClientProfile, NormalizedEvent } from "../domain/types.js";

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortKeys);
  }
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(record).sort()) {
      sorted[key] = sortKeys(record[key]);
    }
    return sorted;
  }
  return value;
}

function sha256(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

export function normalizeEndedCall(
  profile: ClientProfile,
  input: unknown,
  now: Date,
): NormalizedEvent {
  const parsed = EndedCallIngestSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("invalid ended-call");
  }
  const body = parsed.data;
  const receivedAt = now.toISOString();
  const payloadHash = sha256(JSON.stringify(sortKeys(body)));
  return {
    eventId: body.eventId,
    payloadHash,
    profile: profile.slug,
    eventType: "ended-call",
    callId: body.callId,
    receivedAt,
    action: "analyze",
    call: {
      profile: profile.slug,
      callId: body.callId,
      eventId: body.eventId,
      channel: "yino",
      transcript: body.transcript,
      summary: body.summary,
      startedAt: body.startedAt,
      endedAt: body.endedAt,
      durationSeconds: body.durationSeconds,
      recordingUrl: null,
      receivedAt,
    },
  };
}
