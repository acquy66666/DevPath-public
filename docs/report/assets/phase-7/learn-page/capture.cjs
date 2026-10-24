// Nhóm màn 4 (Phase 7) — trang học: video + ghi chú, bài đọc, mục lục, Hỏi đáp,
// trợ giảng AI. Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/learn-page/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/learn-page/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the seed catalogue, a
// Gemini key in infra/.env, and the internet (the seed videos are Mux test
// streams). Registers a one-time learner (@e2e.devpath.example), enrols it in
// the free Python course, ticks four lessons, writes three notes, bookmarks a
// lesson, asks one question that the seed instructor answers, and asks the
// assistant two questions through the API (in scope + out of scope) and one
// more on screen, mid-answer: three Gemini calls. At the end the instructor's
// `qa_question` notification is deleted and `scripts.purge_e2e` removes the
// rest. ONLY=<regex> limits the shots by name.
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
// A course the learner never joins: the "not enrolled" gate.
const OTHER_COURSE = "cau-truc-du-lieu-va-giai-thuat-voi-python";
const PASSWORD = "devpath-trang-hoc-1";
const INSTRUCTOR = {
  email: "khoa.tran@devpath.example",
  password: process.env.SEED_INSTRUCTOR_PASSWORD ?? "devpath-instructor",
};

const VIDEO = "Vòng lặp for và range";
const ARTICLE = "Đọc hiểu thông báo lỗi";
const QA_LESSON = "Ép kiểu và những cái bẫy quen thuộc";
const DONE = [
  "Cài đặt Python và VS Code",
  "Chương trình đầu tiên: Hello, World!",
  "Đọc hiểu thông báo lỗi",
  "Biến và phép gán",
];
// The notes of the phase-6 shots (phase-6/ui/capture.cjs), on the same lesson.
const NOTES = [
  [42, "range(start, stop, step): stop không bao giờ được tính."],
  [85, "range(1, 10, 2) → 1, 3, 5, 7, 9. Bước âm thì đếm ngược: range(10, 0, -2)."],
  [131, "Duyệt danh sách thì dùng thẳng `for x in xs`, cần chỉ số mới dùng enumerate()."],
];
const QUESTION = {
  title: 'int("3.5") báo lỗi nhưng int(3.5) thì không?',
  body:
    'Em gõ `int("3.5")` thì bị `ValueError: invalid literal for int()`, nhưng ' +
    "`int(3.5)` lại ra 3. Sao hai cách viết lại khác nhau vậy ạ?",
  reply:
    "Hai lệnh nhận hai kiểu dữ liệu khác nhau. Với một **số thực**, `int()` bỏ phần " +
    "thập phân nên `int(3.5)` là `3`. Với một **chuỗi**, `int()` chỉ đọc được chuỗi " +
    'viết đúng một số nguyên, nên `"3.5"` bị từ chối. Muốn đi từ chuỗi đó sang số ' +
    'nguyên thì qua số thực trước: `int(float("3.5"))`.',
};
// Two questions of the 22/09 assistant demo (phase-4/chatbot-demo.txt): one
// the course answers, one it must refuse. The third is asked on screen.
const CHAT = ["range(1, 10, 2) sinh ra những số nào?", "Thủ đô của nước Úc là thành phố nào?"];
const LIVE_QUESTION = "Vì sao input() + 1 bị lỗi, sửa thế nào?";
const CHAT_COOLDOWN_MS = 4_000;

async function call(method, pathname, { token, body, raw } = {}) {
  const r = await fetch(`${API}/api/v1${pathname}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  if (raw) return r.text();
  return r.status === 204 ? null : r.json();
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const staged = { threadIds: [] };

async function stage() {
  const email = `tranghoc-${PHASE}-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Trần Minh Anh" },
  });
  staged.email = email;
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const lessons = Object.fromEntries(curriculum.sections.flatMap((s) => s.lessons).map((l) => [l.title, l.id]));

  for (const title of DONE) {
    await call("PUT", `/lessons/${lessons[title]}/progress`, {
      token,
      body: { last_position_s: 0, completed: true },
    });
  }
  // Half-way through the video lesson, so the page opens on it.
  await call("PUT", `/lessons/${lessons[VIDEO]}/progress`, { token, body: { last_position_s: 140 } });
  for (const [timestamp_s, content] of NOTES) {
    await call("POST", `/lessons/${lessons[VIDEO]}/notes`, { token, body: { timestamp_s, content } });
  }
  await call("PUT", `/lessons/${lessons[VIDEO]}/bookmark`, { token });

  const thread = await call("POST", `/lessons/${lessons[QA_LESSON]}/qa-threads`, {
    token,
    body: { title: QUESTION.title, body: QUESTION.body },
  });
  staged.threadIds.push(thread.id);
  const teacher = await call("POST", "/auth/login", { body: INSTRUCTOR });
  try {
    await call("POST", `/qa-threads/${thread.id}/replies`, {
      token: teacher.access_token,
      body: { body: QUESTION.reply },
    });
  } finally {
    await call("POST", "/auth/logout", { token: teacher.access_token }).catch(() => {});
  }

  if (!ONLY || ONLY.test("6-tro-giang-tra-loi")) {
    const chat = await call("POST", `/courses/${course.id}/chat-sessions`, { token });
    for (const [index, question] of CHAT.entries()) {
      if (index) await sleep(CHAT_COOLDOWN_MS);
      console.log(`Gemini ${index + 1}/${CHAT.length + 1}: ${question}`);
      const text = await call("POST", `/chat-sessions/${chat.id}/messages`, {
        token,
        body: { content: question },
        raw: true,
      });
      if (!/^event: done$/m.test(text)) throw new Error(`trợ giảng không trả lời xong: ${text.slice(-300)}`);
    }
  }

  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, lessons };
}

