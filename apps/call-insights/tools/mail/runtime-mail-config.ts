import type { ProfileRegistry } from "../../src/domain/types.js";
import {
  loadProfilesFromDirectory,
  SnapshotProfileRegistry,
  type ConfigHealth,
} from "../../src/profiles/runtime-config.js";
import {
  loadRecipientConfig,
  type RecipientConfig,
} from "./recipient-config.js";

export class RuntimeMailConfig {
  readonly profiles = new SnapshotProfileRegistry();
  private recipients: RecipientConfig | null = null;
  private lastLoadedAt: string | null = null;
  private lastErrorAt: string | null = null;
  private lastError = false;

  constructor(
    private readonly options: {
      profilesDirectory: string;
      recipientsPath: string;
      clock?: () => Date;
    },
  ) {}

  async load(): Promise<boolean> {
    const clock = this.options.clock ?? (() => new Date());
    const at = clock().toISOString();
    try {
      const list = await loadProfilesFromDirectory(this.options.profilesDirectory);
      const registry: ProfileRegistry = {
        get(slug) {
          return list.find((profile) => profile.slug === slug) ?? null;
        },
        list() {
          return [...list];
        },
      };
      const recipients = await loadRecipientConfig(
        this.options.recipientsPath,
        undefined,
        registry,
      );
      this.profiles.replace(list);
      this.recipients = recipients;
      this.lastLoadedAt = at;
      this.lastError = false;
      this.lastErrorAt = null;
      return true;
    } catch {
      this.lastError = true;
      this.lastErrorAt = at;
      return false;
    }
  }

  getRecipients(): RecipientConfig {
    if (!this.recipients) {
      throw new Error("recipient_config_invalid");
    }
    return this.recipients;
  }

  getHealth(): ConfigHealth {
    return {
      status: this.lastError ? "degraded" : "ok",
      profileCount: this.profiles.list().length,
      lastLoadedAt: this.lastLoadedAt,
      lastErrorAt: this.lastError ? this.lastErrorAt : null,
    };
  }
}
