import { constants } from "node:fs";
import { open } from "node:fs/promises";
import type { ProfileRegistry } from "../../src/domain/types.js";

export const MAIL_SENDER = "yinoagent@gmail.com";

const PRIVATE_PERMISSION_MASK = 0o077;
const MAX_CONFIG_BYTES = 64 * 1024;
const MAILBOX_PATTERN =
  /^[A-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}$/i;
const CC_ROLES = new Set([
  "customer-report-cc",
  "customer-report-support",
]);

export interface RecipientConfig {
  sender: typeof MAIL_SENDER;
  profiles: Readonly<Record<string, {
    roles: Readonly<Record<string, readonly string[]>>;
  }>>;
}

export interface RecipientEnvelope {
  to: string[];
  cc: string[];
}

export interface RecipientConfigDependencies {
  open(path: string, flags: number): Promise<{
    stat(): Promise<{
      mode: number;
      uid: number;
      size?: number;
      isFile(): boolean;
    }>;
    readFile(): Promise<Buffer>;
    close(): Promise<void>;
  }>;
  getuid(): number;
}

const DEFAULT_DEPENDENCIES: RecipientConfigDependencies = {
  open: (path, flags) => open(path, flags),
  getuid: () => {
    const uid = process.geteuid?.() ?? process.getuid?.();
    if (uid === undefined) {
      throw new Error("recipient_config_permissions_invalid");
    }
    return uid;
  },
};

interface RecipientFileMetadata {
    mode: number;
    uid: number;
    size?: number;
    isFile(): boolean;
}

export async function loadRecipientConfig(
  path: string,
  _expectedChecksum: string | undefined,
  profiles: ProfileRegistry,
  dependencies: RecipientConfigDependencies = DEFAULT_DEPENDENCIES,
): Promise<RecipientConfig> {
  const noFollow = typeof constants.O_NOFOLLOW === "number"
    ? constants.O_NOFOLLOW
    : 0;
  const handle = await dependencies.open(
    path,
    constants.O_RDONLY | noFollow,
  );
  try {
    const metadata: RecipientFileMetadata = await handle.stat();
    if (
      !metadata.isFile() ||
      metadata.uid !== dependencies.getuid() ||
      (metadata.mode & 0o400) === 0 ||
      (metadata.mode & PRIVATE_PERMISSION_MASK) !== 0 ||
      (metadata.size !== undefined && metadata.size > MAX_CONFIG_BYTES)
    ) {
      throw new Error("recipient_config_permissions_invalid");
    }

    const contents = await handle.readFile();
    if (contents.byteLength > MAX_CONFIG_BYTES) {
      throw new Error("recipient_config_invalid");
    }

    let raw: unknown;
    try {
      raw = JSON.parse(contents.toString("utf8"));
    } catch {
      throw new Error("recipient_config_invalid");
    }
    return validateConfig(raw, requiredProfileRoles(profiles));
  } finally {
    await handle.close();
  }
}

export function resolveRecipientEnvelope(
  config: RecipientConfig,
  profile: string,
  roles: readonly string[],
): RecipientEnvelope {
  const profileConfig = config.profiles[profile];
  if (!profileConfig) {
    throw new Error("recipient_config_invalid");
  }
  const to: string[] = [];
  const cc: string[] = [];
  for (const role of roles) {
    const addresses = profileConfig.roles[role];
    if (!addresses) {
      throw new Error("recipient_config_invalid");
    }
    (CC_ROLES.has(role) ? cc : to).push(...addresses);
  }
  if (to.length === 0) {
    throw new Error("recipient_config_invalid");
  }
  return { to, cc };
}

function requiredProfileRoles(
  profiles: ProfileRegistry,
): Map<string, Set<string>> {
  const required = new Map<string, Set<string>>();
  for (const profile of profiles.list()) {
    const roles = new Set<string>();
    for (const role of [
      ...profile.legacyCustomerReportRecipients,
      ...profile.legacyQualityReportRecipients,
    ]) {
      roles.add(role);
    }
    required.set(profile.slug, roles);
  }
  return required;
}

function validateConfig(
  raw: unknown,
  required: ReadonlyMap<string, ReadonlySet<string>>,
): RecipientConfig {
  if (
    !isObject(raw) ||
    raw.sender !== MAIL_SENDER ||
    !isObject(raw.profiles)
  ) {
    throw new Error("recipient_config_invalid");
  }
  const rawProfiles = raw.profiles;
  const profileNames = Object.keys(rawProfiles);
  if (
    profileNames.length !== required.size ||
    profileNames.some((profile) => !required.has(profile)) ||
    [...required.keys()].some(
      (profile) => !Object.hasOwn(rawProfiles, profile),
    )
  ) {
    throw new Error("recipient_config_invalid");
  }

  const validatedProfiles: Record<string, {
    roles: Readonly<Record<string, readonly string[]>>;
  }> = {};
  for (const profile of profileNames) {
    const profileConfig = rawProfiles[profile];
    const profileRequirements = required.get(profile);
    if (
      !isObject(profileConfig) ||
      !isObject(profileConfig.roles) ||
      !profileRequirements
    ) {
      throw new Error("recipient_config_invalid");
    }
    const rawRoles = profileConfig.roles;
    const roleNames = Object.keys(rawRoles);
    if (
      roleNames.length !== profileRequirements.size ||
      roleNames.some((role) => !profileRequirements.has(role)) ||
      [...profileRequirements].some(
        (role) => !Object.hasOwn(rawRoles, role),
      )
    ) {
      throw new Error("recipient_config_invalid");
    }

    const seen = new Set<string>();
    const roles: Record<string, readonly string[]> = {};
    for (const role of roleNames) {
      const addresses = rawRoles[role];
      if (!Array.isArray(addresses) || addresses.length === 0) {
        throw new Error("recipient_config_invalid");
      }
      const validated: string[] = [];
      for (const address of addresses) {
        if (
          typeof address !== "string" ||
          address !== address.trim() ||
          /[\r\n]/.test(address) ||
          !MAILBOX_PATTERN.test(address)
        ) {
          throw new Error("recipient_config_invalid");
        }
        const normalized = address.toLowerCase();
        if (seen.has(normalized)) {
          throw new Error("recipient_config_invalid");
        }
        seen.add(normalized);
        validated.push(address);
      }
      roles[role] = Object.freeze(validated);
    }
    validatedProfiles[profile] = Object.freeze({
      roles: Object.freeze(roles),
    });
  }
  return Object.freeze({
    sender: MAIL_SENDER,
    profiles: Object.freeze(validatedProfiles),
  });
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
