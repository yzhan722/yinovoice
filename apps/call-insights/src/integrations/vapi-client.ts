export class VapiCallFetchError extends Error {
  constructor() {
    super("vapi_call_fetch_failed");
    this.name = "VapiCallFetchError";
  }
}

const VAPI_REQUEST_TIMEOUT_MS = 20_000;

export async function fetchVapiCallJson(
  callId: string,
  apiKey: string,
  fetchFn: typeof fetch = fetch,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetchFn(`https://api.vapi.ai/call/${encodeURIComponent(callId)}`, {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.timeout(VAPI_REQUEST_TIMEOUT_MS),
      headers: {
        authorization: `Bearer ${apiKey}`,
        accept: "application/json",
      },
    });
  } catch {
    throw new VapiCallFetchError();
  }
  if (!response.ok) {
    try {
      await response.text();
    } catch {
      // Discard the body so it cannot leak into VapiCallFetchError.
    }
    throw new VapiCallFetchError();
  }
  try {
    return await response.json();
  } catch {
    throw new VapiCallFetchError();
  }
}

export async function listVapiCalls(
  apiKey: string,
  assistantId: string,
  limit: number,
  fetchFn: typeof fetch = fetch,
  createdAtLt?: string,
): Promise<unknown[]> {
  if (
    !apiKey.trim() ||
    !assistantId.trim() ||
    !Number.isSafeInteger(limit) ||
    limit < 1 ||
    limit > 100
  ) {
    throw new VapiCallFetchError();
  }
  const url = new URL("https://api.vapi.ai/call");
  url.searchParams.set("assistantId", assistantId);
  url.searchParams.set("limit", String(limit));
  if (createdAtLt !== undefined) {
    if (!Number.isFinite(Date.parse(createdAtLt))) {
      throw new VapiCallFetchError();
    }
    url.searchParams.set("createdAtLt", createdAtLt);
  }
  let response: Response;
  try {
    response = await fetchFn(url, {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.timeout(VAPI_REQUEST_TIMEOUT_MS),
      headers: {
        authorization: `Bearer ${apiKey}`,
        accept: "application/json",
      },
    });
  } catch {
    throw new VapiCallFetchError();
  }
  if (!response.ok) {
    try {
      await response.text();
    } catch {
      // Discard the body so it cannot leak into VapiCallFetchError.
    }
    throw new VapiCallFetchError();
  }
  try {
    const body: unknown = await response.json();
    if (!Array.isArray(body)) {
      throw new VapiCallFetchError();
    }
    return body;
  } catch (error) {
    if (error instanceof VapiCallFetchError) {
      throw error;
    }
    throw new VapiCallFetchError();
  }
}
