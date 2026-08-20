/**
 * Base HTTP client. Every call to the FastAPI backend goes through here so
 * that error parsing, headers and the base URL live in exactly one place.
 */

const FALLBACK_BASE_URL = "http://127.0.0.1:8000";

/**
 * Server and browser reach the backend by different names. Under Docker
 * Compose a Server Component resolves the service hostname `backend`, which
 * means nothing in the user's browser -- the browser has to use the port
 * published on the host. Outside Docker both sides collapse to the same URL.
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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
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

  return (await response.json()) as T;
}
