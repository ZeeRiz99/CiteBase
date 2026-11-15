/**
 * Typed client for the CiteBase API (same origin, behind Caddy at /api).
 *
 * - Sends the signed double-submit CSRF token on every unsafe request.
 * - On 401, refreshes the session once (shared across concurrent requests) and retries.
 * - Turns the backend error envelope into ApiError with field-level messages.
 */

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldError[];
  readonly requestId: string | null;
  readonly details: Record<string, string>;

  constructor(
    status: number,
    code: string,
    message: string,
    fields: FieldError[] = [],
    requestId: string | null = null,
    details: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.requestId = requestId;
    this.details = details;
  }
}

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    fields?: FieldError[];
    request_id?: string | null;
    details?: Record<string, string>;
  };
};

const GENERIC_ERROR = "Something went wrong. Please try again.";

/** Build an ApiError from a status code and raw response text (the backend error envelope). */
export function parseApiError(status: number, text: string): ApiError {
  try {
    const err = (JSON.parse(text) as ErrorEnvelope).error ?? {};
    return new ApiError(
      status,
      err.code ?? "http_error",
      err.message ?? GENERIC_ERROR,
      err.fields ?? [],
      err.request_id ?? null,
      err.details ?? {},
    );
  } catch {
    return new ApiError(status, "http_error", GENERIC_ERROR);
  }
}

const CSRF_COOKIE = "cb_csrf";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
// Endpoints where a 401 is a real answer, not an expired access token.
const NO_REFRESH = [
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
  "/api/v1/auth/csrf",
  "/api/v1/auth/forgot-password",
  "/api/v1/auth/reset-password",
  "/api/v1/auth/verify-email",
];

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length));
  }
  return null;
}

let csrfInFlight: Promise<string> | null = null;

export async function getCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfInFlight ??= fetch("/api/v1/auth/csrf", { credentials: "same-origin" })
    .then(async (res) => {
      if (!res.ok) throw await toApiError(res);
      const body = (await res.json()) as { csrf_token: string };
      return body.csrf_token;
    })
    .finally(() => {
      csrfInFlight = null;
    });
  return csrfInFlight;
}

async function toApiError(res: Response): Promise<ApiError> {
  return parseApiError(res.status, await res.text().catch(() => ""));
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (UNSAFE.has(method)) headers["X-CSRF-Token"] = await getCsrfToken();
  return fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

let refreshInFlight: Promise<boolean> | null = null;

/** Refresh the session once for all concurrent callers. True if the retry may succeed. */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= send("POST", "/api/v1/auth/refresh")
    .then(async (res) => {
      if (res.ok) return true;
      // Another tab rotated the token a moment ago; the shared cookie jar already has the new one.
      if (res.status === 401) return (await toApiError(res)).code === "refresh_race";
      return false;
    })
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

export async function apiRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res = await send(method, path, body);
  if (res.status === 401 && !NO_REFRESH.includes(path) && (await refreshSession())) {
    res = await send(method, path, body);
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => apiRequest<T>("GET", path),
  post: <T>(path: string, body?: unknown) => apiRequest<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>("PATCH", path, body),
  delete: <T>(path: string) => apiRequest<T>("DELETE", path),
};

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "We could not reach the server. Check your connection and try again.";
}
