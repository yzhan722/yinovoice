export function flattenContactInfo(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => flattenContactInfo(item)).join("; ");
  }
  if (typeof value === "object") {
    return Object.keys(value)
      .sort()
      .map((key) => {
        const nested = (value as Record<string, unknown>)[key];
        const flattened = isPlainObject(nested) || Array.isArray(nested)
          ? JSON.stringify(nested)
          : flattenContactInfo(nested);
        return `${key}: ${flattened}`;
      })
      .join("; ");
  }
  return "";
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
