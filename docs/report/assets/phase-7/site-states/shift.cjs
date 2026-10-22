// Task "Trạng thái toàn site" (Phase 7): does a skeleton have the size of what
// replaces it? Every API response is held back HOLD ms (default 1200), so the
// skeletons are on screen long enough to be laid out, then the page's
// Cumulative Layout Shift is read once the data has landed. A skeleton the
// size of the real content moves nothing: CLS 0.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/shift.cjs
//
// Dev stack, seed accounts (pages with real data: an empty page has nothing to
// misplace). Each route is opened once to compile it, then measured. Signs out
// every session it opens. Writes shift-<PHASE>.json next to this file.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const PHASE = process.env.PHASE || "now";
const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const HOLD = Number(process.env.HOLD || 1200);
const WIDTHS = (process.env.WIDTHS || "1440,375").split(",").map(Number);

const ACCOUNTS = {
  student: { email: "nguoimua08@sales.devpath.example", password: "devpath-buyer" },
  instructor: { email: "khoa.tran@devpath.example", password: process.env.SEED_INSTRUCTOR_PASSWORD || "devpath-instructor" },
  admin: { email: "admin@devpath.example", password: process.env.SEED_ADMIN_PASSWORD || "devpath-admin" },
};

async function get(pathname, token) {
  const r = await fetch(`${API}${pathname}`, { headers: token ? { authorization: `Bearer ${token}` } : {} });
  if (!r.ok) throw new Error(`GET ${pathname}: ${r.status}`);
  return r.json();
}

async function as(account, ask) {
  const r = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(account),
  });
  if (!r.ok) throw new Error(`login ${account.email}: ${r.status}`);
  const { access_token: token } = await r.json();
  const cookie = (r.headers.getSetCookie?.() ?? []).map((c) => c.split(";")[0]).join("; ");
  try {
    return await ask(token);
  } finally {
    await fetch(`${API}/api/v1/auth/logout`, { method: "POST", headers: { cookie } }).catch(() => {});
  }
}

async function discover() {
  const slug = "python-co-ban-cho-nguoi-moi-bat-dau";
  const article = await as(ACCOUNTS.student, async (token) => {
    const course = await get(`/api/v1/courses/by-slug/${slug}`, token);
    const curriculum = await get(`/api/v1/courses/${course.id}/curriculum`, token);
    return curriculum.sections.flatMap((s) => s.lessons).find((l) => l.type === "article").id;
  });
  const courseId = await as(ACCOUNTS.instructor, async (token) => (await get("/api/v1/courses/me?page=1&page_size=1", token)).items[0].id);
  return { slug, article, courseId };
}

function routes(d) {
  return {
    guest: ["/khoa-hoc", `/khoa-hoc/${d.slug}`],
    student: [
      "/",
      "/khoa-hoc-cua-toi",
      "/gio-hang",
      "/yeu-thich",
      "/thong-bao",
      "/ho-so",
      "/bang-xep-hang",
      `/khoa-hoc/${d.slug}`,
      `/hoc/${d.slug}?bai=${d.article}`,
    ],
    instructor: ["/giang-day", "/giang-day/thong-ke", "/giang-day/hoi-dap", "/giang-day/cap-bac", `/giang-day/${d.courseId}`],
    admin: [
      "/quan-tri",
      "/quan-tri/khoa-hoc",
      "/quan-tri/bao-cao",
      "/quan-tri/nguoi-dung",
      "/quan-tri/danh-muc",
      "/quan-tri/ma-giam-gia",
      "/quan-tri/banner",
    ],
  };
}

/** Collects every layout shift from the first paint, with what moved. */
function observeShifts() {
  window.__shifts = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue;
      window.__shifts.push({
        value: e.value,
        sources: (e.sources || []).slice(0, 3).map((s) => {
          const n = s.node;
          if (!n || n.nodeType !== 1) return n ? n.nodeName : "?";
          const cls = typeof n.className === "string" ? n.className.split(" ").slice(0, 3).join(".") : "";
          return `${n.tagName.toLowerCase()}.${cls} ${s.previousRect.height}→${s.currentRect.height}px y${s.previousRect.y}→${s.currentRect.y}`;
        }),
      });
    }
  }).observe({ type: "layout-shift", buffered: true });
}

async function signIn(context, account) {
  const page = await context.newPage();
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error(`đăng nhập ${account.email}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
  return page;
}

(async () => {
  const d = await discover();
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const results = [];
  for (const [role, list] of Object.entries(routes(d))) {
    const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const page = role === "guest" ? await context.newPage() : await signIn(context, ACCOUNTS[role]);
    await context.addInitScript(observeShifts);
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
      for (const url of list) {
        // Compile the route first: `next dev` builds a page on its first request.
        await page.goto(BASE + url, { waitUntil: "networkidle", timeout: 180_000 }).catch(() => {});
        await page.route(`${API}/api/v1/**`, async (route) => {
          await new Promise((r) => setTimeout(r, HOLD));
          await route.continue().catch(() => {});
        });
        await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 180_000 });
        await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => {});
        await page.waitForTimeout(1000);
        const shifts = await page.evaluate(() => window.__shifts);
        await page.unroute(`${API}/api/v1/**`);
        const cls = shifts.reduce((sum, s) => sum + s.value, 0);
        results.push({ role, width, url, cls: Number(cls.toFixed(4)), shifts });
        console.log(`${role.padEnd(10)} ${String(width).padStart(4)} CLS ${cls.toFixed(4)} ${url}`);
        for (const s of shifts.filter((x) => x.value >= 0.005)) console.log(`      ${s.value.toFixed(4)} ${s.sources.join(" | ")}`);
      }
    }
    if (role !== "guest") {
      await page
        .evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API)
        .catch(() => {});
    }
    await context.close();
  }
  await browser.close();
  const views = results.length;
  const moved = results.filter((r) => r.cls >= 0.01).length;
  const total = results.reduce((s, r) => s + r.cls, 0);
  console.log(`\n${moved}/${views} lượt xem có CLS ≥ 0,01; tổng ${total.toFixed(3)}; lớn nhất ${Math.max(...results.map((r) => r.cls)).toFixed(3)}`);
  fs.writeFileSync(
    path.join(__dirname, `shift-${PHASE}.json`),
    JSON.stringify({ base: BASE, hold_ms: HOLD, at: new Date().toISOString(), data: d, results }, null, 2),
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
