import { timingSafeEqual } from "node:crypto";
import Fastify, {
  type FastifyInstance,
  type FastifyReply,
} from "fastify";
import { z } from "zod";
import type { EventIngestionService } from "../application/event-ingestion-service.js";
import { normalizeEndedCall } from "../application/normalize-ended-call.js";
import { normalizeVapiEvent } from "../application/normalize-vapi-event.js";
import { resolveRecordingRedirect } from "../application/recording-redirect.js";
import type { RatingService } from "../application/rating-service.js";
import {
  VapiDirectEnvelopeSchema,
  VapiN8nEnvelopeSchema,
} from "../domain/schemas.js";
import type {
  ClientProfile,
  NormalizedEvent,
  ProfileRegistry,
  Rating,
} from "../domain/types.js";
import type { ConfigHealth } from "../profiles/runtime-config.js";
import {
  renderRatingConfirmation,
  renderRatingSavedHtml,
} from "../reports/html.js";
import type {
  OperationalSummary,
  SqliteStore,
} from "../storage/sqlite-store.js";
import type { WorkerHealth } from "../worker/analysis-worker.js";

const ProfileParamsSchema = z.object({
  profile: z.string().min(1),
});

const CallParamsSchema = z.object({
  profile: z.string().min(1),
  callId: z.string().min(1),
});

const JobParamsSchema = z.object({
  jobId: z
    .string()
    .regex(/^[1-9]\d*$/)
    .transform(Number)
    .refine(Number.isSafeInteger),
});

const RatingBodySchema = z
  .object({
    profile: z.string().min(1),
    callId: z.string().min(1),
    score: z.number().int().min(1).max(5),
  })
  .strict();

const RatingQuerySchema = z.object({
  profile: z.string().min(1),
  call_id: z.string().min(1),
  score: z
    .string()
    .regex(/^[1-5]$/)
    .transform(Number),
});

const RecordingQuerySchema = z.object({
  profile: z.string().min(1),
  call_id: z.string().min(1),
});

const VapiEnvelopeSchema = z.union([
  VapiDirectEnvelopeSchema,
  VapiN8nEnvelopeSchema,
]);

const IsoTimestampSchema = z.string().regex(
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
);

const WorkerHealthSchema = z.discriminatedUnion("status", [
  z.object({
    status: z.literal("ok"),
    lastFailure: z.null(),
  }),
  z.object({
    status: z.literal("degraded"),
    lastFailure: z.object({
      category: z.literal("worker_cycle_failed"),
      at: IsoTimestampSchema,
    }),
  }),
]);

const ConfigHealthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  profileCount: z.number().int().nonnegative(),
  lastLoadedAt: IsoTimestampSchema.nullable(),
  lastErrorAt: IsoTimestampSchema.nullable(),
}).strict();

const OperationalSummarySchema = z.object({
  queues: z.object({
    analysis: z.object({
      pending: z.number().int().nonnegative(),
      running: z.number().int().nonnegative(),
      failed: z.number().int().nonnegative(),
    }).strict(),
    mail: z.object({
      suppressed: z.number().int().nonnegative(),
      pending: z.number().int().nonnegative(),
      sending: z.number().int().nonnegative(),
      failed: z.number().int().nonnegative(),
      uncertain: z.number().int().nonnegative(),
    }).strict(),
  }).strict(),
  lastSuccess: z.object({
    analysis: IsoTimestampSchema.nullable(),
    mail: IsoTimestampSchema.nullable(),
  }).strict(),
  mailWorker: z.object({
    status: z.enum(["ok", "degraded"]),
  }).strict(),
}).strict();

const SAFE_JOB_ERRORS: Readonly<Record<string, string>> = {
  "pipeline input invalid": "pipeline_input_invalid",
  "stored analysis invalid": "stored_analysis_invalid",
  "call analysis failed": "call_analysis_failed",
  "quality analysis failed": "quality_analysis_failed",
  "analysis persistence failed": "analysis_persistence_failed",
  "artifact generation failed": "artifact_generation_failed",
  "analysis pipeline failed": "analysis_pipeline_failed",
};

export interface WorkerHealthSource {
  getHealth(): WorkerHealth;
}

export type EventNormalizer = (
  profile: ClientProfile,
  input: unknown,
  now: Date,
) => NormalizedEvent;

