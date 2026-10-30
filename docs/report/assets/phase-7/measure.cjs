/**
 * Số đo "trước"/"sau" của Phase 7 (chương 5): dung lượng JS màn đầu, axe-core,
 * Lighthouse mobile. Chạy vào stack production chạy trên máy dev (stack demo
 * `devpath-demo`, tên miền https://devpath-01.me) để số đo là của bản build
 * thật — nhưng đi thẳng vào nginx của máy này (RESOLVE_TO, mặc định
 * 127.0.0.1), không vòng qua Cloudflare: `stack.cjs` giải thích vì sao.
 *
 *   cd infra && set -a && . ./.env.seed-demo && set +a && cd ..
 *   npm_config_cache=D:/devpath-tmp/npm-cache TEMP=D:/devpath-tmp/temp TMP=D:/devpath-tmp/temp \
 *     LABEL=before NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/measure.cjs
 *
 * `npm_config_cache`/`TEMP` sang ổ D: vì `npx lighthouse` tải ~100 MB, và ổ C:
 * gần đầy từng làm Docker Desktop chết giữa lượt đo 18/10 (site 530).
 *
 * Kết quả vào docs/report/assets/phase-7/<LABEL>/: bundle-stats.json, js.json,
 * axe.json, lighthouse/<trang>-<lượt>.json, summary.json.
 *
 * Biến môi trường:
 *   BASE_URL          mặc định https://devpath-01.me
 *   RESOLVE_TO        mặc định 127.0.0.1; "" = đi đường DNS thật (qua Cloudflare)
 *   LABEL             before | after (thư mục kết quả)
 *   SEED_ADMIN_PASSWORD, SEED_INSTRUCTOR_PASSWORD   cho hai trang giảng viên/admin
 *   COMPOSE_PROJECT   mặc định devpath-demo — bản build trong container frontend,
 *                     một mã chứng chỉ, dọn bằng purge_e2e
 *   LIGHTHOUSE        mặc định lighthouse@13.5.0 (ghim, chạy bằng npx)
 *   RUNS              số lượt Lighthouse mỗi trang, mặc định 3 (lấy trung vị)
 *
 * Hai con số JS:
 *   - bundle-stats.json: "First Load JS" của từng route theo đúng hàm
 *     `writeRouteBundleStats` của Next (16.3 không in bảng này ra màn hình nữa,
 *     chỉ ghi `.next/diagnostics/route-bundle-stats.json` — tệp này không vào
 *     image standalone, nên script chép `.next` từ container frontend rồi gọi
 *     lại đúng hàm đó). Phân tích tĩnh: JS mà route cần trước khi tương tác.
 *   - js.json: mọi tệp JS trình duyệt thật sự tải ở trang chủ (khách, cache
 *     trống), cả chunk tải lười sau khi trang hiện.
 *   Hai số gzip đều nén lại bằng mức 9 để so được với nhau; transferBytes là số
 *   byte thật đi qua mạng (nginx nén ở mức của nó).
 *
 * Ghi dữ liệu: một học viên dùng một lần (@e2e.devpath.example) đăng ký qua
 * form và ghi danh khóa Python miễn phí, để mở được trang học; purge_e2e xóa
 * ở cuối. Giảng viên và admin seed chỉ xem rồi đăng xuất.
 *
 * Lighthouse: mỗi lượt một Chrome riêng do Lighthouse tự mở (mobile, giả lập
 * mạng chậm + CPU 4×, cache trống), cùng luật trỏ tên miền với Playwright.
 * Trang chủ và chi tiết khóa học đo như khách; trang học đo với một phiên đăng
 * nhập mới của học viên trên (cookie qua `--extra-headers`). Mỗi trang RUNS
 * lượt, bảng tóm tắt lấy lượt có điểm hiệu năng ở giữa.
 */
if (process.env.RESOLVE_TO === undefined) process.env.RESOLVE_TO = "127.0.0.1";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const zlib = require("node:zlib");

const { chromium } = require("@playwright/test");
const axeSource = require("axe-core").source;

const { stack, apiClient } = require("./stack.cjs");

