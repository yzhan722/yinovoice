export const DEFAULT_PUBLIC_ORIGIN = "http://127.0.0.1:3210";

export function assertPublicOrigin(value: string): string {
  const trimmed = value.trim();
  const withoutTrailingSlash = trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
  if (withoutTrailingSlash === DEFAULT_PUBLIC_ORIGIN) {
    return DEFAULT_PUBLIC_ORIGIN;
  }

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new Error("invalid public origin");
  }

  if (url.username || url.password || url.search || url.hash) {
    throw new Error("invalid public origin");
  }
  if (url.pathname !== "/" && url.pathname !== "") {
    throw new Error("invalid public origin");
  }

  const hostname = url.hostname.toLowerCase();
  if (hostname === "n8n.cloud" || hostname.endsWith(".n8n.cloud")) {
    throw new Error("n8n.cloud origins are not allowed");
  }
  if (url.protocol !== "https:") {
    throw new Error("invalid public origin");
  }
  return `${url.protocol}//${url.host}`;
}
