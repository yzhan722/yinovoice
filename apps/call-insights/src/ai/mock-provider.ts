import { CallAnalysisSchema, QualityAnalysisSchema } from "../domain/schemas.js";
import type { CallAnalysis, QualityAnalysis } from "../domain/types.js";
import type { AiProvider, CallAnalysisInput, QualityAnalysisInput } from "./provider.js";

export class MockAiProvider implements AiProvider {
  readonly name = "mock" as const;

  close(): void {}

  async analyzeCall(input: CallAnalysisInput): Promise<CallAnalysis> {
    return CallAnalysisSchema.parse({
      customerName: "Demo Customer",
      contactInfo: "demo@example.invalid",
      mainTopics: ["invoice automation"],
      formattedTranscript: input.call.transcript,
      localCallTime: new Intl.DateTimeFormat("en-AU", {
        timeZone: input.profile.timezone,
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(input.call.startedAt)),
    });
  }

  async analyzeQuality(_input: QualityAnalysisInput): Promise<QualityAnalysis> {
    return QualityAnalysisSchema.parse({
      score: 8,
      strengths: ["Stayed on the invoice request"],
      weaknesses: ["Did not confirm the next action"],
      suggestions: ["End with a clear next step"],
      shouldUpdatePrompt: true,
      summary: "The assistant handled the demo invoice request clearly with one follow-up gap.",
    });
  }
}
