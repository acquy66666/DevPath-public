// Nhóm màn 7 (Phase 7) — kiểm hành vi trên Chrome thật: đăng nhập, đăng ký,
// màn chào mừng, hồ sơ.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/account/check.cjs
//
// Needs the dev stack. Signs up throwaway accounts (@e2e.devpath.example),
// removed at the end by `scripts.purge_e2e`; signs in once as Người mua 08
// (read only). Motion is allowed, so Naomi's reaction can be seen playing.
// Writes results.json next to this file; exits 1 if any check fails.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BUYER = "nguoimua08@sales.devpath.example";
const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const PASSWORD = "devpath-new-1";
const stamp = Date.now().toString(36);
const throwaway = (what) => `kiem-tai-khoan-${what}-${stamp}@e2e.devpath.example`;

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail: String(detail) });
  console.log(`${ok ? "✔" : "✘"} ${name}${detail ? ` — ${detail}` : ""}`);
}

let made = false;
function purge() {
  if (!made) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function formReady(page) {
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
}

async function open(page, pathname) {
  await page.goto(`${BASE}${pathname}`, { waitUntil: "domcontentloaded" });
  await formReady(page);
}

async function signOut(page) {
  await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
  await page.context().clearCookies();
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

/** Naomis a person can see: the auth card draws two and CSS shows one. */
const visibleNaomi = (page) =>
  page.locator("[data-mascot]").evaluateAll((els) => els.filter((el) => el.getClientRects().length > 0).length);

/** The phase of the first visible Naomi, given up to 4 s to start playing. */
async function phase(page) {
  const mascot = page.locator("[data-mascot]:visible").first();
  await mascot.waitFor({ timeout: 30_000 });
  await mascot.locator('[data-phase="playing"]').waitFor({ timeout: 4000 }).catch(() => {});
  return mascot.locator("[data-phase]").first().getAttribute("data-phase");
}

async function axe(page) {
  await page.addScriptTag({ content: AXE });
  return page.evaluate(async () =>
    (await window.axe.run(document, { resultTypes: ["violations"] })).violations
      .filter((v) => ["critical", "serious"].includes(v.impact))
      .map((v) => v.id),
  );
}

async function noOverflow(page, name) {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.waitForTimeout(600);
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const naomi = await visibleNaomi(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
  check(`${name}: 360 px không tràn ngang, một Naomi`, extra <= 0 && naomi === 1, `tràn ${extra}, Naomi ${naomi}`);
}

const focusedLabel = (page) =>
  page.evaluate(() => {
    const el = document.activeElement;
    return el?.labels?.[0]?.textContent ?? el?.getAttribute("aria-label") ?? el?.tagName ?? null;
  });

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    // ---- Sign-in
    await page.goto(`${BASE}/dang-nhap?next=/khoa-hoc/${COURSE}`, { waitUntil: "domcontentloaded" });
    const names = await page.locator("form input").evaluateAll((els) => els.map((e) => e.getAttribute("name")));
    check("Đăng nhập: ô nhập không có `name` (gửi trước hydrate không lộ gì)", names.length === 2 && names.every((n) => n === null), JSON.stringify(names));
    await formReady(page);
    check("Đăng nhập: đúng một form", (await page.locator("form").count()) === 1);
    check("Đăng nhập: getByLabel(\"Mật khẩu\") ra đúng một ô", (await page.getByLabel("Mật khẩu").count()) === 1);
    check("Đăng nhập: 1440 px một Naomi, đứng yên", (await visibleNaomi(page)) === 1 && (await phase(page)) === "still");
    const signUpHref = await page.getByRole("link", { name: "Đăng ký miễn phí" }).getAttribute("href");
    check("Đăng nhập: liên kết sang đăng ký giữ `next`", signUpHref === `/dang-ky?next=%2Fkhoa-hoc%2F${COURSE}`, signUpHref);

    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    check("Đăng nhập: gửi khi trống → con trỏ về ô Email", (await focusedLabel(page)) === "Email", await focusedLabel(page));
    check("Đăng nhập: báo lỗi ở cả hai ô", (await page.locator('[aria-invalid="true"]').count()) === 2);

    const field = page.getByLabel("Mật khẩu");
    await field.fill("bi-mat-123");
    await page.getByRole("button", { name: "Hiện ký tự đã gõ" }).click();
    const shownType = await field.getAttribute("type");
    await page.getByRole("button", { name: "Ẩn ký tự đã gõ" }).click();
    check("Đăng nhập: nút Hiện/Ẩn đổi kiểu ô và tên nút", shownType === "text" && (await field.getAttribute("type")) === "password");

    await page.getByLabel("Email").fill(throwaway("sai"));
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await page.getByRole("alert").first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(300);
    check(
      "Đăng nhập: sai mật khẩu → báo lỗi, ô mật khẩu trống và nhận con trỏ",
      (await page.getByRole("alert").first().textContent()).includes("không đúng") && (await field.inputValue()) === "" && (await focusedLabel(page)) === "Mật khẩu",
    );
    const signInAxe = await axe(page);
    check("Đăng nhập: axe 0 lỗi critical/serious", signInAxe.length === 0, signInAxe.join(","));
    await noOverflow(page, "Đăng nhập");

    // ---- Sign-up
    await open(page, `/dang-ky?next=/khoa-hoc/${COURSE}`);
    check("Đăng ký: nói sẽ quay lại khóa đang xem", (await page.getByText("Xong là bạn quay lại").count()) === 1 && (await page.getByRole("link", { name: "Python cơ bản cho người mới bắt đầu" }).count()) >= 1);
    const signInHref = await page.getByRole("link", { name: "Đăng nhập", exact: true }).getAttribute("href");
    check("Đăng ký: liên kết sang đăng nhập giữ `next`", signInHref === `/dang-nhap?next=%2Fkhoa-hoc%2F${COURSE}`, signInHref);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    check("Đăng ký: gửi khi trống → con trỏ về ô Họ và tên", (await focusedLabel(page)) === "Họ và tên", await focusedLabel(page));

    const rule = page.getByText(/^Tối thiểu 8 ký tự/);
    await page.getByLabel("Mật khẩu").fill("abc");
    const counting = await rule.textContent();
    await page.getByLabel("Mật khẩu").fill("abcdefgh");
    const met = await page.locator("[data-met]").count();
    check("Đăng ký: dòng luật mật khẩu đếm ngược rồi thành dấu tích", counting === "Tối thiểu 8 ký tự · còn 5" && met === 1, counting);

    await page.getByLabel("Họ và tên").fill("Lê Thu Hà");
    await page.getByLabel("Email").fill(BUYER);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    const loginWith = page.getByRole("link", { name: "Đăng nhập với email này" });
    await loginWith.waitFor({ timeout: 30_000 });
    const loginWithHref = await loginWith.getAttribute("href");
    check(
      "Đăng ký: email đã có → liên kết đăng nhập mang email và `next`",
      loginWithHref === `/dang-nhap?next=%2Fkhoa-hoc%2F${COURSE}&email=${encodeURIComponent(BUYER)}`,
      loginWithHref,
    );
    await loginWith.click();
    await formReady(page);
    await page.waitForTimeout(300);
    check("Đăng nhập từ liên kết đó: email điền sẵn, con trỏ ở ô mật khẩu", (await page.getByLabel("Email").inputValue()) === BUYER && (await focusedLabel(page)) === "Mật khẩu");

    await open(page, `/dang-ky?next=/khoa-hoc/${COURSE}`);
    const signUpAxe = await axe(page);
    check("Đăng ký: axe 0 lỗi critical/serious", signUpAxe.length === 0, signUpAxe.join(","));
    await noOverflow(page, "Đăng ký");

    // ---- Sign-up for real → welcome
    made = true;
    await page.getByLabel("Họ và tên").fill("Lê Thu Hà");
    await page.getByLabel("Email").fill(throwaway("moi"));
    await page.getByLabel("Mật khẩu").fill(PASSWORD);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    await page.waitForURL((url) => url.pathname === "/chao-mung", { timeout: 60_000 });
    check("Sau đăng ký: tới /chao-mung, giữ `next`", new URL(page.url()).searchParams.get("next") === `/khoa-hoc/${COURSE}`, page.url());
    await page.getByRole("heading", { level: 1, name: "Chào Hà, mình là Naomi!" }).waitFor({ timeout: 60_000 });
    check("Chào mừng: gọi đúng tên (chữ cuối của họ tên)", true);
    check("Chào mừng: wave phản ứng một lần", (await phase(page)) === "playing");
    const back = page.getByRole("link", { name: "Quay lại “Python cơ bản cho người mới bắt đầu”" });
    check("Chào mừng: nút chính quay lại khóa đang xem", (await back.getAttribute("href")) === `/khoa-hoc/${COURSE}`);
    check("Chào mừng: có 3 bước, chủ đề và khóa miễn phí", (await page.locator("ol > li").count()) === 3 && (await page.getByRole("heading", { name: "Bắt đầu với một chủ đề" }).count()) === 1 && (await page.getByRole("heading", { name: "Khóa miễn phí để bắt đầu" }).count()) === 1);
    check("Chào mừng: mỗi màn một Naomi", (await visibleNaomi(page)) === 1);
    const welcomeAxe = await axe(page);
    check("Chào mừng: axe 0 lỗi critical/serious", welcomeAxe.length === 0, welcomeAxe.join(","));
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { level: 1, name: "Chào Hà, mình là Naomi!" }).waitFor({ timeout: 60_000 });
    check("Chào mừng: tải lại thì đứng yên", (await phase(page)) === "still");
    await noOverflow(page, "Chào mừng");

    // ---- Profile of the new account
    await page.goto(`${BASE}/ho-so`, { waitUntil: "domcontentloaded" });
    const name = page.getByLabel("Họ và tên");
    await name.waitFor({ timeout: 60_000 });
    check("Hồ sơ: nút lưu tắt khi chưa đổi gì", (await page.getByRole("button", { name: "Lưu thay đổi" }).isDisabled()) && (await page.getByText("Chưa có gì thay đổi").count()) === 1);
    await name.fill("Lê Thu Hà B");
    await page.getByRole("button", { name: "Lưu thay đổi" }).click();
    await page.getByText("Đã lưu thay đổi.").waitFor({ timeout: 30_000 });
    check("Hồ sơ: lưu tên → dòng trạng thái báo đã lưu, header đổi tên", (await page.getByRole("button", { name: "Tài khoản: Lê Thu Hà B" }).count()) === 1);
    await page.getByLabel("Mật khẩu hiện tại").fill("khong-dung-123");
    await page.getByLabel("Mật khẩu mới").fill("mat-khau-moi-1");
    await page.getByRole("button", { name: "Đổi mật khẩu" }).click();
    await page.getByRole("alert").first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(300);
    check("Hồ sơ: sai mật khẩu hiện tại → ô đó trống và nhận con trỏ", (await page.getByLabel("Mật khẩu hiện tại").inputValue()) === "" && (await focusedLabel(page)) === "Mật khẩu hiện tại");
    const stats = await page.getByRole("list", { name: "Học tập" }).getByRole("link").evaluateAll((els) => els.map((e) => e.getAttribute("href")));
    check("Hồ sơ: chuỗi ngày + XP dẫn sang trang của chúng", JSON.stringify(stats) === JSON.stringify(["/khoa-hoc-cua-toi", "/bang-xep-hang"]), JSON.stringify(stats));
    const profileAxe = await axe(page);
    check("Hồ sơ: axe 0 lỗi critical/serious", profileAxe.length === 0, profileAxe.join(","));
    await page.setViewportSize({ width: 360, height: 800 });
    await page.waitForTimeout(600);
    const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    await page.setViewportSize({ width: 1440, height: 900 });
    check("Hồ sơ: 360 px không tràn ngang", extra <= 0, `tràn ${extra}`);
    await signOut(page);

    // ---- Visitors
    await page.goto(`${BASE}/ho-so`, { waitUntil: "domcontentloaded" });
    await page.getByText("Đăng nhập để xem hồ sơ").waitFor({ timeout: 60_000 });
    check("Hồ sơ (khách): nút đăng nhập quay lại /ho-so", (await page.getByRole("link", { name: "Đăng nhập", exact: true }).last().getAttribute("href")) === "/dang-nhap?next=%2Fho-so");
    await page.goto(`${BASE}/chao-mung`, { waitUntil: "domcontentloaded" });
    await page.getByRole("link", { name: "Tạo tài khoản miễn phí" }).waitFor({ timeout: 60_000 });
    check("Chào mừng (khách): mời tạo tài khoản, Naomi đứng yên", (await phase(page)) === "still");
    await context.close();

    // ---- Reduced motion: a fresh sign-up stays still.
    const calm = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
    const quiet = await calm.newPage();
    await open(quiet, "/dang-ky");
    await quiet.getByLabel("Họ và tên").fill("Trần An");
    await quiet.getByLabel("Email").fill(throwaway("yen"));
    await quiet.getByLabel("Mật khẩu").fill(PASSWORD);
    await quiet.getByRole("button", { name: "Tạo tài khoản" }).click();
    await quiet.waitForURL((url) => url.pathname === "/chao-mung", { timeout: 60_000 });
    await quiet.getByRole("heading", { level: 1, name: "Chào An, mình là Naomi!" }).waitFor({ timeout: 60_000 });
    const running = await quiet.evaluate(() => document.getAnimations().length);
    check("Giảm chuyển động: sau đăng ký Naomi đứng yên, 0 animation", (await phase(quiet)) === "still" && running === 0, `${running} animation`);
    await calm.close();
  } finally {
    await browser.close();
    purge();
  }
  const failed = results.filter((r) => !r.ok).length;
  fs.writeFileSync(
    path.join(__dirname, "results.json"),
    JSON.stringify({ at: new Date().toISOString(), base: BASE, passed: results.length - failed, failed, results }, null, 2),
  );
  console.log(`\n${results.length - failed}/${results.length}`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error(e);
  try {
    purge();
  } catch {}
  process.exit(1);
});
