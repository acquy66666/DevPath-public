/**
 * Setting the stage through the API, and the one step no browser can take.
 *
 * The golden flow is a student's story, told through the UI. What happens
 * before it -- an instructor writing a course, an admin approving it -- is a
 * different person's story with its own tests, so it is done here through the
 * same HTTP API the UI uses, in seconds rather than in a second browser.
 *
 * The step no browser can take is VNPay calling us back. The bank's page is
 * someone else's site and the IPN goes server to server; `simulatePaidIpn`
 * runs the backend's own script, which signs the callback with the secret the
 * backend checks against -- so the secret never leaves the container, and the
 * request still goes through the real signature check and the real handler.
 */
import { execFileSync } from "node:child_process";
import path from "node:path";

import { type APIRequestContext, expect } from "@playwright/test";

export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";

const COMPOSE_FILE =
  process.env.E2E_COMPOSE_FILE ?? path.resolve(__dirname, "../../../infra/docker-compose.yml");

// The seed's own defaults on a development stack (backend/scripts/seed.py).
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@devpath.example";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "devpath-admin";

export const PASSWORD = "mat-khau-e2e-du-dai";

/** A name nobody else on this database has, so every run starts clean. */
export function unique(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

type Json = Record<string, unknown>;

async function send(
  request: APIRequestContext,
  method: "GET" | "POST" | "PATCH" | "PUT",
  url: string,
  { token, data }: { token?: string; data?: Json } = {},
): Promise<Json> {
  const response = await request.fetch(`${API_URL}/api/v1${url}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    data,
  });
  expect(response.ok(), `${method} ${url}: ${response.status()} ${await response.text()}`).toBe(
    true,
  );
  return response.status() === 204 ? {} : ((await response.json()) as Json);
}

async function signIn(request: APIRequestContext, email: string, password: string) {
  const tokens = await send(request, "POST", "/auth/login", { data: { email, password } });
  return tokens.access_token as string;
}

export interface StagedCourse {
  id: string;
  slug: string;
  title: string;
  articleLessonId: string;
  codeLessonId: string;
}

/**
 * A paid course of two lessons -- one to read, one to solve -- written by a
 * fresh instructor and approved by the seeded admin, exactly the way the
 * platform puts any course on sale.
 */
export async function stagePaidCourse(request: APIRequestContext): Promise<StagedCourse> {
  const email = `${unique("giangvien")}@e2e.devpath.example`;
  const registered = await send(request, "POST", "/auth/register", {
    data: { email, password: PASSWORD, full_name: "Giảng Viên E2E" },
  });
  const teacher = registered.access_token as string;
  await send(request, "POST", "/users/me/instructor", { token: teacher });

  const categories = (await send(request, "GET", "/categories")) as unknown as Json[];
  const category = ((categories[0].children as Json[]) ?? [])[0] ?? categories[0];

  const title = `Python nhập môn E2E ${unique("khoa")}`;
  const course = await send(request, "POST", "/courses", {
    token: teacher,
    data: {
      title,
      category_id: category.id,
      subtitle: "Khóa học dựng riêng cho kiểm thử end-to-end",
      description: "Một bài đọc và một bài tập code chấm tự động.",
      price: 199000,
    },
  });
  const courseId = course.id as string;

  const section = await send(request, "POST", `/courses/${courseId}/sections`, {
    token: teacher,
    data: { title: "Chương 1 — Bắt đầu" },
  });
  const article = await send(request, "POST", `/sections/${section.id}/lessons`, {
    token: teacher,
    data: {
      title: "Đọc và in dữ liệu",
      type: "article",
      article_content: "`input()` đọc một dòng, `int()` đổi nó thành số, `print()` in ra.",
    },
  });
  const code = await send(request, "POST", `/sections/${section.id}/lessons`, {
    token: teacher,
    data: { title: "Bài tập: gấp đôi", type: "code_exercise" },
  });
  const exercise = await send(request, "POST", `/lessons/${code.id}/code-exercise`, {
    token: teacher,
    data: {
      statement_md: "Đọc một số nguyên `n` rồi in ra `2 * n`.",
      starter_code: "n = int(input())\n",
    },
  });
  for (const [input, expected, hidden] of [
    ["21", "42", false],
    ["-7", "-14", true],
  ] as const) {
    await send(request, "POST", `/code-exercises/${exercise.id}/test-cases`, {
      token: teacher,
      data: { input, expected_output: expected, is_hidden: hidden },
    });
  }

  await send(request, "POST", `/courses/${courseId}/submit`, { token: teacher });
  const admin = await signIn(request, ADMIN_EMAIL, ADMIN_PASSWORD);
  await send(request, "POST", `/admin/courses/${courseId}/approve`, {
    token: admin,
  });

  return {
    id: courseId,
    slug: course.slug as string,
    title,
    articleLessonId: article.id as string,
    codeLessonId: code.id as string,
  };
}

/** VNPay reporting that the order was paid, signed the way VNPay signs it. */
export function simulatePaidIpn(orderCode: string): string {
  return execFileSync(
    "docker",
    [
      "compose",
      "-f",
      COMPOSE_FILE,
      "exec",
      "-T",
      "backend",
      "python",
      "-m",
      "scripts.simulate_vnpay_ipn",
      orderCode,
    ],
    { encoding: "utf8" },
  );
}
