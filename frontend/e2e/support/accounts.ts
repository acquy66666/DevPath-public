/**
 * Fixed accounts for the suites that look at screens rather than tell a story
 * (visual regression, accessibility): the seed's admin and instructor, plus
 * one student signed up on first use and reused after, so a run leaves no new
 * account behind and the admin's counts stay put from run to run.
 *
 * Sign-in allows 10 tries per email per 15 minutes, so each suite signs a role
 * in once and keeps that page.
 */
import { type APIRequestContext, type Page, expect } from "@playwright/test";

import { API_URL, PASSWORD } from "./stack";

export interface Account {
  email: string;
  password: string;
}

export const ADMIN: Account = { email: "admin@devpath.example", password: "devpath-admin" };
export const INSTRUCTOR: Account = {
  email: "khoa.tran@devpath.example",
  password: "devpath-instructor",
};
export const STUDENT: Account = { email: "visual-hocvien@e2e.devpath.example", password: PASSWORD };

/** The seed's courses (backend/scripts/seed_courses.py). */
export const FREE_COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
export const PAID_COURSE = "cau-truc-du-lieu-va-giai-thuat-voi-python";

export type Json = Record<string, unknown>;

export async function api(
  request: APIRequestContext,
  method: string,
  url: string,
  { token, data, ok = [] }: { token?: string; data?: Json; ok?: number[] } = {},
): Promise<Json> {
  const response = await request.fetch(`${API_URL}/api/v1${url}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    data,
  });
  const accepted = response.ok() || ok.includes(response.status());
  expect(accepted, `${method} ${url}: ${response.status()} ${await response.text()}`).toBe(true);
  return response.status() === 204 || !response.ok() ? {} : ((await response.json()) as Json);
}

/**
 * Sign in through the page's own request context, so the refresh cookie lands
 * in the browser's jar and the next page load comes up signed in -- the same
 * way a reloaded tab does.
 */
export async function signIn(page: Page, who: Account): Promise<string> {
  const login = await page.request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: who.email, password: who.password },
  });
  if (login.ok()) return ((await login.json()) as Json).access_token as string;
  // Only the student may be missing: it is created here, once per database.
  const missingStudent = who === STUDENT && login.status() === 401;
  expect(missingStudent, `login ${who.email}: ${login.status()} ${await login.text()}`).toBe(true);
  const registered = await api(page.request, "POST", "/auth/register", {
    data: { email: who.email, password: who.password, full_name: "Học Viên Ảnh" },
  });
  return registered.access_token as string;
}
