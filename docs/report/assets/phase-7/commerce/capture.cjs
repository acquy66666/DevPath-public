// Nhóm màn 8 (Phase 7) — thương mại: giỏ hàng, yêu thích, kết quả thanh toán.
// Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/commerce/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/commerce/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml). One throwaway learner
// (@e2e.devpath.example), removed at the end with its orders by
// `scripts.purge_e2e`:
//   - cart: the three paid Trần Minh Khoa courses, plus "Lập trình hướng đối
//     tượng với Python", which the learner is then enrolled in straight in the
//     database (the "bạn đã có" line);
//   - wishlist: TypeScript, Docker and the DSA course (also in the cart);
//   - a paid order (IPN signed by `scripts.simulate_vnpay_ipn`), a failed one
//     (`--fail`: VNPay code 24) and one left pending.
// No coupon is spent: CHAOMUNG50 is applied for the cart shot only and taken
// off before paying, so `coupons.used_count` is untouched.
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
const OUT = path.join(REPO, "docs/report/assets/phase-7/commerce", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const PASSWORD = "devpath-shop-1";
const EMAIL = `mua-sam-${PHASE}-${Date.now().toString(36)}@e2e.devpath.example`;
const VNPAY = /sandbox\.vnpayment\.vn/;

const SLUG = {
  dsa: "cau-truc-du-lieu-va-giai-thuat-voi-python",
  recursion: "de-quy-va-quy-hoach-dong-0eyofk",
  advanced: "python-nang-cao-ham-decorator-va-generator-4i5o2i",
  oop: "lap-trinh-huong-doi-tuong-voi-python-a13mtm",
  ts: "typescript-cho-lap-trinh-vien-javascript-r94x6y",
  docker: "docker-cho-lap-trinh-vien-backend-e7b1d0",
};

let made = false;
function exec(...args) {
  return execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", ...args], { encoding: "utf8" });
}
function psql(sql) {
  return exec("postgres", "psql", "-U", "devpath", "-Atc", sql).trim();
}
function purge() {
  if (!made) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}
function ipn(code, fail = false) {
  return exec("backend", "python", "-m", "scripts.simulate_vnpay_ipn", code, ...(fail ? ["--fail"] : []));
}

let token = null;
async function call(method, pathname, body) {
  const headers = {};
  if (body) headers["content-type"] = "application/json";
  if (token) headers.authorization = `Bearer ${token}`;
  const r = await fetch(`${API}/api/v1${pathname}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}
const courseId = (slug) => psql(`select id from courses where slug = '${slug}'`);

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

async function signIn(page) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await formReady(page);
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

const taken = [];
async function shoot(page, name, { width = 1440 } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (page.viewportSize().width !== width) {
    await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled", fullPage: true });
  taken.push(name);
  console.log(`  ${name}`);
}
async function both(page, name) {
  await shoot(page, `${name}-1440`, { width: 1440 });
  await shoot(page, `${name}-375`, { width: 375 });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(800);
}
async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1000);
}
async function openCart(page) {
  await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
  await page.getByText(/khóa học|Giỏ hàng đang trống/).first().waitFor({ timeout: 120_000 });
  await settle(page);
}
/** Check out what is in the cart; returns the order code VNPay was sent. */
async function checkout(page) {
  await page.route(VNPAY, (route) =>
    route.fulfill({ contentType: "text/html; charset=utf-8", body: "<h1>VNPay (giả lập)</h1>" }),
  );
  await page.getByRole("button", { name: /Thanh toán.*qua VNPay/ }).filter({ visible: true }).first().click();
  await page.waitForURL(VNPAY, { timeout: 60_000 });
  const code = new URL(page.url()).searchParams.get("vnp_TxnRef");
  await page.unroute(VNPAY);
  return code;
}
async function openResult(page, code, heading) {
  await page.goto(`${BASE}/thanh-toan/ket-qua?vnp_TxnRef=${code}`, { waitUntil: "domcontentloaded" });
  await page.getByText(heading).first().waitFor({ timeout: 120_000 });
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

    // A guest opens the cart.
    await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
    await page.getByText("Đăng nhập để xem giỏ hàng").waitFor({ timeout: 120_000 });
    await settle(page);
    await shoot(page, "1-gio-hang-khach-1440");

    // The learner and their cart.
    made = true;
    await call("POST", "/auth/register", { email: EMAIL, password: PASSWORD, full_name: "Người mua thử" });
    token = (await call("POST", "/auth/login", { email: EMAIL, password: PASSWORD })).access_token;
    for (const key of ["dsa", "recursion", "advanced", "oop"]) await call("PUT", `/cart/courses/${courseId(SLUG[key])}`);
    for (const key of ["ts", "docker", "dsa"]) await call("PUT", `/wishlist/courses/${courseId(SLUG[key])}`);
    psql(
      `insert into enrollments (user_id, course_id, source) select u.id, c.id, 'purchase' from users u, courses c where u.email = '${EMAIL}' and c.slug = '${SLUG.oop}'`,
    );
    await signIn(page);

    await openCart(page);
    await page.getByLabel("Mã giảm giá").fill("CHAOMUNG50");
    await page.getByRole("button", { name: "Áp dụng" }).click();
    await page.getByRole("button", { name: "Bỏ mã CHAOMUNG50" }).waitFor({ timeout: 30_000 });
    await settle(page);
    await both(page, "2-gio-hang");

    // A refused code.
    await page.getByRole("button", { name: "Bỏ mã CHAOMUNG50" }).click();
    await page.getByLabel("Mã giảm giá").fill("HETHAN");
    await page.getByRole("button", { name: "Áp dụng" }).click();
    await page.getByText(/hết hạn/).first().waitFor({ timeout: 30_000 });
    await settle(page);
    await shoot(page, "3-gio-hang-ma-het-han-1440");

    // The wishlist.
    await page.goto(`${BASE}/yeu-thich`, { waitUntil: "domcontentloaded" });
    await page.getByText(/khóa học/).first().waitFor({ timeout: 120_000 });
    await settle(page);
    await both(page, "4-yeu-thich");

    // Pay for the cart (no coupon), then VNPay's callback says paid.
    await openCart(page);
    const paid = await checkout(page);
    ipn(paid);
    await openResult(page, paid, "Thanh toán thành công");
    await both(page, "5-thanh-toan-thanh-cong");

    // What is left in the cart: the course already owned. Take it out too.
    await call("DELETE", `/cart/courses/${courseId(SLUG.oop)}`);
    await openCart(page);
    await shoot(page, "6-gio-hang-trong-1440");

    // A payment that fails at the bank (code 24: cancelled by the customer).
    await call("PUT", `/cart/courses/${courseId(SLUG.ts)}`);
    await openCart(page);
    const failed = await checkout(page);
    ipn(failed, true);
    await openResult(page, failed, "không thành công");
    await both(page, "7-thanh-toan-that-bai");

    // One that is still waiting for the bank.
    await openCart(page);
    const pending = await checkout(page);
    await openResult(page, pending, /chờ/i);
    await shoot(page, "8-thanh-toan-dang-cho-1440");

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
