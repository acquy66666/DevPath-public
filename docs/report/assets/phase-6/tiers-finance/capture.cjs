// Chụp các màn mới của "cấp bậc giảng viên & tài chính" (20/10/2026) và kiểm
// không có lỗi console. Chạy (stack dev đang bật, frontend :3000, backend :8000):
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/tiers-finance/capture.cjs
//
// Đăng nhập bằng tài khoản seed (mật khẩu mặc định của scripts/seed.py và
// seed_courses.py), không ghi gì vào CSDL ngoài phiên đăng nhập, và thu hồi
// phiên sau khi chụp. ONLY=<regex> để chụp một phần; HEADED=1 để xem.
//
// Stack demo (Phase 7, ảnh "trước"): BASE_URL=API_URL=https://devpath-01.me,
// RESOLVE_TO=127.0.0.1 (đi thẳng vào nginx của máy này —
// docs/report/assets/phase-7/stack.cjs), SEED_*_PASSWORD từ infra/.env.seed-demo,
// OUT_DIR=<thư mục ảnh>. Bảng kê (12) lập một bản nháp tháng trước rồi xóa.

const path = require("node:path");
const { chromium } = require("@playwright/test");

const { stack, realUsers, blurPrivate } = require("../../phase-7/stack.cjs");

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const OUT = path.resolve(process.env.OUT_DIR ?? __dirname);
const ROUTE = stack(BASE);
// Người dùng thật (tài khoản Google của user trên stack demo): làm mờ trên mọi ảnh.
const PRIVATE = realUsers(process.env.COMPOSE_PROJECT ?? "devpath");
const CONTEXT = { viewport: { width: 1360, height: 900 }, locale: "vi-VN", ignoreHTTPSErrors: ROUTE.mapped };

/** Gọi API từ trong trang: cookie và đường đi đúng như của trình duyệt. */
function inPage(page, method, url, { token, data } = {}) {
  return page.evaluate(
    async ({ method, url, token, data }) => {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      if (data !== undefined) headers["Content-Type"] = "application/json";
      const r = await fetch(url, {
        method,
        headers,
        credentials: "include",
        body: data === undefined ? undefined : JSON.stringify(data),
      });
      const text = await r.text();
      return text ? JSON.parse(text) : {};
    },
    { method, url, token, data },
  );
}
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;

const ADMIN = { email: "admin@devpath.example", password: process.env.SEED_ADMIN_PASSWORD ?? "devpath-admin" };
const TEACHER = {
  email: "khoa.tran@devpath.example",
  password: process.env.SEED_INSTRUCTOR_PASSWORD ?? "devpath-instructor",
};

const problems = [];

function wants(name) {
  return !ONLY || ONLY.test(name);
}

async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 90_000 }).catch(() => {});
  await page.waitForTimeout(600);
}

