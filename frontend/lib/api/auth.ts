import { apiFetch } from "./client";

/** Matches UserOut in backend/app/schemas/auth.py. */
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "student" | "instructor" | "admin";
  avatar_url: string | null;
  created_at: string;
}

/**
 * Matches TokenOut. The refresh token is deliberately absent: it never reaches
 * JavaScript, it only travels in the HttpOnly cookie the backend sets.
 */
export interface Session {
  access_token: string;
  token_type: string;
  /** Lifetime of the access token in seconds. */
  expires_in: number;
  user: User;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export function register(input: RegisterInput): Promise<Session> {
  return apiFetch<Session>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function login(input: LoginInput): Promise<Session> {
  return apiFetch<Session>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * One shared refresh request at a time.
 *
 * The backend rotates the refresh token on every successful call and treats a
 * revoked one coming back as theft -- it then closes *every* session of that
 * user. So two overlapping refreshes from the same browser would sign the
 * person out: the second still carries the cookie the first just replaced.
 * React StrictMode makes that the normal case in development by mounting
 * effects twice; a slow network makes it possible anywhere.
 */
let inFlightRefresh: Promise<Session> | null = null;

/**
 * Trade the refresh cookie for a new access token. This is how a reloaded tab
 * gets its session back: the token itself lives only in memory and is gone.
 *
 * Callers that arrive while a refresh is already running get that same promise
 * rather than a second request.
 */
export function refresh(): Promise<Session> {
  inFlightRefresh ??= apiFetch<Session>("/api/v1/auth/refresh", {
    method: "POST",
  }).finally(() => {
    inFlightRefresh = null;
  });

  return inFlightRefresh;
}

export function logout(): Promise<void> {
  return apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
}

export function getMe(accessToken: string): Promise<User> {
  return apiFetch<User>("/api/v1/auth/me", { accessToken });
}
