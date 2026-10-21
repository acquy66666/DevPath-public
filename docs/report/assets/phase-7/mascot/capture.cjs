/**
 * Bằng chứng cho component <Mascot> (Phase 7): đo trên bản `next build`
 * production, dưới đúng chuỗi CSP production, trong Chrome thật.
 *
 *   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/mascot/capture.cjs
 *
 * Không cần stack nào: trang /dev/naomi và hai trang đo không gọi API (lệnh
 * refresh phiên được trả lời như với khách). Script:
 *   1. chép hai trang đo tạm vào frontend/app/(measure)/do-naomi/{khong,co}
 *      — giống nhau, chỉ khác `co` có một <Mascot mood="lost" event />;
 *   2. `next build` với MASCOT_PREVIEW=1 (để /dev/naomi có trong bản build);
 *   3. đo First Load JS + JS tải thật của hai trang đo, và từng chunk hình;
 *   4. `next start` ở 127.0.0.1:3108, rồi trong Chrome (Playwright, channel chrome):
 *      HTML máy chủ có sẵn hình tĩnh không, CSP, tải lười, giảm chuyển động,
 *      không chặn click, luồng chấm bài k/n → verdict, thời gian từng phản ứng;
 *   5. chụp khung hình chính xác (dừng mọi animation, đặt currentTime) của cả
 *      30 mood → frames/sheet-*.png, cộng ảnh lưới tư thế tĩnh;
 *   6. xóa hai trang đo khỏi frontend (kể cả khi lỗi).
 *
 * Cờ: --skip-build (dùng .next có sẵn — hai trang đo phải còn trong đó),
 *     --keep (giữ hai trang đo để xem tay).
 * Kết quả: results.json, build.log, frames/, grid.png, reduced.png cạnh script này.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const http = require("http");
const { execSync, spawn } = require("child_process");

const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..", "..");
const FRONTEND = path.join(REPO, "frontend");
const MEASURE = path.join(FRONTEND, "app", "(measure)");
const CSP_CONF = path.join(REPO, "infra", "nginx", "snippets", "security-headers.conf");
const FRAMES = path.join(HERE, "frames");
const PORT = 3108;
const BASE = `http://127.0.0.1:${PORT}`;
const TIMES = [0, 200, 500, 900, 1400, 2000]; // ms vào phản ứng, cho bảng khung hình
const args = new Set(process.argv.slice(2));
const log = (...m) => console.log(`[naomi ${new Date().toISOString().slice(11, 19)}]`, ...m);
const gzip = (buf) => zlib.gzipSync(buf, { level: 9 }).length;
const kb = (n) => Math.round((n / 1024) * 10) / 10;

const MOODS = [...fs.readFileSync(path.join(FRONTEND, "lib", "mascot", "moods.ts"), "utf8").matchAll(/^  "([a-z-]+)",$/gm)].map((m) => m[1]);

// --- 1. hai trang đo ----------------------------------------------------------

const PAGE = (withMascot) => `// Trang đo tạm của docs/report/assets/phase-7/mascot/capture.cjs — script xóa sau khi đo.
import type { Metadata } from "next";
${withMascot ? 'import { Mascot } from "@/components/mascot/mascot";\n' : ""}
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function Page() {
  return (
    <main className="mx-auto max-w-md flex-1 px-4 py-20 text-center">
      <p className="text-sm font-medium text-muted-foreground">404</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight">Không có trang nào ở đây</h1>
      ${withMascot ? '<Mascot mood="lost" size="lg" event className="mx-auto mt-6" />' : '<span className="mx-auto mt-6 inline-block size-50" />'}
    </main>
  );
}
`;

function stageMeasurePages() {
  for (const [name, withMascot] of [["khong", false], ["co", true]]) {
    const dir = path.join(MEASURE, "do-naomi", name);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "page.tsx"), PAGE(withMascot));
  }
}
function removeMeasurePages() {
  fs.rmSync(MEASURE, { recursive: true, force: true });
}

// --- 2. build -----------------------------------------------------------------

function build() {
  log("next build …");
  const started = Date.now();
  const out = execSync("npx next build", {
    cwd: FRONTEND,
    // API_BASE_URL rỗng = cùng origin, như image production; để mặc định thì
    // lệnh refresh đi tới localhost:8000 và vi phạm connect-src.
    env: { ...process.env, MASCOT_PREVIEW: "1", NEXT_PUBLIC_SITE_URL: BASE, NEXT_PUBLIC_API_BASE_URL: "", NEXT_TELEMETRY_DISABLED: "1" },
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  fs.writeFileSync(path.join(HERE, "build.log"), out);
  log(`build xong sau ${((Date.now() - started) / 1000).toFixed(0)} s`);
}

// --- 3. dung lượng ------------------------------------------------------------

async function firstLoad() {
  const distDir = path.join(FRONTEND, ".next");
  const read = (file) => JSON.parse(fs.readFileSync(path.join(distDir, file), "utf8"));
  const routes = ["/do-naomi/khong", "/do-naomi/co"];
  const { writeRouteBundleStats } = require(path.join(FRONTEND, "node_modules", "next", "dist", "build", "route-bundle-stats"));
  await writeRouteBundleStats({ pages: [], app: routes }, read("build-manifest.json"), distDir, FRONTEND);
  const rows = read(path.join("diagnostics", "route-bundle-stats.json"));
  const stat = (route) => {
    const row = rows.find((r) => r.route === route);
    if (!row) throw new Error(`route-bundle-stats thiếu ${route}`);
    return { chunks: row.firstLoadChunkPaths.length, gzipBytes: row.firstLoadChunkPaths.reduce((n, f) => n + gzip(fs.readFileSync(path.join(FRONTEND, f))), 0) };
  };
  const khong = stat("/do-naomi/khong");
  const co = stat("/do-naomi/co");
  return { khong, co, deltaGzipKB: kb(co.gzipBytes - khong.gzipBytes) };
}

/** Mỗi mood một chunk hình: tìm theo `data-mood="<mood>"` trong chunk tĩnh. */
function artChunks() {
  const dir = path.join(FRONTEND, ".next", "static", "chunks");
  const files = fs.readdirSync(dir, { recursive: true }).filter((f) => f.endsWith(".js"));
  const out = {};
  for (const f of files) {
    const text = fs.readFileSync(path.join(dir, f), "utf8");
    const moods = [...text.matchAll(/data-mood=\\?"([a-z-]+)\\?"/g)].map((m) => m[1]);
    if (moods.length === 1) out[moods[0]] = { file: path.basename(f), gzipBytes: gzip(Buffer.from(text)) };
    else if (moods.length > 1) throw new Error(`${f} gộp ${moods.length} hình (${moods.join(", ")}): mỗi mood phải là một chunk`);
  }
  const missing = MOODS.filter((m) => !out[m]);
  if (missing.length) throw new Error(`không thấy chunk hình của: ${missing.join(", ")}`);
  const sizes = MOODS.map((m) => out[m].gzipBytes).sort((a, b) => a - b);
  return { perMood: out, minKB: kb(sizes[0]), medianKB: kb(sizes[Math.floor(sizes.length / 2)]), maxKB: kb(sizes[sizes.length - 1]) };
}

