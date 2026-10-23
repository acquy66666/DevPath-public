// Nhóm màn 3 (Phase 7) — nộp bài code: đề bài, khung code, kết quả theo verdict,
// lịch sử, toàn màn hình. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/code-submission/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/code-submission/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the seed catalogue, the
// grading worker and the sandbox image. Registers a one-time learner
// (@e2e.devpath.example), enrols it in the free Python course and hands in
// real code to the real sandbox: one trial run and eight submissions, 11 s
// apart (the per-student cooldown is 10 s). `scripts.purge_e2e` removes the
// account, its submissions and its XP at the end. ONLY=<regex> limits the
// shots by name (the submissions still happen, in order).
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
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const PASSWORD = "devpath-nop-bai-1";
const COOLDOWN_MS = 11_000;

const HEAD = "n = int(input())\na = list(map(int, input().split()))\n";
// No indented lines: Monaco indents a new line after "for x in a:" by itself,
// and the inserted spaces would come on top of it.
const CODE = {
  // The demo database's own WA of 18/10: forgets 0 and the negatives (50/100).
  wa: `${HEAD}print(sum(1 for x in a if x % 2 == 0 and x > 0))\n`,
  // Counts the odd numbers: wrong already on sample #1.
  waSample: `${HEAD}print(sum(1 for x in a if x % 2 == 1))\n`,
  ce: `${HEAD}print(sum(1 for x in a if x % 2 == 0)\n`,
  re: `${HEAD}print(len(a) // 0)\n`,
  tle: `${HEAD}while True: pass\n`,
  mle: `${HEAD}grow = []\nwhile True: grow.append(bytearray(10_000_000))\n`,
  ac: `${HEAD}print(sum(1 for x in a if x % 2 == 0))\n`,
};
const HINT = {
  AC: "Chương trình in ra đúng kết quả mong đợi ở mọi test case.",
  WA: "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.",
  TLE: "Chương trình chạy quá lâu và bị dừng.",
  MLE: "Chương trình dùng quá nhiều bộ nhớ và bị dừng.",
  RE: "Chương trình dừng giữa chừng vì một lỗi lúc chạy",
  CE: "Chương trình không chạy được vì sai cú pháp.",
  // A trial that passes: the old page said the AC hint, the new one counts the samples.
  TRIAL: /Chương trình in ra đúng kết quả mong đợi|test mẫu đúng/,
};

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

async function stage() {
  const email = `nopbai-${PHASE}-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Học Viên Nộp Bài" },
  });
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const lesson = curriculum.sections.flatMap((s) => s.lessons).find((l) => l.type === "code_exercise");
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, lessonId: lesson.id };
}

function purge() {
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function signIn(page, email) {
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
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error("đăng nhập thất bại");
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

const taken = [];
async function shoot(page, name, { width = 1440, fullPage = true } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (page.viewportSize().width !== width) {
    await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
    await page.waitForTimeout(800); // Monaco relays itself out on resize
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled", fullPage });
  taken.push(name);
  console.log(`  ${name}`);
}

async function both(page, name) {
  await shoot(page, `${name}-1440`, { width: 1440 });
  await shoot(page, `${name}-375`, { width: 375 });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(800);
}

async function type(page, code) {
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  // One insert rather than typed keys: Monaco auto-closes brackets.
  await page.keyboard.insertText(code);
}

let lastRun = 0;
async function run(page, code, button, verdict, { during } = {}) {
  const wait = lastRun + COOLDOWN_MS - Date.now();
  if (wait > 0) await page.waitForTimeout(wait);
  await type(page, code);
  await page.getByRole("button", { name: button, exact: true }).click();
  lastRun = Date.now();
  if (during) await during();
  await page.getByText(HINT[verdict]).first().waitFor({ timeout: 180_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1200);
}

(async () => {
  const { email, lessonId } = await stage();
  console.log(`${PHASE}: ${email}`);
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      reducedMotion: "reduce",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    await signIn(page, email);
    await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
    await page.locator(".monaco-editor").first().waitFor({ timeout: 120_000 });
    await page.waitForLoadState("networkidle").catch(() => {});
    await both(page, "1-de-bai");

    await run(page, CODE.wa, "Nộp bài", "WA");
    await both(page, "2-sai-ket-qua");

    await run(page, CODE.ac, "Chạy thử", "TRIAL");
    await shoot(page, "3-chay-thu-1440");

    await run(page, CODE.waSample, "Nộp bài", "WA");
    await shoot(page, "4-sai-test-mau-1440");

    await run(page, CODE.ce, "Nộp bài", "CE");
    await shoot(page, "5-loi-cu-phap-1440");

    await run(page, CODE.re, "Nộp bài", "RE");
    await shoot(page, "6-loi-khi-chay-1440");

    await run(page, CODE.tle, "Nộp bài", "TLE");
    await shoot(page, "7-qua-thoi-gian-1440");

    await run(page, CODE.mle, "Nộp bài", "MLE");
    await shoot(page, "8-qua-bo-nho-1440");

    await run(page, CODE.ac, "Nộp bài", "AC", {
      during: async () => {
        // Mid-run: a case or two judged, the rest still to come.
        await page.getByText(/Đang chấm test [2-5]\/6/).first().waitFor({ timeout: 120_000 });
        await shoot(page, "9-dang-cham-1440", { fullPage: false });
      },
    });
    await both(page, "10-dung");

    // The first submission, opened again from the history.
    await page.getByRole("button", { name: "Xem lại", exact: true }).last().click();
    await page.getByText(HINT.WA).first().waitFor({ timeout: 60_000 });
    await page.waitForTimeout(1000);
    await shoot(page, "11-xem-lai-1440");

    const enter = page.getByRole("button", { name: "Toàn màn hình" });
    if ((await enter.count()) > 0) {
      await enter.click();
      await page.waitForTimeout(1200);
      await shoot(page, "12-toan-man-hinh-1440", { fullPage: false });
      await page.keyboard.press("Escape");
    }

    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
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
  process.exit(1);
});
