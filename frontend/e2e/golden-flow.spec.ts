/**
 * The golden flow: a stranger signs up, buys a course, studies it, solves its
 * code exercise in the sandbox, and walks away with a certificate anyone can
 * verify. Every step a student takes is taken in the browser, through the UI
 * a student sees; only the instructor's and admin's work beforehand, and
 * VNPay's server-to-server callback, are done behind the scenes (see
 * support/stack.ts for why).
 *
 * Screenshots of each step go to the test's output folder, or to
 * E2E_EVIDENCE_DIR when that is set -- which is how the thesis evidence in
 * docs/report/assets/phase-6/e2e/ was taken.
 */
import path from "node:path";

import {
  type ConsoleMessage,
  expect,
  type Page,
  request as playwrightRequest,
  test,
} from "@playwright/test";

import {
  PASSWORD,
  purgeSuiteData,
  simulatePaidIpn,
  stagePaidCourse,
  type StagedCourse,
  unique,
} from "./support/stack";

const VNPAY = /^https:\/\/sandbox\.vnpayment\.vn\//;

/**
 * Cloudflare's analytics beacon. Cloudflare's edge adds it to every page of a
 * zone that has RUM switched on -- free zones do by default -- so it is not
 * the site's, and the policy refusing it is the policy doing its job
 * (infra/nginx/snippets/security-headers.conf).
 */
const EDGE_BEACON = /https:\/\/static\.cloudflareinsights\.com\/beacon/;

/** The fields of a grading event this spec reads (`GradingEvent` in lib/api). */
interface GradingFrame {
  type: "snapshot" | "progress";
  status: string;
  verdict: string | null;
  case: object | null;
}

let course: StagedCourse;

test.beforeAll(async () => {
  const api = await playwrightRequest.newContext();
  course = await stagePaidCourse(api);
  await api.dispose();
});

test.afterAll(() => purgeSuiteData());

async function snap(page: Page, name: string) {
  const dir = process.env.E2E_EVIDENCE_DIR;
  await page.screenshot({
    path: dir ? path.join(dir, `${name}.png`) : test.info().outputPath(`${name}.png`),
    fullPage: true,
  });
}

