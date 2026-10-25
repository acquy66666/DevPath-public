// Nhóm màn 4 (Phase 7) — kiểm hành vi trang học trên Chrome thật:
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/learn-page/check.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the seed catalogue and a
// Gemini key (one question to the assistant). Registers a one-time learner,
// writes results.json beside this file and removes the account with
// `scripts.purge_e2e`. Exit 1 if a check fails.
//
// What it checks:
//   * "x/y bài" is written once on the page (the golden-flow test reads it);
//   * the contents opens on the section of the lesson on screen, and opens
//     the next one when "Bài tiếp theo" crosses into it;
//   * "Bài trước" / "Bài tiếp theo" go to the neighbours in reading order;
//   * "Ghi chú tại …" switches to the notes and puts the cursor in the box;
//   * the bookmark button flips, ticking a lesson moves the count and makes
//     "Bài tiếp theo" the screen's primary button;
//   * an article says how long it takes to read;
//   * the assistant: Naomi `thinking` while the answer is written, then
//     `answer` once it cites the course -- each reacting once -- and still
//     when the conversation is reopened from the history;
//   * finishing the course: the reward banner, Naomi `graduate` reacting
//     once, one "Xem chứng chỉ" link; reopened, she is still;
//   * a course not joined: Naomi and an h1 saying so;
//   * nothing spills sideways at 375 px.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const OTHER_COURSE = "cau-truc-du-lieu-va-giai-thuat-voi-python";
const PASSWORD = "devpath-trang-hoc-2";
const QUESTION = "range(1, 10, 2) sinh ra những số nào?";

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "✔" : "✘"} ${name}${detail ? ` — ${detail}` : ""}`);
}

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

let staged = null;
async function stage() {
  const email = `tranghoc-check-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Học Viên Kiểm Trang Học" },
  });
  staged = { email };
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const order = curriculum.sections.flatMap((s) => s.lessons);
  const id = Object.fromEntries(order.map((l) => [l.title, l.id]));
  for (const title of ["Cài đặt Python và VS Code", "Chương trình đầu tiên: Hello, World!", "Đọc hiểu thông báo lỗi", "Biến và phép gán"]) {
    await call("PUT", `/lessons/${id[title]}/progress`, { token, body: { last_position_s: 0, completed: true } });
  }
  await call("PUT", `/lessons/${id["Vòng lặp for và range"]}/bookmark`, { token });
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, id, order, token };
}

/** Every lesson but the last ticked, so ticking the last one finishes the course. */
async function finishAllButLast(email, order) {
  const { access_token: token } = await call("POST", "/auth/login", { body: { email, password: PASSWORD } });
  for (const lesson of order.slice(0, -1)) {
    await call("PUT", `/lessons/${lesson.id}/progress`, { token, body: { last_position_s: 0, completed: true } });
  }
  await call("POST", "/auth/logout", { token }).catch(() => {});
}