// --- 4. server + Chrome -------------------------------------------------------

function get(url) {
  return new Promise((resolve) => {
    http.get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (d) => (body += d));
      res.on("end", () => resolve({ status: res.statusCode, body }));
    }).on("error", () => resolve({ status: 0, body: "" }));
  });
}

async function serve() {
  const child = spawn(process.execPath, [path.join(FRONTEND, "node_modules", "next", "dist", "bin", "next"), "start", "-p", String(PORT), "-H", "127.0.0.1"], {
    cwd: FRONTEND,
    env: { ...process.env, MASCOT_PREVIEW: "1", NEXT_TELEMETRY_DISABLED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.on("data", (d) => (output += d));
  child.stderr.on("data", (d) => (output += d));
  for (let i = 0; i < 120; i++) {
    if ((await get(`${BASE}/do-naomi/khong`)).status === 200) return child;
    if (child.exitCode !== null) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  child.kill();
  throw new Error(`next start không lên:\n${output}`);
}

/** HTML máy chủ trả: hình tĩnh nằm ngay trong đó, hay phải chờ một boundary stream? */
async function serverHtml() {
  const probe = async () => {
    const { status, body } = await get(`${BASE}/do-naomi/co`);
    return { status, drawings: body.split('data-layer="naomi"').length - 1, streamedBoundaries: body.split("<!--$?-->").length - 1 };
  };
  const first = await probe();
  const second = await probe();
  const preview = await get(`${BASE}/dev/naomi`);
  return { first, second, preview: { status: preview.status, drawings: preview.body.split('data-layer="naomi"').length - 1, streamedBoundaries: preview.body.split("<!--$?-->").length - 1 } };
}

function cspHeader() {
  const m = /add_header Content-Security-Policy "([^"]+)" always;/.exec(fs.readFileSync(CSP_CONF, "utf8"));
  if (!m) throw new Error("không đọc được CSP trong security-headers.conf");
  return m[1];
}

/** Policy production lên mọi tài liệu HTML, bộ đếm vi phạm, ghi lại script tải về. */
async function newPage(browser, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "no-preference", ...options });
  const page = await context.newPage();
  const csp = cspHeader();
  const scripts = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/auth/refresh") {
      return route.fulfill({ status: 401, contentType: "application/json", body: '{"code":"NOT_AUTHENTICATED","message":"capture"}' });
    }
    if (route.request().resourceType() !== "document") return route.continue();
    const response = await route.fetch();
    await route.fulfill({ response, headers: { ...response.headers(), "content-security-policy": csp } });
  });
  page.on("response", (r) => {
    if (r.request().resourceType() === "script") scripts.push(new URL(r.url()).pathname);
  });
  await page.addInitScript(() => {
    window.__violations = [];
    document.addEventListener("securitypolicyviolation", (e) => window.__violations.push({ directive: e.effectiveDirective, blocked: e.blockedURI }));
  });
  const problems = [];
  page.on("console", (m) => m.type() === "error" && !/401|auth\/refresh/.test(m.text()) && problems.push(`console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  return { context, page, problems, scripts };
}

const phaseOf = (page, mood) => page.locator(`[data-testid="mood-${mood}"] [data-phase]`).first();

/** JS tải thật khi mở hai trang đo (gzip mức 9 từng tệp trong .next). */
async function transfer(browser) {
  const out = {};
  for (const name of ["khong", "co"]) {
    const { context, page, scripts } = await newPage(browser);
    await page.goto(`${BASE}/do-naomi/${name}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(3500); // phản ứng `lost` chạy hết
    const files = [...new Set(scripts)].filter((p) => p.startsWith("/_next/static/"));
    const bytes = files.reduce((n, p) => n + gzip(fs.readFileSync(path.join(FRONTEND, ".next", p.replace("/_next/", "")))), 0);
    const artLoaded = files.filter((p) => /data-mood=/.test(fs.readFileSync(path.join(FRONTEND, ".next", p.replace("/_next/", "")), "utf8"))).length;
    const animated = name === "co" ? await page.locator("[data-phase]").getAttribute("data-phase") : null;
    out[name] = { scripts: files.length, gzipBytes: bytes, artChunks: artLoaded, phaseAfter: animated };
    await context.close();
  }
  out.deltaGzipKB = kb(out.co.gzipBytes - out.khong.gzipBytes);
  return out;
}

