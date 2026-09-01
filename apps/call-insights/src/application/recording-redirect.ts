import type { Call } from "../domain/types.js";
import { isPresignedHttpsPlaybackUrl, selectPresignedPlaybackUrl } from "../domain/recording-url.js";

export type RecordingRedirectResult =
  | { type: "redirect"; location: string }
  | { type: "error"; status: 404 | 503; error: "not_found" | "recording_unavailable" };

export interface RecordingRedirectInput {
  profile: string;
  callId: string;
  getCall(): Call | null;
  apiKey: string | null;
  fetchCall(callId: string): Promise<unknown>;
}

export async function resolveRecordingRedirect(
  input: RecordingRedirectInput,
): Promise<RecordingRedirectResult> {
  if (input.getCall() === null) {
    return { type: "error", status: 404, error: "not_found" };
  }
  if (!input.apiKey) {
    return { type: "error", status: 503, error: "recording_unavailable" };
  }

  let payload: unknown;
  try {
    payload = await input.fetchCall(input.callId);
  } catch {
    return { type: "error", status: 503, error: "recording_unavailable" };
  }

  const location = presignedLocationFromVapiCall(payload);
  if (location === null) {
    return { type: "error", status: 503, error: "recording_unavailable" };
  }
  return { type: "redirect", location };
}

function presignedLocationFromVapiCall(payload: unknown): string | null {
  if (!isRecord(payload)) {
    return null;
  }
  const artifact = isRecord(payload.artifact) ? payload.artifact : payload;
  const location = selectPresignedPlaybackUrl(artifact);
  if (location === null || !isPresignedHttpsPlaybackUrl(location)) {
    return null;
  }
  return location;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
