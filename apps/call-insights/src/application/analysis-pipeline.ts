import {
  AiProviderShutdownError,
  type AiProvider,
} from "../ai/provider.js";
import { CallAnalysisSchema, QualityAnalysisSchema } from "../domain/schemas.js";
import type {
  AnalysisJob,
  ProfileRegistry,
  StoredAnalysis,
} from "../domain/types.js";
import type {
  ArtifactInput,
  ArtifactResult,
  ArtifactWriter,
} from "../reports/artifact-writer.js";
import {
  OFF_OUTBOX_PLANNER,
  type OutboxPlanningSink,
} from "../outbound/outbox-planner.js";
import type { SqliteStore } from "../storage/sqlite-store.js";

const MAX_ERROR_LENGTH = 500;

type PipelineErrorCategory =
  | "pipeline input invalid"
  | "stored analysis invalid"
  | "call analysis failed"
  | "quality analysis failed"
  | "analysis persistence failed"
  | "artifact generation failed"
  | "outbox_planning_failed"
  | "analysis pipeline failed";

type ArtifactSink = Pick<ArtifactWriter, "write"> & {
  write(input: ArtifactInput): Promise<ArtifactResult>;
};

class CategorizedPipelineError extends Error {
  constructor(readonly category: PipelineErrorCategory) {
    super(category);
  }
}

export class AnalysisPipeline {
  constructor(
    private readonly store: SqliteStore,
    private readonly profiles: ProfileRegistry,
    private readonly ai: AiProvider,
    private readonly artifacts: ArtifactSink,
    private readonly clock: () => Date = () => new Date(),
    private readonly outbox: OutboxPlanningSink = OFF_OUTBOX_PLANNER,
  ) {}

  async process(job: AnalysisJob): Promise<void> {
    try {
      const call = this.store.getCall(job.profile, job.callId);
      if (!call) {
        throw new CategorizedPipelineError("pipeline input invalid");
      }
      const profile = this.profiles.get(job.profile);
      if (!profile) {
        throw new CategorizedPipelineError("pipeline input invalid");
      }
      if (call.profile !== profile.slug || job.profile !== profile.slug) {
        throw new CategorizedPipelineError("pipeline input invalid");
      }

      const generatedAt = this.clock().toISOString();
      let analysis: StoredAnalysis | null;
      try {
        analysis = this.store.getAnalysis(job.profile, job.callId);
      } catch {
        throw new CategorizedPipelineError("stored analysis invalid");
      }
      if (!analysis) {
        let callAnalysis;
        try {
          callAnalysis = CallAnalysisSchema.parse(
            await this.ai.analyzeCall({ call, profile }),
          );
        } catch (error) {
          if (error instanceof AiProviderShutdownError) {
            throw error;
          }
          throw new CategorizedPipelineError("call analysis failed");
        }
        let qualityAnalysis;
        try {
          qualityAnalysis = QualityAnalysisSchema.parse(
            await this.ai.analyzeQuality({ call, profile }),
          );
        } catch (error) {
          if (error instanceof AiProviderShutdownError) {
            throw error;
          }
          throw new CategorizedPipelineError("quality analysis failed");
        }
        try {
          this.store.saveAnalysis(
            job.profile,
            job.callId,
            this.ai.name,
            callAnalysis,
            qualityAnalysis,
            generatedAt,
          );
        } catch {
          throw new CategorizedPipelineError("analysis persistence failed");
        }
        analysis = {
          profile: job.profile,
          callId: job.callId,
          provider: this.ai.name,
          callAnalysis,
          qualityAnalysis,
          createdAt: generatedAt,
        } satisfies StoredAnalysis;
      }

      let artifacts: ArtifactResult;
      try {
        artifacts = await this.artifacts.write({
          profile,
          call,
          analysis: analysis.callAnalysis,
          quality: analysis.qualityAnalysis,
          provider: analysis.provider,
          generatedAt,
        });
      } catch {
        throw new CategorizedPipelineError("artifact generation failed");
      }
      try {
        this.outbox.plan({
          profile,
          call,
          analysis: analysis.callAnalysis,
          quality: analysis.qualityAnalysis,
          artifacts,
        });
      } catch {
        throw new CategorizedPipelineError("outbox_planning_failed");
      }

      this.store.succeedJob(job.jobId);
    } catch (error) {
      if (error instanceof AiProviderShutdownError) {
        this.store.releaseRunningJobForShutdown(job.jobId);
        return;
      }
      this.store.failJob(job.jobId, this.safeError(error));
    }
  }

  private safeError(error: unknown): string {
    const category = error instanceof CategorizedPipelineError
      ? error.category
      : "analysis pipeline failed";
    return category.slice(0, MAX_ERROR_LENGTH);
  }
}