export interface RecordingRedirectSource {
  apiKey: string | null;
  fetchCall(callId: string): Promise<unknown>;
}

export interface WebhookAuthConfig {
  required: boolean;
  token: string | null;
}

export interface AppDependencies {
  profiles: ProfileRegistry;
  ingestion: Pick<EventIngestionService, "ingest">;
  rating: Pick<RatingService, "rate">;
  store: Pick<
    SqliteStore,
    | "getOperationalSummary"
    | "getAnalysis"
    | "getCall"
    | "getJob"
    | "retryJob"
  >;
  worker: WorkerHealthSource;
  clock?: () => Date;
  normalizer?: EventNormalizer;
  recordingRedirect?: RecordingRedirectSource;
  webhookAuth?: WebhookAuthConfig;
  ingestAuth?: WebhookAuthConfig;
  mailExpected?: boolean;
  configHealth?: { getHealth(): ConfigHealth };
}

export function buildApp(dependencies: AppDependencies): FastifyInstance {
  const app = Fastify({
    logger: false,
    bodyLimit: 5 * 1024 * 1024,
  });
  const clock = dependencies.clock ?? (() => new Date());
  const normalizer = dependencies.normalizer ?? normalizeVapiEvent;

  app.setNotFoundHandler((_request, reply) =>
    sendError(reply, 404, "not_found"),
  );
  app.setErrorHandler((error, _request, reply) => {
    const statusCode = (error as { statusCode?: unknown }).statusCode;
    return typeof statusCode === "number" && statusCode >= 400 && statusCode < 500
      ? sendError(reply, 400, "invalid_request")
      : sendError(reply, 500, "internal_error");
  });

  app.post("/v1/vapi/:profile", async (request, reply) => {
    if (!isAuthorizedWebhook(request.headers.authorization, dependencies.webhookAuth)) {
      return sendError(reply, 401, "unauthorized");
    }
    const params = ProfileParamsSchema.safeParse(request.params);
    if (!params.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const profile = dependencies.profiles.get(params.data.profile);
    if (!profile) {
      return sendError(reply, 404, "not_found");
    }
    const envelope = VapiEnvelopeSchema.safeParse(request.body);
    if (!envelope.success) {
      return sendError(reply, 400, "invalid_request");
    }
    if (!hasExpectedAssistant(profile, envelope.data)) {
      return sendError(reply, 400, "invalid_request");
    }

    let event: NormalizedEvent;
    try {
      event = normalizer(profile, envelope.data, clock());
    } catch {
      return sendError(reply, 400, "invalid_request");
    }

    const result = dependencies.ingestion.ingest(event);
    const statusCode = result.status === "duplicate" ? 200 : 202;
    return reply.code(statusCode).send({
      status: result.status,
      callId: result.callId,
      jobId: result.jobId,
    });
  });

  app.post("/v1/ingest/:profile", async (request, reply) => {
    const ingestAuth = dependencies.ingestAuth ?? {
      required: true,
      token: null,
    };
    if (!isAuthorizedWebhook(request.headers.authorization, ingestAuth)) {
      return sendError(reply, 401, "unauthorized");
    }
    const params = ProfileParamsSchema.safeParse(request.params);
    if (!params.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const profile = dependencies.profiles.get(params.data.profile);
    if (!profile) {
      return sendError(reply, 404, "not_found");
    }
    let event;
    try {
      event = normalizeEndedCall(profile, request.body, clock());
    } catch {
      return sendError(reply, 400, "invalid_request");
    }
    const result = dependencies.ingestion.ingest(event);
    const statusCode = result.status === "duplicate" ? 200 : 202;
    return reply.code(statusCode).send({
      status: result.status,
      callId: result.callId,
      jobId: result.jobId,
    });
  });

  app.post("/v1/ratings", async (request, reply) => {
    const parsed = RatingBodySchema.safeParse(request.body);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const rating = saveKnownCallRating(
      dependencies,
      parsed.data.profile,
      parsed.data.callId,
      parsed.data.score,
    );
    if (!rating) {
      return sendError(reply, 404, "not_found");
    }
    return reply.code(200).send(ratingResponse(rating));
  });

  app.get("/rating", async (request, reply) => {
    const parsed = RatingQuerySchema.safeParse(request.query);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    if (
      !dependencies.profiles.get(parsed.data.profile) ||
      !dependencies.store.getCall(
        parsed.data.profile,
        parsed.data.call_id,
      )
    ) {
      return sendError(reply, 404, "not_found");
    }
    return reply
      .code(200)
      .type("text/html")
      .header("cache-control", "no-store")
      .send(renderRatingConfirmation(
        parsed.data.profile,
        parsed.data.call_id,
        parsed.data.score,
      ));
  });

  app.post("/rating", async (request, reply) => {
    const parsed = RatingQuerySchema.safeParse(request.query);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const rating = saveKnownCallRating(
      dependencies,
      parsed.data.profile,
      parsed.data.call_id,
      parsed.data.score,
    );
    if (!rating) {
      return sendError(reply, 404, "not_found");
    }
    return reply
      .code(200)
      .type("text/html")
      .header("cache-control", "no-store")
      .send(renderRatingSavedHtml());
  });

  app.get("/recording", async (request, reply) => {
    const parsed = RecordingQuerySchema.safeParse(request.query);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    if (!dependencies.profiles.get(parsed.data.profile)) {
      return sendError(reply, 404, "not_found");
    }
    const result = await resolveRecordingRedirect({
      profile: parsed.data.profile,
      callId: parsed.data.call_id,
      getCall: () =>
        dependencies.store.getCall(parsed.data.profile, parsed.data.call_id),
      apiKey: dependencies.recordingRedirect?.apiKey ?? null,
      fetchCall:
        dependencies.recordingRedirect?.fetchCall ??
        (async () => {
          throw new Error("recording_unavailable");
        }),
    });
    if (result.type === "redirect") {
      return reply
        .code(302)
        .header("location", result.location)
        .header("cache-control", "no-store")
        .send();
    }
    return sendError(reply, result.status, result.error);
  });

  app.get("/v1/jobs/:jobId", async (request, reply) => {
    const parsed = JobParamsSchema.safeParse(request.params);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const job = dependencies.store.getJob(parsed.data.jobId);
    if (!job) {
      return sendError(reply, 404, "not_found");
    }
    return reply.code(200).send({
      jobId: job.jobId,
      profile: job.profile,
      callId: job.callId,
      status: job.status,
      attempts: job.attempts,
      error: sanitizeJobError(job.lastError),
    });
  });

  app.post("/v1/jobs/:jobId/retry", async (request, reply) => {
    const parsed = JobParamsSchema.safeParse(request.params);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    const job = dependencies.store.getJob(parsed.data.jobId);
    if (!job) {
      return sendError(reply, 404, "not_found");
    }
    if (job.status !== "failed") {
      return sendError(reply, 400, "invalid_request");
    }
    dependencies.store.retryJob(job.jobId);
    return reply.code(202).send({
      jobId: job.jobId,
      status: "pending",
    });
  });

  app.get("/v1/calls/:profile/:callId", async (request, reply) => {
    const parsed = CallParamsSchema.safeParse(request.params);
    if (!parsed.success) {
      return sendError(reply, 400, "invalid_request");
    }
    if (!dependencies.profiles.get(parsed.data.profile)) {
      return sendError(reply, 404, "not_found");
    }
    const call = dependencies.store.getCall(
      parsed.data.profile,
      parsed.data.callId,
    );
    if (!call) {
      return sendError(reply, 404, "not_found");
    }
    const analysis = dependencies.store.getAnalysis(
      parsed.data.profile,
      parsed.data.callId,
    );
    return reply.code(200).send({ call, analysis });
  });

  app.get("/livez", async (_request, reply) =>
    reply.code(200).send({ status: "ok" }));

  app.get("/health", async (_request, reply) => {
    const summary = readSafeOperationalSummary(
      dependencies.store,
      clock(),
      dependencies.mailExpected === true,
    );
    const worker = readSafeWorkerHealth(dependencies.worker);
    const config = readConfigHealth(dependencies);
    const healthy = summary.available &&
      summary.value.mailWorker.status === "ok" &&
      worker.status === "ok" &&
      config.status === "ok";
    const parsed = ConfigHealthSchema.safeParse(config);
    return reply.code(healthy ? 200 : 503).send({
      ...summary.value,
      config: parsed.success ? parsed.data : {
        status: "degraded",
        profileCount: 0,
        lastLoadedAt: null,
        lastErrorAt: null,
      },
    });
  });

  return app;
}

function saveKnownCallRating(
  dependencies: AppDependencies,
  profile: string,
  callId: string,
  score: number,
): Rating | null {
  if (!dependencies.profiles.get(profile)) {
    return null;
  }
  if (!dependencies.store.getCall(profile, callId)) {
    return null;
  }
  return dependencies.rating.rate(profile, callId, score);
}

function ratingResponse(rating: Rating): {
  status: "rated";
  profile: string;
  callId: string;
  score: number;
  ratedAt: string;
} {
  return {
    status: "rated",
    profile: rating.profile,
    callId: rating.callId,
    score: rating.score,
    ratedAt: rating.ratedAt,
  };
}

function sanitizeJobError(lastError: string | null): string | null {
  if (lastError === null) {
    return null;
  }
  return SAFE_JOB_ERRORS[lastError] ?? "analysis_job_failed";
}

function readConfigHealth(dependencies: AppDependencies): ConfigHealth {
  try {
    const health = dependencies.configHealth?.getHealth() ?? {
      status: "ok" as const,
      profileCount: dependencies.profiles.list().length,
      lastLoadedAt: null,
      lastErrorAt: null,
    };
    const parsed = ConfigHealthSchema.safeParse(health);
    if (parsed.success) {
      return parsed.data;
    }
  } catch {
    // The fixed fallback below intentionally discards exception details.
  }
  return {
    status: "degraded",
    profileCount: 0,
    lastLoadedAt: null,
    lastErrorAt: null,
  };
}

function readSafeWorkerHealth(worker: WorkerHealthSource): WorkerHealth {
  try {
    const parsed = WorkerHealthSchema.safeParse(worker.getHealth());
    if (parsed.success) {
      return parsed.data;
    }
  } catch {
    // The fixed fallback below intentionally discards exception details.
  }
  return {
    status: "degraded",
    lastFailure: null,
  };
}

function readSafeOperationalSummary(
  store: Pick<SqliteStore, "getOperationalSummary">,
  now: Date,
  mailExpected: boolean,
): { available: boolean; value: OperationalSummary } {
  try {
    const parsed = OperationalSummarySchema.safeParse(
      store.getOperationalSummary(now, { mailExpected }),
    );
    if (parsed.success) {
      return { available: true, value: parsed.data };
    }
  } catch {
    // The fixed fallback below intentionally discards storage details.
  }
  return {
    available: false,
    value: {
      queues: {
        analysis: { pending: 0, running: 0, failed: 0 },
        mail: {
          suppressed: 0,
          pending: 0,
          sending: 0,
          failed: 0,
          uncertain: 0,
        },
      },
      lastSuccess: { analysis: null, mail: null },
      mailWorker: { status: "degraded" },
    },
  };
}

function sendError(
  reply: FastifyReply,
  statusCode: 400 | 401 | 404 | 500 | 503,
  error:
    | "invalid_request"
    | "unauthorized"
    | "not_found"
    | "internal_error"
    | "recording_unavailable",
): FastifyReply {
  return reply.code(statusCode).send({ error });
}

function isAuthorizedWebhook(
  authorization: string | undefined,
  config: WebhookAuthConfig | undefined,
): boolean {
  if (!config?.required) {
    return true;
  }
  if (!config.token || !authorization?.startsWith("Bearer ")) {
    return false;
  }
  const received = Buffer.from(authorization.slice("Bearer ".length), "utf8");
  const expected = Buffer.from(config.token, "utf8");
  return received.length === expected.length && timingSafeEqual(received, expected);
}

function hasExpectedAssistant(
  profile: ClientProfile,
  envelope: unknown,
): boolean {
  if (!isRecord(envelope)) {
    return false;
  }
  const nestedBody = isRecord(envelope.body) ? envelope.body : null;
  const message = isRecord(envelope.message)
    ? envelope.message
    : nestedBody && isRecord(nestedBody.message)
      ? nestedBody.message
      : null;
  if (!message) {
    return false;
  }
  if (message.type !== "end-of-call-report") {
    return true;
  }
  const call = isRecord(message.call) ? message.call : null;
  const accepted = new Set([
    profile.vapiAssistantId,
    ...(profile.vapiAcceptedAssistantIds ?? []),
  ]);
  return typeof call?.assistantId === "string" && accepted.has(call.assistantId);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