function purge() {
  if (!staged) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
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
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error("đăng nhập thất bại");
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

/** Every change of Naomi's phase inside `scope`, with her mood, in order. */
async function record(page, scope) {
  await page.evaluate((selector) => {
    window.__phases = [];
    window.__observer?.disconnect();
    window.__observer = new MutationObserver((records) => {
      for (const r of records) {
        const el = r.target;
        if (el instanceof Element && el.hasAttribute("data-phase") && el.closest(selector)) {
          window.__phases.push(`${el.getAttribute("data-mood")}:${el.getAttribute("data-phase")}`);
        }
      }
    });
    window.__observer.observe(document, { subtree: true, attributes: true, attributeFilter: ["data-phase"] });
  }, scope);
}
const phases = (page) => page.evaluate(() => window.__phases ?? []);
const playing = (seen, mood) => seen.filter((p) => p === `${mood}:playing`).length;

async function openLesson(page, lessonId) {
  await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("navigation", { name: "Nội dung khóa học" }).waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
}

const sectionButton = (page, title) =>
  page.getByRole("navigation", { name: "Nội dung khóa học" }).getByRole("button", { name: new RegExp(title) }).first();

(async () => {
  const { email, id, order } = await stage();
  console.log(email);
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await signIn(page, email);

    // --- The frame -------------------------------------------------------
    await openLesson(page, id["Vòng lặp for và range"]);
    const counts = await page.getByText(/\d+\/\d+ bài/).count();
    check("“x/y bài” chỉ viết một lần trên trang", counts === 1, `${counts} chỗ`);

    const open3 = await sectionButton(page, "Rẽ nhánh và vòng lặp").getAttribute("aria-expanded");
    const open1 = await sectionButton(page, "Bắt đầu với Python").getAttribute("aria-expanded");
    const current = await page.locator("nav[aria-label='Nội dung khóa học'] [aria-current='true']").innerText();
    check(
      "mục lục mở đúng chương của bài đang học, các chương khác gập",
      open3 === "true" && open1 === "false" && /Vòng lặp for và range/.test(current) && /Đang học/.test(current),
      `chương 3: ${open3}, chương 1: ${open1}`,
    );

    const prevHref = await page.getByRole("link", { name: /^Bài trước/ }).getAttribute("href");
    const nextHref = await page.getByRole("link", { name: /^Bài tiếp theo/ }).getAttribute("href");
    check(
      "“Bài trước” / “Bài tiếp theo” trỏ đúng hai bài kề",
      prevHref.endsWith(id["Câu lệnh if / elif / else"]) && nextHref.endsWith(id["Vòng lặp while và điều kiện dừng"]),
      `${prevHref} · ${nextHref}`,
    );

    // "Ghi chú tại …" from the questions tab.
    await page.getByRole("tab", { name: "Hỏi đáp" }).click();
    await page.getByRole("button", { name: /^Ghi chú tại/ }).click();
    await page.waitForTimeout(300);
    const notesSelected = await page.getByRole("tab", { name: "Ghi chú" }).getAttribute("aria-selected");
    const focused = await page.evaluate(() => document.activeElement?.id ?? "");
    check("“Ghi chú tại …” mở tab ghi chú và đặt con trỏ vào ô", notesSelected === "true" && focused.startsWith("ghi-chu-"), `tab: ${notesSelected}, focus: #${focused}`);

    const flag = page.getByRole("button", { name: "Đánh dấu để xem lại" });
    const before = await flag.getAttribute("aria-pressed");
    await flag.click();
    await page.waitForFunction(() => document.querySelector("[aria-label='Đánh dấu để xem lại']")?.getAttribute("aria-pressed") === "false", null, { timeout: 15_000 }).catch(() => {});
    const after = await flag.getAttribute("aria-pressed");
    await flag.click();
    await page.waitForFunction(() => document.querySelector("[aria-label='Đánh dấu để xem lại']")?.getAttribute("aria-pressed") === "true", null, { timeout: 15_000 }).catch(() => {});
    check("nút đánh dấu xem lại bật/tắt", before === "true" && after === "false" && (await flag.getAttribute("aria-pressed")) === "true", `${before} → ${after} → true`);

    await page.getByRole("button", { name: "Đánh dấu hoàn thành" }).click();
    await page.getByText("5/18 bài · 28%").waitFor({ timeout: 15_000 });
    const nextClass = await page.getByRole("link", { name: /^Bài tiếp theo/ }).getAttribute("class");
    const doneChip = await page.getByRole("list", { name: "Thông tin bài học" }).getByText("Đã hoàn thành").count();
    check("đánh dấu hoàn thành: đếm 5/18, có nhãn “Đã hoàn thành”, “Bài tiếp theo” thành nút chính", /\bbg-primary\b/.test(nextClass) && doneChip === 1, nextClass.match(/bg-\S+/)?.[0] ?? "");

    // Crossing into the next section opens it.
    await openLesson(page, id["Kiểm tra: ép kiểu"]);
    await page.getByRole("link", { name: /^Bài tiếp theo/ }).click();
    await page.getByRole("heading", { level: 1, name: "Câu lệnh if / elif / else" }).waitFor({ timeout: 30_000 });
    const crossed = await sectionButton(page, "Rẽ nhánh và vòng lặp").getAttribute("aria-expanded");
    const kept = await sectionButton(page, "Biến, kiểu dữ liệu và toán tử").getAttribute("aria-expanded");
    check("sang chương mới bằng “Bài tiếp theo”: chương đó mở ra, chương cũ vẫn mở", crossed === "true" && kept === "true", `mới: ${crossed}, cũ: ${kept}`);

    await openLesson(page, id["Ép kiểu và những cái bẫy quen thuộc"]);
    const readChip = await page.getByRole("list", { name: "Thông tin bài học" }).innerText();
    check("bài đọc ghi thời gian đọc", /Bài đọc · \d+ phút đọc/.test(readChip), readChip.replace(/\s+/g, " "));

    // --- The assistant -----------------------------------------------------
    await openLesson(page, id["Vòng lặp for và range"]);
    await page.getByRole("tab", { name: "Trợ giảng AI" }).click();
    const panel = page.getByRole("region", { name: "Trợ giảng AI" });
    await panel.waitFor();
    const idle = await panel.locator("header [data-mood]").first().getAttribute("data-mood");
    check("trợ giảng chưa hỏi gì: Naomi rest", idle === "rest", idle);

    await record(page, "section[aria-label='Trợ giảng AI'] header");
    await panel.getByLabel("Câu hỏi cho trợ giảng AI").fill(QUESTION);
    await panel.getByRole("button", { name: "Gửi câu hỏi" }).click();
    const stepSeen = await panel.getByText("Tra cứu tài liệu khóa học").first().waitFor({ timeout: 30_000 }).then(() => true, () => false);
    await panel.getByText("Nguồn trong khóa học").first().waitFor({ timeout: 120_000 });
    await page.waitForTimeout(2800);
    const asked = await phases(page);
    const status = await panel.locator("header").innerText();
    check("đang trả lời: hiện các bước tra cứu → đọc → soạn", stepSeen);
    check(
      "Naomi `thinking` rồi `answer`, mỗi dáng phản ứng đúng một lần",
      playing(asked, "thinking") === 1 && playing(asked, "answer") === 1,
      asked.join(" → "),
    );
    check("dòng trạng thái đếm nguồn", /Đã trả lời · \d+ nguồn trong khóa học/.test(status), status.replace(/\s+/g, " "));
    const sourceRow = await panel.getByRole("button", { name: /Vòng lặp for và range/ }).last().innerText();
    check("nguồn trùng bài đang xem ghi “Đang xem”", /Đang xem/.test(sourceRow), sourceRow.replace(/\s+/g, " "));

    await record(page, "section[aria-label='Trợ giảng AI'] header");
    await panel.getByRole("button", { name: "Lịch sử trò chuyện" }).click();
    await panel.getByText(QUESTION).first().click();
    await panel.getByText("Nguồn trong khóa học").first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(1500);
    const reopened = await phases(page);
    const reopenedMood = await panel.locator("header [data-mood]").first().getAttribute("data-mood");
    check("mở lại từ lịch sử: Naomi `answer` đứng yên", reopenedMood === "answer" && !reopened.some((p) => p.endsWith(":playing")), reopened.join(" → ") || "không đổi pha");

    // --- 375 px ---------------------------------------------------------------
    await page.setViewportSize({ width: 375, height: 812 });
    await openLesson(page, id["Vòng lặp for và range"]);
    const spill = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check("375 px không tràn ngang", spill <= 0, `${spill} px`);
    await page.setViewportSize({ width: 1440, height: 900 });

    // --- Finishing the course -----------------------------------------------
    await finishAllButLast(email, order);
    const last = order[order.length - 1];
    await openLesson(page, last.id);
    await record(page, "section[aria-labelledby='hoan-thanh-khoa']");
    await page.getByRole("button", { name: "Đánh dấu hoàn thành" }).click();
    await page.getByRole("heading", { name: "Bạn đã hoàn thành khóa học" }).waitFor({ timeout: 20_000 });
    await page.waitForTimeout(2800);
    const graduated = await phases(page);
    const certLinks = await page.getByRole("link", { name: "Xem chứng chỉ" }).count();
    check("xong khóa: Naomi `graduate` phản ứng đúng một lần", playing(graduated, "graduate") === 1, graduated.join(" → "));
    check("đúng một link “Xem chứng chỉ”", certLinks === 1, `${certLinks} link`);

    await page.reload({ waitUntil: "domcontentloaded" });
    await record(page, "section[aria-labelledby='hoan-thanh-khoa']");
    await page.getByRole("heading", { name: "Bạn đã hoàn thành khóa học" }).waitFor({ timeout: 60_000 });
    await page.waitForTimeout(2000);
    const again = await phases(page);
    const stillMood = await page.locator("section[aria-labelledby='hoan-thanh-khoa'] [data-mood]").first().getAttribute("data-mood");
    check("mở lại khóa đã xong: Naomi `graduate` đứng yên", stillMood === "graduate" && !again.some((p) => p.endsWith(":playing")), again.join(" → ") || "không đổi pha");

    // --- A course not joined ------------------------------------------------
    await page.goto(`${BASE}/hoc/${OTHER_COURSE}`, { waitUntil: "domcontentloaded" });
    const gate = page.getByRole("heading", { level: 1, name: "Bạn chưa đăng ký khóa học này" });
    await gate.waitFor({ timeout: 60_000 });
    const naomi = await page.locator("main [data-mascot]:has([data-mood='empty-courses'])").count();
    check("khóa chưa đăng ký: h1 + Naomi cạnh cuốn sách đóng", naomi === 1, `${naomi} Naomi`);

    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
    await context.close();
  } finally {
    await browser.close();
    purge();
  }
  fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify({ at: new Date().toISOString(), base: BASE, results }, null, 2));
  const failed = results.filter((r) => !r.ok).length;
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
