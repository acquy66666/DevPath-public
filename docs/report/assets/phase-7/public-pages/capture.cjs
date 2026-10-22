// Nhóm màn 2 (Phase 7) — trang công khai: trang chủ, danh sách + tìm kiếm,
// chi tiết khóa học, trang "Trở thành giảng viên". Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/public-pages/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/public-pages/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the seed catalogue and
// the `seed_sales` buyers. Signed-in shots use a buyer (read-only: nothing is
// written) and sign it out again. ONLY=<regex> limits the shots by name.
// BASE / API point elsewhere (default localhost:3000 / :8000).
const fs = require("fs");
const path = require("path");
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
const REPO = path.resolve(__dirname, "../../../../..");

const LEARNER = {
  email: process.env.LEARNER_EMAIL || "nguoimua08@sales.devpath.example",
  password: process.env.LEARNER_PASSWORD || "devpath-buyer",
};
const PAID_COURSE = "cau-truc-du-lieu-va-giai-thuat-voi-python";
const FREE_COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";

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
async function shoot(page, name, { width, url, before, fullPage = true } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
  await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 180_000 });
  await settle(page);
  if (before) {
    await before(page);
    await page.waitForTimeout(500);
  }
  // The `next dev` indicator in the corner is not part of the site.
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled", fullPage });
  taken.push(name);
  console.log(`  ${name}`);
}

const newContext = (browser) =>
  browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", reducedMotion: "reduce" });

async function guest(browser) {
  console.log("khách");
  const context = await newContext(browser);
  const page = await context.newPage();
  for (const width of [1440, 375]) {
    await shoot(page, `trang-chu-khach-${width}`, { width, url: "/" });
    await shoot(page, `danh-sach-${width}`, { width, url: "/khoa-hoc" });
    await shoot(page, `tim-python-${width}`, { width, url: "/khoa-hoc?q=python" });
    await shoot(page, `chi-tiet-tra-phi-${width}`, { width, url: `/khoa-hoc/${PAID_COURSE}` });
    await shoot(page, `chi-tiet-mien-phi-${width}`, { width, url: `/khoa-hoc/${FREE_COURSE}` });
    await shoot(page, `giang-vien-khach-${width}`, { width, url: "/tro-thanh-giang-vien" });
  }
  await context.close();
}

async function learner(browser) {
  console.log(`học viên ${LEARNER.email}`);
  const context = await newContext(browser);
  const page = await signIn(context, LEARNER.email, LEARNER.password);
  for (const width of [1440, 375]) {
    await shoot(page, `trang-chu-hoc-vien-${width}`, {
      width,
      url: "/",
      before: async (p) => p.getByRole("region", { name: "Gợi ý cho bạn" }).locator("a").first().waitFor({ timeout: 60_000 }),
    });
    await shoot(page, `chi-tiet-da-ghi-danh-${width}`, { width, url: `/khoa-hoc/${PAID_COURSE}` });
    await shoot(page, `giang-vien-hoc-vien-${width}`, { width, url: "/tro-thanh-giang-vien" });
  }
  await signOut(page);
  await context.close();
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    await guest(browser);
    await learner(browser);
  } finally {
    await browser.close();
  }
  const list = path.join(OUT, "shots.json");
  const earlier = fs.existsSync(list) ? JSON.parse(fs.readFileSync(list, "utf8")).shots : [];
  const shots = [...new Set([...earlier, ...taken])].sort();
  fs.writeFileSync(list, JSON.stringify({ base: BASE, at: new Date().toISOString(), shots }, null, 2));
  console.log(`\n${taken.length} ảnh → ${path.relative(REPO, OUT)}`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
