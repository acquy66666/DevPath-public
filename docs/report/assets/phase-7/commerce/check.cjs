// Nhóm màn 8 (Phase 7) — kiểm hành vi giỏ hàng, yêu thích, kết quả thanh toán
// trên Chrome thật, stack dev, cho phép chuyển động.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/commerce/check.cjs
//
// One throwaway learner (@e2e.devpath.example) with its orders, removed at the
// end by `scripts.purge_e2e`. No coupon is spent (applied, then taken off).
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
const PASSWORD = "devpath-shop-1";
const EMAIL = `kiem-mua-sam-${Date.now().toString(36)}@e2e.devpath.example`;
const VNPAY = /sandbox\.vnpayment\.vn/;
const SLUG = {
  dsa: "cau-truc-du-lieu-va-giai-thuat-voi-python",
  recursion: "de-quy-va-quy-hoach-dong-0eyofk",
  oop: "lap-trinh-huong-doi-tuong-voi-python-a13mtm",
  ts: "typescript-cho-lap-trinh-vien-javascript-r94x6y",
  docker: "docker-cho-lap-trinh-vien-backend-e7b1d0",
};

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "✔" : "✖"} ${name}${detail ? ` — ${detail}` : ""}`);
}

let made = false;
const exec = (...args) => execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", ...args], { encoding: "utf8" });
const psql = (sql) => exec("postgres", "psql", "-U", "devpath", "-Atc", sql).trim();
const ipn = (code, fail = false) =>
  exec("backend", "python", "-m", "scripts.simulate_vnpay_ipn", code, ...(fail ? ["--fail"] : []));
function purge() {
  if (made) exec("backend", "python", "-m", "scripts.purge_e2e");
}
const courseId = (slug) => psql(`select id from courses where slug = '${slug}'`);

let token = null;
async function call(method, pathname, body) {
  const headers = {};
  if (body) headers["content-type"] = "application/json";
  if (token) headers.authorization = `Bearer ${token}`;
  const r = await fetch(`${API}/api/v1${pathname}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
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

const visibleNaomi = (page) =>
  page.locator("[data-mascot]").evaluateAll((els) => els.filter((el) => el.getClientRects().length > 0).length);

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

