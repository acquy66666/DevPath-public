/**
 * Accessibility sweep: axe-core on every main screen, as each role sees it,
 * at a desktop and a phone width. The bar is zero `critical` or `serious`
 * violations (Phase 7 plan, "Rà truy cập").
 *
 * Every screen of a role is visited before anything is asserted, so one run
 * lists everything that is wrong instead of stopping at the first page.
 * Menus and popovers are checked open as well as closed: a dropdown that
 * only exists while open is invisible to a scan of the page at rest.
 *
 * Runs against any seeded stack (`npm run test:e2e`): what axe judges --
 * names, roles, contrast, structure -- does not depend on which courses or
 * how many orders the database holds.
 */
import { type Browser, type Page, type TestInfo, expect, test } from "@playwright/test";

import {
  ADMIN,
  FREE_COURSE,
  INSTRUCTOR,
  type Json,
  PAID_COURSE,
  STUDENT,
  api,
  signIn,
} from "../support/accounts";
import { type Finding, axe, report } from "../support/axe";

const WIDTHS = [
  { name: "1440", viewport: { width: 1440, height: 900 } },
  { name: "375", viewport: { width: 375, height: 812 } },
] as const;

/** The page has arrived: a heading, no skeleton, nothing in flight. */
async function settle(page: Page) {
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  await animationsDone(page);
}

/**
 * A menu fading in is measured at part opacity: axe would report the contrast
 * of a frame nobody reads. Wait for every running animation to end.
 */
async function animationsDone(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        // A spinner never ends, and a cancelled animation rejects: neither is
        // a frame to wait for.
        .filter((a) => a.effect?.getComputedTiming().endTime !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
}

async function scan(page: Page, path: string, width: string): Promise<Finding[]> {
  await page.goto(path);
  await settle(page);
  return axe(page, `${path} @${width}`);
}

/** Open a menu or popover by its trigger's name, scan, close it again. */
async function scanOpen(page: Page, trigger: RegExp, where: string): Promise<Finding[]> {
  const button = page.getByRole("button", { name: trigger }).first();
  if (!(await button.isVisible())) return [];
  await button.click();
  await page.waitForLoadState("networkidle");
  await animationsDone(page);
  const found = await axe(page, where);
  await page.keyboard.press("Escape");
  return found;
}

async function rolePage(browser: Browser, testInfo: TestInfo, viewport: { width: number; height: number }): Promise<Page> {
  const { baseURL, locale, timezoneId } = testInfo.project.use;
  const context = await browser.newContext({ baseURL, locale, timezoneId, viewport });
  return context.newPage();
}

async function lessonPaths(page: Page): Promise<string[]> {
  const course = await api(page.request, "GET", `/courses/by-slug/${FREE_COURSE}`);
  const curriculum = await api(page.request, "GET", `/courses/${course.id}/curriculum`);
  const lessons = (curriculum.sections as { lessons: Json[] }[]).flatMap((s) => s.lessons);
  // One lesson of every type the seed has: the learn page draws each differently.
  const seen = new Map<string, Json>();
  for (const lesson of lessons) if (!seen.has(String(lesson.type))) seen.set(String(lesson.type), lesson);
  return [...seen.values()].map((lesson) => `/hoc/${FREE_COURSE}?bai=${lesson.id}`);
}

const GUEST_PATHS = [
  "/",
  "/khoa-hoc",
  `/khoa-hoc/${PAID_COURSE}`,
  "/dang-nhap",
  "/dang-ky",
  "/bang-xep-hang",
  "/chinh-sach-bao-mat",
  "/khong-co-trang-nay",
];

const ADMIN_PATHS = [
  "/quan-tri",
  "/quan-tri/khoa-hoc",
  "/quan-tri/bao-cao",
  "/quan-tri/nguoi-dung",
  "/quan-tri/doanh-thu",
  "/quan-tri/xep-hang",
  "/quan-tri/cap-giang-vien",
  "/quan-tri/thanh-toan",
  "/quan-tri/loi-nhuan",
  "/quan-tri/danh-muc",
  "/quan-tri/ma-giam-gia",
  "/quan-tri/banner",
];

const INSTRUCTOR_PATHS = [
  "/giang-day",
  "/giang-day/thong-ke",
  "/giang-day/hoi-dap",
  "/giang-day/cap-bac",
  "/giang-day/moi",
];

const STUDENT_PATHS = [
  "/chao-mung",
  "/khoa-hoc-cua-toi",
  "/gio-hang",
  "/yeu-thich",
  "/ho-so",
  "/thong-bao",
  "/tro-thanh-giang-vien",
];

for (const { name: width, viewport } of WIDTHS) {
  test.describe(`axe @${width}`, () => {
    test("khách", async ({ browser }, testInfo) => {
      const page = await rolePage(browser, testInfo, viewport);
      const found: Finding[] = [];
      for (const path of GUEST_PATHS) found.push(...(await scan(page, path, width)));
      await page.goto("/");
      await settle(page);
      found.push(...(await scanOpen(page, /^Mở menu điều hướng$/, `/ menu @${width}`)));
      await page.context().close();
      expect(found, report(found)).toEqual([]);
    });

    test("học viên", async ({ browser }, testInfo) => {
      const page = await rolePage(browser, testInfo, viewport);
      const token = await signIn(page, STUDENT);
      const free = await api(page.request, "GET", `/courses/by-slug/${FREE_COURSE}`);
      await api(page.request, "POST", `/courses/${free.id}/enroll`, { token, ok: [409] });
      const found: Finding[] = [];
      for (const path of [...STUDENT_PATHS, ...(await lessonPaths(page))]) {
        found.push(...(await scan(page, path, width)));
      }
      await page.goto("/khoa-hoc-cua-toi");
      await settle(page);
      found.push(...(await scanOpen(page, /^Tài khoản: /, `menu tài khoản @${width}`)));
      found.push(...(await scanOpen(page, /Thông báo/, `chuông thông báo @${width}`)));
      await page.context().close();
      expect(found, report(found)).toEqual([]);
    });

    test("giảng viên", async ({ browser }, testInfo) => {
      const page = await rolePage(browser, testInfo, viewport);
      await signIn(page, INSTRUCTOR);
      const course = await api(page.request, "GET", `/courses/by-slug/${FREE_COURSE}`);
      const found: Finding[] = [];
      for (const path of [
        ...INSTRUCTOR_PATHS,
        `/giang-day/${course.id}`,
        `/giang-day/${course.id}?tab=thong-tin`,
      ]) {
        found.push(...(await scan(page, path, width)));
      }
      await page.context().close();
      expect(found, report(found)).toEqual([]);
    });

    test("quản trị", async ({ browser }, testInfo) => {
      const page = await rolePage(browser, testInfo, viewport);
      await signIn(page, ADMIN);
      const course = await api(page.request, "GET", `/courses/by-slug/${PAID_COURSE}`);
      const found: Finding[] = [];
      for (const path of [...ADMIN_PATHS, `/quan-tri/khoa-hoc/${course.id}`]) {
        found.push(...(await scan(page, path, width)));
      }
      // Below lg the admin sidebar folds into one button.
      await page.goto("/quan-tri");
      await settle(page);
      found.push(...(await scanOpen(page, /^Quản trị/, `menu quản trị @${width}`)));
      await page.context().close();
      expect(found, report(found)).toEqual([]);
    });
  });
}
