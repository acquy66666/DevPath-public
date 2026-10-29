import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a stack that is already up -- `docker compose
 * up` in infra/, seeded -- rather than one Playwright starts itself. The golden
 * flow needs all of it at once: Postgres, Redis, the API, the Celery worker
 * that grades code in a Docker sandbox, and the one that draws certificates.
 * There is no smaller stack that tells the truth about that flow.
 *
 *   npm run test:e2e                       # against http://localhost:3000
 *   E2E_CHROME_CHANNEL=chrome npm run test:e2e   # use the installed Chrome
 *
 * One worker, one browser: the flow is a story told in order, and two copies
 * of it would only race each other for the same grading queue.
 */
export default defineConfig({
  testDir: "./e2e",
  // A cold `next dev` compiles each page on first visit, and grading starts a
  // container per test case. Generous on purpose; a slow pass is still a pass.
  timeout: 240_000,
  expect: {
    timeout: 30_000,
    // Visual suite: both sides of a comparison come out of the same Linux
    // image, so a real diff is a real change. 0.1 % of a full page leaves room
    // for antialiasing on a glyph edge and nothing the eye would call a change.
    toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: "disabled", caret: "hide" },
  },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    navigationTimeout: 60_000,
  },
  projects: [
    {
      name: "chromium",
      testIgnore: /[\\/]visual[\\/]/,
      use: {
        ...devices["Desktop Chrome"],
        // Locally the installed Chrome saves downloading a browser; CI
        // installs Playwright's own Chromium and leaves this unset.
        ...(process.env.E2E_CHROME_CHANNEL ? { channel: process.env.E2E_CHROME_CHANNEL } : {}),
      },
    },
    // Visual regression (e2e/visual). Run through scripts/visual.sh only: the
    // baselines are Linux pictures from Playwright's image, and a run on
    // Windows or macOS would draw different glyphs and fail every one.
    {
      name: "visual-desktop",
      testMatch: /[\\/]visual[\\/].*\.spec\.ts$/,
      // A screenshot that needs a second try is a flaky screenshot.
      retries: 0,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "visual-mobile",
      testMatch: /[\\/]visual[\\/].*\.spec\.ts$/,
      retries: 0,
      use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 } },
    },
  ],
});