/** Bấm "Phát" từng mood, đo tới khi hết `playing`, rồi kiểm không còn animation. */
async function reactions(browser) {
  const { context, page, problems } = await newPage(browser);
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  const rows = {};
  for (const mood of MOODS) {
    const card = page.locator(`[data-testid="mood-${mood}"]`);
    await card.scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    const t0 = await page.evaluate(() => performance.now());
    await page.locator(`[data-testid="play-${mood}"]`).click();
    await page.waitForFunction((m) => document.querySelector(`[data-testid="mood-${m}"] [data-phase]`)?.getAttribute("data-phase") === "playing", mood);
    const started = await page.evaluate(() => performance.now());
    await page.waitForFunction((m) => document.querySelector(`[data-testid="mood-${m}"] [data-phase]`)?.getAttribute("data-phase") !== "playing", mood, { timeout: 6000 });
    const ended = await page.evaluate(() => performance.now());
    await page.waitForTimeout(100);
    rows[mood] = {
      startMs: Math.round(started - t0),
      reactionMs: Math.round(ended - started),
      phaseAfter: await phaseOf(page, mood).getAttribute("data-phase"),
      animationsAfter: await card.evaluate((el) => el.getAnimations({ subtree: true }).length),
    };
  }
  const violations = await page.evaluate(() => window.__violations);
  await context.close();
  return { rows, violations, problems };
}

