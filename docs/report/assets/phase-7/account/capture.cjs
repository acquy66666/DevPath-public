// Nhóm màn 7 (Phase 7) — tài khoản: đăng nhập, đăng ký, màn chào mừng sau
// đăng ký, hồ sơ. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/account/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/account/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml). Who is looked at:
//   - Người mua 08 (`nguoimua08@sales.devpath.example`), read only: the
//     profile of someone who has been learning.
//   - Two throwaway accounts (@e2e.devpath.example), removed at the end by
//     `scripts.purge_e2e`: one signs up through the form (what comes after
//     sign-up), one is turned into a Google-only account in the database
//     (`password_hash` cleared, a made-up `oauth_sub`: `ck_users_credential`
//     wants one of the two).
// The wrong-password shot is taken against a throwaway email, so it never
// counts towards a real account's sign-in limit (10 per 15 minutes).
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
const OUT = path.join(REPO, "docs/report/assets/phase-7/account", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const BUYER = "nguoimua08@sales.devpath.example";
const BUYER_PASSWORD = "devpath-buyer";
const NEW_PASSWORD = "devpath-new-1";
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const stamp = Date.now().toString(36);
const throwaway = (what) => `tai-khoan-${what}-${PHASE}-${stamp}@e2e.devpath.example`;

let made = false;
function compose(...args) {
  return execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", ...args], { encoding: "utf8" });
}
function purge() {
  if (!made) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function call(method, pathname, { body } = {}) {
  const r = await fetch(`${API}/api/v1${pathname}`, {
    method,
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

/** Wait until React owns the one form on the page: a click before that submits it as a GET. */
async function formReady(page) {
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
}

async function signIn(page, email, password) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await formReady(page);
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
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

const taken = [];
async function shoot(page, name, { width = 1440, fullPage = true } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (page.viewportSize().width !== width) {
    await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  if (fullPage) await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled", fullPage });
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

async function openProfile(page) {
  await page.goto(`${BASE}/ho-so`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Họ và tên").waitFor({ timeout: 120_000 });
  await settle(page);
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      reducedMotion: "reduce",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    // Sign-in, as a visitor sees it.
    await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
    await formReady(page);
    await settle(page);
    await both(page, "1-dang-nhap");

    // A wrong password, against an email nobody owns.
    await page.getByLabel("Email").fill(throwaway("sai"));
    await page.getByLabel("Mật khẩu").fill("khong-dung-mat-khau");
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await page.getByRole("alert").first().waitFor({ timeout: 30_000 });
    await shoot(page, "2-dang-nhap-sai-1440");

    // Sign-up, arriving from a course page, filled in.
    await page.goto(`${BASE}/dang-ky?next=/khoa-hoc/${COURSE}`, { waitUntil: "domcontentloaded" });
    await formReady(page);
    await settle(page);
    await page.getByLabel("Họ và tên").fill("Lê Thu Hà");
    await page.getByLabel("Email").fill("thuha@example.com");
    await page.getByLabel("Mật khẩu").fill("hoc-python-2026");
    await both(page, "3-dang-ky");

    // An email that already has an account.
    await page.getByLabel("Email").fill(BUYER);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    await page.getByRole("alert").first().waitFor({ timeout: 30_000 });
    await shoot(page, "4-dang-ky-email-da-co-1440");

    // What comes right after signing up.
    made = true;
    await page.goto(`${BASE}/dang-ky`, { waitUntil: "domcontentloaded" });
    await formReady(page);
    await page.getByLabel("Họ và tên").fill("Lê Thu Hà");
    await page.getByLabel("Email").fill(throwaway("moi"));
    await page.getByLabel("Mật khẩu").fill(NEW_PASSWORD);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    await page.waitForURL((url) => !url.pathname.startsWith("/dang-ky"), { timeout: 60_000 });
    await page.getByRole("heading", { level: 1 }).first().waitFor({ timeout: 60_000 });
    await settle(page);
    await both(page, "5-sau-dang-ky");
    await signOut(page);

    // Người mua 08's profile.
    await signIn(page, BUYER, BUYER_PASSWORD);
    await openProfile(page);
    await both(page, "6-ho-so");
    await signOut(page);

    // A Google-only account: no password to change.
    const google = throwaway("google");
    await call("POST", "/auth/register", { body: { email: google, password: NEW_PASSWORD, full_name: "Lê Thu Hà" } });
    await signIn(page, google, NEW_PASSWORD);
    compose("postgres", "psql", "-U", "devpath", "-c", `update users set password_hash = null, oauth_provider = 'google', oauth_sub = 'e2e-${stamp}' where email = '${google}'`);
    await openProfile(page);
    await both(page, "7-ho-so-google");
    await signOut(page);

    // The profile page to a visitor.
    await page.goto(`${BASE}/ho-so`, { waitUntil: "domcontentloaded" });
    await page.getByText("Đăng nhập để xem hồ sơ").waitFor({ timeout: 120_000 });
    await settle(page);
    await shoot(page, "8-ho-so-khach-1440");

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
