// Nhóm màn 5 (Phase 7) — quiz: hành vi trên Chrome thật, sau khi thiết kế lại.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/quiz/check.cjs
//
// Same stage as capture.cjs (one-time learner, the Python course's "Kiểm tra:
// vòng lặp for" timed at 10 minutes for the run, the clock moved through the
// open attempt's `started_at`), motion allowed so Naomi's reaction can be
// seen. Writes results.json next to this file and exits 1 if a check fails.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const QUIZ = "Kiểm tra: vòng lặp for";
const PASSWORD = "devpath-quiz-1";
const LIMIT_S = 600;

const KEY = ["0, 1, 2, 3, 4", "range(1, 11)", "enumerate", "Bên ngoài vòng lặp", "Khi biết trước sẽ đi qua những gì"];
const COMFORT = ["0, 1, 2, 3, 4", "range(1, 10)", "append", "Bên trong vòng lặp", null];
const PROUD = ["0, 1, 2, 3, 4", "range(1, 11)", "range(len(ds))", "Bên ngoài vòng lặp", "Khi biết trước sẽ đi qua những gì"];

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

const sql = (statement) =>
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "postgres", "psql", "-U", "devpath", "-At", "-c", statement], {
    encoding: "utf8",
  }).trim();

const staged = {};

async function stage() {
  const email = `quiz-check-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Trần Minh Anh" },
  });
  staged.email = email;
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const quizLesson = curriculum.sections.flatMap((s) => s.lessons).find((l) => l.title === QUIZ);
  const chapter = curriculum.sections.find((s) => s.lessons.some((l) => l.id === quizLesson.id));
  for (const section of curriculum.sections) {
    for (const lesson of section.lessons) {
      if (lesson.id === quizLesson.id) break;
      await call("PUT", `/lessons/${lesson.id}/progress`, { token, body: { last_position_s: 0, completed: true } });
    }
    if (section === chapter) break;
  }
  const quiz = await call("GET", `/lessons/${quizLesson.id}/quiz`, { token });
  staged.quizId = quiz.id;
  staged.limit = sql(`select coalesce(time_limit_s::text, 'NULL') from quizzes where id = '${quiz.id}'`);
  sql(`update quizzes set time_limit_s = ${LIMIT_S} where id = '${quiz.id}'`);
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, lessonId: quizLesson.id, chapterStart: chapter.lessons[0].id, chapterNumber: curriculum.sections.indexOf(chapter) + 1 };
}

function ageFinished() {
  sql(
    `update quiz_attempts set started_at = started_at - interval '30 minutes', submitted_at = submitted_at - interval '30 minutes' ` +
      `where submitted_at is not null and user_id = (select id from users where email = '${staged.email}')`,
  );
}

function rewind(seconds) {
  ageFinished();
  sql(
    `update quiz_attempts set started_at = started_at - interval '${seconds} seconds' ` +
      `where submitted_at is null and user_id = (select id from users where email = '${staged.email}')`,
  );
}

function purge() {
  if (staged.quizId && staged.limit) sql(`update quizzes set time_limit_s = ${staged.limit} where id = '${staged.quizId}'`);
  if (staged.email) {
    execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
      stdio: "inherit",
    });
  }
}

const results = [];
async function check(name, fn) {
  try {
    const detail = await fn();
    results.push({ name, ok: true, detail: detail ?? null });
    console.log(`  ✔ ${name}${detail ? ` — ${detail}` : ""}`);
  } catch (error) {
    results.push({ name, ok: false, detail: String(error.message ?? error).split("\n")[0] });
    console.log(`  ✖ ${name} — ${String(error.message ?? error).split("\n")[0]}`);
  }
}

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

async function signIn(page, email) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
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
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

const START = /^(Bắt đầu làm bài|Tiếp tục làm bài|Làm lại)$/;

async function openQuiz(page, lessonId) {
  await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: START }).first().waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
}

async function start(page) {
  await page.getByRole("button", { name: START }).first().click();
  await page.getByRole("radio").first().waitFor({ timeout: 30_000 });
}

async function answer(page, paper) {
  for (const option of paper) {
    if (option !== null) await page.getByRole("radio", { name: option, exact: true }).check({ force: true });
  }
}

async function handIn(page) {
  const marked = page.waitForResponse((r) => /\/quiz-attempts\/[^/]+\/submit$/.test(r.url()));
  await page.getByRole("button", { name: "Nộp bài", exact: true }).click();
  await marked;
  await page.getByRole("heading", { name: "Xem lại bài làm" }).waitFor({ timeout: 30_000 });
  await page.waitForTimeout(400);
}

const nextLink = (page) => page.getByRole("link", { name: /^Bài tiếp theo:/ });
const classOf = (locator) => locator.evaluate((el) => el.className);
const mood = (page) => page.locator("[data-mascot] [data-mood]").first();
const live = (page) => page.locator("p.sr-only[aria-live=polite]").last();

async function noOverflow(page, label) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(600);
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
  expect(width <= 375, `${label}: rộng ${width} px ở 375`);
  return `${label}: ${width} px`;
}

(async () => {
  const { email, lessonId, chapterStart, chapterNumber } = await stage();
  console.log(`check: ${email}`);
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    await signIn(page, email);
    await openQuiz(page, lessonId);

    // --- Before an attempt ---------------------------------------------
    await check("đầu bài ghi số câu của quiz", async () => {
      await page.getByRole("list", { name: "Thông tin bài học" }).getByText("Quiz · 5 câu").waitFor({ timeout: 10_000 });
    });
    await check("màn trước khi làm có 3 thông tin và nút chính", async () => {
      for (const value of ["5 câu", "10 phút", "70%"]) {
        await page.locator("dd", { hasText: value }).first().waitFor({ timeout: 5_000 });
      }
      const button = page.getByRole("button", { name: "Bắt đầu làm bài" });
      expect((await classOf(button)).includes("bg-primary"), "nút bắt đầu không phải nút chính");
      expect((await classOf(nextLink(page))).includes("bg-secondary"), "Bài tiếp theo đang là nút chính");
    });
    await check("không tràn ngang: trước khi làm", () => noOverflow(page, "trước khi làm"));

    // --- Below half, before the lesson is finished ----------------------
    await start(page);
    await answer(page, COMFORT);
    await handIn(page);
    await check("dưới 50%: Naomi an ủi, 'Ôn lại chương' là nút chính, trỏ về đầu chương", async () => {
      expect((await mood(page).getAttribute("data-mood")) === "comfort", "mood không phải comfort");
      const link = page.getByRole("link", { name: `Ôn lại chương ${chapterNumber}` });
      const href = await link.getAttribute("href");
      expect(href?.endsWith(`?bai=${chapterStart}`), `href ${href}`);
      expect((await classOf(link)).includes("bg-primary"), "Ôn lại không phải nút chính");
      expect((await classOf(page.getByRole("button", { name: "Làm lại" }))).includes("border-input"), "Làm lại không phải nút viền");
      expect((await classOf(nextLink(page))).includes("bg-secondary"), "Bài tiếp theo đang là nút chính");
      return href;
    });
    await check("bỏ trống được đếm riêng với câu sai", async () => {
      await page.getByRole("button", { name: "Câu sai: câu 2, 3, 4 · bỏ trống: câu 5" }).waitFor({ timeout: 5_000 });
      // exact: getByText ignores case, and the pointer above says "bỏ trống" too.
      await page.getByText("· Bỏ trống", { exact: true }).waitFor({ timeout: 5_000 });
    });

    // --- Sitting it ----------------------------------------------------
    await page.getByRole("button", { name: "Làm lại" }).click();
    await page.getByRole("radio").first().waitFor({ timeout: 30_000 });
    await check("mở bài: focus vào câu 1", async () => {
      const tag = await page.evaluate(() => document.activeElement?.tagName);
      expect(tag === "FIELDSET", `focus ở ${tag}`);
    });
    await check("đang làm: Bài tiếp theo không phải nút chính", async () => {
      expect((await classOf(nextLink(page))).includes("bg-secondary"), "Bài tiếp theo đang là nút chính");
    });
    await check("bàn phím: Tab vào câu 1, Space chọn, mũi tên đổi phương án", async () => {
      await page.keyboard.press("Tab");
      await page.keyboard.press("Space");
      await page.getByText("Đã trả lời 1/5 câu").waitFor({ timeout: 5_000 });
      await page.keyboard.press("ArrowDown");
      const checked = await page.getByRole("radio", { name: "0, 1, 2, 3, 4, 5", exact: true }).isChecked();
      expect(checked, "mũi tên không chuyển sang phương án B");
      return "A → B, vẫn 1/5";
    });
    await check("code trong dấu backtick hiện thành code", async () => {
      const code = await page.locator("code", { hasText: "range(5)" }).count();
      const raw = await page.evaluate(() => document.body.innerText.includes("`range(5)`"));
      expect(code >= 1 && !raw, `code=${code}, backtick thô=${raw}`);
    });
    await answer(page, PROUD.slice(0, 3));
    await check("dòng trên nút nộp đếm câu bỏ trống", async () => {
      await page.getByText("Còn 2 câu chưa trả lời: câu 4 và câu 5").waitFor({ timeout: 5_000 });
    });
    await check("nút số câu đưa tới câu đó, không bị thanh dính che", async () => {
      await page.getByRole("button", { name: "Câu 4, chưa trả lời" }).click();
      await page.waitForTimeout(400);
      const box = await page.evaluate(() => {
        const focused = document.activeElement;
        const bar = document.querySelector('[aria-label="Đi tới câu hỏi"]')?.closest("div.sticky");
        return {
          tag: focused?.tagName,
          text: focused?.textContent?.slice(0, 12),
          top: focused?.getBoundingClientRect().top ?? -1,
          barBottom: bar?.getBoundingClientRect().bottom ?? 0,
        };
      });
      expect(box.tag === "FIELDSET" && box.text?.startsWith("Câu 4"), `focus: ${box.tag} ${box.text}`);
      expect(box.top >= box.barBottom, `câu 4 ở ${box.top}, thanh dính tới ${box.barBottom}`);
      return `câu 4 ở ${Math.round(box.top)} px, thanh tới ${Math.round(box.barBottom)} px`;
    });
    await check("đồng hồ là timer im lặng, vùng đọc không đọc từng giây", async () => {
      const timer = page.getByRole("timer").filter({ visible: true });
      const text = await timer.first().textContent();
      expect(/\d\d:\d\d/.test(text ?? ""), `đồng hồ: ${text}`);
      const said = (await live(page).textContent())?.trim();
      expect(said === "", `vùng đọc: "${said}"`);
      return text?.trim();
    });
    await check("không tràn ngang: đang làm", () => noOverflow(page, "đang làm"));

    await check("tải lại giữa chừng: tiếp tục, câu đã chọn còn nguyên", async () => {
      await openQuiz(page, lessonId);
      await page.getByText("Bạn đang làm dở một lượt", { exact: false }).waitFor({ timeout: 10_000 });
      await start(page);
      await page.getByText("Đã trả lời 3/5 câu").waitFor({ timeout: 5_000 });
    });

    await check("dưới 1 phút: đồng hồ đổi màu và nói rõ", async () => {
      rewind(LIMIT_S - 50);
      await openQuiz(page, lessonId);
      await start(page);
      await page.getByText("Còn dưới 1 phút").waitFor({ timeout: 10_000 });
      const timer = page.getByRole("timer").filter({ visible: true }).first();
      const cls = await timer.evaluate((el) => `${el.className} ${el.parentElement?.className}`);
      expect(cls.includes("verdict-tle"), "đồng hồ không đổi màu");
    });

    // --- The result that passes --------------------------------------
    await answer(page, PROUD);
    await handIn(page);
    await check("nộp xong: focus và khung nhìn ở dải kết quả", async () => {
      const box = await page.evaluate(() => {
        const el = document.activeElement;
        return { text: el?.textContent ?? "", top: el?.getBoundingClientRect().top ?? -1, height: window.innerHeight };
      });
      expect(box.text.includes("4/5 câu đúng"), `focus ở: ${box.text.slice(0, 40)}`);
      expect(box.top >= 0 && box.top < box.height, `dải kết quả ở ${box.top}`);
    });
    await check("vùng đọc báo điểm", async () => {
      const said = (await live(page).textContent())?.trim();
      expect(said === "80%. Đạt. 4/5 câu đúng.", `vùng đọc: "${said}"`);
      return said;
    });
    await check("Naomi tự hào, phản ứng một lần", async () => {
      const node = mood(page);
      expect((await node.getAttribute("data-mood")) === "proud", `mood ${await node.getAttribute("data-mood")}`);
      await page.waitForFunction(
        () => ["playing", "settled"].includes(document.querySelector("[data-mascot] [data-mood]")?.getAttribute("data-phase") ?? ""),
        null,
        { timeout: 5_000 },
      );
      return await node.getAttribute("data-phase");
    });
    await check("dòng 'Câu sai: câu 3' đưa tới câu 3", async () => {
      await page.getByRole("button", { name: "Câu sai: câu 3" }).click();
      await page.waitForTimeout(500);
      const top = await page.locator("li", { hasText: "Câu 3 · Sai" }).first().evaluate((el) => el.getBoundingClientRect().top);
      expect(top >= 0 && top < 300, `câu 3 ở ${top}`);
    });
    await check("lọc 'Câu sai' chỉ còn câu 3", async () => {
      await page.getByRole("button", { name: "Câu sai · 1" }).click();
      const rows = page.locator("ol > li", { hasText: /^Câu \d/ });
      const count = await rows.count();
      const first = await rows.first().textContent();
      expect(count === 1 && first?.startsWith("Câu 3"), `${count} câu, đầu là ${first?.slice(0, 10)}`);
      await page.getByRole("button", { name: "Tất cả · 5" }).click();
    });
    await check("đạt rồi: Bài tiếp theo là nút chính, Làm lại là nút viền", async () => {
      await page.getByRole("list", { name: "Thông tin bài học" }).getByText("Đã hoàn thành").waitFor({ timeout: 10_000 });
      expect((await classOf(nextLink(page))).includes("bg-primary"), "Bài tiếp theo chưa là nút chính");
      expect((await classOf(page.getByRole("button", { name: "Làm lại" }))).includes("border-input"), "Làm lại không phải nút viền");
    });
    await check("lịch sử đánh số lượt, lượt đang xem ghi rõ", async () => {
      await page.getByText("Đang xem").waitFor({ timeout: 10_000 });
      const row = await page.locator("li", { hasText: "Đang xem" }).first().textContent();
      expect(row?.includes("Lượt 2") && row.includes("80%"), `dòng: ${row}`);
      return row?.replace(/\s+/g, " ").trim();
    });
    await check("không tràn ngang: kết quả", () => noOverflow(page, "kết quả"));

    // --- Out of time ---------------------------------------------------
    await page.getByRole("button", { name: "Làm lại" }).click();
    await page.getByRole("radio").first().waitFor({ timeout: 30_000 });
    await answer(page, [KEY[0], null, null, null, null]);
    rewind(LIMIT_S + 15);
    await handIn(page);
    await check("hết giờ: Naomi giật mình, câu nào cũng 'Chưa nộp', không có bộ lọc", async () => {
      await page.getByRole("heading", { name: /Bài chưa kịp nộp/ }).waitFor({ timeout: 5_000 });
      expect((await mood(page).getAttribute("data-mood")) === "startled", "mood không phải startled");
      const unscored = await page.getByText("· Chưa nộp").count();
      const filter = await page.getByRole("group", { name: "Lọc câu hỏi" }).count();
      expect(unscored === 5 && filter === 0, `chưa nộp=${unscored}, bộ lọc=${filter}`);
    });

    // --- An old attempt, opened again ----------------------------------
    await check("mở lại lượt cũ: Naomi đứng yên, đóng lại về màn đầu", async () => {
      await page.getByRole("button", { name: "Xem lại lượt 1" }).click();
      await page.getByText("Lượt 1 · xem lại").waitFor({ timeout: 10_000 });
      await page.waitForTimeout(1_500);
      expect((await mood(page).getAttribute("data-phase")) === "still", `phase ${await mood(page).getAttribute("data-phase")}`);
      await page.getByRole("button", { name: "Đóng lượt này" }).click();
      await page.getByRole("button", { name: "Làm lại" }).waitFor({ timeout: 10_000 });
      const focused = await page.evaluate(() => document.activeElement?.textContent?.trim());
      expect(focused === "Làm lại", `focus ở: ${focused}`);
    });

    // --- A quiz with no clock ------------------------------------------
    await check("không tính giờ: không có đồng hồ", async () => {
      sql(`update quizzes set time_limit_s = NULL where id = '${staged.quizId}'`);
      await openQuiz(page, lessonId);
      await page.getByText("Không tính giờ, cứ làm thong thả.").waitFor({ timeout: 10_000 });
      await start(page);
      const timers = await page.getByRole("timer").count();
      await page.getByText("Không tính giờ", { exact: true }).filter({ visible: true }).first().waitFor({ timeout: 5_000 });
      expect(timers === 0, `${timers} timer`);
      await answer(page, KEY);
      await handIn(page);
      expect((await mood(page).getAttribute("data-mood")) === "party", "100% mà không phải party");
    });

    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
    await context.close();
  } finally {
    await browser.close();
    purge();
  }
  const failed = results.filter((r) => !r.ok).length;
  fs.writeFileSync(
    path.join(__dirname, "results.json"),
    JSON.stringify({ at: new Date().toISOString(), base: BASE, passed: results.length - failed, failed, results }, null, 2),
  );
  console.log(`\n${results.length - failed}/${results.length} đạt`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error(e);
  try {
    purge();
  } catch (error) {
    console.error("dọn hỏng — chạy tay `python -m scripts.purge_e2e`:", String(error).split("\n")[0]);
  }
  process.exit(1);
});
