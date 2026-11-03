import { apiFetch } from "./client";
import type { Session, User } from "./auth";

export type InstructorApplicationStatus = "pending" | "approved" | "rejected";

/** Mirrors `InstructorApplicationOut`: the applicant's own receipt. */
export interface InstructorApplication {
  id: string;
  status: InstructorApplicationStatus;
  motivation: string | null;
  rejection_reason: string | null;
  created_at: string;
  decided_at: string | null;
}

/** The caller's latest application to teach, or null if they never applied. */
export async function getMyInstructorApplication(
  accessToken: string,
): Promise<InstructorApplication | null> {
  const body = await apiFetch<{ application: InstructorApplication | null }>(
    "/api/v1/users/me/instructor-application",
    { accessToken },
  );
  return body.application;
}

/**
 * Ask an admin to make this account an instructor. Changes no role: the
 * account stays a student until the application is approved.
 */
export function applyToTeach(
  accessToken: string,
  motivation: string,
): Promise<InstructorApplication> {
  return apiFetch<InstructorApplication>("/api/v1/users/me/instructor-application", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ motivation }),
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

export interface AvatarUploadRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface AvatarUploadTicket {
  upload_url: string;
  storage_key: string;
  expires_in: number;
  /** Must be sent back verbatim as the Content-Type of the PUT: it is signed. */
  content_type: string;
}

/**
 * Ask the backend where to put a new profile picture. Moves no bytes.
 *
 * The key it answers with sits inside this account's own folder, and is the
 * only key the confirm call below will accept.
 */
export function createAvatarUpload(
  accessToken: string,
  input: AvatarUploadRequest,
): Promise<AvatarUploadTicket> {
  return apiFetch<AvatarUploadTicket>("/api/v1/users/me/avatar", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

/** Tell the backend the bytes arrived, so the account starts wearing them. */
export function completeAvatarUpload(
  accessToken: string,
  storageKey: string,
): Promise<User> {
  return apiFetch<User>("/api/v1/users/me/avatar/complete", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ storage_key: storageKey }),
  });
}
