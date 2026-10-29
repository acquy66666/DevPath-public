/**
 * Visual regression: ten key screens, each at a desktop and a phone width.
 *
 * Runs only through `scripts/visual.sh`, inside Playwright's Linux image, on a
 * stack seeded by `scripts.seed` and nothing else -- the same stack CI's E2E
 * job brings up. The baselines are pictures of that data; a developer's
 * database, with its sales and study history, would not match them.
 *
 * What changes between two honest runs is taken out before capture rather
 * than tolerated by a loose threshold:
 *  - dates and clock times in the text are rewritten to one fixed value
 *    (the seed stamps the courses with the day it ran);
 *  - animations are finished (`animations: "disabled"`, reduced motion), the
 *    caret and Next's dev indicator hidden (screenshot.css);
 *  - accounts are fixed: the seed's admin and instructor, plus one student
 *    this suite signs up once and reuses, so the admin's counts do not climb
 *    from run to run.
 */
import path from "node:path";

import { type APIRequestContext, type Browser, type Page, type TestInfo, expect, test } from "@playwright/test";

import { API_URL, PASSWORD } from "../support/stack";

const STYLE = path.join(__dirname, "screenshot.css");

const ADMIN = { email: "admin@devpath.example", password: "devpath-admin" };
const INSTRUCTOR = { email: "khoa.tran@devpath.example", password: "devpath-instructor" };
const STUDENT = { email: "visual-hocvien@e2e.devpath.example", password: PASSWORD };

const FREE_COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const PAID_COURSE = "cau-truc-du-lieu-va-giai-thuat-voi-python";

type Json = Record<string, unknown>;

async function api(
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
async function signIn(page: Page, who: { email: string; password: string }): Promise<string> {
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

/** Rewrite every date and clock time on the page to the same fixed text. */
async function freezeTimes(page: Page) {
  await page.evaluate(() => {
    const rules: [RegExp, string][] = [
      [/\b\d{1,2}\/\d{1,2}\/\d{4}\b/g, "01/01/2026"],
      [/\b\d{1,2}\/\d{1,2}\b/g, "01/01"],
      [/\b\d{1,2}:\d{2}\b/g, "08:00"],
      // "3 phút trước", but not "30 ngày trước đó": that one names a period.
      [/\b\d+ (giây|phút|giờ|ngày|tuần|tháng|năm) trước(?! đó)/g, "1 ngày trước"],
    ];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!parent || parent.closest("script, style")) continue;
      let text = node.nodeValue ?? "";
      for (const [pattern, fixed] of rules) text = text.replace(pattern, fixed);
      if (text !== node.nodeValue) node.nodeValue = text;
    }
  });
}

/** Wait until the page has really arrived: a heading, no skeleton, no request. */
async function settle(page: Page, heading: string | RegExp) {
  await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

async function snap(page: Page, name: string, heading: string | RegExp) {
  await settle(page, heading);
  await freezeTimes(page);
  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true, stylePath: STYLE });
}

/** One page for a whole role, so each account signs in once per project. */
async function rolePage(browser: Browser, testInfo: TestInfo): Promise<Page> {
  // Read from the project, not from fixtures: a beforeAll has no test-scoped ones.
  const { baseURL, viewport, locale, timezoneId } = testInfo.project.use;
  const context = await browser.newContext({
    baseURL,
    viewport,
    locale,
    timezoneId,
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  return context.newPage();
}

test.use({ colorScheme: "light", reducedMotion: "reduce" });

test.describe("khách", () => {
  test("trang chủ", async ({ page }) => {
    await page.goto("/");
    await snap(page, "trang-chu", /.+/);
  });

  test("logo không lệch điểm ảnh nào", async ({ page }) => {
    await page.goto("/");
    await settle(page, /.+/);
    await expect(page.locator('header a[href="/"]').first()).toHaveScreenshot("logo.png", {
      maxDiffPixels: 0,
      stylePath: STYLE,
    });
  });

  test("danh sách khóa học", async ({ page }) => {
    await page.goto("/khoa-hoc");
    await snap(page, "danh-sach-khoa-hoc", /Khóa học/);
  });

  test("chi tiết khóa học", async ({ page }) => {
    await page.goto(`/khoa-hoc/${PAID_COURSE}`);
    await snap(page, "chi-tiet-khoa-hoc", /Cấu trúc dữ liệu/);
  });

  test("đăng nhập", async ({ page }) => {
    await page.goto("/dang-nhap");
    await snap(page, "dang-nhap", /Đăng nhập/);
  });

  test("404", async ({ page }) => {
    await page.goto("/khong-co-trang-nay");
    await snap(page, "404", /.+/);
  });

  test("bảng xếp hạng", async ({ page }) => {
    await page.goto("/bang-xep-hang");
    await snap(page, "bang-xep-hang", /Bảng xếp hạng/);
  });
});

test.describe("học viên", () => {
  test.describe.configure({ mode: "serial" });
  let page: Page;

  test.beforeAll(async ({ browser }, testInfo) => {
    page = await rolePage(browser, testInfo);
    const token = await signIn(page, STUDENT);
    const free = await api(page.request, "GET", `/courses/by-slug/${FREE_COURSE}`);
    const paid = await api(page.request, "GET", `/courses/by-slug/${PAID_COURSE}`);
    await api(page.request, "POST", `/courses/${free.id}/enroll`, { token, ok: [409] });
    // The cart is put back to exactly one course, whatever a run left there.
    await api(page.request, "DELETE", "/cart", { token, ok: [404] });
    await api(page.request, "PUT", `/cart/courses/${paid.id}`, { token });
  });

  test.afterAll(async () => {
    await page.context().close();
  });

  test("khóa học của tôi", async () => {
    await page.goto("/khoa-hoc-cua-toi");
    await snap(page, "khoa-hoc-cua-toi", /Khóa học của tôi/);
  });

  test("giỏ hàng", async () => {
    await page.goto("/gio-hang");
    await snap(page, "gio-hang", /Giỏ hàng/);
  });

  test("trang học — bài đọc", async () => {
    const free = await api(page.request, "GET", `/courses/by-slug/${FREE_COURSE}`);
    const curriculum = await api(page.request, "GET", `/courses/${free.id}/curriculum`);
    const lessons = (curriculum.sections as { lessons: Json[] }[]).flatMap((s) => s.lessons);
    const article = lessons.find((lesson) => lesson.type === "article");
    expect(article, "the seeded Python course has an article lesson").toBeTruthy();
    await page.goto(`/hoc/${FREE_COURSE}?bai=${article!.id}`);
    await snap(page, "trang-hoc", String(article!.title));
  });
});

test.describe("giảng viên", () => {
  test("khu giảng dạy", async ({ browser }, testInfo) => {
    const page = await rolePage(browser, testInfo);
    await signIn(page, INSTRUCTOR);
    await page.goto("/giang-day");
    await snap(page, "giang-day", /.+/);
    await page.context().close();
  });
});

test.describe("quản trị", () => {
  test("tổng quan", async ({ browser }, testInfo) => {
    const page = await rolePage(browser, testInfo);
    await signIn(page, ADMIN);
    await page.goto("/quan-tri");
    await snap(page, "quan-tri", /.+/);
    await page.context().close();
  });
});
