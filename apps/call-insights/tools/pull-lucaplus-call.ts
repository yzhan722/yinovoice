import {
  LUCAPLUS_MIA_ASSISTANT_ID,
  mapVapiCallToEndOfCallEnvelope as mapKnownVapiCall,
  type EndOfCallEnvelope,
} from "../src/integrations/vapi-call-mapper.js";
import { fetchVapiCallJson } from "../src/integrations/vapi-client.js";

export { LUCAPLUS_MIA_ASSISTANT_ID };
export type { EndOfCallEnvelope };
export const DEFAULT_TRIAL_CALL_ID =
  "019ffebb-795d-711f-ae46-1674252cc39c";

const CALL_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type TrialErrorCode =
  | "trial_not_confirmed"
  | "trial_credentials_missing"
  | "trial_call_fetch_failed"
  | "trial_call_not_lucaplus"
  | "trial_mapping_failed"
  | "trial_analysis_failed"
  | "trial_send_failed"
  | "trial_cleanup_failed";

export class TrialError extends Error {
  constructor(readonly code: TrialErrorCode) {
    super(code);
    this.name = "TrialError";
  }
}

export function parseTrialCallId(value: string | undefined): string {
  if (value === undefined || value.length === 0) {
    return DEFAULT_TRIAL_CALL_ID;
  }
  if (!CALL_ID_PATTERN.test(value)) {
    throw new TrialError("trial_mapping_failed");
  }
  return value;
}

export function mapVapiCallToEndOfCallEnvelope(call: unknown): EndOfCallEnvelope {
  if (isRecord(call) && call.assistantId !== LUCAPLUS_MIA_ASSISTANT_ID) {
    throw new TrialError("trial_call_not_lucaplus");
  }
  try {
    return mapKnownVapiCall("lucaplus", call);
  } catch {
    throw new TrialError("trial_mapping_failed");
  }
}

export async function fetchLucaPlusCall(
  callId: string,
  apiKey: string,
  fetchFn: typeof fetch,
): Promise<unknown> {
  try {
    return await fetchVapiCallJson(callId, apiKey, fetchFn);
  } catch {
    throw new TrialError("trial_call_fetch_failed");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

