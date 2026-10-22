// Task "Trạng thái toàn site": does "Thử lại" on an error page bring the page
// back once the backend answers again? The course page renders on the server,
// so only `retry` (fetch the segment again) can; `reset` re-renders the
// failure already on the client.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/retry.cjs
//
// Dev stack. Stops the backend container for a moment and starts it again.
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const SLUG = "python-co-ban-cho-nguoi-moi-bat-dau";
const COMPOSE = path.resolve(__dirname, "../../../../../infra/docker-compose.yml");
const OUT = path.join(__dirname, "after");
const compose = (...args) => execFileSync("docker", ["compose", "-f", COMPOSE, ...args], { stdio: "inherit" });

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  // Compile the page while the backend is up.
  await page.goto(`${BASE}/khoa-hoc/${SLUG}`, { waitUntil: "networkidle", timeout: 180_000 });
  compose("stop", "backend");
  try {
    await page.goto(`${BASE}/khoa-hoc/${SLUG}`, { waitUntil: "domcontentloaded", timeout: 180_000 });
    await page.getByRole("heading", { name: "Không tải được khóa học" }).waitFor({ timeout: 60_000 });
    await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
    await page.screenshot({ path: path.join(OUT, "loi-khoa-hoc-that-1440.png"), animations: "disabled" });
    const naomi = await page.locator('[data-mascot] [data-mood="sorry"]').count();
    console.log(`trang lỗi: có, Naomi sorry: ${naomi ? "có" : "KHÔNG"}`);
  } finally {
    compose("start", "backend");
  }
  // Wait for the API, then retry from the page itself.
  for (let i = 0; i < 60; i++) {
    const ok = await fetch("http://localhost:8000/api/v1/health").then((r) => r.ok, () => false);
    if (ok) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  // A marker on window survives a client-side retry, not a full reload.
  await page.evaluate(() => (window.__sameDocument = true));
  await page.getByRole("button", { name: "Thử lại" }).click();
  await page.getByRole("heading", { level: 1, name: /Python cơ bản/ }).waitFor({ timeout: 60_000 });
  const same = await page.evaluate(() => window.__sameDocument === true);
  console.log(`sau "Thử lại": trang khóa học hiện lại; ${same ? "cùng tài liệu (không tải lại cả trang)" : "trình duyệt đã tải lại cả trang"}`);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
