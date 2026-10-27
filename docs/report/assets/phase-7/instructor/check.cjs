// Nhóm màn 9 (Phase 7) — kiểm hành vi khu giảng viên trên Chrome thật.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/instructor/check.cjs
//
// Same throwaway data as capture.cjs (stage.cjs), removed at the end.
// Writes results.json next to this file; exits 1 if any check fails.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { BASE, PASSWORD, accounts, purge, signIn, stage, stageCourses, ask } = require("./stage.cjs");

const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const { teacher: TEACHER, learner: LEARNER } = accounts(`check-${Date.now().toString(36)}`);

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "✔" : "✖"} ${name}${detail ? ` — ${detail}` : ""}`);
}

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForFunction(() => !document.querySelector("[data-slot=skeleton], [aria-busy=true]"), null, {
    timeout: 30_000,
  }).catch(() => {});
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
async function at360(page, name) {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.waitForTimeout(700);
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
  check(`${name}: 360 px không tràn ngang`, extra <= 0, `tràn ${extra}`);
}
const visibleNaomi = (page) => page.locator("[data-mascot]:visible").count();

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  try {
    const t = await stage(TEACHER);
    const c = await stageCourses(t);
    await ask(LEARNER, c.main.id, c.article.id);

    // Motion allowed: Naomi's greeting must still not move.
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN" });
    const page = await context.newPage();
    await signIn(page, TEACHER, PASSWORD);

    // --- Overview
    await open(page, "/giang-day");
    const nav = page.getByRole("navigation", { name: "Khu giảng viên" });
    check(
      "Thanh điều hướng: “Khóa học” là trang hiện tại",
      (await nav.getByRole("link", { name: "Khóa học", exact: true }).getAttribute("aria-current")) === "page",
    );
    const badge = await nav.getByRole("link", { name: /^Hỏi đáp/ }).innerText();
    check("Thanh điều hướng: “Hỏi đáp” đếm 1 câu chờ trả lời", /1/.test(badge), badge.replace(/\s+/g, " "));
    check("Tổng quan: lời chào gọi tên", await page.getByRole("heading", { level: 1, name: "Chào Hà" }).isVisible());
    const naomi = await visibleNaomi(page);
    await page.waitForTimeout(1500);
    const moving = await page.evaluate(
      () => document.getAnimations().filter((a) => a.effect?.target?.closest?.("[data-mascot]")).length,
    );
    check("Tổng quan: một Naomi, đứng yên", naomi === 1 && moving === 0, `${naomi} Naomi, ${moving} hoạt ảnh`);
    const tasks = page.getByRole("region", { name: "Việc đang chờ" }).getByRole("link");
    const taskTexts = (await tasks.allInnerTexts()).map((s) => s.replace(/\s+/g, " "));
    check(
      "Việc đang chờ: câu hỏi → khóa bị từ chối → 2 bản nháp",
      taskTexts.length === 4 && /câu hỏi/.test(taskTexts[0]) && /bị từ chối/.test(taskTexts[1]) && /bản nháp/.test(taskTexts[3]),
      taskTexts.join(" | "),
    );
    const chips = page.getByRole("group", { name: "Lọc theo trạng thái" }).getByRole("button");
    check(
      "Lọc: chỉ hiện trạng thái có khóa (không có “Chờ duyệt”)",
      (await chips.allInnerTexts()).join("|") === "Tất cả · 4|Đã xuất bản · 1|Bản nháp · 2|Bị từ chối · 1",
      (await chips.allInnerTexts()).join("|"),
    );
    await page.getByRole("button", { name: "Bản nháp · 2" }).click();
    const rows = page.getByRole("region", { name: "Khóa học của bạn" }).getByRole("listitem");
    check(
      "Lọc “Bản nháp”: 2 dòng, nút được nhấn",
      (await rows.count()) === 2 && (await page.getByRole("button", { name: "Bản nháp · 2" }).getAttribute("aria-pressed")) === "true",
      `${await rows.count()} dòng`,
    );
    const overviewAxe = await axe(page);
    check("Tổng quan: axe 0 lỗi critical/serious", overviewAxe.length === 0, overviewAxe.join(","));
    await at360(page, "Tổng quan");

    // --- A rejected course, from its task
    await page.getByRole("button", { name: "Tất cả · 4" }).click();
    await page.getByRole("link", { name: /bị từ chối.*Xem lý do/ }).click();
    await page.waitForURL(/tab=thong-tin/);
    await settle(page);
    check(
      "“Xem lý do” mở thẳng tab Thông tin, có lý do của quản trị viên",
      (await page.getByRole("tab", { name: "Thông tin khóa học" }).getAttribute("aria-selected")) === "true" &&
        (await page.getByText("Chương 2 chưa có bài nào").isVisible()),
    );
    const hint = await page.getByText(/Gợi ý, không bắt buộc/).innerText();
    check("Gợi ý trước khi gửi duyệt: 1/4 (có mô tả ngắn, chương 2 trống, chưa có bài học thử)", /1\/4/.test(hint), hint);
    check("Nút “Gửi duyệt lại” không bị khóa vì gợi ý", await page.getByRole("button", { name: "Gửi duyệt lại" }).isEnabled());
    const infoAxe = await axe(page);
    check("Thông tin khóa học: axe 0 lỗi critical/serious", infoAxe.length === 0, infoAxe.join(","));

    // --- The published course's curriculum
    await open(page, `/giang-day/${c.main.id}`);
    check("Mở không có ?tab: tab Nội dung", (await page.getByRole("tab", { name: "Nội dung" }).getAttribute("aria-selected")) === "true");
    await page.getByRole("button", { name: "Sửa bài học Bài tập: đếm số chẵn", exact: true }).click();
    await settle(page);
    const lessonTitle = page.getByLabel("Tên bài học", { exact: true });
    await lessonTitle.fill("Bài tập: đếm số chẵn (đang sửa dở)");
    await page.getByRole("tab", { name: "Thông tin khóa học" }).click();
    check("Đổi tab: địa chỉ thành ?tab=thong-tin, không tải lại trang", /tab=thong-tin/.test(page.url()));
    await page.getByRole("tab", { name: "Nội dung" }).click();
    check(
      "Quay lại tab Nội dung: bài đang sửa dở còn nguyên",
      (await lessonTitle.inputValue()) === "Bài tập: đếm số chẵn (đang sửa dở)" && !/tab=/.test(page.url()),
    );
    const editorAxe = await axe(page);
    check("Soạn bài tập code: axe 0 lỗi critical/serious", editorAxe.length === 0, editorAxe.join(","));

    const chapter1 = page.locator("li", { has: page.getByRole("heading", { name: "Làm quen với dữ liệu" }) }).first();
    await chapter1.getByRole("button", { name: "Thêm bài học" }).click();
    const kinds = chapter1.getByRole("group", { name: "Loại bài" }).getByRole("radio");
    check("Thêm bài: 4 loại là 4 nút chọn", (await kinds.count()) === 4);
    await chapter1.getByRole("group", { name: "Loại bài" }).locator("label", { hasText: "Trắc nghiệm" }).click();
    check("Bấm nhãn “Trắc nghiệm” chọn đúng loại", await chapter1.getByRole("radio", { name: "Trắc nghiệm" }).isChecked());
    await chapter1.getByLabel("Tên bài học mới").fill("Kiểm tra: đọc tệp");
    await chapter1.getByRole("button", { name: "Thêm bài" }).click();
    await page.getByText("Kiểm tra: đọc tệp").waitFor({ timeout: 15_000 });
    const added = chapter1.locator("li", { hasText: "Kiểm tra: đọc tệp" });
    check("Thêm bài “Trắc nghiệm”: dòng mới mang loại Trắc nghiệm", /Trắc nghiệm/.test(await added.innerText()));
    check(
      "Tóm tắt chương cập nhật theo",
      await chapter1.getByText("3 bài · 1 video · 1 bài đọc · 1 trắc nghiệm").locator("visible=true").first().isVisible(),
    );
    await at360(page, "Soạn khóa");

    await page.getByRole("button", { name: "Sửa bài học Kiểm tra: ép kiểu", exact: true }).click();
    await settle(page);
    check("Quiz: 2 câu AI chờ duyệt có nút Duyệt", (await page.getByRole("button", { name: /^Duyệt câu/ }).count()) === 2);
    check(
      "Quiz: chưa xuất bản được khi còn câu chờ duyệt",
      await page.getByRole("button", { name: "Xuất bản cho học viên" }).isDisabled(),
    );
    const quizAxe = await axe(page);
    check("Soạn quiz: axe 0 lỗi critical/serious", quizAxe.length === 0, quizAxe.join(","));

    // --- Q&A
    await open(page, "/giang-day/hoi-dap");
    check(
      "Hỏi đáp: mở ở tab “Chờ trả lời · 1”",
      (await page.getByRole("tab", { name: "Chờ trả lời · 1" }).getAttribute("aria-selected")) === "true",
    );
    check("Hỏi đáp: thấy câu hỏi của học viên", await page.getByText("UnicodeDecodeError").first().isVisible());
    const qaAxe = await axe(page);
    check("Hỏi đáp: axe 0 lỗi critical/serious", qaAxe.length === 0, qaAxe.join(","));
    await at360(page, "Hỏi đáp");

    // --- New course
    await open(page, "/giang-day/moi");
    check(
      "Tạo khóa: không có nút “Tạo khóa học” trên thanh điều hướng",
      (await nav.getByRole("link", { name: "Tạo khóa học" }).count()) === 0,
    );
    const newAxe = await axe(page);
    check("Tạo khóa: axe 0 lỗi critical/serious", newAxe.length === 0, newAxe.join(","));
    await at360(page, "Tạo khóa");

    for (const [name, route] of [
      ["Thống kê", "/giang-day/thong-ke"],
      ["Cấp bậc", "/giang-day/cap-bac"],
    ]) {
      await open(page, route);
      const current = await nav.getByRole("link", { name, exact: true }).getAttribute("aria-current");
      const found = await axe(page);
      check(`${name}: là trang hiện tại, axe 0 lỗi critical/serious`, current === "page" && found.length === 0, found.join(","));
    }
    await context.close();

    // Reduced motion: nothing animates on the overview.
    const calm = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN", reducedMotion: "reduce" });
    const quiet = await calm.newPage();
    await signIn(quiet, TEACHER, PASSWORD);
    await open(quiet, "/giang-day");
    const running = await quiet.evaluate(() => document.getAnimations().length);
    check("Giảm chuyển động: tổng quan 0 hoạt ảnh", running === 0, `${running}`);
    await calm.close();
  } finally {
    await browser.close();
    purge();
    fs.writeFileSync(path.join(__dirname, "results.json"), JSON.stringify(results, null, 2) + "\n");
    const failed = results.filter((r) => !r.ok).length;
    console.log(`${results.length - failed}/${results.length} đạt`);
    if (failed) process.exitCode = 1;
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
