// Nhóm màn 9 (Phase 7) — khu giảng viên: tổng quan, tạo khóa, soạn khóa
// (mục lục, bài tập code, trắc nghiệm), thông tin khóa, hỏi đáp, thống kê,
// cấp bậc. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/instructor/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/instructor/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml). Writes, all on throwaway
// @e2e.devpath.example accounts removed at the end by `scripts.purge_e2e`:
//   - an instructor "Lê Thu Hà" with four courses: one published (status set
//     straight in the database, so no Gemini quota is spent on ingest), one
//     draft, one sent back by the seeded admin with a reason, one empty;
//   - in the published course: a video, an article, a code exercise with
//     three test cases and a quiz whose last two questions are marked
//     AI-written and not yet reviewed (also in the database: no Gemini call);
//   - a learner who enrols in the published course and asks one question.
// Statistics and the tier page are shot on the seeded Trần Minh Khoa, whose
// numbers are the real ones; his session is logged out afterwards.
//
// REPO=<checkout> lets a copy of this script outside the repo write into it.
// ONLY=<regex> limits the shots by name.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { BASE, REPO, PASSWORD, KHOA, accounts, purge, signIn, stage, stageCourses, ask } = require("./stage.cjs");

const PHASE = process.env.PHASE;
if (!["before", "after"].includes(PHASE)) {
  console.error("PHASE=before|after");
  process.exit(2);
}
const OUT = path.join(REPO, "docs/report/assets/phase-7/instructor", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const STAMP = `${PHASE}-${Date.now().toString(36)}`;
const { teacher: TEACHER, learner: LEARNER } = accounts(STAMP);

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
  await page.waitForFunction(() => !document.querySelector("[data-slot=skeleton], [aria-busy=true]"), null, {
    timeout: 30_000,
  }).catch(() => {});
  await page.waitForTimeout(600);
}
async function open(page, pathname) {
  await page.goto(`${BASE}${pathname}`, { waitUntil: "domcontentloaded" });
  await settle(page);
}

async function openLesson(page, title) {
  await page.getByRole("button", { name: `Sửa bài học ${title}`, exact: true }).click();
  await settle(page);
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN", reducedMotion: "reduce" });
  const page = await context.newPage();
  try {
    const t = await stage(TEACHER);
    await signIn(page, TEACHER, PASSWORD);

    console.log(`PHASE=${PHASE}`);
    await open(page, "/giang-day");
    await shoot(page, "1-chua-co-khoa-1440");
    await open(page, "/giang-day/moi");
    await shoot(page, "2-tao-khoa-1440");
    await open(page, "/giang-day/hoi-dap");
    await shoot(page, "3-hoi-dap-trong-1440");

    const c = await stageCourses(t);
    await ask(LEARNER, c.main.id, c.article.id);

    await open(page, "/giang-day");
    await both(page, "4-tong-quan");

    await open(page, `/giang-day/${c.empty.id}`);
    await shoot(page, "5-muc-luc-trong-1440");

    await open(page, `/giang-day/${c.main.id}`);
    await openLesson(page, "Bài tập: đếm số chẵn");
    await both(page, "6-soan-bai-code");

    await open(page, `/giang-day/${c.main.id}`);
    await openLesson(page, "Kiểm tra: ép kiểu");
    await shoot(page, "7-soan-quiz-1440");

    await open(page, `/giang-day/${c.rejected.id}`);
    if (PHASE === "after") {
      await page.getByRole("tab", { name: "Thông tin khóa học" }).click();
      await settle(page);
    }
    await shoot(page, "8-thong-tin-bi-tu-choi-1440");

    await open(page, "/giang-day/hoi-dap");
    await both(page, "9-hoi-dap");

    // The seeded instructor, for numbers that mean something.
    await context.clearCookies();
    await signIn(page, KHOA.email, KHOA.password);
    await open(page, "/giang-day/thong-ke");
    await shoot(page, "10-thong-ke-1440");
    await open(page, "/giang-day/cap-bac");
    await shoot(page, "11-cap-bac-1440");
    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), require("./stage.cjs").API);

    console.log(`${taken.length} ảnh → ${path.relative(REPO, OUT)}`);
  } finally {
    await browser.close();
    purge();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