function compose(...args) {
  return execFileSync("docker", ["compose", "-f", COMPOSE, ...args], { encoding: "utf8" });
}

function purge() {
  for (const id of staged.threadIds) {
    const removed = compose(
      "exec", "-T", "postgres", "psql", "-U", "devpath", "-At", "-c",
      `with gone as (delete from notifications where payload->>'thread_id' = '${id}' returning 1) select count(*) from gone`,
    ).trim();
    console.log(`đã xóa ${removed} thông báo của câu hỏi tạm`);
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

async function openLesson(page, lessonId) {
  await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("navigation", { name: "Nội dung khóa học" }).waitFor({ timeout: 120_000 });
  await settle(page);
}

/** The first frame of the HLS stream, so the player is not a black box. */
async function videoReady(page) {
  await page
    .waitForFunction(() => {
      const video = document.querySelector("video");
      return video !== null && video.readyState >= 2;
    }, null, { timeout: 30_000 })
    .catch(() => console.log("  (video chưa tải được khung đầu)"));
  await page.waitForTimeout(500);
}

async function openAssistant(page) {
  await page.getByRole("tab", { name: "Trợ giảng AI" }).click();
  await page.getByRole("region", { name: "Trợ giảng AI" }).waitFor({ timeout: 30_000 });
  await settle(page);
}

/** A stored conversation, from the assistant's own history. */
async function openConversation(page, title) {
  const region = page.getByRole("region", { name: "Trợ giảng AI" });
  await region.getByRole("button", { name: "Lịch sử trò chuyện" }).click();
  await region.getByText(title, { exact: false }).first().click();
  await region.getByText(/Nguồn|nguồn/).first().waitFor({ timeout: 30_000 }).catch(() => {});
  await settle(page);
}

(async () => {
  const { email, lessons } = await stage();
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

    // Video lesson, the page as it opens: notes underneath.
    await openLesson(page, lessons[VIDEO]);
    await videoReady(page);
    await both(page, "1-video-ghi-chu");

    await openLesson(page, lessons[ARTICLE]);
    await both(page, "2-bai-doc");

    // Questions under a lesson: the list, then the answered one.
    await openLesson(page, lessons[QA_LESSON]);
    await page.getByRole("tab", { name: "Hỏi đáp" }).click();
    await page.getByText(QUESTION.title).first().waitFor({ timeout: 30_000 });
    await settle(page);
    await shoot(page, "3-hoi-dap-1440");
    await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessons[QA_LESSON]}&hoi-dap=${staged.threadIds[0]}`, {
      waitUntil: "domcontentloaded",
    });
    await page.getByText("Hai lệnh nhận hai kiểu dữ liệu khác nhau", { exact: false }).first().waitFor({
      timeout: 60_000,
    });
    await settle(page);
    await both(page, "4-hoi-dap-cau-hoi");

    // The assistant: waiting for a first question, then two stored answers.
    await openLesson(page, lessons[VIDEO]);
    await videoReady(page);
    await openAssistant(page);
    await shoot(page, "5-tro-giang-trong-1440", { fullPage: false });

    if (!ONLY || ONLY.test("6-tro-giang-tra-loi")) {
      // Both answers fit the panel: the sourced one, then the refusal.
      await openConversation(page, CHAT[0]);
      await shoot(page, "6-tro-giang-tra-loi-1440", { fullPage: false });
      await shoot(page, "6-tro-giang-tra-loi-375", { width: 375 });
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(800);
    }

    // Mid-answer, on screen: a new conversation, one question.
    if (!ONLY || ONLY.test("7-tro-giang-dang-tra-loi")) {
      const region = page.getByRole("region", { name: "Trợ giảng AI" });
      const fresh = region.getByRole("button", { name: "Cuộc trò chuyện mới" });
      if (await fresh.isEnabled()) await fresh.click();
      await sleep(CHAT_COOLDOWN_MS);
      console.log(`Gemini ${CHAT.length + 1}/${CHAT.length + 1}: ${LIVE_QUESTION}`);
      await region.getByLabel("Câu hỏi cho trợ giảng AI").fill(LIVE_QUESTION);
      await region.getByRole("button", { name: "Gửi câu hỏi" }).click();
      // Once the sources are in and the first words have arrived.
      await page
        .waitForFunction(() => /Đang đọc \d+ bài/.test(document.body.innerText), null, { timeout: 60_000 })
        .catch(() => console.log("  (không bắt được lúc đang trả lời)"));
      await shoot(page, "7-tro-giang-dang-tra-loi-1440", { fullPage: false });
      await region.getByRole("button", { name: "Gửi câu hỏi" }).waitFor({ timeout: 120_000 });
    }

    // A course this learner never joined.
    await page.goto(`${BASE}/hoc/${OTHER_COURSE}`, { waitUntil: "domcontentloaded" });
    await page.getByText("Bạn chưa đăng ký khóa học này").first().waitFor({ timeout: 60_000 });
    await settle(page);
    await shoot(page, "8-chua-dang-ky-1440", { fullPage: false });

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
