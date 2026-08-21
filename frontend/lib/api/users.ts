import { apiFetch } from "./client";
import type { Session, User } from "./auth";

/**
 * Upgrade the signed-in account to `instructor`.
 *
 * There is no id in the path on purpose: the endpoint only ever touches the
 * account the token belongs to.
 */
export function becomeInstructor(accessToken: string): Promise<User> {
  return apiFetch<User>("/api/v1/users/me/instructor", {
    method: "POST",
    accessToken,
  });
}

export interface ProfileUpdate {
  full_name: string;
}

export function updateProfile(
  accessToken: string,
  input: ProfileUpdate,
): Promise<User> {
  return apiFetch<User>("/api/v1/users/me", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

/**
 * Change the password and start the sessions over.
 *
 * The backend revokes every session of this user, including the refresh cookie
 * this browser held, and answers with a replacement pair — so the caller has
 * to adopt the new session or it is signed out along with the other devices.
 */
export function changePassword(
  accessToken: string,
  input: PasswordChange,
): Promise<Session> {
  return apiFetch<Session>("/api/v1/users/me/password", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}