async function signIn(context, account) {
  const page = await context.newPage();
  page.on("console", (message) => {
    // The sign-in page first asks whether a session exists: a 401 is its answer.
    const expected = page.url().includes("/dang-nhap") && message.text().includes("401");
    if (message.type() === "error" && !expected) problems.push(`${page.url()} :: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`${page.url()} :: ${error.message}`));
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((key) => key.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const response = await answered;
  if (!response.ok()) throw new Error(`đăng nhập ${account.email}: ${response.status()}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
  await settle(page);
  return page;
}

async function shot(page, name, route, prepare) {
  if (!wants(name)) return;
  if (route) {
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 120_000 });
    await settle(page);
  }
  if (prepare) await prepare(page);
  const masked = await blurPrivate(page, PRIVATE);
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log("chụp", path.relative(process.cwd(), file), masked ? `(che ${masked} chỗ có người dùng thật)` : "");
}

(async () => {
  const browser = await chromium.launch({
    channel: process.env.CHROME_CHANNEL ?? "chrome",
    headless: !process.env.HEADED,
    args: ROUTE.chromeArgs,
  });
  try {
    // --- Admin ---------------------------------------------------------------
    const adminContext = await browser.newContext(CONTEXT);
    const admin = await signIn(adminContext, ADMIN);
    await shot(admin, "01-admin-tong-quan", "/quan-tri");
    await shot(admin, "02-admin-doanh-thu-30-ngay", "/quan-tri/doanh-thu");
    await shot(admin, "03-admin-doanh-thu-12-thang-theo-thang", null, async (page) => {
      await page.getByRole("button", { name: "12 tháng" }).click();
      await page.getByLabel("Gom theo").selectOption("month");
      await settle(page);
    });
    await shot(admin, "04-admin-xep-hang", "/quan-tri/xep-hang", async (page) => {
      await page.getByRole("button", { name: "12 tháng" }).click();
      await settle(page);
    });
    await shot(admin, "05-admin-cap-giang-vien", "/quan-tri/cap-giang-vien", async (page) => {
      const details = page.getByRole("button", { name: "Chi tiết" }).first();
      if (await details.count()) {
        await details.click();
        await settle(page);
      }
    });
    await shot(admin, "06-admin-doi-cap-hop-thoai", null, async (page) => {
      await page.getByRole("button", { name: "Đổi cấp" }).first().click();
      await page.waitForTimeout(500);
    });
    await admin.keyboard.press("Escape");
    await shot(admin, "07-admin-thanh-toan", "/quan-tri/thanh-toan");
    await shot(admin, "08-admin-loi-nhuan", "/quan-tri/loi-nhuan");
    if (wants("12-admin-bang-ke")) {
      // A real statement for last month, photographed, then thrown away (a draft
      // leaves nothing behind): the dev database ends as it started.
      const token = await admin.evaluate(async (api) => {
        const r = await fetch(`${api}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
        return (await r.json()).access_token;
      }, API);
      const now = new Date(Date.now() + 7 * 3600_000);
      const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1)).toISOString().slice(0, 10);
      const batch = await inPage(admin, "POST", `${API}/api/v1/admin/payouts/statements`, {
        token,
        data: { month, instructor_ids: [] },
      });
      for (const statement of batch.created ?? []) {
        await shot(admin, "12-admin-bang-ke", `/quan-tri/thanh-toan/${statement.id}`);
        await inPage(admin, "DELETE", `${API}/api/v1/admin/payouts/statements/${statement.id}`, { token });
      }
      if (!batch.created?.length) console.log("không có gì để lập bảng kê tháng", month, JSON.stringify(batch));
    }
    await inPage(admin, "POST", `${API}/api/v1/auth/logout`).catch(() => {});
    await adminContext.close();

    // --- Instructor ----------------------------------------------------------
    const teacherContext = await browser.newContext(CONTEXT);
    const teacher = await signIn(teacherContext, TEACHER);
    await shot(teacher, "09-giang-vien-thong-ke", "/giang-day/thong-ke", async (page) => {
      await page.getByRole("button", { name: "12 tháng" }).click();
      await settle(page);
    });
    await shot(teacher, "10-giang-vien-pheu-theo-bai", null, async (page) => {
      await page.getByRole("button", { name: "Theo bài" }).first().click();
      await settle(page);
    });
    await teacher.keyboard.press("Escape");
    await shot(teacher, "11-giang-vien-cap-bac", "/giang-day/cap-bac");
    // The instructor must not see money anywhere on these pages.
    for (const route of ["/giang-day/thong-ke", "/giang-day/cap-bac"]) {
      await teacher.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
      await settle(teacher);
      const text = await teacher.locator("main").innerText();
      // "Doanh thu 12 tháng" is a tier criterion's *name*, shown met / not met;
      // a sum of money would carry the currency.
      if (/₫|\d\.\d{3}\s?đ/.test(text)) problems.push(`${route} hiện số tiền cho giảng viên`);
    }
    const forbidden = await teacher.goto(`${BASE}/quan-tri/doanh-thu`, { waitUntil: "domcontentloaded" });
    await settle(teacher);
    console.log("giảng viên mở /quan-tri/doanh-thu:", forbidden?.status(), new URL(teacher.url()).pathname);
    await inPage(teacher, "POST", `${API}/api/v1/auth/logout`).catch(() => {});
    await teacherContext.close();
  } finally {
    await browser.close();
  }

  if (problems.length) {
    console.log("\nLỖI / VẤN ĐỀ:");
    for (const problem of problems) console.log(" -", problem);
    process.exitCode = 1;
  } else {
    console.log("\nKhông có lỗi console, giảng viên không thấy số tiền nào.");
  }
})();
