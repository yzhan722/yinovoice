import {
  INP_ENGLISH_ASSISTANT_ID,
  LUCAPLUS_MIA_ASSISTANT_ID,
  VapiCallMappingError,
  mapVapiCallToEndOfCallEnvelope,
  type EndOfCallEnvelope,
  type ShadowProfile,
} from "../src/integrations/vapi-call-mapper.js";

const PROFILE_ASSISTANTS = [
  ["lucaplus", LUCAPLUS_MIA_ASSISTANT_ID],
  ["inp-group", INP_ENGLISH_ASSISTANT_ID],
] as const;

export interface ShadowReplayDependencies {
  listCalls(
    assistantId: string,
    limit: number,
    createdAtLt?: string,
  ): Promise<unknown[]>;
  fetchCall(callId: string): Promise<unknown>;
  processEnvelope(
    profile: ShadowProfile,
    envelope: EndOfCallEnvelope,
  ): Promise<void>;
  countSuppressedMail(): number;
}

export interface ShadowReplayResult {
  status: "succeeded";
  profiles: {
    lucaplus: number;
    "inp-group": number;
  };
  suppressedMail: number;
}

type LineWriter = (line: string) => void;

export async function runShadowReplay(
  args: readonly string[],
  dependencies: ShadowReplayDependencies,
): Promise<ShadowReplayResult> {
  const perProfile = parsePerProfile(args);
  const counts = {
    lucaplus: 0,
    "inp-group": 0,
  };

  for (const [profile, assistantId] of PROFILE_ASSISTANTS) {
    const seen = new Set<string>();
    for await (
      const candidates of listEndedCandidatePages(
        dependencies,
        assistantId,
      )
    ) {
      for (const candidate of candidates) {
        if (counts[profile] >= perProfile) {
          break;
        }
        const callId = candidate.id;
        if (seen.has(callId)) {
          continue;
        }
        seen.add(callId);
        let envelope: EndOfCallEnvelope;
        try {
          envelope = mapVapiCallToEndOfCallEnvelope(
            profile,
            await dependencies.fetchCall(callId),
          );
        } catch (error) {
          if (error instanceof VapiCallMappingError) {
            continue;
          }
          throw new Error("shadow_replay_failed");
        }
        await dependencies.processEnvelope(profile, envelope);
        counts[profile] += 1;
      }
      if (counts[profile] >= perProfile) {
        break;
      }
    }
    if (counts[profile] !== perProfile) {
      throw new Error("shadow_replay_insufficient_calls");
    }
  }

  const suppressedMail = dependencies.countSuppressedMail();
  if (suppressedMail !== perProfile * PROFILE_ASSISTANTS.length * 2) {
    throw new Error("shadow_replay_outbox_mismatch");
  }
  return {
    status: "succeeded",
    profiles: counts,
    suppressedMail,
  };
}

export async function runShadowReplayCommand(
  args: readonly string[],
  dependencies: ShadowReplayDependencies,
  writeLine: LineWriter = console.log,
): Promise<ShadowReplayResult> {
  const result = await runShadowReplay(args, dependencies);
  writeLine(JSON.stringify(result));
  return result;
}

function parsePerProfile(args: readonly string[]): number {
  if (
    args.length !== 2 ||
    args[0] !== "--per-profile" ||
    !/^[1-9]\d*$/.test(args[1] ?? "")
  ) {
    throw new Error("invalid_arguments");
  }
  const value = Number(args[1]);
  if (!Number.isSafeInteger(value) || value > 10) {
    throw new Error("invalid_arguments");
  }
  return value;
}

function readCallId(candidate: unknown): string | null {
  if (
    typeof candidate !== "object" ||
    candidate === null ||
    Array.isArray(candidate) ||
    !("id" in candidate) ||
    typeof candidate.id !== "string" ||
    candidate.id.length === 0
  ) {
    return null;
  }
  return candidate.id;
}

interface ListedCallCandidate {
  id: string;
  createdAt: string;
}

async function* listEndedCandidatePages(
  dependencies: ShadowReplayDependencies,
  assistantId: string,
): AsyncGenerator<ListedCallCandidate[]> {
  let createdAtLt: string | undefined;
  for (;;) {
    const page = await dependencies.listCalls(
      assistantId,
      100,
      createdAtLt,
    );
    let oldestCreatedAt: string | null = null;
    const candidates: ListedCallCandidate[] = [];
    for (const item of page) {
      const id = readCallId(item);
      const createdAt = readTimestamp(item, "createdAt");
      if (createdAt !== null) {
        if (
          oldestCreatedAt === null ||
          Date.parse(createdAt) < Date.parse(oldestCreatedAt)
        ) {
          oldestCreatedAt = createdAt;
        }
      }
      if (
        id === null ||
        createdAt === null ||
        readTimestamp(item, "endedAt") === null
      ) {
        continue;
      }
      candidates.push({ id, createdAt });
    }
    yield candidates.sort(
      (left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt),
    );
    if (
      page.length < 100 ||
      oldestCreatedAt === null ||
      (createdAtLt !== undefined &&
        Date.parse(oldestCreatedAt) >= Date.parse(createdAtLt))
    ) {
      break;
    }
    createdAtLt = oldestCreatedAt;
  }
}

function readTimestamp(
  value: unknown,
  field: "createdAt" | "endedAt",
): string | null {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value)
  ) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const timestamp = record[field];
  if (
    typeof timestamp !== "string" ||
    !Number.isFinite(Date.parse(timestamp))
  ) {
    return null;
  }
  return timestamp;
}
