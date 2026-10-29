/**
 * The golden flow again, with no mouse: sign up, buy, study, solve the code
 * exercise and open the certificate using only the keyboard.
 *
 * Every control is reached the way a keyboard user reaches it -- Tab, one
 * press at a time, from wherever focus was -- and must show where focus is
 * when it gets there. Typing a URL into the address bar is allowed (that is a
 * keyboard action too); clicking is not. axe looks at the states the sweep in
 * e2e/a11y cannot reach: a cart with something in it, a paid order, a graded
 * submission, a certificate.
 */
import { type Locator, type Page, expect, request as playwrightRequest, test } from "@playwright/test";

import { type Finding, axe, report } from "./support/axe";
import {
  PASSWORD,
  purgeSuiteData,
  simulatePaidIpn,
  stagePaidCourse,
  type StagedCourse,
  unique,
} from "./support/stack";

const VNPAY = /^https:\/\/sandbox\.vnpayment\.vn\//;

/** More than any page here needs; a control further than this is unreachable in practice. */
const MAX_TABS = 120;

let course: StagedCourse;

test.beforeAll(async () => {
  const api = await playwrightRequest.newContext();
  course = await stagePaidCourse(api);
  await api.dispose();
});

test.afterAll(() => purgeSuiteData());

async function holdsFocus(target: Locator): Promise<boolean> {
  return target.evaluate((el) => el === document.activeElement || el.contains(document.activeElement));
}

/**
 * Press Tab until `target` has focus, then check that focus can be seen: an
 * outline or a ring (box-shadow) on the focused element. Fails if it takes
 * more than MAX_TABS presses, i.e. the control is not in the tab order.
 */
async function tabTo(
  page: Page,
  target: Locator,
  label: string,
  focusShown?: () => Promise<boolean>,
) {
  await expect(target, `${label} is on the page`).toBeVisible();
  for (let presses = 0; presses < MAX_TABS; presses++) {
    if (await holdsFocus(target)) {
      const visible = focusShown ? await focusShown() : await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || !el.matches(":focus-visible")) return false;
        const style = getComputedStyle(el);
        const outline = style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
        return outline || style.boxShadow !== "none";
      });
      expect(visible, `${label}: focus can be seen`).toBe(true);
      return presses;
    }
    await page.keyboard.press("Tab");
  }
  throw new Error(`${label}: not reached in ${MAX_TABS} presses of Tab`);
}

/** Start the tab order from the top of the page, as a fresh load does. */
async function fromTop(page: Page) {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.locator("body").focus();
}

