// A 100 % code, end to end through the real UI on the dev stack.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/zero-total-order/ui-drill.cjs
//
// A throwaway @e2e student puts the platform's paid course in the cart, types
// a 100 % code made for the drill (coupon.py), and presses the button. The
// order must come back settled -- no payment URL asked for, no request to
// VNPay -- and the course must be the student's. Everything is removed
// afterwards: the session, the account (`purge_e2e`), the code.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API_URL || "http://localhost:8000";
const REPO = path.resolve(__dirname, "../../../../..");
const HERE = __dirname;
const COMPOSE = ["compose", "-f", path.join(REPO, "infra", "docker-compose.yml")];

function backend(args, input) {
  return execFileSync("docker", [...COMPOSE, "exec", "-T", "backend", ...args], {
    input,
    encoding: "utf8",
  }).trim();
}
const couponScript = fs.readFileSync(path.join(HERE, "coupon.py"));

(async () => {
  const code = backend(["python", "-", "create"], couponScript).split("\n").pop();
  const checks = [];
  const check = (label, ok, detail) => checks.push([label, Boolean(ok), detail]);
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const account = {
      email: `zero-${Date.now()}@e2e.devpath.example`,
      password: "devpath-zero-drill",
      full_name: "Thử đơn 0đ",
    };
    const registered = await (
      await context.request.post(`${API}/api/v1/auth/register`, { data: account })
    ).json();
    const auth = { Authorization: `Bearer ${registered.access_token}` };

    const catalogue = await (
      await context.request.get(`${API}/api/v1/courses?page_size=50`)
    ).json();
    const course = catalogue.items.find((item) => Number(item.price) > 0);
    await context.request.put(`${API}/api/v1/cart/courses/${course.id}`, { headers: auth });
    check("a paid course in the cart", true, `${course.title} — ${Number(course.price).toLocaleString("vi-VN")} ₫`);

    const page = await context.newPage();
    const toGateway = [];
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("vnpayment") || url.includes("/payment-url")) toGateway.push(url.split("?")[0]);
    });

    await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => {
        const forms = document.querySelectorAll("form");
        return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
      },
      null,
      { timeout: 60_000 },
    );
    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mật khẩu").fill(account.password);
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 45_000 });

    await page.goto(`${BASE}/gio-hang`, { waitUntil: "domcontentloaded" });
    await page.getByLabel("Mã giảm giá").fill(code);
    await page.getByRole("button", { name: "Áp dụng" }).click();
    const button = page.getByRole("button", { name: "Nhận khóa học" });
    await button.waitFor({ timeout: 30_000 });
    check("the button says what it will do", true, `"Nhận khóa học" with ${code}`);
    await page.screenshot({ path: path.join(HERE, "cart-100-percent.png") });

    await button.click();
    await page.waitForURL(/\/thanh-toan\/ket-qua\?ma=/, { timeout: 30_000 });
    await page.getByText("Đã nhận khóa học").waitFor({ timeout: 30_000 });
    const orderCode = new URL(page.url()).searchParams.get("ma");
    check("straight to our own result page", true, new URL(page.url()).pathname + `?ma=${orderCode}`);
    check("no payment URL asked for, no request to VNPay", toGateway.length === 0, toGateway.join(", ") || "none");
    check("no VNPay transaction shown", (await page.getByText("Mã giao dịch VNPay").count()) === 0, "row absent");
    await page.screenshot({ path: path.join(HERE, "result-settled.png") });

    const order = await (
      await context.request.get(`${API}/api/v1/orders/${orderCode}`, { headers: auth })
    ).json();
    check(
      "the order, as the API stores it",
      order.status === "paid" && order.total === "0.00" && order.payment_provider === "none",
      `status ${order.status}, total ${order.total}, provider ${order.payment_provider}, ref ${order.provider_txn_id}`,
    );
    const mine = await (await context.request.get(`${API}/api/v1/enrollments/me`, { headers: auth })).json();
    check(
      "the course is the student's",
      mine.items.some((item) => item.course.id === course.id),
      `${mine.items.length} enrolment(s)`,
    );
    const cart = await (await context.request.get(`${API}/api/v1/cart`, { headers: auth })).json();
    check("and out of the cart", cart.items.length === 0, `${cart.items.length} line(s) left`);

    await context.request.post(`${API}/api/v1/auth/logout`, { headers: auth }).catch(() => {});
  } finally {
    await browser.close();
    console.log(backend(["python", "-m", "scripts.purge_e2e"]).split("\n").pop());
    console.log(backend(["python", "-", "delete", code], couponScript));
  }

  let failed = 0;
  for (const [label, ok, detail] of checks) {
    failed += ok ? 0 : 1;
    console.log(`${ok ? "PASS" : "FAIL"}  ${label.padEnd(48)} ${detail}`);
  }
  console.log(`${checks.length - failed}/${checks.length}`);
  process.exit(failed ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
