// Nhóm màn 3 (Phase 7) — kiểm hành vi trang nộp bài trên Chrome thật:
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/code-submission/check.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with the grading worker.
// Registers a one-time learner, hands in real code (one trial, three
// submissions, 11 s apart), writes results.json beside this file and removes
// the account with `scripts.purge_e2e`. Exit 1 if a check fails.
//
// What it checks, each against the reaction map (thiết kế UI/UX mục 5):
//   * a trial run gets no Naomi;
//   * a submission: `grading` while judged, then her verdict mood, reacting
//     once (`data-phase` goes to "playing" exactly once per mood);
//   * a result reopened from the history is still, never "playing";
//   * with prefers-reduced-motion she never plays;
//   * the result band is brought into view after "Nộp bài";
//   * full screen keeps the same Monaco (no remount), locks the page behind,
//     leaves on Escape and gives the keyboard back to its button;
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
const PASSWORD = "devpath-nop-bai-1";
const COOLDOWN_MS = 11_000;
const HEAD = "n = int(input())\na = list(map(int, input().split()))\n";
const AC = `${HEAD}print(sum(1 for x in a if x % 2 == 0))\n`;
const WA = `${HEAD}print(sum(1 for x in a if x % 2 == 0 and x > 0))\n`;
const AC_HINT = "Chương trình in ra đúng kết quả mong đợi ở mọi test case.";
const WA_HINT = "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.";

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
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