async function at360(page, name, naomis) {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.waitForTimeout(700);
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const naomi = await visibleNaomi(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
  check(`${name}: 360 px không tràn ngang, ${naomis} Naomi`, extra <= 0 && naomi === naomis, `tràn ${extra}, Naomi ${naomi}`);
}

async function openCart(page) {
  await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
  await page.getByText(/khóa học|Giỏ hàng đang trống/).first().waitFor({ timeout: 120_000 });
  await page.waitForLoadState("networkidle").catch(() => {});
}

async function checkout(page) {
  await page.route(VNPAY, (route) => route.fulfill({ contentType: "text/html; charset=utf-8", body: "<h1>VNPay</h1>" }));
  await page.getByRole("button", { name: /^Thanh toán .+ qua VNPay$/ }).click();
  await page.waitForURL(VNPAY, { timeout: 60_000 });
  const sent = new URL(page.url());
  await page.unroute(VNPAY);
  return sent;
}

async function openResult(page, code, title) {
  await page.goto(`${BASE}/thanh-toan/ket-qua?vnp_TxnRef=${code}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: title }).waitFor({ timeout: 120_000 });
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    // Guest.
    await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
    await page.getByText("Đăng nhập để xem giỏ hàng").waitFor({ timeout: 120_000 });
    const login = page.getByRole("link", { name: "Đăng nhập", exact: true }).last();
    check("Khách: nút đăng nhập quay lại giỏ", (await login.getAttribute("href")) === "/dang-nhap?next=/gio-hang");

    // The learner.
    made = true;
    await call("POST", "/auth/register", { email: EMAIL, password: PASSWORD, full_name: "Người kiểm thử" });
    token = (await call("POST", "/auth/login", { email: EMAIL, password: PASSWORD })).access_token;
    for (const key of ["dsa", "recursion", "oop"]) await call("PUT", `/cart/courses/${courseId(SLUG[key])}`);
    for (const key of ["ts", "docker"]) await call("PUT", `/wishlist/courses/${courseId(SLUG[key])}`);
    psql(`insert into enrollments (user_id, course_id, source) select u.id, c.id, 'purchase' from users u, courses c where u.email = '${EMAIL}' and c.slug = '${SLUG.oop}'`);
    await signIn(page);
    await openCart(page);

    check("Giỏ: dòng tóm tắt đếm khóa đã có", await page.getByText("3 khóa học · 1 khóa bạn đã có không bị tính tiền").isVisible());
    check("Giỏ: khóa đã có có nhãn và lối vào học", (await page.getByText("Bạn đã có khóa này").count()) === 1 && (await page.getByRole("link", { name: "Vào học" }).getAttribute("href")) === `/hoc/${SLUG.oop}`);
    const payName = await page.getByRole("button", { name: /^Thanh toán .+ qua VNPay$/ }).textContent();
    check("Giỏ: nút thanh toán ghi số tiền (898.000 ₫, không tính khóa đã có)", /898\.000/.test(payName ?? ""), payName ?? "");
    check("Giỏ: gợi ý từ yêu thích có 2 khóa", (await page.getByRole("button", { name: /^Thêm .+ vào giỏ$/ }).count()) === 2);

    // Coupon: refused, then applied, then removed.
    await page.getByLabel("Mã giảm giá").fill("HETHAN");
    await page.getByRole("button", { name: "Áp dụng" }).click();
    const refusal = page.getByRole("alert").filter({ hasText: "hết hạn" });
    await refusal.waitFor({ timeout: 30_000 });
    const input = page.getByLabel("Mã giảm giá");
    check(
      "Mã hết hạn: lỗi ngay dưới ô, ô aria-invalid và trỏ tới lỗi, giữ chữ đã gõ",
      (await input.getAttribute("aria-invalid")) === "true" &&
        (await input.getAttribute("aria-describedby")) === (await refusal.getAttribute("id")) &&
        (await input.inputValue()) === "HETHAN",
    );
    await input.fill("CHAOMUNG50");
    await page.getByRole("button", { name: "Áp dụng" }).click();
    await page.getByRole("button", { name: "Bỏ mã CHAOMUNG50" }).waitFor({ timeout: 30_000 });
    check("Mã CHAOMUNG50: tổng 449.000 ₫, nút đổi theo", (await page.getByTestId("cart-total").textContent()).includes("449.000") && /449\.000/.test(await page.getByRole("button", { name: /^Thanh toán .+ qua VNPay$/ }).textContent()));
    check("Mã đã áp: dòng mô tả có hạn dùng", await page.getByText(/Giảm 50% · hết hạn \d{2}\/\d{2}\/\d{4}/).isVisible());
    const cartAxe = await axe(page);
    check("Giỏ: axe 0 lỗi critical/serious", cartAxe.length === 0, cartAxe.join(","));
    await at360(page, "Giỏ", 0);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(600);
    const bar = page.getByRole("button", { name: "Thanh toán qua VNPay" });
    const box = await bar.boundingBox();
    check("Điện thoại: nút thanh toán dính đáy màn hình, chỉ một nút hiện", box && box.y + box.height <= 812 && box.y > 700 && (await page.getByRole("button", { name: /qua VNPay/ }).count()) === 1, JSON.stringify(box));
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("button", { name: "Bỏ mã CHAOMUNG50" }).click();

    // "Để dành sau": out of the cart, into the wishlist.
    await page.getByRole("button", { name: "Để dành Đệ quy và quy hoạch động vào yêu thích" }).click();
    await page.getByText("2 khóa học · 1 khóa bạn đã có không bị tính tiền").waitFor({ timeout: 30_000 });
    const saved = await call("GET", "/wishlist?page=1");
    check("Để dành sau: rời giỏ, vào yêu thích", saved.items.some((item) => item.course.slug === SLUG.recursion));

    // Add from the wishlist row (newest saved first: the course just saved, then Docker).
    await page.getByRole("button", { name: /^Thêm Docker .+ vào giỏ$/ }).click();
    await page.getByText("3 khóa học · 1 khóa bạn đã có không bị tính tiền").waitFor({ timeout: 30_000 });
    check("Thêm từ gợi ý yêu thích: vào giỏ", true);

    // Wishlist page.
    await page.goto(`${BASE}/yeu-thich`, { waitUntil: "domcontentloaded" });
    await page.getByText(/khóa học bạn để dành/).waitFor({ timeout: 120_000 });
    await page.waitForLoadState("networkidle").catch(() => {});
    check("Yêu thích: khóa đã ở trong giỏ dẫn tới giỏ", (await page.getByRole("link", { name: /: đã ở trong giỏ$/ }).count()) === 1);
    const wishAxe = await axe(page);
    check("Yêu thích: axe 0 lỗi critical/serious", wishAxe.length === 0, wishAxe.join(","));
    await at360(page, "Yêu thích", 0);
    await page.getByRole("button", { name: "Bỏ TypeScript cho lập trình viên JavaScript khỏi yêu thích" }).click();
    await page.getByRole("button", { name: "Bỏ TypeScript cho lập trình viên JavaScript khỏi yêu thích" }).waitFor({ state: "detached", timeout: 30_000 });
    check("Yêu thích: nút tim bỏ lưu", true);

    // Pay: paid.
    await openCart(page);
    const sent = await checkout(page);
    check("Thanh toán: sang VNPay với URL đã ký, đúng số tiền", sent.searchParams.get("vnp_Amount") === "89800000" && Boolean(sent.searchParams.get("vnp_SecureHash")), sent.searchParams.get("vnp_Amount"));
    const paid = sent.searchParams.get("vnp_TxnRef");
    ipn(paid);
    await openResult(page, paid, "Thanh toán thành công");
    check("Thành công: Naomi paid phản ứng", (await phase(page)) === "playing");
    check("Thành công: một Naomi", (await visibleNaomi(page)) === 1);
    check("Thành công: mỗi khóa vừa mua có nút Bắt đầu học", (await page.getByRole("link", { name: /^Bắt đầu học / }).count()) === 2);
    const resultAxe = await axe(page);
    check("Thành công: axe 0 lỗi critical/serious", resultAxe.length === 0, resultAxe.join(","));
    await at360(page, "Thành công", 1);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Thanh toán thành công" }).waitFor({ timeout: 120_000 });
    check("Thành công: tải lại thì Naomi đứng yên", (await phase(page)) === "still");

    // Owned courses leave the cart's wishlist row and change the wishlist button.
    await call("PUT", `/wishlist/courses/${courseId(SLUG.dsa)}`);
    await openCart(page);
    await page.waitForTimeout(1500);
    check("Giỏ: khóa vừa mua không được mời thêm vào giỏ", (await page.getByRole("button", { name: /^Thêm Cấu trúc dữ liệu .+ vào giỏ$/ }).count()) === 0);
    await page.goto(`${BASE}/yeu-thich`, { waitUntil: "domcontentloaded" });
    const owned = page.getByRole("link", { name: /^Đã có · Vào học Cấu trúc dữ liệu/ });
    await owned.waitFor({ timeout: 60_000 });
    check("Yêu thích: khóa đã mua thành “Đã có · Vào học”", (await owned.getAttribute("href")) === `/hoc/${SLUG.dsa}`);

    // Failed.
    await call("DELETE", `/cart/courses/${courseId(SLUG.oop)}`);
    await call("PUT", `/cart/courses/${courseId(SLUG.ts)}`);
    await openCart(page);
    const failed = (await checkout(page)).searchParams.get("vnp_TxnRef");
    ipn(failed, true);
    await openResult(page, failed, "Thanh toán không thành công");
    check("Thất bại: Naomi oops phản ứng", (await phase(page)) === "playing");
    check("Thất bại: nói lý do bằng chữ và giỏ còn nguyên", (await page.getByText("Bạn đã hủy giao dịch trên trang của VNPay.").isVisible()) && (await page.getByText(/giỏ hàng của bạn vẫn còn nguyên/).isVisible()));
    check("Thất bại: nút chính quay lại giỏ", (await page.getByRole("link", { name: "Quay lại giỏ hàng" }).getAttribute("href")) === "/gio-hang");
    const failAxe = await axe(page);
    check("Thất bại: axe 0 lỗi critical/serious", failAxe.length === 0, failAxe.join(","));

    // Pending: no Naomi, polls, then turns paid by itself.
    await openCart(page);
    const pending = (await checkout(page)).searchParams.get("vnp_TxnRef");
    await openResult(page, pending, "Đang chờ ngân hàng xác nhận");
    check("Đang chờ: không có Naomi", (await visibleNaomi(page)) === 0);
    ipn(pending);
    await page.getByRole("heading", { name: "Thanh toán thành công" }).waitFor({ timeout: 30_000 });
    check("Đang chờ → tự đổi sang thành công khi IPN tới, Naomi phản ứng", (await phase(page)) === "playing");
    await context.close();

    // Reduced motion.
    const calm = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh", reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
    const quiet = await calm.newPage();
    await signIn(quiet);
    await quiet.evaluate(() => localStorage.clear());
    await openResult(quiet, failed, "Thanh toán không thành công");
    await quiet.waitForTimeout(1500);
    const running = await quiet.evaluate(() => document.getAnimations().length);
    check("Giảm chuyển động: Naomi đứng yên, 0 animation", (await phase(quiet)) === "still" && running === 0, `${running} animation`);
    await calm.close();
  } finally {
    await browser.close();
    purge();
  }
  const failedCount = results.filter((r) => !r.ok).length;
  fs.writeFileSync(
    path.join(__dirname, "results.json"),
    JSON.stringify({ at: new Date().toISOString(), base: BASE, passed: results.length - failedCount, failed: failedCount, results }, null, 2),
  );
  console.log(`\n${results.length - failedCount}/${results.length}`);
  process.exit(failedCount ? 1 : 0);
})().catch((e) => {
  console.error(e);
  try {
    purge();
  } catch {}
  process.exit(1);
});