/** Giảm chuyển động: bấm "Phát tất cả", lấy mẫu 3 s — không animation nào, không mood nào đổi. */
async function reducedMotion(browser) {
  const { context, page, problems } = await newPage(browser, { reducedMotion: "reduce" });
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  await page.locator('[data-testid="play-all"]').click();
  const samples = [];
  for (let i = 0; i < 15; i++) {
    await page.waitForTimeout(200);
    samples.push(
      await page.evaluate(() => ({
        animations: document.getAnimations().length,
        moved: [...document.querySelectorAll("[data-layer],[data-part]")].some((el) => getComputedStyle(el).translate !== "none" || getComputedStyle(el).rotate !== "none" || getComputedStyle(el).scale !== "none"),
        phases: [...new Set([...document.querySelectorAll("[data-phase]")].map((el) => el.getAttribute("data-phase")))],
        wrongMood: [...document.querySelectorAll("[data-testid^='mood-']")].filter((li) => li.querySelector("[data-mood]")?.getAttribute("data-mood") !== li.dataset.testid.slice(5)).length,
      })),
    );
  }
  await page.locator("main ul").screenshot({ path: path.join(HERE, "reduced.png") });
  await context.close();
  return {
    anyAnimation: samples.some((s) => s.animations > 0),
    anyLayerMoved: samples.some((s) => s.moved),
    phases: [...new Set(samples.flatMap((s) => s.phases))],
    moodsChanged: Math.max(...samples.map((s) => s.wrongMood)),
    problems,
  };
}

/** Tải lười: mood ở cuối trang không phản ứng khi chưa cuộn tới. */
async function lazy(browser) {
  const { context, page } = await newPage(browser, { viewport: { width: 1280, height: 700 } });
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  const last = MOODS[MOODS.length - 1];
  await page.locator('[data-testid="play-all"]').click();
  await page.waitForTimeout(600);
  const offscreenBefore = await phaseOf(page, last).getAttribute("data-phase");
  const firstPlaying = await phaseOf(page, MOODS[0]).getAttribute("data-phase");
  await page.locator(`[data-testid="mood-${last}"]`).scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  const offscreenAfter = await phaseOf(page, last).getAttribute("data-phase");
  await context.close();
  return { firstOnScreen: firstPlaying, lastBeforeScroll: offscreenBefore, lastAfterScroll: offscreenAfter };
}

