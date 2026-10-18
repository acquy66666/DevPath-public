/**
 * Bằng chứng "Bật đăng nhập Google trên tên miền thật" (18/10/2026): nút Google
 * trên trang đăng nhập, cú chuyển hướng sang accounts.google.com mang đúng
 * redirect_uri, cookie state, và trang chính sách bảo mật mà Google đòi.
 *
 *   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/google-login/capture.cjs
 *
 * Chỉ đi tới màn hình đăng nhập của Google — không đăng nhập (bước đó là của
 * người có tài khoản Google). Không ghi gì vào CSDL.
 *
 * Biến môi trường:
 *   BASE_URL         mặc định https://devpath-01.me
 *   CHROME_CHANNEL   mặc định "chrome" (Chrome cài trên máy); "" = Chromium của Playwright.
 */
const fs = require("node:fs");
const path = require("node:path");

const { chromium } = require("@playwright/test");

const BASE = (process.env.BASE_URL ?? "https://devpath-01.me").replace(/\/$/, "");
const CHANNEL = process.env.CHROME_CHANNEL ?? "chrome";
const OUT = __dirname;
const AUTHORIZE = "/api/v1/auth/google/authorize";
const STATE_COOKIE = "devpath_oauth_state";

// The client id is public (it rides in every authorize URL), but the evidence
// file does not need all of it.
function maskClientId(id) {
  if (!id) return id;
  const [head, ...rest] = id.split("-");
  return `${head.slice(0, 4)}…-…${rest.join("-").slice(-28)}`;
}

async function main() {
  const browser = await chromium.launch({ channel: CHANNEL || undefined, headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    locale: "vi-VN",
  });
  const page = await context.newPage();
  const log = { base: BASE, at: new Date().toISOString() };

  // 1. The button exists on the real domain.
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "networkidle" });
  const button = page.getByRole("link", { name: "Đăng nhập bằng Google" });
  await button.waitFor();
  log.button_href = await button.getAttribute("href");
  await page.screenshot({ path: path.join(OUT, "01-dang-nhap.png") });

  // 2. Pressing it: backend answers with a redirect to Google and a state cookie.
  const authorize = page.waitForResponse((r) => r.url().startsWith(`${BASE}${AUTHORIZE}`));
  await button.click();
  const response = await authorize;
  const headers = await response.allHeaders();
  log.authorize = {
    status: response.status(),
    location_host: new URL(headers.location).host,
    set_cookie_flags: (headers["set-cookie"] ?? "")
      .split(";")
      .slice(1)
      .map((part) => part.trim())
      .filter(Boolean),
  };

  await page.waitForURL(/^https:\/\/accounts\.google\.com\//, { timeout: 30_000 });
  await page.waitForLoadState("networkidle").catch(() => {});

  const google = new URL(headers.location);
  const params = Object.fromEntries(google.searchParams);
  // Path=/api/v1/auth: the cookie is only sent to (and only listed for) the callback.
  const callback = `${BASE}/api/v1/auth/google/callback`;
  const cookie = (await context.cookies(callback)).find((c) => c.name === STATE_COOKIE);
  log.google = {
    endpoint: `${google.origin}${google.pathname}`,
    client_id: maskClientId(params.client_id),
    redirect_uri: params.redirect_uri,
    redirect_uri_expected: `${BASE}/api/v1/auth/google/callback`,
    response_type: params.response_type,
    scope: params.scope,
    prompt: params.prompt,
    state_length: params.state?.length,
    state_matches_cookie: Boolean(cookie) && cookie.value === params.state,
    cookie: cookie && {
      path: cookie.path,
      httpOnly: cookie.httpOnly,
      secure: cookie.secure,
      sameSite: cookie.sameSite,
      lifetime_seconds: Math.round(cookie.expires - Date.now() / 1000),
    },
    landed_on: new URL(page.url()).host + new URL(page.url()).pathname,
    page_title: await page.title(),
  };
  await page.screenshot({ path: path.join(OUT, "02-google-dang-nhap.png") });

  // 3. The privacy policy Google needs before the app can leave "Testing".
  const policy = await page.goto(`${BASE}/chinh-sach-bao-mat`, { waitUntil: "networkidle" });
  log.privacy_policy = {
    status: policy.status(),
    title: await page.title(),
    headings: await page.locator("article h2").allTextContents(),
    footer_link: await page.locator("footer a[href='/chinh-sach-bao-mat']").count(),
  };
  await page.screenshot({ path: path.join(OUT, "03-chinh-sach-bao-mat.png"), fullPage: true });

  await browser.close();
  fs.writeFileSync(path.join(OUT, "capture-log.json"), `${JSON.stringify(log, null, 2)}\n`);
  console.log(JSON.stringify(log, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
