// Nhóm màn 5 (Phase 7) — quiz: trước khi làm, đang làm có đồng hồ, sắp hết
// giờ, kết quả theo 4 mức + hết giờ, lịch sử. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/quiz/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/quiz/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the seed catalogue and
// the quiz "Kiểm tra: vòng lặp for" of the Python course (5 questions, hand
// reviewed at the phase-4 gate, untimed). No Gemini call.
//
// Registers a one-time learner (@e2e.devpath.example), enrols it in the free
// Python course and ticks every lesson before the quiz. The quiz is timed for
// the run (10 minutes, written straight to `quizzes.time_limit_s`, put back at
// the end) and the clock is moved by rewriting the open attempt's
// `started_at`: that is how "sắp hết giờ" and "hết giờ" are reached without
// waiting ten minutes. Five attempts, in this order: 20%, 60%, hết giờ, 80%
// (the one that passes the lesson), 100%. At the end `scripts.purge_e2e`
// removes the learner, its attempts and its progress.
//
// REPO=<checkout> lets a copy of this script outside the repo write into it
// (the "before" run is made on the previous branch, where this file is not).
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
const OUT = path.join(REPO, "docs/report/assets/phase-7/quiz", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const QUIZ = "Kiểm tra: vòng lặp for";
const PASSWORD = "devpath-quiz-1";
const LIMIT_S = 600;

// The answer key, then four papers: each a list of option texts, null = blank.
const KEY = ["0, 1, 2, 3, 4", "range(1, 11)", "enumerate", "Bên ngoài vòng lặp", "Khi biết trước sẽ đi qua những gì"];
const PAPERS = {
  comfort: ["0, 1, 2, 3, 4", "range(1, 10)", "append", "Bên trong vòng lặp", null], // 20%
  cheer: ["0, 1, 2, 3, 4", "range(1, 11)", "range(len(ds))", "Bên ngoài vòng lặp", "Chỉ khi duyệt một chuỗi ký tự"], // 60%
  proud: ["0, 1, 2, 3, 4", "range(1, 11)", "range(len(ds))", "Bên ngoài vòng lặp", "Khi biết trước sẽ đi qua những gì"], // 80%
  party: KEY, // 100%
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

function compose(...args) {
  return execFileSync("docker", ["compose", "-f", COMPOSE, ...args], { encoding: "utf8" });
}

function sql(statement) {
  return compose("exec", "-T", "postgres", "psql", "-U", "devpath", "-At", "-c", statement).trim();
}

const staged = {};

async function stage() {
  const email = `quiz-${PHASE}-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Trần Minh Anh" },
  });
  staged.email = email;
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const quizLesson = curriculum.sections.flatMap((s) => s.lessons).find((l) => l.title === QUIZ);
  if (!quizLesson) throw new Error(`không thấy bài "${QUIZ}"`);

  // Everything before the quiz is done: the page opens where a learner who
  // reached it would be.
  for (const section of curriculum.sections) {
    for (const lesson of section.lessons) {
      if (lesson.id === quizLesson.id) break;
      await call("PUT", `/lessons/${lesson.id}/progress`, { token, body: { last_position_s: 0, completed: true } });
    }
    if (section.lessons.some((l) => l.id === quizLesson.id)) break;
  }

  const quiz = await call("GET", `/lessons/${quizLesson.id}/quiz`, { token });
  staged.quizId = quiz.id;
  staged.limit = sql(`select coalesce(time_limit_s::text, 'NULL') from quizzes where id = '${quiz.id}'`);
  sql(`update quizzes set time_limit_s = ${LIMIT_S} where id = '${quiz.id}'`);
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, lessonId: quizLesson.id };
}

/**
 * Move every finished attempt half an hour into the past. Called before each
 * rewind, so the attempt being rewound stays the newest: the history numbers
 * attempts by when they started, and a ten-minute rewind would otherwise put
 * it before attempts made a minute ago.
 */
function ageFinished() {
  sql(
    `update quiz_attempts set started_at = started_at - interval '30 minutes', ` +
      `submitted_at = submitted_at - interval '30 minutes' ` +
      `where submitted_at is not null and user_id = (select id from users where email = '${staged.email}')`,
  );
}

/** Move the open attempt's start back: the server's clock is what counts. */
function rewind(seconds) {
  ageFinished();
  const moved = sql(
    `with moved as (update quiz_attempts set started_at = started_at - interval '${seconds} seconds' ` +
      `where submitted_at is null and user_id = (select id from users where email = '${staged.email}') returning 1) ` +
      `select count(*) from moved`,
  );
  if (moved !== "1") throw new Error(`không có lượt đang mở để lùi giờ (${moved})`);
}

function purge() {
  if (staged.quizId && staged.limit) {
    sql(`update quizzes set time_limit_s = ${staged.limit} where id = '${staged.quizId}'`);
    console.log(`trả time_limit_s = ${staged.limit}`);
  }
  if (staged.email) {
    execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
      stdio: "inherit",
    });
  }
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
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  // A whole-page shot is taken from the top: scrolled, the quiz's sticky bar
  // is drawn where the window was, in the middle of the picture.
  if (fullPage) await page.evaluate(() => window.scrollTo(0, 0));
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

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(800);
}

const START = /^(Bắt đầu làm bài|Tiếp tục làm bài|Làm lại)$/;

async function openQuiz(page, lessonId) {
  await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("navigation", { name: "Nội dung khóa học" }).waitFor({ timeout: 120_000 });
  await page.getByRole("button", { name: START }).first().waitFor({ timeout: 60_000 });
  await settle(page);
}

/** "Làm lại" starts a paper at once after the redesign, and went back to the intro before it. */
async function startPaper(page) {
  for (let round = 0; round < 2; round += 1) {
    await page.getByRole("button", { name: START }).first().click();
    const open = await page
      .getByRole("radio")
      .first()
      .waitFor({ timeout: 15_000 })
      .then(() => true, () => false);
    if (open) {
      await settle(page);
      return;
    }
  }
  throw new Error("không mở được bài làm");
}

async function answer(page, paper) {
  for (const option of paper) {
    if (option !== null) await page.getByRole("radio", { name: option, exact: true }).check({ force: true });
  }
}

async function handIn(page) {
  const marked = page.waitForResponse((r) => /\/quiz-attempts\/[^/]+\/submit$/.test(r.url()));
  await page.getByRole("button", { name: "Nộp bài", exact: true }).click();
  if (!(await marked).ok()) throw new Error("nộp bài thất bại");
  await settle(page);
}

/** The quiz's top at the top of the window, as a learner scrolled to it. */
async function scrollToQuiz(page) {
  await page.evaluate(() => {
    const quiz = document.querySelector("input[type=radio]")?.closest("section");
    if (quiz) window.scrollTo(0, quiz.getBoundingClientRect().top + window.scrollY - 24);
  });
  await page.waitForTimeout(500);
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

    await openQuiz(page, lessonId);
    await both(page, "1-truoc-khi-lam");

    // Three attempts that do not pass, each shown as it lands.
    await startPaper(page);
    await answer(page, PAPERS.comfort);
    await handIn(page);
    await shoot(page, "2-muc-20-1440");

    await startPaper(page);
    await answer(page, PAPERS.cheer);
    await handIn(page);
    await shoot(page, "3-muc-60-1440");

    await startPaper(page);
    await answer(page, [KEY[0], KEY[1], null, null, null]);
    rewind(LIMIT_S + 15); // past the deadline and its 10 s of grace
    await handIn(page);
    await shoot(page, "4-het-gio-1440");

    // Coming back to the lesson: the intro with the history under it.
    await openQuiz(page, lessonId);
    await shoot(page, "5-co-lich-su-1440");

    // The paper that passes: half answered, then left and resumed with under
    // a minute to go, then handed in.
    await startPaper(page);
    await answer(page, PAPERS.proud.slice(0, 3));
    await both(page, "6-dang-lam");
    rewind(LIMIT_S - 58);
    await openQuiz(page, lessonId);
    await shoot(page, "7-lam-do-1440", { fullPage: false });
    await startPaper(page);
    await scrollToQuiz(page);
    await shoot(page, "8-sap-het-gio-1440", { fullPage: false });
    await answer(page, PAPERS.proud);
    await handIn(page);
    await both(page, "9-ket-qua-80");

    await startPaper(page);
    await answer(page, PAPERS.party);
    await handIn(page);
    await shoot(page, "10-muc-100-1440");

    // An old attempt opened again from the history (the redesign only).
    if (PHASE === "after") {
      await page.getByRole("button", { name: "Xem lại lượt 1" }).click();
      await page.getByText("Lượt 1 · xem lại").waitFor({ timeout: 30_000 });
      await settle(page);
      await shoot(page, "11-xem-lai-luot-cu-1440");
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
  try {
    purge();
  } catch (error) {
    console.error("dọn hỏng — chạy tay `python -m scripts.purge_e2e`:", String(error).split("\n")[0]);
  }
  process.exit(1);
});
