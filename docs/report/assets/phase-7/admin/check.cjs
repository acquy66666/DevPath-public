// Nhóm màn 10 (Phase 7) — kiểm hành vi khu quản trị trên Chrome thật.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/admin/check.cjs
//
// Same throwaway data as capture.cjs (stage.cjs), removed at the end. Signs in
// as the seeded admin once and logs out. Writes results.json next to this
// file; exits 1 if any check fails.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { API, BASE, ADMIN_EMAIL, ADMIN_PASSWORD, purge, signIn, stage } = require("./stage.cjs");

const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "✔" : "✖"} ${name}${detail ? ` — ${detail}` : ""}`);
}
async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page
    .waitForFunction(() => !document.querySelector("[data-slot=skeleton], [aria-busy=true]"), null, { timeout: 30_000 })
    .catch(() => {});
  await page.waitForTimeout(500);
}
async function open(page, pathname) {
  await page.goto(`${BASE}${pathname}`, { waitUntil: "domcontentloaded" });
  await settle(page);
}
async function axe(page) {
  await page.addScriptTag({ content: AXE });
  return page.evaluate(async () =>
    (await window.axe.run(document, { resultTypes: ["violations"] })).violations
      .filter((v) => ["critical", "serious"].includes(v.impact))
      .map((v) => v.id),
  );
}
async function overflow(page) {
  const widths = {};
  for (const width of [360, 375, 1440]) {
    await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
    await page.waitForTimeout(500);
    widths[width] = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(300);
  return widths;
}
const visibleNaomi = (page) => page.locator("[data-mascot]:visible").count();

const ROUTES = [
  ["Tổng quan", "/quan-tri"],
  ["Duyệt khóa học", "/quan-tri/khoa-hoc"],
  ["Báo cáo vi phạm", "/quan-tri/bao-cao"],
  ["Người dùng", "/quan-tri/nguoi-dung"],
  ["Doanh thu", "/quan-tri/doanh-thu"],
  ["Xếp hạng", "/quan-tri/xep-hang"],
  ["Cấp giảng viên", "/quan-tri/cap-giang-vien"],
  ["Thanh toán giảng viên", "/quan-tri/thanh-toan"],
  ["Lợi nhuận", "/quan-tri/loi-nhuan"],
  ["Danh mục", "/quan-tri/danh-muc"],
  ["Mã giảm giá", "/quan-tri/ma-giam-gia"],
  ["Banner", "/quan-tri/banner"],
];

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN" });
  const page = await context.newPage();
  let staged = false;
  try {
    await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    // --- Empty, before anything is staged: Naomi only here.
    await open(page, "/quan-tri/khoa-hoc");
    const emptyQueue = await page.getByRole("heading", { name: "Không còn khóa học nào chờ duyệt" }).count();
    if (emptyQueue > 0) {
      check("Hàng đợi trống: một Naomi đứng yên", (await visibleNaomi(page)) === 1);
    } else {
      check("Hàng đợi trống: bỏ qua, CSDL dev đang có khóa chờ duyệt", true);
    }

    staged = true;
    const s = await stage(`check-${Date.now().toString(36)}`);

    // --- Side menu and overview
    await open(page, "/quan-tri");
    const nav = page.getByRole("navigation", { name: "Khu vực quản trị" });
    check(
      "Thanh bên: 12 mục trong 4 nhóm, “Tổng quan” là trang hiện tại",
      (await nav.getByRole("link").count()) === 12 &&
        (await nav.getByRole("link", { name: "Tổng quan" }).getAttribute("aria-current")) === "page",
    );
    const queueLink = (await nav.getByRole("link", { name: /^Duyệt khóa học/ }).innerText()).replace(/\s+/g, " ");
    check("Thanh bên: “Duyệt khóa học” đếm ít nhất 2 khóa chờ", /([2-9]|\d\d)/.test(queueLink), queueLink);
    const tops = await page.evaluate(() => {
      const aside = document.querySelector("aside nav");
      const main = document.querySelector("h1");
      return [aside?.getBoundingClientRect().top ?? -1, main?.getBoundingClientRect().top ?? -1];
    });
    check("Thanh bên nằm cạnh nội dung ở 1440 px (không chiếm một hàng riêng)", tops[0] >= 0 && Math.abs(tops[0] - tops[1]) < 40, tops.join(" / "));
    const attention = page.getByRole("region", { name: "Cần xử lý" }).getByRole("link");
    const cards = (await attention.allInnerTexts()).map((t) => t.replace(/\s+/g, " "));
    check(
      "Cần xử lý: 3 thẻ, thẻ đầu gọi tên khóa chờ lâu nhất",
      cards.length === 3 && /Git từ số 0/.test(cards[0]) && /chờ 4 ngày/.test(cards[0]),
      cards[0],
    );
    check("Tổng quan: không có Naomi", (await visibleNaomi(page)) === 0);

    // --- Queue
    await open(page, "/quan-tri/khoa-hoc");
    const pendingChip = page.getByRole("group", { name: "Lọc theo trạng thái" }).getByRole("button", { name: /^Chờ duyệt/ });
    check("Hàng đợi: chip “Chờ duyệt” đang nhấn", (await pendingChip.getAttribute("aria-pressed")) === "true");
    const first = page.getByRole("listitem").filter({ hasText: "Git từ số 0" });
    check("Hàng đợi: khóa chờ 4 ngày ghi “chờ 4 ngày”", /chờ 4 ngày/.test(await first.innerText()));
    await page.getByRole("group", { name: "Lọc theo trạng thái" }).getByRole("button", { name: "Đang bán" }).click();
    await settle(page);
    check("Đổi chip “Đang bán”: khóa chờ duyệt rời danh sách", (await page.getByText("Git từ số 0").count()) === 0);

    // --- Review
    await open(page, `/quan-tri/khoa-hoc/${s.git.id}`);
    check(
      "Trang duyệt: đường dẫn vị trí về hàng đợi + h1 là tên khóa",
      (await page.getByRole("navigation", { name: "Vị trí" }).getByRole("link", { name: "Duyệt khóa học" }).count()) === 1 &&
        (await page.getByRole("heading", { level: 1, name: /Git từ số 0/ }).count()) === 1,
    );
    check(
      "Thanh bên: trang duyệt thuộc mục “Duyệt khóa học”",
      (await nav.getByRole("link", { name: /^Duyệt khóa học/ }).getAttribute("aria-current")) === "page",
    );
    const passGit = await page.getByRole("region", { name: "Kiểm tra nhanh" }).getByText(": đạt").count();
    check("Kiểm tra nhanh (khóa đủ): 4/4 đạt", passGit === 4, `${passGit}`);
    await open(page, `/quan-tri/khoa-hoc/${s.sql.id}`);
    const missSql = await page.getByRole("region", { name: "Kiểm tra nhanh" }).getByText(": chưa có").count();
    check("Kiểm tra nhanh (khóa thiếu): 4/4 chưa có, nút duyệt vẫn bấm được", missSql === 4 && (await page.getByRole("button", { name: "Duyệt và xuất bản" }).isEnabled()), `${missSql}`);

    // --- Reports
    await open(page, "/quan-tri/bao-cao");
    const pendingTab = page.getByRole("group", { name: "Hàng đợi" }).getByRole("button", { name: /^Hàng đợi/ });
    check("Báo cáo: tab “Hàng đợi” đang nhấn", (await pendingTab.getAttribute("aria-pressed")) === "true");
    const select = await page.getByLabel("Loại nội dung").boundingBox();
    check("Ô chọn ở thanh lọc cao ≥ 40 px (không cắt dấu)", select && select.height >= 40, select ? `${select.height}` : "");
    check("Báo cáo: thấy nguyên văn đánh giá bị báo cáo", await page.getByText("ai học khóa này là phí thời gian").isVisible());

    // --- Users: the lock asks first
    await open(page, "/quan-tri/nguoi-dung");
    await page.getByRole("button", { name: "Khóa Đỗ Minh Thư" }).click();
    const dialog = page.getByRole("dialog", { name: "Khóa tài khoản Đỗ Minh Thư?" });
    check("Khóa: hỏi lại bằng hộp thoại", await dialog.isVisible());
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    check(
      "Esc đóng hộp thoại, tài khoản chưa bị khóa",
      (await dialog.count()) === 0 && (await page.getByRole("button", { name: "Khóa Đỗ Minh Thư" }).isVisible()),
    );

    // --- Phone: the folded menu
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(500);
    const fold = page.getByRole("button", { name: /^Quản trị.*Người dùng/ });
    check("375 px: thanh bên gập thành một nút ghi tên trang", (await fold.getAttribute("aria-expanded")) === "false");
    await fold.click();
    const folded = page.getByRole("navigation", { name: "Khu vực quản trị" });
    check("Bấm nút: mở đủ 12 mục", (await folded.getByRole("link").count()) === 12);
    await page.keyboard.press("Escape");
    check("Esc gập lại và trả focus về nút", (await fold.getAttribute("aria-expanded")) === "false" && (await fold.evaluate((el) => el === document.activeElement)));
    const lockCard = page.getByRole("button", { name: "Khóa Đỗ Minh Thư" });
    check("375 px: nút khóa nằm trong màn hình", await lockCard.isVisible() && ((await lockCard.boundingBox())?.x ?? 999) + 40 < 375);
    await page.setViewportSize({ width: 1440, height: 900 });

    // --- Every screen: axe and sideways overflow
    for (const [name, route] of [...ROUTES, ["Trang duyệt", `/quan-tri/khoa-hoc/${s.git.id}`]]) {
      await open(page, route);
      const found = await axe(page);
      check(`${name}: axe 0 lỗi critical/serious`, found.length === 0, found.join(","));
      const widths = await overflow(page);
      check(`${name}: 360/375/1440 px không tràn ngang`, Object.values(widths).every((w) => w <= 0), JSON.stringify(widths));
    }

    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
  } finally {
    await browser.close();
    if (staged) purge();
    fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify(results, null, 2) + "\n");
    const failed = results.filter((r) => !r.ok).length;
    console.log(`${results.length - failed}/${results.length} đạt`);
    if (failed) process.exitCode = 1;
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
