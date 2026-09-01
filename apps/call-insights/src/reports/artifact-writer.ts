import { randomUUID } from "node:crypto";
import {
  lstat,
  mkdir,
  readdir,
  realpath,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import {
  isAbsolute,
  join,
  parse,
  relative,
  resolve,
  sep,
} from "node:path";
import { ArtifactPathSegmentSchema } from "../domain/schemas.js";
import type { Call, CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import { assertPublicOrigin, DEFAULT_PUBLIC_ORIGIN } from "../domain/public-origin.js";
import { renderCustomerReport, renderQualityReport } from "./html.js";
import { composeOutboundMailPlan } from "./outbound.js";

const ARTIFACT_FILES = [
  "call.json",
  "customer-report.html",
  "quality-report.html",
  "manifest.json",
] as const;
const WRITER_TEMPORARY_FILE_PATTERN =
  /^(?:call\.json|customer-report\.html|quality-report\.html|manifest\.json)\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp$/i;

type ArtifactFilename = (typeof ARTIFACT_FILES)[number];
type FileStats = Awaited<ReturnType<typeof lstat>>;

export interface ArtifactWriterDependencies {
  publicOrigin?: string;
  beforeFileWrite?(
    directory: string,
    filename: ArtifactFilename,
  ): void | Promise<void>;
  lstat?(path: string): Promise<FileStats>;
  realpath?(path: string): Promise<string>;
}

export interface ArtifactInput {
  profile: ClientProfile;
  call: Call;
  analysis: CallAnalysis;
  quality: QualityAnalysis;
  provider: "mock" | "deepseek";
  generatedAt: string;
}

export interface ArtifactResult {
  directory: string;
  files: [
    "call.json",
    "customer-report.html",
    "quality-report.html",
    "manifest.json",
  ];
}

export class ArtifactWriter {
  private readonly publicOrigin: string;

  constructor(
    private readonly rootDirectory: string,
    private readonly dependencies: ArtifactWriterDependencies = {},
  ) {
    this.publicOrigin = assertPublicOrigin(
      this.dependencies.publicOrigin ?? DEFAULT_PUBLIC_ORIGIN,
    );
  }

  async write(input: ArtifactInput): Promise<ArtifactResult> {
    const profile = assertSafePathSegment(input.profile.slug, "profile");
    const callId = assertSafePathSegment(input.call.callId, "call id");
    const directory = join(this.rootDirectory, profile, callId);
    let prepared = false;

    try {
      await this.prepareDirectory(directory);
      prepared = true;
      await this.cleanupTemporaryFiles(directory);
      await this.removeRegularFileIfSafe(join(directory, "manifest.json"));
      await this.writeAtomic(
        directory,
        "call.json",
        `${JSON.stringify(
          {
            profile,
            callId,
            call: input.call,
            analysis: input.analysis,
            quality: input.quality,
            provider: input.provider,
            generatedAt: input.generatedAt,
          },
          null,
          2,
        )}\n`,
      );
      await this.writeAtomic(
        directory,
        "customer-report.html",
        renderCustomerReport({
          profile: input.profile,
          call: input.call,
          analysis: input.analysis,
          ratingBaseUrl: this.publicOrigin,
        }),
      );
      await this.writeAtomic(
        directory,
        "quality-report.html",
        renderQualityReport({
          profile: input.profile,
          call: input.call,
          analysis: input.analysis,
          quality: input.quality,
        }),
      );
      await this.writeAtomic(
        directory,
        "manifest.json",
        `${JSON.stringify(
          {
            schemaVersion: 1,
            profile,
            callId,
            provider: input.provider,
            generatedAt: input.generatedAt,
            files: [...ARTIFACT_FILES],
            legacyCustomerReportRecipients: input.profile.legacyCustomerReportRecipients,
            legacyQualityReportRecipients: input.profile.legacyQualityReportRecipients,
            outboundMail: composeOutboundMailPlan({
              profile: input.profile,
              analysis: input.analysis,
              quality: input.quality,
            }),
          },
          null,
          2,
        )}\n`,
      );
      return { directory, files: [...ARTIFACT_FILES] };
    } catch (error) {
      if (prepared) {
        await this.cleanupTemporaryFiles(directory, true);
        await this.removeRegularFileIfSafe(join(directory, "manifest.json"));
      }
      throw error;
    }
  }

  async listFiles(profileSlug: string, callIdValue: string): Promise<string[]> {
    try {
      const profile = assertSafePathSegment(profileSlug, "profile");
      const callId = assertSafePathSegment(callIdValue, "call id");
      const directory = join(this.rootDirectory, profile, callId);
      await this.assertContainedDirectory(directory);
      const entries = (await readdir(directory)).sort();
      const expected = [...ARTIFACT_FILES].sort();
      if (
        entries.length !== expected.length ||
        entries.some((entry, index) => entry !== expected[index])
      ) {
        throw new Error("artifact_set_invalid");
      }
      const files = ARTIFACT_FILES.map((filename) => join(directory, filename));
      for (const file of files) {
        await this.assertContainedRegularFile(file);
      }
      return files;
    } catch {
      throw new Error("artifact_discovery_failed");
    }
  }

  private async writeAtomic(
    directory: string,
    filename: ArtifactFilename,
    contents: string,
  ): Promise<void> {
    await this.assertContainedDirectory(directory);
    await this.dependencies.beforeFileWrite?.(directory, filename);
    await this.assertContainedDirectory(directory);
    const tempPath = join(directory, `${filename}.${randomUUID()}.tmp`);
    const destinationPath = join(directory, filename);
    try {
      await writeFile(tempPath, contents, { encoding: "utf8", flag: "wx" });
      await this.assertContainedRegularFile(tempPath);
      await this.assertSafeExistingDestination(destinationPath);
      await this.assertContainedDirectory(directory);
      await rename(tempPath, destinationPath);
      await this.assertContainedRegularFile(destinationPath);
    } catch (error) {
      await this.removeRegularFileIfSafe(tempPath);
      throw error;
    }
  }

  private async prepareDirectory(directory: string): Promise<void> {
    await this.assertNoLinkedAncestors(this.rootDirectory, true);
    await this.assertNoLinkedAncestors(directory, true);
    await mkdir(directory, { recursive: true });
    await this.assertContainedDirectory(directory);
  }

  private async assertContainedDirectory(directory: string): Promise<void> {
    await this.assertNoLinkedAncestors(this.rootDirectory, false);
    await this.assertNoLinkedAncestors(directory, false);
    const rootPath = resolve(this.rootDirectory);
    const directoryPath = resolve(directory);
    const rootStats = await this.readStats(rootPath);
    const directoryStats = await this.readStats(directoryPath);
    if (!rootStats.isDirectory() || !directoryStats.isDirectory()) {
      throw physicalContainmentError();
    }
    const [physicalRoot, physicalDirectory] = await Promise.all([
      this.readRealpath(rootPath),
      this.readRealpath(directoryPath),
    ]);
    if (!isWithin(physicalRoot, physicalDirectory)) {
      throw physicalContainmentError();
    }
  }

  private async assertContainedRegularFile(path: string): Promise<void> {
    await this.assertNoLinkedAncestors(path, false);
    const stats = await this.readStats(path);
    if (stats.isSymbolicLink() || !stats.isFile()) {
      throw physicalContainmentError();
    }
    const physicalRoot = await this.readRealpath(resolve(this.rootDirectory));
    const physicalFile = await this.readRealpath(resolve(path));
    if (!isWithin(physicalRoot, physicalFile)) {
      throw physicalContainmentError();
    }
  }

  private async assertSafeExistingDestination(path: string): Promise<void> {
    try {
      await this.assertContainedRegularFile(path);
    } catch (error) {
      if (isNotFound(error)) {
        return;
      }
      throw error;
    }
  }

  private async removeRegularFileIfSafe(path: string): Promise<void> {
    try {
      await this.assertContainedRegularFile(path);
    } catch (error) {
      if (isNotFound(error)) {
        return;
      }
      throw error;
    }
    await this.assertContainedDirectory(join(path, ".."));
    await rm(path, { force: true });
  }

  private async cleanupTemporaryFiles(
    directory: string,
    bestEffort = false,
  ): Promise<void> {
    let entries: string[];
    try {
      await this.assertContainedDirectory(directory);
      entries = await readdir(directory);
    } catch (error) {
      if (bestEffort) {
        return;
      }
      throw error;
    }
    for (const entry of entries.filter((name) =>
      WRITER_TEMPORARY_FILE_PATTERN.test(name)
    )) {
      if (bestEffort) {
        try {
          await this.removeRegularFileIfSafe(join(directory, entry));
        } catch {
          // The original write error remains authoritative during cleanup.
        }
      } else {
        await this.removeRegularFileIfSafe(join(directory, entry));
      }
    }
  }

  private async assertNoLinkedAncestors(
    target: string,
    allowMissing: boolean,
  ): Promise<void> {
    const absolute = resolve(target);
    const root = parse(absolute).root;
    const segments = absolute.slice(root.length).split(/[\\/]+/).filter(Boolean);
    let current = root;
    for (const segment of segments) {
      current = join(current, segment);
      let stats: FileStats;
      try {
        stats = await this.readStats(current);
      } catch (error) {
        if (allowMissing && isNotFound(error)) {
          return;
        }
        throw error;
      }
      if (stats.isSymbolicLink()) {
        throw physicalContainmentError();
      }
    }
  }

  private readStats(path: string): Promise<FileStats> {
    return (this.dependencies.lstat ?? lstat)(path);
  }

  private readRealpath(path: string): Promise<string> {
    return (this.dependencies.realpath ?? realpath)(path);
  }
}

function assertSafePathSegment(value: string, label: string): string {
  const parsed = ArtifactPathSegmentSchema.safeParse(value);
  if (!parsed.success) {
    throw new Error(`invalid ${label}: unsafe artifact path segment`);
  }
  return parsed.data;
}

function isWithin(root: string, candidate: string): boolean {
  const pathFromRoot = relative(root, candidate);
  return (
    pathFromRoot === "" ||
    (!pathFromRoot.startsWith(`..${sep}`) &&
      pathFromRoot !== ".." &&
      !isAbsolute(pathFromRoot))
  );
}

function physicalContainmentError(): Error {
  return new Error("artifact_physical_containment_failed");
}

function isNotFound(error: unknown): boolean {
  return (
    error !== null &&
    typeof error === "object" &&
    "code" in error &&
    error.code === "ENOENT"
  );
}