const BASE = (process.env.BASE_URL ?? "https://devpath-01.me").replace(/\/$/, "");
const ROUTE = stack(BASE);
const client = apiClient(BASE);
const LABEL = process.env.LABEL ?? "before";
const PROJECT = process.env.COMPOSE_PROJECT ?? "devpath-demo";
const LIGHTHOUSE = process.env.LIGHTHOUSE ?? "lighthouse@13.5.0";
const RUNS = Number(process.env.RUNS ?? 3);
const OUT = path.join(__dirname, LABEL);
const PYTHON = "python-co-ban-cho-nguoi-moi-bat-dau";
const DESKTOP = { width: 1440, height: 900 };

fs.mkdirSync(path.join(OUT, "lighthouse"), { recursive: true });

function log(...parts) {
  console.log(new Date().toISOString().slice(11, 19), ...parts);
}

function container(service) {
  return execFileSync(
    "docker",
    ["ps", "-q", "--filter", `label=com.docker.compose.project=${PROJECT}`, "--filter", `label=com.docker.compose.service=${service}`],
    { encoding: "utf8" },
  ).trim().split("\n")[0];
}

function sql(query) {
  return execFileSync(
    "docker",
    ["exec", container("postgres"), "sh", "-c", `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "${query}"`],
    { encoding: "utf8" },
  ).trim();
}

async function settle(page, ms = 800) {
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(ms);
}

async function hydrated(page) {
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 60_000 },
  );
}

async function signIn(page, email, password) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await hydrated(page);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill(password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error(`đăng nhập ${email} hỏng`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 45_000 });
}

/** Đúng endpoint nút "Đăng xuất" gọi, từ trong trang (cookie refresh đi kèm). */
async function signOut(page) {
  if (!page.url().startsWith(BASE)) {
    await page.goto(`${BASE}/chinh-sach-bao-mat`, { waitUntil: "domcontentloaded" }).catch(() => {});
  }
  await page
    .evaluate(() => fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }))
    .catch(() => {});
}

function gzip(buffer) {
  return zlib.gzipSync(buffer, { level: 9 }).length;
}

// --- 0. First Load JS theo bản build --------------------------------------------

async function buildStats() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "devpath-next-"));
  try {
    execFileSync("docker", ["cp", `${container("frontend")}:/app/.next`, dir]);
    const distDir = path.join(dir, ".next");
    const read = (file) => JSON.parse(fs.readFileSync(path.join(distDir, file), "utf8"));
    const routes = [...new Set(Object.values(read("app-path-routes-manifest.json")))];
    const { writeRouteBundleStats } = require("next/dist/build/route-bundle-stats");
    await writeRouteBundleStats({ pages: [], app: routes }, read("build-manifest.json"), distDir, dir);
    const rows = read(path.join("diagnostics", "route-bundle-stats.json")).map((row) => ({
      route: row.route,
      chunks: row.firstLoadChunkPaths.length,
      rawBytes: row.firstLoadUncompressedJsBytes,
      gzipBytes: row.firstLoadChunkPaths.reduce((n, file) => n + gzip(fs.readFileSync(path.join(dir, file))), 0),
    }));
    const result = {
      next: require("next/package.json").version,
      buildId: fs.readFileSync(path.join(distDir, "BUILD_ID"), "utf8").trim(),
      note: "First Load JS (Next writeRouteBundleStats) trên .next của container frontend; gzip mức 9",
      routes: rows,
    };
    fs.writeFileSync(path.join(OUT, "bundle-stats.json"), `${JSON.stringify(result, null, 2)}\n`);
    const home = rows.find((r) => r.route === "/");
    log(`First Load JS "/": ${home.chunks} tệp, ${(home.rawBytes / 1024).toFixed(1)} KB thô, ${(home.gzipBytes / 1024).toFixed(1)} KB gzip`);
    return result;
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

// --- 1. JS màn đầu của trang chủ ------------------------------------------------

async function measureJs(page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.clearBrowserCache");
  await page.goto(`${BASE}/`, { waitUntil: "load" });
  await settle(page, 1_500);
  const entries = await page.evaluate(() =>
    performance.getEntriesByType("resource")
      .filter((e) => e.initiatorType === "script" || /\.js(\?|$)/.test(e.name))
      .map((e) => ({ url: e.name, transfer: e.transferSize, decoded: e.decodedBodySize })),
  );
  const scripts = [];
  for (const entry of entries) {
    if (!entry.url.startsWith(BASE)) {
      scripts.push({ ...entry, gzip: null, thirdParty: true });
      continue;
    }
    const { body } = await ROUTE.request("GET", entry.url);
    scripts.push({ ...entry, url: entry.url.slice(BASE.length), raw: body.length, gzip: gzip(body) });
  }
  const own = scripts.filter((s) => !s.thirdParty);
  const sum = (key) => own.reduce((n, s) => n + (s[key] ?? 0), 0);
  const result = {
    page: "/",
    scripts: own.length,
    thirdParty: scripts.filter((s) => s.thirdParty).map((s) => s.url),
    rawBytes: sum("raw"),
    gzipBytes: sum("gzip"),
    transferBytes: sum("transfer"),
    files: scripts,
  };
  fs.writeFileSync(path.join(OUT, "js.json"), `${JSON.stringify(result, null, 2)}\n`);
  log(`JS trang chủ: ${own.length} tệp, ${(result.rawBytes / 1024).toFixed(1)} KB thô, ${(result.gzipBytes / 1024).toFixed(1)} KB gzip, ${(result.transferBytes / 1024).toFixed(1)} KB qua mạng`);
  return result;
}

// --- 2. axe-core -------------------------------------------------------------------

async function axe(page, url) {
  await page.goto(`${BASE}${url}`, { waitUntil: "domcontentloaded" });
  await settle(page, 1_200);
  // evaluate đi qua CDP, không bị CSP của trang chặn.
  await page.evaluate(axeSource);
  const result = await page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ["violations", "incomplete"] });
    return {
      violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, tags: v.tags, nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })),
      incomplete: r.incomplete.length,
    };
  });
  const byImpact = {};
  for (const v of result.violations) byImpact[v.impact] = (byImpact[v.impact] ?? 0) + 1;
  log(`axe ${url}: ${result.violations.length} luật vi phạm ${JSON.stringify(byImpact)}`);
  return { url, byImpact, ...result };
}

