// Phase 7 — Chuyển động và chất lượng, task 1: micro-interaction.
// Kiểm trên Chrome thật, stack dev, hai lượt: chuyển động bình thường và
// `page.emulateMedia({ reducedMotion: "reduce" })`.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/motion/check.cjs
//
// One throwaway learner (@e2e.devpath.example), removed at the end by
// `scripts.purge_e2e`. Writes results.json next to this file; exits 1 if any
// check fails.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const PASSWORD = "devpath-motion-1";
const EMAIL = `kiem-chuyen-dong-${Date.now().toString(36)}@e2e.devpath.example`;
const SLUG = {
  dsa: "cau-truc-du-lieu-va-giai-thuat-voi-python",
  recursion: "de-quy-va-quy-hoach-dong-0eyofk",
  ts: "typescript-cho-lap-trinh-vien-javascript-r94x6y",
  free: "python-co-ban-cho-nguoi-moi-bat-dau",
};

const results = [];
function check(mode, name, ok, detail = "") {
  results.push({ mode, name, ok: Boolean(ok), detail });
  console.log(`${ok ? "✔" : "✖"} [${mode}] ${name}${detail ? ` — ${detail}` : ""}`);
}

let made = false;
const exec = (...args) => execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", ...args], { encoding: "utf8" });
const psql = (sql) => exec("postgres", "psql", "-U", "devpath", "-Atc", sql).trim();
const course = (slug) => psql(`select id || '|' || title from courses where slug = '${slug}'`).split("|");

let token = null;
async function call(method, pathname, body) {
  const headers = {};
  if (body) headers["content-type"] = "application/json";
  if (token) headers.authorization = `Bearer ${token}`;
  const r = await fetch(`${API}/api/v1${pathname}`, { method, headers, body: body ? JSON.stringify(body) : undefined }).catch(
    (error) => {
      throw new Error(`${method} ${pathname}: ${error.cause?.code || error.message}`);
    },
  );
  if (!r.ok && r.status !== 409) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 || !r.ok ? null : r.json();
}

async function signIn(page) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

async function axe(page) {
  await page.addScriptTag({ content: AXE });
  return page.evaluate(async () =>
    (await window.axe.run(document, { resultTypes: ["violations"] })).violations
      .filter((v) => ["critical", "serious"].includes(v.impact))
      .map((v) => v.id),
  );
}

/** CSS animations still able to move or loop: what reduced motion must leave none of. */
const liveAnimations = (page) =>
  page.evaluate(() =>
    document
      .getAnimations()
      .filter((a) => a instanceof CSSAnimation)
      .map((a) => ({ name: a.animationName, timing: a.effect.getComputedTiming() }))
      .filter(({ timing }) => timing.duration > 1 || timing.iterations === Infinity)
      .map(({ name, timing }) => `${name} ${timing.duration}ms × ${timing.iterations}`),
  );

const style = (locator, pseudo, ...props) =>
  locator.evaluate(
    (el, [pseudo, props]) => {
      const s = getComputedStyle(el, pseudo);
      return Object.fromEntries(props.map((p) => [p, p.startsWith("--") ? s.getPropertyValue(p).trim() : s[p]]));
    },
    [pseudo, props],
  );

/** An offset that does not move: unset, or the registered property's 0. */
const still = (value) => value === "" || value === "0" || value === "0px";
/** `transition-none` sets the property list to none and leaves the duration. */
const noTransition = (s) => s.transitionProperty === "none" || seconds(s.transitionDuration) === 0;
const seconds = (value) => parseFloat(value) * (value.endsWith("ms") ? 0.001 : 1);

const openToast = (page) => page.locator('[data-slot="toast"][data-state="open"]').last();

async function stage(ids) {
  await call("DELETE", "/cart");
  for (const id of [ids.dsa, ids.recursion]) await call("PUT", `/cart/courses/${id}`);
  await call("PUT", `/wishlist/courses/${ids.ts}`);
}

