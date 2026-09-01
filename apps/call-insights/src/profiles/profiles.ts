import type { ClientProfile, ProfileRegistry } from "../domain/types.js";
import lucaplusJson from "./lucaplus.json" with { type: "json" };
import inpGroupJson from "./inp-group.json" with { type: "json" };

const profiles: ClientProfile[] = [
  lucaplusJson as ClientProfile,
  inpGroupJson as ClientProfile,
];

export const profileRegistry: ProfileRegistry = {
  get(slug: string): ClientProfile | null {
    return profiles.find((profile) => profile.slug === slug) ?? null;
  },
  list(): ClientProfile[] {
    return [...profiles];
  },
};

export function loadProfile(slug: string): ClientProfile | null {
  return profileRegistry.get(slug);
}