test("bàn phím: đăng ký → mua → học → nộp code → nhận chứng chỉ", async ({ page }) => {
  const email = `${unique("banphim")}@e2e.devpath.example`;
  const findings: Finding[] = [];
  const presses: Record<string, number> = {};

  await test.step("đăng ký", async () => {
    await page.goto("/dang-ky");
    presses["Họ và tên"] = await tabTo(page, page.getByLabel("Họ và tên"), "Họ và tên");
    await page.keyboard.type("Học Viên Bàn Phím");
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Email")).toBeFocused();
    await page.keyboard.type(email);
    await tabTo(page, page.getByLabel("Mật khẩu"), "Mật khẩu");
    await page.keyboard.type(PASSWORD);
    await page.keyboard.press("Enter");
    await page.waitForURL((url) => url.pathname === "/chao-mung");
  });

  await test.step("thêm vào giỏ, sang giỏ hàng", async () => {
    await page.goto(`/khoa-hoc/${course.slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(course.title);
    // The first Tab of a page lands on the skip link; following it, the next
    // Tab is already past the header.
    await fromTop(page);
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Bỏ qua tới nội dung chính" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(() => document.getElementById("noi-dung")?.contains(document.activeElement)),
      "after the skip link, Tab is inside <main>",
    ).toBe(true);
    const add = page.getByRole("button", { name: "Thêm vào giỏ hàng" });
    presses["Thêm vào giỏ hàng"] = await tabTo(page, add, "Thêm vào giỏ hàng");
    await page.keyboard.press("Enter");
    const toCart = page.getByRole("link", { name: "Xem giỏ hàng" });
    await expect(toCart).toBeVisible();
    // Focus stays where it was: the next Tabs walk on from the add button.
    await tabTo(page, toCart, "Xem giỏ hàng");
    await page.keyboard.press("Enter");
    await page.waitForURL((url) => url.pathname === "/gio-hang");
    await expect(page.getByText(course.title)).toBeVisible();
    await page.waitForLoadState("networkidle");
    findings.push(...(await axe(page, "giỏ hàng có một khóa")));
  });

  const orderCode = await test.step("thanh toán qua VNPay", async () => {
    await page.route(VNPAY, (route) =>
      route.fulfill({ contentType: "text/html; charset=utf-8", body: "<h1>VNPay (giả lập)</h1>" }),
    );
    await fromTop(page);
    const pay = page.getByRole("button", { name: /^Thanh toán .+ qua VNPay$/ });
    presses["Thanh toán"] = await tabTo(page, pay, "Thanh toán qua VNPay");
    await page.keyboard.press("Enter");
    await page.waitForURL(VNPAY);
    return new URL(page.url()).searchParams.get("vnp_TxnRef") as string;
  });

  await test.step("trang kết quả thanh toán", async () => {
    expect(simulatePaidIpn(orderCode)).toMatch(/: paid\b/);
    await page.goto(`/thanh-toan/ket-qua?vnp_TxnRef=${orderCode}`);
    await expect(page.getByText("Thanh toán thành công")).toBeVisible();
    await page.waitForLoadState("networkidle");
    findings.push(...(await axe(page, "thanh toán thành công")));
    const start = page.getByRole("link", { name: `Bắt đầu học ${course.title}` });
    presses["Bắt đầu học"] = await tabTo(page, start, "Bắt đầu học");
    await page.keyboard.press("Enter");
    await page.waitForURL((url) => url.pathname === `/hoc/${course.slug}`);
  });

  await test.step("học bài đọc", async () => {
    await page.goto(`/hoc/${course.slug}?bai=${course.articleLessonId}`);
    await expect(page.getByText("0/2 bài")).toBeVisible();
    const done = page.getByRole("button", { name: "Đánh dấu hoàn thành" });
    presses["Đánh dấu hoàn thành"] = await tabTo(page, done, "Đánh dấu hoàn thành");
    await page.keyboard.press("Space");
    await expect(page.getByText("1/2 bài")).toBeVisible();
  });

  await test.step("nộp bài code", async () => {
    await page.goto(`/hoc/${course.slug}?bai=${course.codeLessonId}`);
    // The whole editor: Monaco takes focus on a hidden textarea or, where the
    // browser has EditContext, on a div -- either way inside this box.
    const editor = page.locator(".monaco-editor").first();
    presses["Trình soạn code"] = await tabTo(page, editor, "Trình soạn code", () =>
      // Monaco draws its own focus (cursor, border) when it has this class.
      editor.evaluate((el) => el.classList.contains("focused")),
    );
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.press("Delete");
    await page.keyboard.insertText("n = int(input())\nprint(2 * n)\n");
    // Inside the editor Tab indents. Ctrl+M is Monaco's own way out: Tab
    // moves focus again until it is pressed a second time.
    await page.keyboard.press("Control+M");
    const submit = page.getByRole("button", { name: "Nộp bài" });
    presses["Nộp bài"] = await tabTo(page, submit, "Nộp bài");
    // What is about to be graded, read off the editor's rendered lines (the
    // Tabs above must have moved focus, not indented anything). If the verdict
    // below is not AC with this code on screen, grading is at fault, not the
    // keyboard. Monaco renders spaces as U+00A0.
    const lines = await editor.locator(".view-line").allInnerTexts();
    expect(lines.map((line) => line.replace(/ /g, " ").trimEnd()).filter(Boolean)).toEqual([
      "n = int(input())",
      "print(2 * n)",
    ]);
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("Chương trình in ra đúng kết quả mong đợi ở mọi test case."),
    ).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("2/2 bài")).toBeVisible();
    await page.waitForLoadState("networkidle");
    findings.push(...(await axe(page, "bài code đã chấm Đúng")));
  });

  await test.step("mở chứng chỉ", async () => {
    const certificate = page.getByRole("link", { name: "Xem chứng chỉ" });
    presses["Xem chứng chỉ"] = await tabTo(page, certificate, "Xem chứng chỉ");
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/cert\/[A-Z0-9]{16}$/);
    await expect(page.getByText("Chứng chỉ hợp lệ")).toBeVisible();
    await page.waitForLoadState("networkidle");
    findings.push(...(await axe(page, "chứng chỉ")));
  });

  // How far each control sits in the tab order, for the evidence file.
  test.info().annotations.push({ type: "tab-presses", description: JSON.stringify(presses) });
  console.log("tab presses:", JSON.stringify(presses));
  expect(findings, report(findings)).toEqual([]);
});
