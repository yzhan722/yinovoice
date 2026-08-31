import { selectPresignedPlaybackUrl } from "../domain/recording-url.js";

export const LUCAPLUS_MIA_ASSISTANT_ID =
  "d10d041a-3aad-4636-ba4f-9cab48bb6ac0";
export const INP_ENGLISH_ASSISTANT_ID =
  "86279b2f-3b5b-4a3e-83d2-d6b539f051e0";
export const INP_CHINESE_ASSISTANT_ID =
  "61d3dd3e-a9f1-463b-89fa-102ec2aaa281";

const ASSISTANT_BY_PROFILE = {
  lucaplus: LUCAPLUS_MIA_ASSISTANT_ID,
  "inp-group": INP_ENGLISH_ASSISTANT_ID,
} as const;

export type ShadowProfile = keyof typeof ASSISTANT_BY_PROFILE;

export interface EndOfCallEnvelope {
  message: {
    type: "end-of-call-report";
    timestamp: number;
    call: { id: string; assistantId: string };
    startedAt: string;
    endedAt: string;
    transcript: string;
    summary: string;
    artifact?: { recordingUrl: string };
  };
}

export class VapiCallMappingError extends Error {
  constructor() {
    super("vapi_call_mapping_failed");
    this.name = "VapiCallMappingError";
  }
}

export function mapVapiCallToEndOfCallEnvelope(
  profile: ShadowProfile,
  call: unknown,
): EndOfCallEnvelope {
  if (!isRecord(call) || call.assistantId !== ASSISTANT_BY_PROFILE[profile]) {
    throw new VapiCallMappingError();
  }
  if (
    typeof call.id !== "string" ||
    call.id.length === 0 ||
    typeof call.startedAt !== "string" ||
    typeof call.endedAt !== "string"
  ) {
    throw new VapiCallMappingError();
  }
  const timestamp = Date.parse(call.endedAt);
  if (!Number.isFinite(timestamp) || !Number.isFinite(Date.parse(call.startedAt))) {
    throw new VapiCallMappingError();
  }

  const artifact = isRecord(call.artifact) ? call.artifact : null;
  const analysis = isRecord(call.analysis) ? call.analysis : null;
  const transcript = firstNonemptyString(call.transcript, artifact?.transcript);
  const summary = firstNonemptyString(call.summary, analysis?.summary);
  if (transcript.length === 0 && summary.length === 0) {
    throw new VapiCallMappingError();
  }
  const recordingUrl = selectPresignedPlaybackUrl(artifact);
  return {
    message: {
      type: "end-of-call-report",
      timestamp,
      call: {
        id: call.id,
        assistantId: ASSISTANT_BY_PROFILE[profile],
      },
      startedAt: call.startedAt,
      endedAt: call.endedAt,
      transcript,
      summary,
      ...(recordingUrl === null ? {} : { artifact: { recordingUrl } }),
    },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function firstNonemptyString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }
  return "";
}
