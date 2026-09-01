import { createHash } from "node:crypto";
import { ArtifactPathSegmentSchema } from "../domain/schemas.js";
import type { Call, ClientProfile, NormalizedEvent } from "../domain/types.js";
import { selectPresignedPlaybackUrl } from "../domain/recording-url.js";

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

function stableStringify(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sha256(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

function extractMessage(input: unknown): Record<string, unknown> {
  const root = input as Record<string, unknown>;
  const message =
    root.message ??
    (root.body as Record<string, unknown> | undefined)?.message;
  if (!message || typeof message !== "object" || Array.isArray(message)) {
    throw new Error("invalid VAPI envelope: missing message");
  }
  return message as Record<string, unknown>;
}

function normalizeRecordingUrl(message: Record<string, unknown>): string | null {
  return selectPresignedPlaybackUrl(message.artifact);
}

function parseTimestamp(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  throw new Error("invalid message.timestamp");
}

function parseIsoDate(value: unknown, field: string): string {
  if (typeof value !== "string") {
    throw new Error(`invalid ${field}`);
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`invalid ${field}`);
  }
  return date.toISOString();
}

function computeDurationSeconds(startedAt: string, endedAt: string): number {
  const startMs = Date.parse(startedAt);
  const endMs = Date.parse(endedAt);
  if (endMs < startMs) {
    throw new Error("endedAt must not be before startedAt");
  }
  return Math.floor((endMs - startMs) / 1000);
}

function normalizeCallId(call: Record<string, unknown> | null): string | null {
  if (!call || call.id === undefined) {
    return null;
  }
  const parsed = ArtifactPathSegmentSchema.safeParse(call.id);
  if (!parsed.success) {
    throw new Error("invalid call.id");
  }
  return parsed.data;
}

function buildEventId(
  profile: string,
  eventType: string,
  callId: string,
  timestamp: number,
): string {
  return sha256(`${profile}|${eventType}|${callId}|${timestamp}`);
}

function sanitizeMessage(message: Record<string, unknown>): Record<string, unknown> {
  const sanitized: Record<string, unknown> = {
    type: message.type,
    timestamp: message.timestamp,
  };

  if (message.call && typeof message.call === "object" && !Array.isArray(message.call)) {
    const call = message.call as Record<string, unknown>;
    const callSanitized: Record<string, unknown> = {};
    if (typeof call.id === "string") {
      callSanitized.id = call.id;
    }
    sanitized.call = callSanitized;
  }

  if (typeof message.startedAt === "string") {
    sanitized.startedAt = message.startedAt;
  }
  if (typeof message.endedAt === "string") {
    sanitized.endedAt = message.endedAt;
  }
  if (typeof message.transcript === "string") {
    sanitized.transcript = message.transcript;
  }
  if (typeof message.summary === "string") {
    sanitized.summary = message.summary;
  }

  const recordingUrl = normalizeRecordingUrl(message);
  if (recordingUrl !== null) {
    sanitized.artifact = { recordingUrl };
  }

  if (typeof message.status === "string") {
    sanitized.status = message.status;
  }

  return sanitized;
}

export function normalizeVapiEvent(
  profile: ClientProfile,
  input: unknown,
  now: Date,
): NormalizedEvent {
  const message = extractMessage(input);
  const eventType = typeof message.type === "string" ? message.type : "unknown";
  const timestamp = parseTimestamp(message.timestamp);
  const callObj =
    message.call && typeof message.call === "object" && !Array.isArray(message.call)
      ? (message.call as Record<string, unknown>)
      : null;
  const callId = normalizeCallId(callObj);

  const sanitized = sanitizeMessage(message);
  const payloadHash = sha256(stableStringify(sanitized));
  const receivedAt = now.toISOString();

  if (eventType === "end-of-call-report") {
    if (callId === null) {
      throw new Error("end-of-call-report requires call.id");
    }

    const startedAt = parseIsoDate(message.startedAt, "startedAt");
    const endedAt = parseIsoDate(message.endedAt, "endedAt");
    const durationSeconds = computeDurationSeconds(startedAt, endedAt);

    const transcript = typeof message.transcript === "string" ? message.transcript : "";
    const summary = typeof message.summary === "string" ? message.summary : "";

    if (transcript.length === 0 && summary.length === 0) {
      throw new Error("end-of-call-report requires transcript or summary");
    }

    const eventId = buildEventId(profile.slug, eventType, callId, timestamp);
    const recordingUrl = normalizeRecordingUrl(message);

    const call: Call = {
      profile: profile.slug,
      callId,
      eventId,
      channel: "vapi",
      transcript,
      summary,
      startedAt,
      endedAt,
      durationSeconds,
      recordingUrl,
      receivedAt,
    };

    return {
      eventId,
      payloadHash,
      profile: profile.slug,
      eventType,
      callId,
      receivedAt,
      action: "analyze",
      call,
    };
  }

  const eventId = buildEventId(profile.slug, eventType, callId ?? "none", timestamp);

  return {
    eventId,
    payloadHash,
    profile: profile.slug,
    eventType,
    callId,
    receivedAt,
    action: "skip",
    call: null,
  };
}