// --- 3. Lighthouse --------------------------------------------------------------------

/**
 * Một lượt Lighthouse, trong Chrome riêng mà Lighthouse tự mở (cache trống,
 * hồ sơ trống — cách đo chuẩn). Không gắn vào Chrome của Playwright: Playwright
 * tự gắn vào mọi tab mới, và tab Lighthouse mở ra đứng im ở `Page.navigate`
 * (đo 20/10: 10 phút không xong); nối Playwright rồi ngắt ra thì Lighthouse ra
 * NO_NAVSTART. `cookie` = phiên của học viên, gửi kèm mọi request qua
 * `--extra-headers`, cho trang cần đăng nhập.
 */
function lighthouse(name, url, run, cookie) {
  const out = path.join(OUT, "lighthouse", `${name}-${run}.json`);
  const win = process.platform === "win32";
  // npx.cmd cần shell trên Windows, và cmd.exe chỉ nối các tham số bằng dấu
  // cách: tham số có dấu cách phải tự bọc ngoặc kép.
  const quote = (arg) => (win ? `"${arg}"` : arg);
  // yargs của Lighthouse tách --chrome-flags theo dấu cách, giữ nguyên chuỗi trong nháy đơn.
  const chromeFlags = ["--headless", ...ROUTE.chromeArgs.map((flag) => flag.replace(/=(.* .*)$/, "='$1'"))].join(" ");
  const args = [
    "-y", LIGHTHOUSE, quote(`${BASE}${url}`), quote(`--chrome-flags=${chromeFlags}`),
    "--only-categories=performance,accessibility,best-practices,seo",
    "--output=json", quote(`--output-path=${out}`), "--quiet",
  ];
  const headers = cookie ? path.join(os.tmpdir(), `devpath-lh-headers-${process.pid}.json`) : null;
  if (headers) {
    fs.writeFileSync(headers, JSON.stringify({ Cookie: cookie }));
    args.push(quote(`--extra-headers=${headers}`));
  }
  try {
    // Lighthouse sometimes loses the start of its trace on a busy machine
    // (NO_NAVSTART, exit 1, nothing measured): one more go, a fresh Chrome.
    // A signed-in retry may reuse a cookie the failed run already rotated; the
    // backend's 30 s leeway covers that, and an expired one shows up as the
    // learning page's sign-in gate in the report rather than as a wrong number.
    for (let attempt = 1; ; attempt++) {
      try {
        execFileSync(win ? "npx.cmd" : "npx", args, { stdio: "inherit", shell: win });
        break;
      } catch (error) {
        const partial = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, "utf8")) : null;
        if (attempt >= 2 || (partial && partial.runtimeError?.code !== "NO_NAVSTART")) throw error;
        log(`lighthouse ${name} #${run}: NO_NAVSTART, chạy lại`);
      }
    }
  } finally {
    if (headers) fs.rmSync(headers, { force: true });
  }
  const r = JSON.parse(fs.readFileSync(out, "utf8"));
  if (r.runtimeError) throw new Error(`lighthouse ${name} #${run}: ${r.runtimeError.code} ${r.runtimeError.message}`);
  fs.writeFileSync(out, `${JSON.stringify(slim(r))}\n`);
  const audit = (id) => r.audits[id]?.numericValue ?? null;
  const row = {
    name, url, run,
    lighthouse: r.lighthouseVersion,
    formFactor: r.configSettings.formFactor,
    throttling: r.configSettings.throttlingMethod,
    finalUrl: r.finalDisplayedUrl,
    performance: r.categories.performance.score,
    accessibility: r.categories.accessibility.score,
    bestPractices: r.categories["best-practices"].score,
    seo: r.categories.seo.score,
    signedIn: Boolean(cookie),
    // Edge Cloudflare chèn beacon này vào HTML: có nó là lượt đo đã không đi đường nội bộ.
    viaCloudflare: r.audits["network-requests"].details.items.some((i) => /cloudflareinsights/.test(i.url)),
    lcpMs: audit("largest-contentful-paint"),
    cls: audit("cumulative-layout-shift"),
    tbtMs: audit("total-blocking-time"),
    fcpMs: audit("first-contentful-paint"),
    siMs: audit("speed-index"),
  };
  log(`lighthouse ${name} #${run}: perf ${row.performance} LCP ${Math.round(row.lcpMs)} ms CLS ${row.cls?.toFixed(3)} TBT ${Math.round(row.tbtMs)} ms a11y ${row.accessibility}`);
  return row;
}

