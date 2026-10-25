// Nhóm màn 6 (Phase 7) — thành tích: khối chuỗi ngày + XP ở "Khóa học của
// tôi", bảng xếp hạng, chứng chỉ, khối gợi ý. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/achievements/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/achievements/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the sales/study demo
// data loaded TODAY: streaks are cut when read and the week board only counts
// this week, so data loaded on an earlier day shows empty streaks. Reload with
// `seed_study --purge`, `seed_sales --purge`, `seed_sales`, `seed_study`,
// `rebuild_leaderboard`, `rebuild_recommendations` (README "Ngày tháng tính
// theo lúc chạy").
//
// The learners are the demo buyers (`nguoimuaNN@sales.devpath.example`), read
// only: each is signed in through the form, looked at, signed out.
//   - Người mua 08: chuỗi đang giữ, hôm nay đã học; hạng 1 tuần này.
//   - Người mua 01: chuỗi đang giữ, hôm nay chưa học.
//   - Người mua 38: chuỗi vừa đứt (học tới hôm kia).
//   - Người mua 34: một khóa đã học, ba gợi ý.
// Plus one throwaway account (@e2e.devpath.example) for "tài khoản mới",
// removed at the end by `scripts.purge_e2e`.
//
// REPO=<checkout> lets a copy of this script outside the repo write into it.
// ONLY=<regex> limits the shots by name.
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
const REPO = process.env.REPO || path.resolve(__dirname, "../../../../..");
const OUT = path.join(REPO, "docs/report/assets/phase-7/achievements", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const BUYER_PASSWORD = "devpath-buyer";
const NEW_PASSWORD = "devpath-new-1";
const buyer = (n) => `nguoimua${n}@sales.devpath.example`;

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

/** One look at the API as a learner: their id and their first certificate. */
async function peek(email, password) {
  const { access_token: token } = await call("POST", "/auth/login", { body: { email, password } });
  try {
    const me = await call("GET", "/auth/me", { token });
    const enrolments = await call("GET", "/enrollments/me", { token });
    const week = await call("GET", "/leaderboard?period=week", { token });
    return {
      id: me.id,
      certificate: enrolments.items.find((item) => item.certificate_code)?.certificate_code ?? null,
      week,
    };
  } finally {
    await call("POST", "/auth/logout", { token }).catch(() => {});
  }
}

let throwaway = null;
function purge() {
  if (!throwaway) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function signIn(page, email, password) {
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
  if (!(await answered).ok()) throw new Error(`đăng nhập thất bại: ${email}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

async function signOut(page) {
  await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
  await page.context().clearCookies();
  await page.evaluate(() => localStorage.clear());
}

const taken = [];
async function shoot(page, name, { width = 1440, fullPage = true, element = null } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (page.viewportSize().width !== width) {
    await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  if (fullPage) await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  const file = path.join(OUT, `${name}.png`);
  if (element) {
    await element(page).screenshot({ path: file, animations: "disabled" });
  } else {
    await page.screenshot({ path: file, animations: "disabled", fullPage });
  }
  taken.push(name);
  console.log(`  ${name}`);
}

async function both(page, name, options = {}) {
  await shoot(page, `${name}-1440`, { width: 1440, ...options });
  await shoot(page, `${name}-375`, { width: 375, ...options });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(800);
}

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1000);
}

async function openMyCourses(page) {
  await page.goto(`${BASE}/khoa-hoc-cua-toi`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { level: 1, name: "Khóa học của tôi" }).waitFor({ timeout: 120_000 });
  await page.getByText(/\d+ XP/).first().waitFor({ timeout: 60_000 });
  await settle(page);
}

async function openBoard(page, tab) {
  await page.goto(`${BASE}/bang-xep-hang`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { level: 1, name: "Bảng xếp hạng" }).waitFor({ timeout: 120_000 });
  if (tab) await page.getByRole("tab", { name: tab }).click();
  await page.getByText(/hạng \d+/i).first().waitFor({ timeout: 60_000 });
  await settle(page);
}

/** The "Gợi ý cho bạn" section of the home page, wherever it sits. */
const recommendations = (page) => page.locator('section[aria-label="Gợi ý cho bạn"]').first();

(async () => {
  const eight = await peek(buyer("08"), BUYER_PASSWORD);
  if (!eight.certificate) throw new Error("Người mua 08 chưa có chứng chỉ — nạp lại seed_study");
  console.log(`${PHASE}: chứng chỉ ${eight.certificate}`);

  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      reducedMotion: "reduce",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    // Người mua 08: the streak kept, the week board, a rank that went up.
    await signIn(page, buyer("08"), BUYER_PASSWORD);
    await openMyCourses(page);
    await both(page, "1-khoa-hoc-cua-toi");
    await openBoard(page, null);
    await both(page, "4-bang-xep-hang-tuan");
    await openBoard(page, "Tháng này");
    await shoot(page, "5-bang-xep-hang-thang-1440");
    if (PHASE === "after") {
      // The last visit saw rank 4 this week: the board answers "lên 3 hạng".
      const { starts_on: startsOn, me } = eight.week;
      if (!me) throw new Error("Người mua 08 không có XP tuần này");
      await page.evaluate(
        ([key, rank]) => localStorage.setItem(key, String(rank)),
        [`devpath:rank-seen:${eight.id}:week:${startsOn}`, me.rank + 3],
      );
      await openBoard(page, null);
      await shoot(page, "6-len-hang-1440", { fullPage: false });
    }
    await signOut(page);

    // The certificate is public: no session needed.
    await page.goto(`${BASE}/cert/${eight.certificate}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Chứng nhận hoàn thành" }).waitFor({ timeout: 120_000 });
    await settle(page);
    await both(page, "7-chung-chi");

    // Người mua 01: still on a streak, nothing done today.
    await signIn(page, buyer("01"), BUYER_PASSWORD);
    await openMyCourses(page);
    await shoot(page, "2-chuoi-chua-hoc-1440");
    await signOut(page);

    // Người mua 38: the streak broke yesterday.
    await signIn(page, buyer("38"), BUYER_PASSWORD);
    await openMyCourses(page);
    await shoot(page, "3-chuoi-vua-mat-1440");
    await signOut(page);

    // Người mua 34: three recommendations on the home page.
    await signIn(page, buyer("34"), BUYER_PASSWORD);
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    await recommendations(page).waitFor({ timeout: 120_000 });
    await recommendations(page).getByRole("link").first().waitFor({ timeout: 60_000 });
    await settle(page);
    await both(page, "8-goi-y-trang-chu", { element: recommendations });
    await signOut(page);

    // A brand-new account: no streak, no XP, no course.
    throwaway = `thanh-tich-${PHASE}-${Date.now().toString(36)}@e2e.devpath.example`;
    await call("POST", "/auth/register", {
      body: { email: throwaway, password: NEW_PASSWORD, full_name: "Trần Minh Anh" },
    });
    await signIn(page, throwaway, NEW_PASSWORD);
    await openMyCourses(page);
    await shoot(page, "9-tai-khoan-moi-1440");
    await signOut(page);

    await context.close();
  } finally {
    await browser.close();
    purge();
  }
  fs.writeFileSync(
    path.join(OUT, "shots.json"),
    JSON.stringify({ base: BASE, at: new Date().toISOString(), shots: taken.sort() }, null, 2),
  );
  console.log(`\n${taken.length} ảnh → ${path.relative(REPO, OUT)}`);
})().catch((e) => {
  console.error(e);
  try {
    purge();
  } catch (error) {
    console.error("dọn hỏng — chạy tay `python -m scripts.purge_e2e`:", String(error).split("\n")[0]);
  }
  process.exit(1);
});