/** Không chặn click: điểm giữa Naomi đè lên nút vẫn là nút. */
async function clickThrough(browser) {
  const { context, page } = await newPage(browser);
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  const under = page.locator('[data-testid="under"]');
  await under.scrollIntoViewIfNeeded();
  const box = await page.locator('[data-testid="under"] + [data-mascot]').boundingBox();
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const hit = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest("[data-testid]")?.getAttribute("data-testid") ?? null, [x, y]);
  await page.mouse.click(x, y);
  await page.mouse.click(x, y);
  const label = await under.innerText();
  await context.close();
  return { elementAtMascotCentre: hit, buttonTextAfterTwoClicks: label };
}

/** Animation bị hủy từ bên ngoài (dev tools, script khác): Naomi không kẹt giữa phản ứng. */
async function recovery(browser) {
  const { context, page } = await newPage(browser);
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  const card = page.locator('[data-testid="mood-celebrate"]');
  await card.scrollIntoViewIfNeeded();
  await page.locator('[data-testid="play-celebrate"]').click();
  await page.waitForFunction(() => document.querySelector('[data-testid="mood-celebrate"] [data-phase]')?.dataset.phase === "playing");
  const t0 = Date.now();
  await card.evaluate((el) => el.getAnimations({ subtree: true }).forEach((a) => a.cancel()));
  await page.waitForFunction(() => document.querySelector('[data-testid="mood-celebrate"] [data-phase]')?.dataset.phase !== "playing", null, { timeout: 8000 });
  const out = { recoveredAfterMs: Date.now() - t0, phase: await phaseOf(page, "celebrate").getAttribute("data-phase") };
  await context.close();
  return out;
}

/** Luồng nộp bài thu nhỏ: thanh laptop sáng theo k/n, rồi verdict cùng mã bài nộp. */
async function gradingFlow(browser) {
  const { context, page } = await newPage(browser);
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  await page.locator('[data-testid="flow-ac"]').click();
  const lit = [];
  for (let i = 0; i < 9; i++) {
    lit.push(
      await page.locator('[data-testid="flow"]').evaluate((el) => ({
        mood: el.querySelector("[data-mood]")?.getAttribute("data-mood"),
        lit: [...el.querySelectorAll("[data-seg]")].filter((s) => s.getAttribute("fill") === "var(--color-green-600)").length,
      })),
    );
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(3000);
  const end = await page.locator('[data-testid="flow"] [data-phase]').evaluate((el) => ({ mood: el.dataset.mood, phase: el.dataset.phase }));
  const role = await page.locator('[data-testid="flow"] [data-mascot]').evaluate((el) => ({ role: el.getAttribute("role"), label: el.getAttribute("aria-label") }));
  await context.close();
  return { samples: lit, end, accessible: role };
}

/** Khung hình chính xác: dừng mọi animation của thẻ, đặt currentTime, chụp. */
async function frames(browser) {
  fs.rmSync(FRAMES, { recursive: true, force: true });
  fs.mkdirSync(FRAMES, { recursive: true });
  const { context, page } = await newPage(browser);
  await page.goto(`${BASE}/dev/naomi`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "lg", exact: true }).click();
  await page.locator("main ul").screenshot({ path: path.join(HERE, "grid.png") });
  const shots = {};
  for (const mood of MOODS) {
    const card = page.locator(`[data-testid="mood-${mood}"]`);
    const stage = card.locator("div").first();
    await card.scrollIntoViewIfNeeded();
    await page.locator(`[data-testid="play-${mood}"]`).click();
    await page.waitForFunction((m) => document.querySelector(`[data-testid="mood-${m}"] [data-phase]`)?.getAttribute("data-phase") === "playing", mood);
    await card.evaluate((el) => el.getAnimations({ subtree: true }).forEach((a) => a.pause()));
    shots[mood] = [];
    for (const t of TIMES) {
      await card.evaluate((el, t) => el.getAnimations({ subtree: true }).forEach((a) => (a.currentTime = t)), t);
      await page.waitForTimeout(40);
      const file = path.join(FRAMES, `${mood}-${t}.png`);
      await stage.screenshot({ path: file });
      shots[mood].push(file);
    }
    // Chrome không báo `finished` cho animation đang dừng bị tua quá điểm cuối,
    // nên Naomi về tư thế tĩnh nhờ hẹn giờ dự phòng của component (≤ endsAt + 1 s).
    await card.evaluate((el) => el.getAnimations({ subtree: true }).forEach((a) => a.finish()));
    await page
      .waitForFunction((m) => document.querySelector(`[data-testid="mood-${m}"] [data-phase]`)?.getAttribute("data-phase") !== "playing", mood, { timeout: 8000 })
      .catch((e) => {
        throw new Error(`${mood}: vẫn đang phản ứng sau finish() — ${e.message}`);
      });
    const after = path.join(FRAMES, `${mood}-sau.png`);
    await stage.screenshot({ path: after });
    shots[mood].push(after);
  }
  // Ba bảng, mỗi bảng 10 mood × (6 mốc + sau phản ứng).
  const heads = [...TIMES.map((t) => `${t} ms`), "sau"];
  for (let s = 0; s * 10 < MOODS.length; s++) {
    const rows = MOODS.slice(s * 10, s * 10 + 10)
      .map((m) => `<tr><th>${m}</th>${shots[m].map((f) => `<td><img src="data:image/png;base64,${fs.readFileSync(f).toString("base64")}"></td>`).join("")}</tr>`)
      .join("");
    const html = `<style>body{margin:0;font:12px ui-monospace,monospace}table{border-collapse:collapse}td,th{border:1px solid #dde;padding:2px}th{padding:4px 8px;text-align:right}img{width:150px;display:block}</style><table><tr><th></th>${heads.map((h) => `<th style="text-align:center">${h}</th>`).join("")}</tr>${rows}</table>`;
    const sheet = await context.newPage();
    await sheet.setContent(html, { waitUntil: "load" });
    await sheet.locator("table").screenshot({ path: path.join(FRAMES, `sheet-${s + 1}.png`) });
    await sheet.close();
  }
  for (const list of Object.values(shots)) for (const f of list) fs.unlinkSync(f);
  await context.close();
}

