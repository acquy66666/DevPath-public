// Task "Trạng thái toàn site" (Phase 7, mục Nền): screenshots of every 404,
// error boundary, route skeleton and empty state, before and after the change.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml): the error boundaries and
// route skeletons are shot on /dev/trang-thai, which a production build does
// not serve. Empty states are the real pages, seen by two throwaway accounts
// (@e2e.devpath.example, see stageAccounts); `scripts.purge_e2e` removes them
// at the end. The admin is the seed one, read-only. ONLY=<regex> limits the shots
// by name, SECTIONS=guest,account,admin the parts that run. BASE / API point
// elsewhere (default localhost:3000 / :8000).
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const PHASE = process.env.PHASE;
if (!["before", "after"].includes(PHASE)) {
  console.error("PHASE=before|after");
  process.exit(2);
}
const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const OUT = path.join(__dirname, PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const SECTIONS = (process.env.SECTIONS || "guest,account,admin").split(",");
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = process.env.E2E_COMPOSE_FILE || path.join(REPO, "infra/docker-compose.yml");

const ADMIN = {
  email: process.env.ADMIN_EMAIL || "admin@devpath.example",
  password: process.env.SEED_ADMIN_PASSWORD || "devpath-admin",
};
const PASSWORD = "devpath-states-1";
const FREE_COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";

// --- API ----------------------------------------------------------------------

async function call(method, pathname, { token, body } = {}) {
  const r = await fetch(`${API}/api/v1${pathname}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

async function register(name, fullName) {
  const email = `${name}-${Date.now().toString(36)}@e2e.devpath.example`;
  const session = await call("POST", "/auth/register", { body: { email, password: PASSWORD, full_name: fullName } });
  return { email, token: session.access_token };
}

/**
 * Two throwaway accounts, both instructors as well as learners. `fresh` has
 * nothing at all: no course, no cart, no notification, nothing taught. `busy`
 * is enrolled in the free Python course (for the panels of the learning page)
 * and has one draft course without a section (for the curriculum builder).
 */
async function stageAccounts() {
  const fresh = await register("trangthai-trong", "Học Viên Mới");
  await call("POST", "/users/me/instructor", { token: fresh.token });

  const busy = await register("trangthai-hoc", "Học Viên Trạng Thái");
  await call("POST", "/users/me/instructor", { token: busy.token });
  const categories = await call("GET", "/categories");
  const category = (categories[0].children ?? [])[0] ?? categories[0];
  const draft = await call("POST", "/courses", {
    token: busy.token,
    body: { title: "Khóa nháp chưa có chương", category_id: category.id, price: 0 },
  });
  const course = await call("GET", `/courses/by-slug/${FREE_COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token: busy.token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token: busy.token });
  const lessons = {};
  for (const l of curriculum.sections.flatMap((s) => s.lessons)) lessons[l.type] ??= l.id;

  for (const { token } of [fresh, busy]) await call("POST", "/auth/logout", { token }).catch(() => {});
  return { fresh: { email: fresh.email }, busy: { email: busy.email, draftId: draft.id, lessons } };
}

function purge() {
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

// --- Browser ------------------------------------------------------------------

async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(700);
}

async function signIn(context, email, password) {
  const page = await context.newPage();
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  // Clicking before React owns the form submits it as a GET.
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill(password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const response = await answered;
  if (!response.ok()) throw new Error(`đăng nhập ${email}: ${response.status()}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
  return page;
}

async function signOut(page) {
  await page
    .evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API)
    .catch(() => {});
}

const taken = [];
async function shoot(page, name, { width, url, before, element, fullPage } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (width) await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
  if (url) {
    await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 180_000 });
    await settle(page);
  }
  if (before) {
    await before(page);
    await page.waitForTimeout(500);
  }
  // The `next dev` indicator in the corner is not part of the site.
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  const file = path.join(OUT, `${name}.png`);
  const target = !element ? page : typeof element === "function" ? element(page) : page.locator(element).first();
  if (element) await target.scrollIntoViewIfNeeded();
  await target.screenshot({ path: file, animations: "disabled", fullPage: element ? undefined : fullPage });
  taken.push(name);
  console.log(`  ${name}`);
}

const PREVIEW_STATES = [
  "404-site", "404-course", "404-cert",
  "error-site", "error-learn", "error-course", "error-catalogue", "error-cert", "error-auth", "error-instructor", "error-admin",
  "loading-catalogue", "loading-auth", "loading-instructor", "loading-instructor-qa", "loading-instructor-stats", "loading-admin",
];

const newContext = (browser) => browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });

/** The preview page, then the real 404s and the empty search, signed out. */
async function guest(browser) {
  console.log("khách");
  const context = await newContext(browser);
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/dev/trang-thai`, { waitUntil: "domcontentloaded", timeout: 180_000 });
  await settle(page);
  for (const id of PREVIEW_STATES) await shoot(page, `xem-truoc-${id}-1440`, { element: `[data-testid="state-${id}"]` });
  await page.setViewportSize({ width: 375, height: 812 });
  await settle(page);
  for (const id of ["404-site", "404-course", "error-site", "error-learn", "loading-catalogue"]) {
    await shoot(page, `xem-truoc-${id}-375`, { element: `[data-testid="state-${id}"]` });
  }
  for (const width of [1440, 375]) {
    await shoot(page, `404-trang-${width}`, { width, url: "/khong-co-trang-nay" });
    await shoot(page, `404-khoa-hoc-${width}`, { width, url: "/khoa-hoc/khong-co-khoa-nay" });
    await shoot(page, `404-chung-chi-${width}`, { width, url: "/cert/KHONGCOMANAY0000" });
    await shoot(page, `tim-khong-ra-${width}`, { width, url: "/khoa-hoc?q=khongtimthayxyz" });
  }
  await context.close();
}

/** Learner and instructor screens with nothing in them, as the fresh account. */
async function fresh(browser, { email }) {
  console.log(`tài khoản trống ${email}`);
  const context = await newContext(browser);
  const page = await signIn(context, email, PASSWORD);
  for (const width of [1440, 375]) {
    await shoot(page, `khoa-hoc-cua-toi-${width}`, { width, url: "/khoa-hoc-cua-toi", fullPage: true });
    await shoot(page, `gio-hang-${width}`, { width, url: "/gio-hang" });
    await shoot(page, `yeu-thich-${width}`, { width, url: "/yeu-thich" });
    await shoot(page, `thong-bao-${width}`, { width, url: "/thong-bao" });
    await shoot(page, `giang-day-${width}`, { width, url: "/giang-day" });
  }
  await shoot(page, "chuong-thong-bao-1440", {
    width: 1440,
    url: "/khoa-hoc",
    before: async (p) => {
      await p.getByRole("button", { name: /^Thông báo/ }).click();
      await p.getByRole("menu").waitFor();
    },
  });
  await page.keyboard.press("Escape");
  await shoot(page, "giang-day-thong-ke-1440", { width: 1440, url: "/giang-day/thong-ke" });
  await shoot(page, "giang-day-hoi-dap-1440", { width: 1440, url: "/giang-day/hoi-dap" });
  await signOut(page);
  await context.close();
}

/** Panels of the learning page and the empty curriculum, as the busy account. */
async function busy(browser, { email, lessons, draftId }) {
  console.log(`tài khoản đang học ${email}`);
  const context = await newContext(browser);
  const page = await signIn(context, email, PASSWORD);
  const learn = (type) => `/hoc/${FREE_COURSE}?bai=${lessons[type]}`;
  for (const width of [1440, 375]) {
    await shoot(page, `hoc-ghi-chu-${width}`, {
      width,
      url: learn("article"),
      element: (p) => p.getByRole("tabpanel", { name: "Ghi chú" }),
      before: async (p) => p.getByRole("tab", { name: "Ghi chú" }).click(),
    });
    await shoot(page, `hoc-hoi-dap-${width}`, {
      element: (p) => p.getByRole("tabpanel", { name: "Hỏi đáp" }),
      before: async (p) => p.getByRole("tab", { name: "Hỏi đáp" }).click(),
    });
    await shoot(page, `hoc-tro-giang-${width}`, {
      element: "aside",
      before: async (p) => p.getByRole("tab", { name: "Trợ giảng AI" }).click(),
    });
  }
  /** Scroll a line of text into view once it has arrived. */
  const showText = (text) => async (p) => {
    await p.getByText(text).first().waitFor({ timeout: 60_000 });
    await p.getByText(text).first().scrollIntoViewIfNeeded();
  };
  await shoot(page, "hoc-lich-su-nop-1440", { width: 1440, url: learn("code_exercise"), before: showText(/chưa nộp bài nào|Chưa có bài nộp nào/) });
  await shoot(page, "danh-gia-khoa-hoc-1440", { width: 1440, url: `/khoa-hoc/${FREE_COURSE}`, before: showText(/Chưa có đánh giá nào/) });
  await shoot(page, "giang-day-chuong-trinh-1440", { width: 1440, url: `/giang-day/${draftId}`, before: showText(/Chưa có chương nào/) });
  await signOut(page);
  await context.close();
}

/** Queues that are empty on the dev database, as the seed admin. */
async function admin(browser) {
  console.log("admin");
  const context = await newContext(browser);
  const page = await signIn(context, ADMIN.email, ADMIN.password);
  for (const width of [1440, 375]) await shoot(page, `quan-tri-bao-cao-${width}`, { width, url: "/quan-tri/bao-cao" });
  await shoot(page, "quan-tri-loi-nhuan-1440", { width: 1440, url: "/quan-tri/loi-nhuan", fullPage: true });
  await shoot(page, "quan-tri-nguoi-dung-1440", {
    width: 1440,
    url: "/quan-tri/nguoi-dung",
    before: async (p) => {
      await p.getByRole("searchbox").first().fill("khongcoaitenvay");
      await p.getByRole("searchbox").first().press("Enter");
      await settle(p);
    },
  });
  await signOut(page);
  await context.close();
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  let staged = null;
  try {
    if (SECTIONS.includes("guest")) await guest(browser);
    if (SECTIONS.includes("account")) {
      staged = await stageAccounts();
      await fresh(browser, staged.fresh);
      await busy(browser, staged.busy);
    }
    if (SECTIONS.includes("admin")) await admin(browser);
  } finally {
    await browser.close();
    if (staged) purge();
  }
  // A partial run (ONLY, SECTIONS) adds to the list instead of replacing it.
  const list = path.join(OUT, "shots.json");
  const earlier = fs.existsSync(list) ? JSON.parse(fs.readFileSync(list, "utf8")).shots : [];
  const shots = [...new Set([...earlier, ...taken])].sort();
  fs.writeFileSync(list, JSON.stringify({ base: BASE, at: new Date().toISOString(), shots }, null, 2));
  console.log(`\n${taken.length} ảnh → ${path.relative(REPO, OUT)}`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
