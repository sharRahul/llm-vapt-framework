/**
 * The console's single HTTP client for the VulnoraIQ API.
 *
 * Every component used to carry its own copy of `fetch` + CSRF-token plumbing,
 * which meant seven slightly different error messages and seven chances to
 * forget the CSRF header on a mutating call. `apiPost` and `apiPatch` obtain the
 * token themselves, so callers only supply a path and a body.
 */

/** An API call that returned a non-2xx status, carrying the server's message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * The message to show for a failed response.
 *
 * The API reports failures as `{"error": "..."}`. Using the raw body put the
 * whole JSON envelope on screen — braces, quotes, and `
` escapes and all —
 * which for a Docker build failure meant an unreadable wall of encoded log.
 */
function errorMessage(body: string, statusText: string): string {
  const text = body.trim();
  if (text.startsWith("{")) {
    try {
      const parsed = JSON.parse(text) as { error?: unknown; message?: unknown };
      const detail = parsed.error ?? parsed.message;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
    } catch {
      // Not JSON after all; the raw text is still better than nothing.
    }
  }
  return text || statusText;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(await response.text(), response.statusText));
  }
  return (await response.json()) as T;
}

/** GET a JSON resource. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

// The server keeps a CSRF token valid for VULNORAIQ_CSRF_TOKEN_TTL (300s by
// default). Fetching a fresh one before every mutation doubled the request
// count for each user action and pushed the console into the rate limiter
// during normal use. Cache it well inside the server's window and re-fetch on
// the one failure that means it expired.
const TOKEN_TTL_MS = 120_000;
let cachedToken: { value: string; expires: number } | null = null;

/** Fetch the current CSRF token for this session, reusing a cached one. */
export async function csrfToken(forceRefresh = false): Promise<string> {
  if (!forceRefresh && cachedToken && cachedToken.expires > Date.now()) return cachedToken.value;
  const { csrf_token } = await apiGet<{ csrf_token: string }>("/api/csrf-token");
  cachedToken = { value: csrf_token, expires: Date.now() + TOKEN_TTL_MS };
  return csrf_token;
}

/** Drop the cached CSRF token, forcing the next mutation to fetch a new one. */
export function clearCsrfToken(): void {
  cachedToken = null;
}

async function send<T>(method: "POST" | "PATCH", path: string, body: unknown, token: string): Promise<T> {
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
    body: JSON.stringify(body ?? {}),
  });
}

async function mutate<T>(method: "POST" | "PATCH", path: string, body: unknown): Promise<T> {
  try {
    return await send<T>(method, path, body, await csrfToken());
  } catch (error) {
    // A 403 on a mutation is what an expired cached token looks like. Retry
    // once with a fresh one; anything else is a real failure.
    if (error instanceof ApiError && error.status === 403) {
      clearCsrfToken();
      return send<T>(method, path, body, await csrfToken(true));
    }
    throw error;
  }
}

/** POST a JSON body, attaching the CSRF token the server requires. */
export function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return mutate<T>("POST", path, body);
}

/** PATCH a JSON body, attaching the CSRF token the server requires. */
export function apiPatch<T>(path: string, body: unknown = {}): Promise<T> {
  return mutate<T>("PATCH", path, body);
}

/**
 * Like `apiPost`, but resolves to `null` instead of throwing.
 *
 * For optional enrichment (CVE lookups, assistant explanations) where the panel
 * should simply stay empty when the backing service is unavailable.
 */
export async function apiPostOptional<T>(path: string, body: unknown = {}): Promise<T | null> {
  try {
    return await apiPost<T>(path, body);
  } catch {
    return null;
  }
}
