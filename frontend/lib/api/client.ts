/**
 * Base HTTP client. Every call to the FastAPI backend goes through here so
 * that error parsing, headers and the base URL live in exactly one place.
 */

const FALLBACK_BASE_URL = "http://localhost:8000";

/**
 * Where the browser sends API calls.
 *
 * An empty `NEXT_PUBLIC_API_BASE_URL` is an answer, not a missing value: it
 * means *the origin the page came from*. In production nginx routes /api to
 * the backend on that same origin, so the browser needs no host at all -- and
 * the image stops carrying the domain it was built for. One build then serves
 * a tunnel URL, a custom domain, or a bare IP, which matters because the
 * value is inlined at build time and cannot be changed by restarting.
 *
 * Unset is a different thing and keeps the local default, so `next dev`
 * against a backend on port 8000 still works with no configuration.
 *
 * When it is set, it must stay on `localhost` rather than `127.0.0.1`: those
 * count as different sites, and the refresh cookie is `SameSite=lax`, so the
 * browser would silently drop it on every call from a page at localhost:3000.
 */
function browserBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  return configured === undefined ? FALLBACK_BASE_URL : configured;
}

/**
 * Where a Server Component sends them -- never same-origin, because a
 * relative URL inside Node has no origin to be relative to. Hence `||` rather
 * than `??`: an empty public value is meant for the browser and must fall
 * through to something absolute here.
 *
 * Under Docker Compose that is the service hostname `backend`, which resolves
 * on the compose network and means nothing in the user's browser.
 */
function serverBaseUrl(): string {
  return (
    process.env.API_BASE_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    FALLBACK_BASE_URL
  );
}

function baseUrl(): string {
  return typeof window === "undefined" ? serverBaseUrl() : browserBaseUrl();
}

/**
 * URL of a backend endpoint, for links the browser follows itself. Same-origin
 * deployments get a root-relative path, which is exactly what an `href` wants.
 * `fetch` calls go through apiFetch instead and never need this.
 */
export function apiUrl(path: string): string {
  return `${baseUrl()}${path}`;
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
