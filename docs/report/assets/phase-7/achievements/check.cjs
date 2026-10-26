// Nhóm màn 6 (Phase 7) — kiểm hành vi trên Chrome thật, cho phép chuyển động:
// Naomi phản ứng đúng một lần (fire, sad, levelup, graduate), đứng yên khi mở
// lại, giảm chuyển động thì đứng yên; mỗi màn một Naomi; tab bảng xếp hạng có
// panel (axe); "Cách DevPath gợi ý"; sao chép liên kết; 375 px không tràn.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/achievements/check.cjs
//
// Same data as capture.cjs (demo buyers, loaded today). Read only, except one
// throwaway account removed by `scripts.purge_e2e`. Writes results.json next
// to this file and exits 1 if a check fails.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const buyer = (n) => `nguoimua${n}@sales.devpath.example`;

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail: String(detail) });
  console.log(`${ok ? "✔" : "✘"} ${name}${detail ? ` — ${detail}` : ""}`);
}

async function call(method, pathname, { token, body } = {}) {
  const r = await fetch(`${API}/api/v1${pathname}`, {
    method,
    headers: { ...(body ? { "content-type": "application/json" } : {}), ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

async function signIn(page, email, password = "devpath-buyer") {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => {
    const forms = document.querySelectorAll("form");
    return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
  }, null, { timeout: 120_000 });
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill(password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error(`đăng nhập thất bại: ${email}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

async function signOut(page) {
  await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
  await page.context().clearCookies();
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
}

/** The phase of the Naomi inside `scope` a moment after she came on screen. */
async function phase(page, selector) {
  const mascot = page.locator(`${selector} [data-mascot]`).first();
  await mascot.waitFor({ timeout: 30_000 });
  await mascot.scrollIntoViewIfNeeded();
  // A reaction may wait for its drawing to load (the dev server compiles it on
  // first use): give "playing" up to 4 s to show, then read what is there.
  await mascot
    .locator('[data-phase="playing"]')
    .waitFor({ timeout: 4000 })
    .catch(() => {});
  return mascot.locator("[data-phase]").first().getAttribute("data-phase");
}

async function openMyCourses(page) {
  await page.goto(`${BASE}/khoa-hoc-cua-toi`, { waitUntil: "domcontentloaded" });
  await page.locator("[data-streak]").first().waitFor({ timeout: 120_000 });
  await page.waitForTimeout(800);
}

async function openBoard(page) {
  await page.goto(`${BASE}/bang-xep-hang`, { waitUntil: "domcontentloaded" });
  await page.locator('section[aria-label="Vị trí của bạn"]').waitFor({ timeout: 120_000 });
  await page.waitForTimeout(800);
}

const naomiCount = (page) => page.locator("main [data-mascot], [data-mascot]").count();

async function noOverflow(page, name) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(800);
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(`${name}: 375 px không tràn ngang`, extra <= 0, `scrollWidth − innerWidth = ${extra}`);
  await page.setViewportSize({ width: 1440, height: 900 });
}

let throwaway = null;

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", viewport: { width: 1440, height: 900 } });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
    const page = await context.newPage();

    // ---- Người mua 08: streak lit, the board, the certificate.
    await signIn(page, buyer("08"));
    await openMyCourses(page);
    check("08: thẻ chuỗi ở trạng thái lit", (await page.locator("[data-streak]").getAttribute("data-streak")) === "lit");
    check("08: fire phản ứng ở lần đầu thấy hôm nay", (await phase(page, "[data-streak]")) === "playing");
    check("08: mỗi màn một Naomi (Khóa học của tôi)", (await naomiCount(page)) === 1, `${await naomiCount(page)} Naomi`);
    const strip = await page.locator("[data-day]").evaluateAll((els) => els.map((e) => e.getAttribute("data-day")));
    check("08: dải tuần đủ 7 ngày, hôm nay đã tính", strip.length === 7 && strip.includes("done"), strip.join(","));
    check("08: câu đọc cho trình đọc màn hình", await page.getByText(/^Chuỗi \d+ ngày: /).count() === 1);
    await openMyCourses(page);
    check("08: mở lại cùng ngày thì fire đứng yên", (await phase(page, "[data-streak]")) === "still");

    // "Cách DevPath gợi ý"
    const how = page.getByRole("button", { name: "Cách DevPath gợi ý" });
    await how.scrollIntoViewIfNeeded();
    check("Gợi ý: nút đóng lúc đầu", (await how.getAttribute("aria-expanded")) === "false");
    await how.click();
    const panel = page.locator(`#${(await how.getAttribute("aria-controls")).replace(/:/g, "\\:")}`);
    check("Gợi ý: bấm thì mở panel ba nguồn", (await how.getAttribute("aria-expanded")) === "true" && (await panel.getByText("Học viên giống bạn").count()) === 1);
    const tags = await page.locator("[data-reason-tag]").evaluateAll((els) => els.map((e) => e.getAttribute("data-reason-tag")));
    check("Gợi ý: thẻ có nhãn nguồn", tags.length > 0, tags.join(","));
    await noOverflow(page, "Khóa học của tôi");

    // Board: first visit still; a better rank than last seen jumps once.
    await openBoard(page);
    check("BXH: lần đầu xem thì levelup đứng yên", (await phase(page, 'section[aria-label="Vị trí của bạn"]')) === "still");
    check("BXH: không có dòng lên hạng ở lần đầu", (await page.getByText(/^Lên \d+ hạng/).count()) === 0);
    const seen = await page.evaluate(() => Object.keys(localStorage).find((k) => k.startsWith("devpath:rank-seen:") && k.includes(":week:")));
    const rank = Number(await page.evaluate((k) => localStorage.getItem(k), seen));
    check("BXH: nhớ hạng đã xem theo tuần", Number.isInteger(rank) && rank > 0, seen);
    await page.evaluate(([k, r]) => localStorage.setItem(k, String(r + 2)), [seen, rank]);
    await openBoard(page);
    check("BXH: hạng tốt hơn lần trước thì levelup phản ứng", (await phase(page, 'section[aria-label="Vị trí của bạn"]')) === "playing");
    check("BXH: có dòng “Lên 2 hạng từ lần trước bạn xem”", (await page.getByText("Lên 2 hạng từ lần trước bạn xem").count()) === 1);
    await openBoard(page);
    check("BXH: mở lại thì đứng yên, hết dòng lên hạng", (await phase(page, 'section[aria-label="Vị trí của bạn"]')) === "still" && (await page.getByText(/^Lên \d+ hạng/).count()) === 0);
    check("BXH: mỗi màn một Naomi", (await naomiCount(page)) === 1);
    const triggers = await page.getByRole("tab").evaluateAll((els) => els.map((e) => ({ id: e.getAttribute("aria-controls"), exists: !!document.getElementById(e.getAttribute("aria-controls")) })));
    check("BXH: tab nào cũng trỏ tới panel có thật", triggers.length === 3 && triggers.every((t) => t.exists), JSON.stringify(triggers.map((t) => t.exists)));
    await page.addScriptTag({ content: AXE });
    const axe = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.filter((v) => ["critical", "serious"].includes(v.impact)).map((v) => v.id));
    check("BXH: axe 0 lỗi critical/serious", axe.length === 0, axe.join(","));
    for (const tab of ["Tháng này", "Mọi thời gian"]) {
      await page.getByRole("tab", { name: tab }).click();
      await page.locator('section[aria-label="Vị trí của bạn"]').waitFor();
      await page.waitForTimeout(600);
    }
    check("BXH: tab Mọi thời gian có bục 3 hạng", (await page.locator('section[aria-label^="Ba hạng đầu"]').count()) === 1);
    await noOverflow(page, "Bảng xếp hạng");

    const certificate = await page.evaluate(async (api) => {
      const r = await fetch(`${api}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
      const { access_token: t } = await r.json();
      const e = await (await fetch(`${api}/api/v1/enrollments/me`, { headers: { authorization: `Bearer ${t}` } })).json();
      return e.items.find((i) => i.certificate_code)?.certificate_code;
    }, API);
    await signOut(page);

    // ---- Certificate: still for a visitor, graduate once for the tab that earned it.
    await page.goto(`${BASE}/cert/${certificate}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Chứng nhận hoàn thành" }).waitFor({ timeout: 120_000 });
    check("Chứng chỉ: người xem thường thấy Naomi đứng yên", (await phase(page, 'section[aria-label="Chia sẻ chứng chỉ"]')) === "still");
    check("Chứng chỉ: mỗi màn một Naomi", (await naomiCount(page)) === 1);
    await page.evaluate((code) => sessionStorage.setItem(`devpath:cert-earned:${code}`, "1"), certificate);
    await page.reload({ waitUntil: "domcontentloaded" });
    check("Chứng chỉ: vừa nhận trong tab này thì graduate phản ứng", (await phase(page, 'section[aria-label="Chia sẻ chứng chỉ"]')) === "playing");
    check("Chứng chỉ: dấu được dùng một lần", (await page.evaluate((code) => sessionStorage.getItem(`devpath:cert-earned:${code}`), certificate)) === null);
    await page.reload({ waitUntil: "domcontentloaded" });
    check("Chứng chỉ: tải lại thì đứng yên", (await phase(page, 'section[aria-label="Chia sẻ chứng chỉ"]')) === "still");
    check("Chứng chỉ: PDF là nút chính duy nhất", (await page.getByRole("link", { name: "Tải chứng chỉ PDF" }).count()) === 1);
    await page.getByRole("button", { name: "Sao chép liên kết" }).click();
    await page.getByRole("button", { name: "Đã sao chép" }).waitFor({ timeout: 5000 });
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    check("Chứng chỉ: sao chép đúng địa chỉ trang", clip === `${BASE}/cert/${certificate}`, clip);
    await noOverflow(page, "Chứng chỉ");

    // ---- Người mua 38: a streak just broken.
    await signIn(page, buyer("38"));
    await openMyCourses(page);
    check("38: thẻ chuỗi ở trạng thái lost", (await page.locator("[data-streak]").getAttribute("data-streak")) === "lost");
    check("38: sad phản ứng ở lần đầu", (await phase(page, "[data-streak]")) === "playing");
    await openMyCourses(page);
    check("38: mở lại thì sad đứng yên", (await phase(page, "[data-streak]")) === "still");
    await signOut(page);

    // ---- Người mua 01: on a streak, nothing done today.
    await signIn(page, buyer("01"));
    await openMyCourses(page);
    check("01: thẻ chuỗi ở trạng thái pending", (await page.locator("[data-streak]").getAttribute("data-streak")) === "pending");
    check("01: chuỗi chờ hôm nay thì fire đứng yên", (await phase(page, "[data-streak]")) === "still");
    check("01: hôm nay là ô mở", (await page.locator('[data-day="open"]').count()) === 1);
    await signOut(page);

    // ---- A new account: no streak, the course list's Naomi only.
    throwaway = `thanh-tich-check-${Date.now().toString(36)}@e2e.devpath.example`;
    await call("POST", "/auth/register", { body: { email: throwaway, password: "devpath-new-1", full_name: "Trần Minh Anh" } });
    await signIn(page, throwaway, "devpath-new-1");
    await openMyCourses(page);
    check("Tài khoản mới: thẻ chuỗi ở trạng thái none, không Naomi", (await page.locator("[data-streak] [data-mascot]").count()) === 0 && (await page.locator("[data-streak]").getAttribute("data-streak")) === "none");
    await page.getByText("Chưa có khóa học nào").waitFor({ timeout: 30_000 });
    check("Tài khoản mới: một Naomi (trạng thái rỗng của danh sách)", (await naomiCount(page)) === 1);
    await signOut(page);
    await context.close();

    // ---- Reduced motion: the first look at a lit streak stays still.
    const calm = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
    const quiet = await calm.newPage();
    await signIn(quiet, buyer("08"));
    await openMyCourses(quiet);
    const playing = await quiet.evaluate(() => document.getAnimations().length);
    check("Giảm chuyển động: Naomi đứng yên, 0 animation", (await phase(quiet, "[data-streak]")) === "still" && playing === 0, `${playing} animation`);
    await signOut(quiet);
    await calm.close();
  } finally {
    await browser.close();
    if (throwaway) execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], { stdio: "inherit" });
  }
  const failed = results.filter((r) => !r.ok).length;
  fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify({ at: new Date().toISOString(), base: BASE, passed: results.length - failed, failed, results }, null, 2));
  console.log(`\n${results.length - failed}/${results.length}`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error(e);
  if (throwaway) {
    try { execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], { stdio: "inherit" }); } catch {}
  }
  process.exit(1);
});
