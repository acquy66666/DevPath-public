// Nhóm màn 10 (Phase 7) — khu quản trị: tổng quan, duyệt khóa học, báo cáo
// vi phạm, người dùng, danh mục / mã giảm giá / banner, năm trang tài chính.
// Ảnh trước/sau, 1440 + 375 px.
//
//   PHASE=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/admin/capture.cjs
//   PHASE=after  NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/admin/capture.cjs
//
// Needs the dev stack (infra/docker-compose.yml). Signs in as the seeded admin
// through the form (one of the 10 sign-ins per 15 minutes the email allows)
// and logs that session out at the end. The queue and the reports are shot
// empty first, then stage.cjs writes the throwaway content, which
// `scripts.purge_e2e` removes at the end.
//
// REPO=<checkout> lets a copy of this script outside the repo write into it.
// ONLY=<regex> limits the shots by name.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { API, BASE, REPO, ADMIN_EMAIL, ADMIN_PASSWORD, purge, signIn, stage } = require("./stage.cjs");

const PHASE = process.env.PHASE;
if (!["before", "after"].includes(PHASE)) {
  console.error("PHASE=before|after");
  process.exit(2);
}
const OUT = path.join(REPO, "docs/report/assets/phase-7/admin", PHASE);
fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const STAMP = `${PHASE}-${Date.now().toString(36)}`;

const taken = [];
async function shoot(page, name, { width = 1440 } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  if (page.viewportSize().width !== width) {
    await page.setViewportSize({ width, height: width < 768 ? 812 : 900 });
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled", fullPage: true });
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
  await page
    .waitForFunction(() => !document.querySelector("[data-slot=skeleton], [aria-busy=true]"), null, { timeout: 30_000 })
    .catch(() => {});
  await page.waitForTimeout(600);
}
async function open(page, pathname) {
  await page.goto(`${BASE}${pathname}`, { waitUntil: "domcontentloaded" });
  await settle(page);
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN", reducedMotion: "reduce" });
  const page = await context.newPage();
  let staged = false;
  try {
    console.log(`PHASE=${PHASE}`);
    await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    await open(page, "/quan-tri/khoa-hoc");
    await shoot(page, "1-hang-doi-trong-1440");
    await open(page, "/quan-tri/bao-cao");
    await shoot(page, "2-bao-cao-trong-1440");

    staged = true;
    const s = await stage(STAMP);

    await open(page, "/quan-tri");
    await both(page, "3-tong-quan");
    if (PHASE === "after") {
      await page.setViewportSize({ width: 375, height: 812 });
      await page.waitForTimeout(800);
      await page.getByRole("button", { name: /^Quản trị/, expanded: false }).click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(OUT, "3-menu-mo-375.png"), animations: "disabled" });
      taken.push("3-menu-mo-375");
      console.log("  3-menu-mo-375");
      await page.setViewportSize({ width: 1440, height: 900 });
    }

    await open(page, "/quan-tri/khoa-hoc");
    await both(page, "4-hang-doi");

    await open(page, `/quan-tri/khoa-hoc/${s.git.id}`);
    await both(page, "5-trang-duyet");
    await page.getByRole("button", { name: "Từ chối…" }).click();
    await page.getByLabel("Lý do từ chối").fill("Bài “Commit đầu tiên” chưa có video. Tải video lên rồi gửi duyệt lại nhé.");
    await shoot(page, "6-tu-choi-1440");

    await open(page, `/quan-tri/khoa-hoc/${s.sql.id}`);
    await shoot(page, "7-trang-duyet-thieu-1440");

    await open(page, "/quan-tri/bao-cao");
    await both(page, "8-bao-cao");

    await open(page, "/quan-tri/nguoi-dung");
    await both(page, "9-nguoi-dung");
    if (PHASE === "after") {
      await page.getByRole("button", { name: "Khóa Đỗ Minh Thư" }).click();
      await page.getByRole("dialog").waitFor();
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(OUT, "10-hop-thoai-khoa-1440.png"), animations: "disabled" });
      taken.push("10-hop-thoai-khoa-1440");
      console.log("  10-hop-thoai-khoa-1440");
      await page.keyboard.press("Escape");
    }

    for (const [name, route, phone] of [
      ["11-danh-muc", "/quan-tri/danh-muc", false],
      ["12-ma-giam-gia", "/quan-tri/ma-giam-gia", true],
      ["13-banner", "/quan-tri/banner", false],
      ["14-doanh-thu", "/quan-tri/doanh-thu", false],
      ["15-xep-hang", "/quan-tri/xep-hang", false],
      ["16-cap-giang-vien", "/quan-tri/cap-giang-vien", false],
      ["17-thanh-toan", "/quan-tri/thanh-toan", false],
      ["18-loi-nhuan", "/quan-tri/loi-nhuan", false],
    ]) {
      await open(page, route);
      if (phone) await both(page, name);
      else await shoot(page, `${name}-1440`);
    }

    await page.evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API);
    console.log(`${taken.length} ảnh → ${path.relative(REPO, OUT)}`);
  } finally {
    await browser.close();
    if (staged) purge();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
