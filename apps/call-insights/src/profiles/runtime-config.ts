import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import type { z } from "zod";
import { ClientProfileSchema } from "../domain/schemas.js";
import type { ClientProfile, ProfileRegistry } from "../domain/types.js";

export const CONFIG_POLL_INTERVAL_MS = 3_000;

export interface ConfigHealth {
  status: "ok" | "degraded";
  profileCount: number;
  lastLoadedAt: string | null;
  lastErrorAt: string | null;
}

export class SnapshotProfileRegistry implements ProfileRegistry {
  constructor(private profiles: readonly ClientProfile[] = []) {}

  replace(profiles: readonly ClientProfile[]): void {
    this.profiles = profiles;
  }

  get(slug: string): ClientProfile | null {
    return this.profiles.find((profile) => profile.slug === slug) ?? null;
  }

  list(): ClientProfile[] {
    return [...this.profiles];
  }
}

export async function loadProfilesFromDirectory(
  directory: string,
): Promise<ClientProfile[]> {
  const names = (await readdir(directory))
    .filter((name) => name.endsWith(".json"))
    .sort((left, right) => left.localeCompare(right));
  const loaded: ClientProfile[] = [];
  const seen = new Set<string>();
  for (const name of names) {
    const slug = name.slice(0, -".json".length);
    let raw: unknown;
    try {
      raw = JSON.parse(await readFile(join(directory, name), "utf8"));
    } catch {
      throw new Error("config_invalid");
    }
    const parsed = ClientProfileSchema.safeParse(raw);
    if (!parsed.success || parsed.data.slug !== slug || seen.has(slug)) {
      throw new Error("config_invalid");
    }
    seen.add(slug);
    loaded.push(toClientProfile(parsed.data));
  }
  if (loaded.length === 0) {
    throw new Error("config_invalid");
  }
  return loaded;
}

export class RuntimeProfileSource {
  readonly registry = new SnapshotProfileRegistry();
  private lastLoadedAt: string | null = null;
  private lastErrorAt: string | null = null;
  private lastError = false;

  constructor(
    private readonly options: {
      directory: string;
      clock?: () => Date;
    },
  ) {}

  async load(): Promise<boolean> {
    const clock = this.options.clock ?? (() => new Date());
    const at = clock().toISOString();
    try {
      const profiles = await loadProfilesFromDirectory(this.options.directory);
      this.registry.replace(profiles);
      this.lastLoadedAt = at;
      this.lastErrorAt = null;
      this.lastError = false;
      return true;
    } catch {
      this.lastErrorAt = at;
      this.lastError = true;
      return false;
    }
  }

  getHealth(): ConfigHealth {
    return {
      status: this.lastError ? "degraded" : "ok",
      profileCount: this.registry.list().length,
      lastLoadedAt: this.lastLoadedAt,
      lastErrorAt: this.lastError ? this.lastErrorAt : null,
    };
  }
}

function toClientProfile(
  parsed: z.infer<typeof ClientProfileSchema>,
): ClientProfile {
  const profile: ClientProfile = {
    slug: parsed.slug,
    displayName: parsed.displayName,
    assistantName: parsed.assistantName,
    vapiAssistantId: parsed.vapiAssistantId,
    timezone: parsed.timezone,
    brandName: parsed.brandName,
    analysisLanguage: parsed.analysisLanguage,
    qualityLanguage: parsed.qualityLanguage,
    companyAliases: parsed.companyAliases,
    legacyCustomerReportRecipients: parsed.legacyCustomerReportRecipients,
    legacyQualityReportRecipients: parsed.legacyQualityReportRecipients,
  };
  if (parsed.vapiAcceptedAssistantIds) {
    profile.vapiAcceptedAssistantIds = parsed.vapiAcceptedAssistantIds;
  }
  if (parsed.mailEnabled !== undefined) {
    profile.mailEnabled = parsed.mailEnabled;
  }
  return profile;
}