async function run(browser, mode, ids, titles) {
  const reduce = mode === "reduce";
  const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.emulateMedia({ reducedMotion: reduce ? "reduce" : "no-preference" });
  check(mode, "trình duyệt nhận đúng chế độ", (await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)) === reduce);
  await stage(ids);
  await signIn(page);

  // ---- Cart: toast, undo, press.
  await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
  const remove = page.getByRole("button", { name: `Bỏ ${titles.dsa} khỏi giỏ hàng` }).first();
  await remove.waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
  if (reduce) check(mode, "giỏ hàng: không còn hoạt ảnh CSS nào chạy hay lặp", (await liveAnimations(page)).length === 0, (await liveAnimations(page)).join(", "));

  // Press: 1px down while held, nothing with reduced motion. The pointer leaves
  // before it is released, so this is not a click.
  const box = await remove.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(200);
  // Tailwind 4's translate-* writes the `translate` property, not `transform`.
  const pressed = (await style(remove, null, "translate")).translate;
  await page.mouse.move(5, 5);
  await page.mouse.up();
  check(mode, reduce ? "nút: không lún khi nhấn" : "nút: lún 1px khi nhấn", reduce ? pressed === "none" : pressed === "0px 1px", pressed);

  await remove.click();
  const toast = openToast(page);
  await toast.waitFor({ timeout: 15_000 });
  const title = (await toast.locator("[class*=font-semibold]").first().textContent()) ?? "";
  check(mode, "bỏ khỏi giỏ: toast nêu tên khóa", title.includes(titles.dsa), title);
  const t = await style(toast, null, "animationName", "animationDuration", "--tw-enter-translate-x");
  check(
    mode,
    reduce ? "toast vào: chỉ mờ dần, xong ngay" : "toast vào: trượt 1rem trong duration-slow",
    reduce ? seconds(t.animationDuration) <= 0.001 && still(t["--tw-enter-translate-x"]) : t.animationName === "enter" && seconds(t.animationDuration) === 0.32 && !still(t["--tw-enter-translate-x"]),
    `${t.animationName} ${t.animationDuration} x=${t["--tw-enter-translate-x"] || "∅"}`,
  );
  const viewport = await page.locator("ol[tabindex]").last().evaluate((el) => getComputedStyle(el).pointerEvents);
  check(mode, "toast không chắn chuột ngoài thẻ của nó", viewport === "none", viewport);
  check(mode, "toast có trong cây truy cập (Radix: role=status)", (await page.getByRole("status").filter({ hasText: titles.dsa }).count()) > 0);
  const violations = await axe(page);
  check(mode, "axe khi toast đang mở: 0 critical/serious", violations.length === 0, violations.join(", "));

  // Undo, straight away: nothing has to finish first.
  await toast.getByRole("button", { name: "Hoàn tác" }).click();
  await page.getByRole("button", { name: `Bỏ ${titles.dsa} khỏi giỏ hàng` }).first().waitFor({ timeout: 15_000 });
  check(mode, "Hoàn tác: khóa quay lại giỏ", true);
  await page.locator('[data-slot="toast"]').first().waitFor({ state: "detached", timeout: 5000 }).catch(() => {});
  check(mode, "toast đóng xong thì rời DOM", (await page.locator('[data-slot="toast"]').count()) === 0);

  // A phone: the toast sits under the header, clear of the sticky pay bar.
  await page.setViewportSize({ width: 360, height: 760 });
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: `Bỏ ${titles.recursion} khỏi giỏ hàng` }).first().click();
  const small = openToast(page);
  await small.waitFor({ timeout: 15_000 });
  await page.waitForTimeout(500);
  const toastBox = await small.boundingBox();
  const bar = await page.getByRole("button", { name: /^Thanh toán( .+)? qua VNPay$/ }).last().boundingBox();
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const clear = bar && toastBox && (toastBox.y + toastBox.height <= bar.y || toastBox.y >= bar.y + bar.height);
  check(mode, "360 px: toast không đè nút thanh toán, không tràn ngang", clear && extra <= 0, `toast ${Math.round(toastBox.y)}–${Math.round(toastBox.y + toastBox.height)}, nút ${bar ? Math.round(bar.y) : "?"}, tràn ${extra}`);
  if (!reduce) {
    await page.screenshot({ path: path.join(__dirname, "toast-360.png") });
  }
  await small.getByRole("button", { name: "Hoàn tác" }).click();
  await page.getByRole("button", { name: `Bỏ ${titles.recursion} khỏi giỏ hàng` }).first().waitFor({ timeout: 15_000 });
  await page.setViewportSize({ width: 1440, height: 900 });

  // Leaving a toast alone: it closes by itself.
  await page.getByRole("button", { name: `Bỏ ${titles.recursion} khỏi giỏ hàng` }).first().click();
  await openToast(page).waitFor({ timeout: 15_000 });
  if (!reduce) await page.screenshot({ path: path.join(__dirname, "toast-1440.png") });
  await page.mouse.move(5, 5);
  await page.locator('[data-slot="toast"]').first().waitFor({ state: "detached", timeout: 12_000 });
  check(mode, "toast tự đóng sau ~6 s", true);

  // ---- Wishlist: the same toast with its own undo.
  await page.goto(`${BASE}/yeu-thich`, { waitUntil: "domcontentloaded" });
  const unsave = page.getByRole("button", { name: `Bỏ ${titles.ts} khỏi yêu thích` });
  await unsave.waitFor({ timeout: 120_000 });
  await unsave.click();
  const wish = openToast(page);
  await wish.waitFor({ timeout: 15_000 });
  check(mode, "bỏ khỏi yêu thích: toast nêu tên khóa", ((await wish.textContent()) ?? "").includes(titles.ts));
  await wish.getByRole("button", { name: "Hoàn tác" }).click();
  await page.getByRole("button", { name: `Bỏ ${titles.ts} khỏi yêu thích` }).waitFor({ timeout: 15_000 });
  check(mode, "Hoàn tác: khóa quay lại yêu thích", true);

  // ---- Learn page: progress bar and line tabs.
  await page.goto(`${BASE}/hoc/${SLUG.free}`, { waitUntil: "domcontentloaded" });
  const bar2 = page.locator('[data-slot="progress"]').first();
  await bar2.waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
  if (reduce) check(mode, "trang học: không còn hoạt ảnh CSS nào chạy hay lặp", (await liveAnimations(page)).length === 0, (await liveAnimations(page)).join(", "));
  const fill = await style(bar2.locator('[data-slot="progress-indicator"]'), null, "transitionProperty", "transitionDuration");
  check(
    mode,
    reduce ? "thanh tiến độ: nhảy thẳng tới giá trị" : "thanh tiến độ: trượt transform trong duration-progress",
    reduce ? noTransition(fill) : fill.transitionProperty.split(", ").includes("transform") && seconds(fill.transitionDuration) === 0.6,
    `${fill.transitionProperty} ${fill.transitionDuration}`,
  );

  const tabs = page.getByRole("tablist", { name: "Dưới bài học" });
  await tabs.waitFor({ timeout: 60_000 });
  const first = page.locator('[role="tabpanel"][data-state="active"]').last();
  check(mode, "tab: panel đầu không mờ vào lúc tải trang", (await style(first, null, "animationName")).animationName === "none");
  const qa = tabs.getByRole("tab", { name: "Hỏi đáp" });
  await qa.click();
  // The learn page has a second set of tabs (contents | AI tutor): find the
  // panel by the tab that owns it.
  const panel = page.locator(`[id="${await qa.getAttribute("aria-controls")}"]`);
  await panel.waitFor({ timeout: 15_000 });
  const p = await style(panel, null, "animationName", "animationDuration", "--tw-enter-translate-y");
  check(
    mode,
    reduce ? "tab: panel mới chỉ mờ vào, xong ngay" : "tab: panel mới mờ vào và nhích 4px trong duration-base",
    reduce ? seconds(p.animationDuration) <= 0.001 && still(p["--tw-enter-translate-y"]) : p.animationName === "enter" && seconds(p.animationDuration) === 0.22 && !still(p["--tw-enter-translate-y"]),
    `${p.animationName} ${p.animationDuration} y=${p["--tw-enter-translate-y"] || "∅"}`,
  );
  // Tailwind 4's scale-x-* writes the `scale` property. Read once it has grown.
  await page.waitForTimeout(400);
  const on = await style(qa, "::after", "scale", "transitionProperty", "transitionDuration");
  const off = await style(tabs.getByRole("tab", { name: "Ghi chú" }), "::after", "scale");
  check(
    mode,
    reduce ? "tab: vạch dưới hiện ngay" : "tab: vạch dưới giãn ra trong duration-base",
    /^1( 1)?$/.test(on.scale) && /^0( 1)?$/.test(off.scale) && (reduce ? noTransition(on) : seconds(on.transitionDuration) === 0.22),
    `chọn ${on.scale} ${on.transitionProperty} ${on.transitionDuration}, bỏ ${off.scale}`,
  );
  if (!reduce) await page.screenshot({ path: path.join(__dirname, "tabs-line.png"), clip: { x: 0, y: Math.max(0, (await tabs.boundingBox()).y - 40), width: 1440, height: 260 } });

  await context.close();
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    // The database first: a blocking `docker compose exec` between two
    // requests outlasts uvicorn's keep-alive, and fetch then reuses a dead
    // socket (ECONNRESET).
    const [dsa, dsaTitle] = course(SLUG.dsa);
    const [recursion, recursionTitle] = course(SLUG.recursion);
    const [ts, tsTitle] = course(SLUG.ts);
    const [free] = course(SLUG.free);
    made = true;
    await call("POST", "/auth/register", { email: EMAIL, password: PASSWORD, full_name: "Người kiểm chuyển động" });
    token = (await call("POST", "/auth/login", { email: EMAIL, password: PASSWORD })).access_token;
    await call("POST", `/courses/${free}/enroll`);
    const ids = { dsa, recursion, ts };
    const titles = { dsa: dsaTitle, recursion: recursionTitle, ts: tsTitle };
    for (const mode of ["normal", "reduce"]) await run(browser, mode, ids, titles);
  } catch (error) {
    const why = `${error.message || error}${error.cause ? ` (${error.cause.code || error.cause})` : ""}`;
    check("-", "chạy hết kịch bản", false, why.split("\n")[0]);
  } finally {
    await browser.close();
    if (made) exec("backend", "python", "-m", "scripts.purge_e2e");
    fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify(results, null, 2) + "\n");
    const failed = results.filter((r) => !r.ok).length;
    console.log(`\n${results.length - failed}/${results.length} đạt`);
    process.exit(failed ? 1 : 0);
  }
})();
