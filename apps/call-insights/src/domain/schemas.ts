import { z } from "zod";

const vapiMessageSchema = z.record(z.string(), z.unknown());

export const UtcMillisecondTimestampSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  .refine((value) => new Date(value).toISOString() === value);

export const ArtifactPathSegmentSchema = z
  .string()
  .min(1)
  .regex(/^[A-Za-z0-9._-]+$/)
  .refine((value) => value !== "." && value !== "..");

export const VapiDirectEnvelopeSchema = z.object({
  message: vapiMessageSchema,
});

export const VapiN8nEnvelopeSchema = z.object({
  body: z.object({
    message: vapiMessageSchema,
  }),
});

export const ClientProfileSchema = z.object({
  slug: ArtifactPathSegmentSchema,
  displayName: z.string().min(1),
  assistantName: z.string().min(1),
  vapiAssistantId: z.string().min(1),
  vapiAcceptedAssistantIds: z.array(z.string().min(1)).optional(),
  timezone: z.string().min(1),
  brandName: z.string().min(1),
  analysisLanguage: z.literal("en"),
  qualityLanguage: z.literal("zh"),
  companyAliases: z.array(z.string().min(1)).min(1),
  legacyCustomerReportRecipients: z.array(z.string().min(1)).min(1),
  legacyQualityReportRecipients: z.array(z.string().min(1)).min(1),
  mailEnabled: z.boolean().optional(),
}).strict();

export const EndedCallIngestSchema = z
  .object({
    schemaVersion: z.literal(1),
    channel: z.literal("yino"),
    callId: ArtifactPathSegmentSchema,
    eventId: z.string().regex(/^[a-f0-9]{64}$/),
    startedAt: UtcMillisecondTimestampSchema,
    endedAt: UtcMillisecondTimestampSchema,
    durationSeconds: z.number().int().min(0).max(86_400),
    transcript: z.string(),
    summary: z.string(),
    recordingUrl: z.null(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.transcript.length === 0 && value.summary.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "transcript or summary required",
      });
    }
    const expected = Math.floor(
      (Date.parse(value.endedAt) - Date.parse(value.startedAt)) / 1000,
    );
    if (value.durationSeconds !== expected) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "durationSeconds mismatch",
      });
    }
    if (Date.parse(value.endedAt) < Date.parse(value.startedAt)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "endedAt before startedAt",
      });
    }
  });

export const CallAnalysisSchema = z.object({
  customerName: z.string(),
  contactInfo: z.string(),
  mainTopics: z.array(z.string()),
  formattedTranscript: z.string(),
  localCallTime: z.string(),
});

export const QualityAnalysisSchema = z.object({
  score: z.number().min(0).max(10),
  strengths: z.array(z.string()),
  weaknesses: z.array(z.string()),
  suggestions: z.array(z.string()),
  shouldUpdatePrompt: z.boolean(),
  summary: z.string(),
});

export type CallAnalysisOutput = z.infer<typeof CallAnalysisSchema>;
export type QualityAnalysisOutput = z.infer<typeof QualityAnalysisSchema>;