// --- main ---------------------------------------------------------------------

async function main() {
  const { chromium } = require("@playwright/test");
  const results = { measuredAt: new Date().toISOString(), moods: MOODS.length };
  stageMeasurePages();
  let server;
  try {
    if (!args.has("--skip-build")) build();
    results.firstLoad = await firstLoad();
    results.artChunks = artChunks();
    log(`First Load JS Δ ${results.firstLoad.deltaGzipKB} KB; chunk hình ${results.artChunks.minKB}–${results.artChunks.maxKB} KB gzip`);
    server = await serve();
    results.serverHtml = await serverHtml();
    const browser = await chromium.launch({ channel: "chrome" });
    try {
      results.transfer = await transfer(browser);
      log(`JS tải thật Δ ${results.transfer.deltaGzipKB} KB`);
      results.reactions = await reactions(browser);
      results.reducedMotion = await reducedMotion(browser);
      results.lazy = await lazy(browser);
      results.clickThrough = await clickThrough(browser);
      results.recovery = await recovery(browser);
      results.gradingFlow = await gradingFlow(browser);
      await frames(browser);
    } finally {
      await browser.close();
    }
  } finally {
    if (server) server.kill();
    if (!args.has("--keep")) removeMeasurePages();
  }
  fs.writeFileSync(path.join(HERE, "results.json"), JSON.stringify(results, null, 2) + "\n");
  const r = results.reactions.rows;
  log(`phản ứng dài nhất ${Math.max(...Object.values(r).map((x) => x.reactionMs))} ms; vi phạm CSP ${results.reactions.violations.length}; lỗi ${results.reactions.problems.length}`);
  log(`giảm chuyển động: animation ${results.reducedMotion.anyAnimation}, lớp dịch ${results.reducedMotion.anyLayerMoved}, pha ${results.reducedMotion.phases}`);
  log("đã ghi results.json");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