test("đăng ký → mua → học → nộp code → nhận chứng chỉ", async ({ page }) => {
  const fullName = "Học Viên Luồng Vàng";
  const email = `${unique("hocvien")}@e2e.devpath.example`;

  // Everything the browser refused -- or, under a Report-Only policy, would
  // have refused -- on the way. nginx sends the Content-Security-Policy, so
  // the dev stack has none and this stays empty there; against the production
  // stack it is the check that the policy and the site still agree
  // (docs/report/assets/phase-6/csp-enforce.txt). Chrome prints every
  // violation, a worker's included, to the console.
  const refused: string[] = [];
  const noteRefusal = (where: () => string) => (message: ConsoleMessage) => {
    const text = message.text();
    if (/Content Security Policy/i.test(text) && !EDGE_BEACON.test(text)) {
      refused.push(`${where()}: ${text}`);
    }
  };
  page.on("console", noteRefusal(() => page.url()));
  page.on("worker", (worker) => worker.on("console", noteRefusal(() => worker.url())));

  await test.step("đăng ký tài khoản", async () => {
    const response = await page.goto("/dang-ky");
    if (new URL(page.url()).protocol === "https:") {
      // Behind nginx: the policy is enforced, not merely reported.
      expect(response?.headers()["content-security-policy"]).toContain("default-src 'self'");
    }
    await page.getByLabel("Họ và tên").fill(fullName);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Mật khẩu").fill(PASSWORD);
    await snap(page, "01-dang-ky");
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    // A new account lands on the welcome page, greeted by name.
    await page.waitForURL((url) => url.pathname === "/chao-mung");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("mình là Naomi");
  });

  await test.step("thêm khóa học vào giỏ", async () => {
    await page.goto(`/khoa-hoc/${course.slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(course.title);
    await page.getByRole("button", { name: "Thêm vào giỏ hàng" }).click();
    await expect(page.getByRole("link", { name: "Xem giỏ hàng" })).toBeVisible();
    await snap(page, "02-trang-khoa-hoc");
  });

  const orderCode = await test.step("thanh toán qua VNPay", async () => {
    await page.goto("/gio-hang");
    await expect(page.getByText(course.title)).toBeVisible();
    await snap(page, "03-gio-hang");

    // The bank's page is somebody else's site. Stand in for it: what matters
    // here is that the browser was sent there with a URL we signed.
    await page.route(VNPAY, (route) =>
      route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: "<h1>VNPay sandbox (giả lập trong E2E)</h1>",
      }),
    );
    await page.getByRole("button", { name: "Thanh toán qua VNPay" }).click();
    await page.waitForURL(VNPAY);

    const sent = new URL(page.url());
    expect(sent.searchParams.get("vnp_Amount")).toBe("19900000");
    expect(sent.searchParams.get("vnp_SecureHash")).toBeTruthy();
    const code = sent.searchParams.get("vnp_TxnRef");
    expect(code).toBeTruthy();
    return code as string;
  });

  await test.step("VNPay báo đã trả tiền, trang kết quả xác nhận", async () => {
    // The script's last line about the order: "đơn hàng : paid lúc …".
    expect(simulatePaidIpn(orderCode)).toMatch(/: paid\b/);
    // VNPay sends the browser back with its parameters; the page reads only
    // the order code from them and asks the API what is true.
    await page.goto(`/thanh-toan/ket-qua?vnp_TxnRef=${orderCode}`);
    await expect(page.getByText("Thanh toán thành công")).toBeVisible();
    await snap(page, "04-thanh-toan-thanh-cong");
  });

  await test.step("học bài đọc", async () => {
    await page.goto(`/hoc/${course.slug}?bai=${course.articleLessonId}`);
    await expect(page.getByText("0/2 bài")).toBeVisible();
    await page.getByRole("button", { name: "Đánh dấu hoàn thành" }).click();
    await expect(page.getByText("1/2 bài")).toBeVisible();
    await snap(page, "05-hoc-bai-doc");
  });

  await test.step("nộp bài code, được chấm Đúng trong sandbox", async () => {
    await page.goto(`/hoc/${course.slug}?bai=${course.codeLessonId}`);
    const editor = page.locator(".monaco-editor").first();
    await expect(editor).toBeVisible();
    await editor.click();
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.press("Delete");
    // One insert rather than typed keys: Monaco auto-closes brackets as they
    // are typed, and the answer has to arrive exactly as written.
    await page.keyboard.insertText("n = int(input())\nprint(2 * n)\n");

    // What the grading socket said. The page reaches the same verdict by
    // polling when the socket fails, so without these frames a proxy that
    // refuses the WebSocket upgrade -- or a Redis that publishes nothing --
    // would pass here unnoticed. Whether that ever happens is what decides
    // if polling needs per-case progress of its own
    // (docs/report/assets/phase-6/polling-progress-decision.txt).
    const frames: GradingFrame[] = [];
    page.on("websocket", (socket) => {
      if (!/\/api\/v1\/submissions\/[^/]+\/events$/.test(socket.url())) return;
      socket.on("framereceived", ({ payload }) => {
        frames.push(JSON.parse(String(payload)) as GradingFrame);
      });
    });

    await page.getByRole("button", { name: "Nộp bài" }).click();
    // The overall verdict, not a per-case badge: "Đúng" shows on test 1 while
    // test 2 is still running, and an assertion on that passes too early. A
    // container per test case, so this is the slow step.
    await expect(
      page.getByText("Chương trình in ra đúng kết quả mong đợi ở mọi test case."),
    ).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("100/100").first()).toBeVisible();
    // Per-case progress published by the worker, and the verdict itself, both
    // over the socket: the live channel worked end to end.
    expect(
      frames.some((frame) => frame.type === "progress" && frame.case !== null),
      "per-case progress arrived over the WebSocket",
    ).toBe(true);
    expect(frames.at(-1)).toMatchObject({ status: "done", verdict: "AC" });
    await snap(page, "06-nop-code-dung");
  });

  await test.step("hoàn thành khóa học và mở chứng chỉ", async () => {
    await expect(page.getByText("2/2 bài")).toBeVisible();
    const certificate = page.getByRole("link", { name: "Xem chứng chỉ" });
    await expect(certificate).toBeVisible();
    await snap(page, "07-hoan-thanh-khoa-hoc");

    await certificate.click();
    await page.waitForURL(/\/cert\/[A-Z0-9]{16}$/);
    await expect(page.getByText("Chứng chỉ hợp lệ")).toBeVisible();
    await expect(page.getByText(fullName).first()).toBeVisible();
    await expect(page.getByText(course.title).first()).toBeVisible();
    await snap(page, "08-chung-chi");
  });

  // The last page's late loads report too.
  await page.waitForLoadState("networkidle");
  expect(refused, "Content-Security-Policy violations").toEqual([]);
});