async function stage() {
  const email = `nopbai-check-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Học Viên Kiểm Tra" },
  });
  const course = await call("GET", `/courses/by-slug/${COURSE}`);
  await call("POST", `/courses/${course.id}/enroll`, { token });
  const curriculum = await call("GET", `/courses/${course.id}/curriculum`, { token });
  const lesson = curriculum.sections.flatMap((s) => s.lessons).find((l) => l.type === "code_exercise");
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, lessonId: lesson.id };
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

// Every change of Naomi's phase, with her mood, in the order it happened.
const RECORD = () => {
  window.__phases = [];
  new MutationObserver((records) => {
    for (const r of records) {
      const el = r.target;
      if (el instanceof Element && el.hasAttribute("data-phase") && el.closest("[aria-label='Kết quả']")) {
        window.__phases.push(`${el.getAttribute("data-mood")}:${el.getAttribute("data-phase")}`);
      }
    }
  }).observe(document, { subtree: true, attributes: true, attributeFilter: ["data-phase"], childList: true });
};

let lastRun = 0;
async function run(page, code, button, hint) {
  const wait = lastRun + COOLDOWN_MS - Date.now();
  if (wait > 0) await page.waitForTimeout(wait);
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  await page.keyboard.insertText(code);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: button, exact: true }).click();
  lastRun = Date.now();
  await page.getByText(hint).first().waitFor({ timeout: 180_000 });
  await page.waitForTimeout(3500); // a reaction is at most 2,4 s
}

const phases = (page) => page.evaluate(() => window.__phases.splice(0));
const mascotsInResult = (page) => page.locator("[aria-label='Kết quả'] [data-mascot]").count();

async function open(browser, email, lessonId, reducedMotion) {
  const context = await browser.newContext({
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    reducedMotion,
    viewport: { width: 1440, height: 900 },
  });
  await context.addInitScript(RECORD);
  const page = await context.newPage();
  await signIn(page, email);
  await page.goto(`${BASE}/hoc/${COURSE}?bai=${lessonId}`, { waitUntil: "domcontentloaded" });
  await page.locator(".monaco-editor").first().waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
  return { context, page };
}

(async () => {
  const { email, lessonId } = await stage();
  console.log(email);
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    // ---------------------------------------------------------- motion allowed
    const { context, page } = await open(browser, email, lessonId, "no-preference");

    await run(page, AC, "Chạy thử", /test mẫu đúng/);
    check("chạy thử: không có Naomi", (await mascotsInResult(page)) === 0);
    await phases(page);

    await run(page, WA, "Nộp bài", WA_HINT);
    let seen = await phases(page);
    check(
      "nộp WA: grading rồi partial, mỗi mood phản ứng đúng một lần",
      seen.filter((p) => p === "grading:playing").length === 1 &&
        seen.filter((p) => p === "partial:playing").length === 1,
      seen.join(" → "),
    );

    await run(page, AC, "Nộp bài", AC_HINT);
    seen = await phases(page);
    check(
      "nộp AC: celebrate phản ứng đúng một lần",
      seen.filter((p) => p === "celebrate:playing").length === 1,
      seen.join(" → "),
    );
    const band = await page.locator("[aria-label='Kết quả']").first().boundingBox();
    check("kết quả được cuộn vào màn hình", band && band.y < 900 && band.y + 120 > 0, band ? `y = ${Math.round(band.y)}` : "");
    await page.waitForTimeout(3000);
    check("không phản ứng lại khi trang vẽ lại", (await phases(page)).length === 0);

    await page.getByRole("button", { name: "Xem lại", exact: true }).first().click();
    await page.getByText(WA_HINT).first().waitFor({ timeout: 60_000 });
    await page.waitForTimeout(3500);
    seen = await phases(page);
    const still = await page.locator("[aria-label='Kết quả'] [data-mood='partial'][data-phase='still']").count();
    check("mở lại từ lịch sử: Naomi đứng yên", still === 1 && !seen.some((p) => p.endsWith(":playing")), seen.join(" → ") || "không đổi pha");

    // Full screen: same editor, page locked, Escape out, focus back.
    await page.evaluate(() => {
      window.__editor = document.querySelector(".monaco-editor");
    });
    await page.getByRole("button", { name: "Toàn màn hình" }).click();
    const region = page.getByRole("region", { name: "Làm bài toàn màn hình" });
    await region.waitFor();
    await page.waitForTimeout(800);
    const inside = await page.evaluate(() => ({
      same: document.querySelector(".monaco-editor") === window.__editor,
      locked: document.body.style.overflow === "hidden",
      editorHeight: document.querySelector(".monaco-editor").getBoundingClientRect().height,
    }));
    check("toàn màn hình: cùng một Monaco, không dựng lại", inside.same);
    check("toàn màn hình: trang phía sau không cuộn", inside.locked);
    check("toàn màn hình: editor cao theo màn hình", inside.editorHeight > 300, `${Math.round(inside.editorHeight)} px`);
    const panes = await page.evaluate(() => {
      const statement = document.querySelector("[aria-label='Làm bài toàn màn hình'] section[aria-labelledby]");
      const editor = document.querySelector(".monaco-editor");
      const a = statement.getBoundingClientRect();
      const b = editor.getBoundingClientRect();
      return { side: a.right <= b.left + 1, statementWidth: Math.round(a.width) };
    });
    check("toàn màn hình: đề bài bên trái editor", panes.side, `${panes.statementWidth} px`);
    await page.locator(".monaco-editor").first().click();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    const after = await page.evaluate(() => ({
      gone: !document.querySelector("[aria-label='Làm bài toàn màn hình']"),
      unlocked: document.body.style.overflow !== "hidden",
      focus: document.activeElement?.getAttribute("aria-label"),
      same: document.querySelector(".monaco-editor") === window.__editor,
    }));
    check("Esc thoát toàn màn hình", after.gone && after.unlocked);
    check("thoát rồi: bàn phím về nút Toàn màn hình", after.focus === "Toàn màn hình", String(after.focus));
    check("thoát rồi: vẫn cùng một Monaco", after.same);

    // 375 px: no sideways spill with a result and the history on screen.
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(1000);
    const spill = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check("375 px: không tràn ngang", spill <= 0, `${spill} px`);
    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
    await context.close();

    // ---------------------------------------------------------- reduced motion
    const reduced = await open(browser, email, lessonId, "reduce");
    await run(reduced.page, AC, "Nộp bài", AC_HINT);
    seen = await phases(reduced.page);
    const mood = await reduced.page.locator("[aria-label='Kết quả'] [data-mood]").first().getAttribute("data-mood");
    check(
      "giảm chuyển động: Naomi hiện celebrate, không phản ứng",
      mood === "celebrate" && !seen.some((p) => p.endsWith(":playing")),
      seen.join(" → ") || "không đổi pha",
    );
    await reduced.page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
    await reduced.context.close();
  } finally {
    await browser.close();
    execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
      stdio: "inherit",
    });
  }
  fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify({ at: new Date().toISOString(), results }, null, 2));
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} đạt`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