/**
 * Báo cáo Lighthouse bỏ các ảnh chụp base64 (dải phim, ảnh cuối, ảnh cả trang
 * — hơn nửa dung lượng tệp). Mọi số đo và chẩn đoán còn nguyên; mở lại được
 * bằng Lighthouse Viewer, chỉ thiếu hình.
 */
function slim(report) {
  // Lighthouse chép `--extra-headers` vào báo cáo: đó là cookie refresh của phiên đo.
  if (report.configSettings?.extraHeaders) report.configSettings.extraHeaders = { Cookie: "<đã xóa>" };
  delete report.fullPageScreenshot;
  for (const id of ["screenshot-thumbnails", "final-screenshot"]) {
    if (report.audits[id]) delete report.audits[id].details;
  }
  return report;
}

function median(rows) {
  const sorted = [...rows].sort((a, b) => a.performance - b.performance);
  return sorted[Math.floor(sorted.length / 2)];
}

// --- Chạy ------------------------------------------------------------------------

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true, args: ROUTE.chromeArgs });
  const context = await browser.newContext({
    viewport: DESKTOP,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    ignoreHTTPSErrors: ROUTE.mapped,
  });
  const summary = {
    label: LABEL,
    base: BASE,
    route: ROUTE.mapped ? `${ROUTE.host} → ${process.env.RESOLVE_TO} (nginx trên máy dev)` : "DNS thật",
    commit: execFileSync("git", ["rev-parse", "--short", "HEAD"], { encoding: "utf8" }).trim(),
    at: new Date().toISOString(),
    lighthouse: LIGHTHOUSE,
  };
  let purged = null;
  try {
    const build = await buildStats();
    summary.buildId = build.buildId;
    summary.firstLoadJs = Object.fromEntries(
      build.routes
        .filter((r) => ["/", "/khoa-hoc/[slug]", "/hoc/[slug]"].includes(r.route))
        .map((r) => [r.route, { rawBytes: r.rawBytes, gzipBytes: r.gzipBytes }]),
    );

    const page = await context.newPage();
    summary.js = (await measureJs(page)).gzipBytes;

    const certificate = sql("select code from certificates where pdf_key is not null order by issued_at limit 1");
    const course = await client.call("GET", `/courses/by-slug/${PYTHON}`);
    const lessons = (await client.call("GET", `/courses/${course.id}/curriculum`)).sections.flatMap((s) => s.lessons);
    const video = lessons.find((l) => l.type === "video").id;
    const code = lessons.find((l) => l.type === "code_exercise").id;

    // Học viên dùng một lần.
    const email = `measure-${Date.now().toString(36)}@e2e.devpath.example`;
    const password = `m-${Date.now()}-easure`;
    await page.goto(`${BASE}/dang-ky`, { waitUntil: "domcontentloaded" });
    await hydrated(page);
    await page.getByLabel("Họ và tên").fill("Học Viên Đo Đạc");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Mật khẩu").fill(password);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    // Sign-up lands on the welcome page since Phase 7 group 7; on the home page before.
    await page.waitForURL((url) => ["/", "/chao-mung"].includes(url.pathname), { timeout: 45_000 });
    await page.goto(`${BASE}/khoa-hoc/${PYTHON}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Đăng ký học miễn phí" }).click();
    await page.waitForURL((url) => url.pathname.startsWith("/hoc/"), { timeout: 30_000 });
    log(`học viên ${email} đã ghi danh`);

    const axePages = [
      "/", "/khoa-hoc", `/khoa-hoc/${PYTHON}`, "/bang-xep-hang", `/cert/${certificate}`,
      `/hoc/${PYTHON}?bai=${video}`, `/hoc/${PYTHON}?bai=${code}`, "/khoa-hoc-cua-toi", "/gio-hang", "/ho-so",
    ];
    const axeResults = [];
    for (const url of axePages) axeResults.push(await axe(page, url));

    // Lighthouse: trang của Playwright đứng ở about:blank để không có gì chạy nền
    // (chuông thông báo hỏi mỗi 60 s). Hai trang công khai đo như khách lần
    // đầu ghé; trang học đo với một phiên đăng nhập mới mỗi lượt — refresh
    // token xoay vòng, dùng lại cookie cũ quá 30 s là bị coi là token bị trộm.
    await page.goto("about:blank");
    const targets = [
      ["trang-chu", "/", false],
      ["chi-tiet-khoa-hoc", `/khoa-hoc/${PYTHON}`, false],
      ["trang-hoc", `/hoc/${PYTHON}?bai=${video}`, true],
    ];
    const lighthouseRows = [];
    for (const [name, url, signedIn] of targets) {
      for (let run = 1; run <= RUNS; run++) {
        const session = signedIn ? await client.login({ email, password }) : null;
        try {
          lighthouseRows.push(lighthouse(name, url, run, session?.cookie));
        } finally {
          await client.logout(session);
        }
      }
    }
    summary.lighthouse_runs = lighthouseRows;
    summary.lighthouse_median = targets.map(([name]) => median(lighthouseRows.filter((r) => r.name === name)));

    // Hai trang của giảng viên và admin, đăng nhập lần lượt trên cùng tab.
    await signOut(page);
    if (process.env.SEED_INSTRUCTOR_PASSWORD) {
      await signIn(page, "khoa.tran@devpath.example", process.env.SEED_INSTRUCTOR_PASSWORD);
      axeResults.push(await axe(page, "/giang-day/thong-ke"));
      await signOut(page);
    }
    if (process.env.SEED_ADMIN_PASSWORD) {
      await signIn(page, "admin@devpath.example", process.env.SEED_ADMIN_PASSWORD);
      axeResults.push(await axe(page, "/quan-tri"));
      await signOut(page);
    }
    fs.writeFileSync(path.join(OUT, "axe.json"), `${JSON.stringify({ axe: require("axe-core/package.json").version, pages: axeResults }, null, 2)}\n`);
    summary.axe = axeResults.map((r) => ({ url: r.url.replace(certificate, "<mã>"), ...r.byImpact, rules: r.violations.map((v) => `${v.id}(${v.impact})`) }));
  } finally {
    await browser.close();
    try {
      purged = execFileSync("docker", ["exec", container("backend"), "python", "-m", "scripts.purge_e2e"], { encoding: "utf8" }).trim();
    } catch (error) {
      purged = `DỌN HỎNG: ${error}`;
    }
  }
  summary.purged = purged;
  fs.writeFileSync(path.join(OUT, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(JSON.stringify({ first_load_js: summary.firstLoadJs, js_gzip: summary.js, lighthouse: summary.lighthouse_median.map((r) => ({ name: r.name, perf: r.performance, lcp: Math.round(r.lcpMs), cls: r.cls, tbt: Math.round(r.tbtMs), a11y: r.accessibility })), axe: summary.axe.map((a) => `${a.url}: ${a.rules.join(", ") || "0"}`), purged }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
