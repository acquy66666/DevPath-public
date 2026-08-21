import { apiFetch } from "./client";
import type { User } from "./auth";

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
