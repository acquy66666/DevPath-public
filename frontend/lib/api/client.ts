/**
 * Base HTTP client. Every call to the FastAPI backend goes through here so
 * that error parsing, headers and the base URL live in exactly one place.
 */

const FALLBACK_BASE_URL = "http://localhost:8000";

/**
 * Server and browser reach the backend by different names. Under Docker
 * Compose a Server Component resolves the service hostname `backend`, which
 * means nothing in the user's browser -- the browser has to use the port
 * published on the host. Outside Docker both sides collapse to the same URL.
 *
 * The browser URL must stay on `localhost`, not `127.0.0.1`: those count as
 * different sites, and the refresh cookie is `SameSite=lax`, so the browser
 * would silently drop it on every call from a page served at localhost:3000.
 */
function baseUrl(): string {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL_INTERNAL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      FALLBACK_BASE_URL
    );
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL ?? FALLBACK_BASE_URL;
}

/** Mirrors the backend envelope: {"detail": {"code", "message"}}. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiRequestInit extends RequestInit {
  /** Access token to send as `Authorization: Bearer`, when the call needs one. */
  accessToken?: string | null;
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { accessToken, headers, ...rest } = init;

  const response = await fetch(`${baseUrl()}${path}`, {
    ...rest,
    // The refresh token is an HttpOnly cookie on the backend origin; without
    // this the browser keeps it to itself and every refresh looks signed out.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = response.statusText;

    try {
      const body = await response.json();
      if (body?.detail?.code) {
        code = body.detail.code;
        message = body.detail.message ?? message;
      }
    } catch {
      // Body was not JSON — keep the status text.
    }

    throw new ApiError(code, message, response.status);
  }

  // 204 and friends have no body at all; parsing one would throw.
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return (await response.json()) as T;
}
