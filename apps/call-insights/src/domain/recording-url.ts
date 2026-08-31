export function isPresignedHttpsPlaybackUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.searchParams.has("X-Amz-Signature");
  } catch {
    return false;
  }
}

function firstPresignedHttpsUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length === 0) {
    return null;
  }
  return isPresignedHttpsPlaybackUrl(value) ? value : null;
}

export function selectPresignedPlaybackUrl(artifact: unknown): string | null {
  if (typeof artifact !== "object" || artifact === null || Array.isArray(artifact)) {
    return null;
  }
  const record = artifact as Record<string, unknown>;
  return (
    firstPresignedHttpsUrl(record.presignedMonoUrl) ??
    firstPresignedHttpsUrl(record.presignedStereoUrl) ??
    firstPresignedHttpsUrl(record.recordingUrl)
  );
}
