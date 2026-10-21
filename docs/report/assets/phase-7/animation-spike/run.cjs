/**
 * Spike công nghệ hoạt ảnh (Phase 7): cùng một phản ứng `celebrate` của Naomi
 * bằng bốn cách, đo dung lượng tải, CPU, CSP và kiểm prefers-reduced-motion.
 *
 *   static  SVG tĩnh trong cùng khung — mốc để trừ
 *   css     CSS keyframes sinh từ choreography.json, không JS riêng
 *   mini    motion/react-mini (Web Animations API, ~WAAPI)
 *   motion  motion/react đầy đủ (animate() lai, giá trị transform độc lập)
 *
 * Chạy từ gốc repo, stack nào cũng không cần (trang spike không gọi API):
 *
 *   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/animation-spike/run.cjs
 *
 * Script chép src/ vào frontend/app/(spike)/spike-naomi, sinh _gen/ (SVG có lớp
 * bọc, easing, CSS), `next build` trên máy, đo, `next start` ở 127.0.0.1:3107,
 * đo bằng Chrome (Playwright, channel chrome), rồi XÓA thư mục spike khỏi
 * frontend. `motion` cài bằng `npm install --no-save` (không vào package.json).
 * Cờ: --keep (giữ thư mục spike để xem tay), --skip-build (dùng .next có sẵn),
 * --sheet (chỉ ghép lại frames/contact-sheet.png từ ảnh đã chụp).
 *
 * Kết quả: results.json, build.log, frames/<variant>-<ms>.png cạnh script này.
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
const TARGET = path.join(FRONTEND, "app", "(spike)", "spike-naomi");
const GROUP = path.dirname(TARGET);
const MOODS = path.join(REPO, "docs", "ui-ux", "mascot", "naomi", "moods");
const TOKENS = path.join(REPO, "docs", "ui-ux", "design-system", "project", "tokens.json");
const CSP_CONF = path.join(REPO, "infra", "nginx", "snippets", "security-headers.conf");
const FRAMES = path.join(HERE, "frames");

const MOTION_VERSION = "14.2.0";
const PORT = 3107;
const BASE = `http://127.0.0.1:${PORT}`;
const VARIANTS = ["static", "css", "mini", "motion"];
const ANIMATED = VARIANTS.filter((v) => v !== "static");
const RUNS = 7; // lượt đo mỗi biến thể mỗi mức bóp CPU
const WINDOW_MS = 3000; // phản ứng 2400 ms + đổi về tư thế nghỉ 220 ms + dư
const THROTTLE = [1, 4]; // 4 = mức Lighthouse dùng cho mobile
const SHOTS = [250, 700, 1100, 1800, 2900];

const args = new Set(process.argv.slice(2));
const log = (...m) => console.log(`[spike ${new Date().toISOString().slice(11, 19)}]`, ...m);
const gzip = (buf) => zlib.gzipSync(buf, { level: 9 }).length;
const choreography = JSON.parse(fs.readFileSync(path.join(HERE, "src", "choreography.json"), "utf8"));

// --- 1. sinh _gen ------------------------------------------------------------

/** Lớp bọc cho những phần tử có thuộc tính transform riêng: transform của CSS
 *  THAY thuộc tính transform của SVG chứ không cộng vào, nên #naomi
 *  (translate 0 -8) và từng ngôi sao (translate + scale đặt chỗ) cần một <g>
 *  trống bên ngoài để làm chuyển động. */
function celebrateMarkup() {
  let svg = fs.readFileSync(path.join(MOODS, "naomi-celebrate.svg"), "utf8").replace(/<!--[\s\S]*?-->\s*/g, "");
  if (!svg.includes('<g id="naomi" transform="translate(0 -8)">')) throw new Error("celebrate: #naomi đổi dạng, sửa run.cjs");
  svg = svg.replace('<g id="naomi"', '<g id="jump"><g id="naomi"');
  const close = svg.lastIndexOf("</g>");
  svg = `${svg.slice(0, close)}</g></g>${svg.slice(close + 4)}`;
  let sparks = 0;
  svg = svg.replace(/(<g id="scene">)([\s\S]*?)(<\/g>)/, (_, open, body, end) => {
    const wrapped = body.replace(/<path [^>]*\/>/g, (p) => {
      sparks += 1;
      return `<g class="spark">${p}</g>`;
    });
    return open + wrapped + end;
  });
  if (sparks === 0) throw new Error("celebrate: không thấy ngôi sao nào trong #scene");
  return { svg, sparks };
}

/** Tư thế nghỉ nằm cùng trang với celebrate: đổi id để hai bản vẽ không trùng. */
function restMarkup() {
  return fs
    .readFileSync(path.join(MOODS, "naomi-rest.svg"), "utf8")
    .replace(/<!--[\s\S]*?-->\s*/g, "")
    .replace(/ id="([^"]+)"/g, ' id="rest-$1"');
}

function easingTokens() {
  const tokens = JSON.parse(fs.readFileSync(TOKENS, "utf8")).easing.tokens;
  return Object.fromEntries(
    tokens.map((t) => {
      const m = /^cubic-bezier\(([^)]+)\)$/.exec(t.value);
      if (!m) throw new Error(`easing ${t.name}: không phải cubic-bezier`);
      return [t.name, m[1].split(",").map(Number)];
    }),
  );
}

const CEL = '[data-part="celebrate"]';
const layerSel = (t) => (t.layer === "spark" ? `${CEL} .spark` : `${CEL} #${t.layer}`);
const cubic = (list) => `cubic-bezier(${list.join(", ")})`;

function spikeCss() {
  const lines = [
    "/* Sinh bởi run.cjs từ choreography.json. */",
    '.naomi [data-part="rest"] { opacity: 0; }',
    // viewBox 200x200 xén mọi thứ ra ngoài khung: cú nhảy 30 đơn vị mất đỉnh đầu.
    ".naomi svg { overflow: visible; }",
  ];
  for (const t of choreography.tracks) {
    const origin = t.origin === "center" ? "fill-box; transform-origin: 50% 50%" : `view-box; transform-origin: ${t.origin[0]}px ${t.origin[1]}px`;
    lines.push(`.naomi ${layerSel(t)} { transform-box: ${origin}; }`);
  }
  lines.push("@media (prefers-reduced-motion: no-preference) {", `  .naomi[data-playing] ${CEL} .spark { opacity: 0; }`, "}");
  return `${lines.join("\n")}\n`;
}

function keyframesCss(ease, sparks) {
  const out = ["/* Sinh bởi run.cjs từ choreography.json. Biến thể css: không JS. */"];
  const rules = [];
  for (const t of choreography.tracks) {
    const name = `naomi-${t.layer}`;
    out.push(`@keyframes ${name} {`);
    t.times.forEach((time, i) => {
      const decl = [];
      if (t.y) decl.push(`translate: 0px ${t.y[i]}px`);
      if (t.scale) decl.push(`scale: ${t.scale[i]}`);
      else if (t.scaleX || t.scaleY) decl.push(`scale: ${t.scaleX ? t.scaleX[i] : 1} ${t.scaleY ? t.scaleY[i] : 1}`);
      if (t.rotate) decl.push(`rotate: ${t.rotate[i]}deg`);
      if (t.opacity) decl.push(`opacity: ${t.opacity[i]}`);
      if (i < t.ease.length) decl.push(`animation-timing-function: ${cubic(ease[t.ease[i]])}`);
      out.push(`  ${+(time * 100).toFixed(3)}% { ${decl.join("; ")}; }`);
    });
    out.push("}");
    if (t.stagger) {
      for (let i = 0; i < sparks; i++) {
        rules.push(`  .naomi[data-playing] ${CEL} .spark:nth-child(${i + 1}) { animation: ${name} ${t.duration}ms ${t.delay + i * t.stagger}ms both; }`);
      }
    } else {
      rules.push(`  .naomi[data-playing] ${layerSel(t)} { animation: ${name} ${t.duration}ms ${t.delay}ms both; }`);
    }
  }
  const swap = `${choreography.swapMs}ms ${cubic(ease[choreography.swapEase])} ${choreography.swapAtMs}ms both`;
  out.push("@keyframes naomi-swap-out { from { opacity: 1; } to { opacity: 0; } }");
  out.push("@keyframes naomi-swap-in { from { opacity: 0; } to { opacity: 1; } }");
  rules.push(`  .naomi[data-playing] ${CEL} { animation: naomi-swap-out ${swap}; }`);
  rules.push(`  .naomi[data-playing] [data-part="rest"] { animation: naomi-swap-in ${swap}; }`);
  out.push("@media (prefers-reduced-motion: no-preference) {", ...rules, "}");
  return `${out.join("\n")}\n`;
}

function generate() {
  if (fs.existsSync(TARGET)) throw new Error(`${TARGET} đã có — lượt trước chưa dọn? Xóa tay rồi chạy lại.`);
  fs.cpSync(path.join(HERE, "src"), TARGET, { recursive: true });
  const gen = path.join(TARGET, "_gen");
  fs.mkdirSync(gen, { recursive: true });
  const { svg, sparks } = celebrateMarkup();
  const ease = easingTokens();
  fs.writeFileSync(
    path.join(gen, "naomi.ts"),
    `// Sinh bởi run.cjs từ docs/ui-ux/mascot/naomi/moods.\nexport const CELEBRATE = ${JSON.stringify(svg)};\nexport const REST = ${JSON.stringify(restMarkup())};\n`,
  );
  fs.writeFileSync(
    path.join(gen, "easing.ts"),
    `// Sinh bởi run.cjs từ tokens.json.\nexport const EASE: Record<string, [number, number, number, number]> = ${JSON.stringify(ease)};\n`,
  );
  fs.writeFileSync(path.join(gen, "spike.css"), spikeCss());
  fs.writeFileSync(path.join(gen, "keyframes.css"), keyframesCss(ease, sparks));
  log(`đã chép spike vào ${path.relative(REPO, TARGET)} (${sparks} ngôi sao)`);
}

// --- 2. build + First Load JS ---------------------------------------------------

function ensureMotion() {
  const pkg = path.join(FRONTEND, "node_modules", "motion", "package.json");
  const have = fs.existsSync(pkg) ? JSON.parse(fs.readFileSync(pkg, "utf8")).version : null;
  if (have === MOTION_VERSION) return;
  log(`cài motion@${MOTION_VERSION} (--no-save; đang có: ${have ?? "không"})`);
  execSync(`npm install --no-save --no-audit --no-fund motion@${MOTION_VERSION}`, { cwd: FRONTEND, stdio: "inherit" });
}

function build() {
  log("next build …");
  const started = Date.now();
  const outLog = execSync("npx next build", {
    cwd: FRONTEND,
    // API_BASE_URL rỗng = cùng origin, đúng như image production (lib/api/client.ts);
    // để mặc định thì lệnh refresh phiên đi tới localhost:8000 và vi phạm connect-src.
    env: { ...process.env, NEXT_PUBLIC_SITE_URL: BASE, NEXT_PUBLIC_API_BASE_URL: "", NEXT_TELEMETRY_DISABLED: "1" },
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  fs.writeFileSync(path.join(HERE, "build.log"), outLog);
  log(`build xong sau ${((Date.now() - started) / 1000).toFixed(0)} s`);
}

async function bundleStats() {
  const distDir = path.join(FRONTEND, ".next");
  const read = (file) => JSON.parse(fs.readFileSync(path.join(distDir, file), "utf8"));
  const routes = VARIANTS.map((v) => `/spike-naomi/${v}`);
  const { writeRouteBundleStats } = require(path.join(FRONTEND, "node_modules", "next", "dist", "build", "route-bundle-stats"));
  await writeRouteBundleStats({ pages: [], app: routes }, read("build-manifest.json"), distDir, FRONTEND);
  const rows = read(path.join("diagnostics", "route-bundle-stats.json"));
  return Object.fromEntries(
    VARIANTS.map((v) => {
      const row = rows.find((r) => r.route === `/spike-naomi/${v}`);
      if (!row) throw new Error(`route-bundle-stats thiếu /spike-naomi/${v}`);
      return [
        v,
        {
          chunks: row.firstLoadChunkPaths.length,
          rawBytes: row.firstLoadUncompressedJsBytes,
          gzipBytes: row.firstLoadChunkPaths.reduce((n, f) => n + gzip(fs.readFileSync(path.join(FRONTEND, f))), 0),
          files: row.firstLoadChunkPaths.map((f) => path.basename(f)),
        },
      ];
    }),
  );
}

// --- 3. server --------------------------------------------------------------

function get(url) {
  return new Promise((resolve) => {
    http.get(url, (res) => (res.resume(), resolve(res.statusCode))).on("error", () => resolve(0));
  });
}

async function serve() {
  const child = spawn(process.execPath, [path.join(FRONTEND, "node_modules", "next", "dist", "bin", "next"), "start", "-p", String(PORT), "-H", "127.0.0.1"], {
    cwd: FRONTEND,
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.on("data", (d) => (output += d));
  child.stderr.on("data", (d) => (output += d));
  for (let i = 0; i < 120; i++) {
    if ((await get(`${BASE}/spike-naomi/static`)) === 200) return child;
    if (child.exitCode !== null) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  child.kill();
  throw new Error(`next start không lên:\n${output}`);
}

// --- 4. Chrome --------------------------------------------------------------

function cspHeader() {
  const m = /add_header Content-Security-Policy "([^"]+)" always;/.exec(fs.readFileSync(CSP_CONF, "utf8"));
  if (!m) throw new Error("không đọc được CSP trong security-headers.conf");
  return m[1];
}

/** Chính policy production lên mọi tài liệu HTML, cộng bộ đếm vi phạm. */
async function newPage(browser, options = {}) {
  const context = await browser.newContext({ viewport: { width: 800, height: 600 }, ...options });
  const page = await context.newPage();
  const csp = cspHeader();
  await page.route("**/*", async (route) => {
    // Không có backend: trả lời refresh như với một khách chưa đăng nhập.
    if (new URL(route.request().url()).pathname === "/api/v1/auth/refresh") {
      return route.fulfill({ status: 401, contentType: "application/json", body: '{"code":"NOT_AUTHENTICATED","message":"spike"}' });
    }
    if (route.request().resourceType() !== "document") return route.continue();
    const response = await route.fetch();
    await route.fulfill({ response, headers: { ...response.headers(), "content-security-policy": csp } });
  });
  await page.addInitScript(() => {
    window.__violations = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      window.__violations.push({ directive: e.effectiveDirective, blocked: e.blockedURI, sample: e.sample }),
    );
  });
  const problems = [];
  page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  return { context, page, problems };
}

async function open(page, variant) {
  await page.goto(`${BASE}/spike-naomi/${variant}`, { waitUntil: "load" });
  await page.waitForFunction(() => {
    const b = document.querySelector('[data-testid="replay"]');
    return b && Object.keys(b).some((k) => k.startsWith("__reactProps"));
  });
}

/** Nhấn "Phát lại" và ghi khung rAF trong cùng một lượt evaluate. */
function playAndRecord(page, click) {
  return page.evaluate(
    ({ ms, click }) =>
      new Promise((resolve) => {
        const stamps = [];
        const t0 = performance.now();
        const frame = (now) => {
          stamps.push(now);
          if (now - t0 < ms) requestAnimationFrame(frame);
          else resolve(stamps);
        };
        requestAnimationFrame(frame);
        if (click) document.querySelector('[data-testid="replay"]').click();
      }),
    { ms: WINDOW_MS, click },
  );
}

const pick = (metrics) => Object.fromEntries(metrics.map((m) => [m.name, m.value]));
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};
const ms = (s) => +(s * 1000).toFixed(2);

function frameSummary(stamps) {
  const gaps = stamps.slice(1).map((t, i) => t - stamps[i]);
  const sorted = [...gaps].sort((a, b) => a - b);
  return {
    frames: gaps.length,
    p95: +sorted[Math.floor(sorted.length * 0.95)].toFixed(1),
    max: +sorted[sorted.length - 1].toFixed(1),
    over25: gaps.filter((g) => g > 25).length,
  };
}

async function cpu(browser, variant, rate) {
  const { context, page, problems } = await newPage(browser);
  const cdp = await context.newCDPSession(page);
  await cdp.send("Performance.enable", { timeDomain: "threadTicks" });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate });
  await open(page, variant);
  await page.waitForTimeout(WINDOW_MS); // phản ứng lúc mount chạy hết
  await playAndRecord(page, true); // lượt làm nóng, bỏ
  const runs = [];
  for (const click of [...Array(RUNS).fill(true), false, false, false]) {
    const before = pick((await cdp.send("Performance.getMetrics")).metrics);
    const stamps = await playAndRecord(page, click);
    const after = pick((await cdp.send("Performance.getMetrics")).metrics);
    const d = (k) => after[k] - before[k];
    runs.push({
      click,
      task: ms(d("TaskDuration")),
      script: ms(d("ScriptDuration")),
      style: ms(d("RecalcStyleDuration")),
      layout: ms(d("LayoutDuration")),
      styleCount: d("RecalcStyleCount"),
      ...frameSummary(stamps),
    });
  }
  await context.close();
  const played = runs.filter((r) => r.click);
  const idle = runs.filter((r) => !r.click);
  const med = (list, k) => +median(list.map((r) => r[k])).toFixed(2);
  return {
    rate,
    median: Object.fromEntries(["task", "script", "style", "layout", "styleCount", "frames", "p95", "max", "over25"].map((k) => [k, med(played, k)])),
    idle: Object.fromEntries(["task", "script", "style", "frames"].map((k) => [k, med(idle, k)])),
    runs,
    problems,
  };
}

/** Dung lượng thật trình duyệt tải: mở trang, chờ, phát lại một lần. */
async function transfer(browser, variant) {
  const { context, page, problems } = await newPage(browser);
  const files = [];
  page.on("response", async (res) => {
    const type = res.request().resourceType();
    if (type !== "script" && type !== "stylesheet") return;
    try {
      const body = await res.body();
      files.push({ type, url: new URL(res.url()).pathname, raw: body.length, gzip: gzip(body) });
    } catch {
      /* chuyển hướng / hủy */
    }
  });
  await open(page, variant);
  await page.waitForTimeout(1500);
  await playAndRecord(page, true);
  const sum = (type, key) => files.filter((f) => f.type === type).reduce((n, f) => n + f[key], 0);
  const violations = await page.evaluate(() => window.__violations);
  await context.close();
  return {
    js: { files: files.filter((f) => f.type === "script").length, raw: sum("script", "raw"), gzip: sum("script", "gzip") },
    css: { files: files.filter((f) => f.type === "stylesheet").length, raw: sum("stylesheet", "raw"), gzip: sum("stylesheet", "gzip") },
    files,
    violations,
    problems,
  };
}

/** Cái gì đang chạy giữa phản ứng: WAAPI hay JS, điểm xoay có giữ không. */
async function inspect(browser, variant) {
  const { context, page } = await newPage(browser);
  await open(page, variant);
  await page.waitForTimeout(WINDOW_MS);
  await page.evaluate(() => document.querySelector('[data-testid="replay"]').click());
  await page.waitForTimeout(800);
  const mid = await page.evaluate(() => {
    const cel = '[data-part="celebrate"]';
    const el = (s) => document.querySelector(`${cel} ${s}`);
    const style = (s) => {
      const e = el(s);
      const c = getComputedStyle(e);
      return { inline: e.getAttribute("style"), transformBox: c.transformBox, transformOrigin: c.transformOrigin, transform: c.transform, rotate: c.rotate };
    };
    return {
      animations: document.getAnimations().map((a) => ({
        type: a.constructor.name,
        target: a.effect?.target?.id || a.effect?.target?.getAttribute("class") || a.effect?.target?.dataset?.part || "?",
        props: Object.keys(a.effect.getKeyframes()[0] ?? {}).filter((k) => !["offset", "easing", "composite", "computedOffset"].includes(k)),
      })),
      jump: style("#jump"),
      arm: style("#arm-left"),
      // Điểm xoay đúng thì vai (126,126 trong bản vẽ) đứng yên khi tay vẫy:
      // so tâm khung bao của tay với lúc nghỉ.
      shoulder: (() => {
        const r = el("#arm-left-limb").getBoundingClientRect();
        return { left: +r.left.toFixed(1), bottom: +r.bottom.toFixed(1) };
      })(),
    };
  });
  await context.close();
  return mid;
}

async function shots(browser, variant) {
  fs.mkdirSync(FRAMES, { recursive: true });
  const { context, page } = await newPage(browser, { deviceScaleFactor: 2 });
  await open(page, variant);
  await page.waitForTimeout(WINDOW_MS);
  for (const at of SHOTS) {
    await page.evaluate(() => document.querySelector('[data-testid="replay"]').click());
    await page.waitForTimeout(at);
    await page.locator('[data-testid="mascot"]').screenshot({ path: path.join(FRAMES, `${variant}-${at}.png`) });
    await page.waitForTimeout(WINDOW_MS - at);
  }
  await context.close();
}

/** prefers-reduced-motion: reduce → không gì di chuyển, đứng ở tư thế celebrate. */
async function reducedMotion(browser, variant) {
  const { context, page, problems } = await newPage(browser, { reducedMotion: "reduce" });
  await open(page, variant);
  const samples = await page.evaluate(
    (ms) =>
      new Promise((resolve) => {
        document.querySelector('[data-testid="replay"]').click();
        const out = [];
        const t0 = performance.now();
        const tick = () => {
          const cel = '[data-part="celebrate"]';
          const c = (s) => getComputedStyle(document.querySelector(s));
          const moved = ["#jump", "#arm-left", "#tail", "#shadow", ".spark"].some((s) => {
            const st = c(`${cel} ${s}`);
            return st.transform !== "none" || st.translate !== "none" || st.scale !== "none" || st.rotate !== "none";
          });
          out.push({
            t: Math.round(performance.now() - t0),
            running: document.getAnimations().filter((a) => a.playState === "running").length,
            moved,
            celebrate: +c(cel).opacity,
            rest: +c('[data-part="rest"]').opacity,
            spark: +c(`${cel} .spark`).opacity,
          });
          if (performance.now() - t0 < ms) setTimeout(tick, 100);
          else resolve(out);
        };
        tick();
      }),
    WINDOW_MS,
  );
  await page.locator('[data-testid="mascot"]').screenshot({ path: path.join(FRAMES, `${variant}-reduced.png`) });
  await context.close();
  return {
    samples: samples.length,
    anyRunning: samples.some((s) => s.running > 0),
    anyMoved: samples.some((s) => s.moved),
    celebrateAlwaysShown: samples.every((s) => s.celebrate === 1 && s.spark === 1),
    restNeverShown: samples.every((s) => s.rest === 0),
    problems,
  };
}

/** Một tấm ảnh: mỗi hàng một biến thể, mỗi cột một thời điểm, cột cuối reduced. */
async function contactSheet(browser) {
  const img = (file) => `data:image/png;base64,${fs.readFileSync(path.join(FRAMES, file)).toString("base64")}`;
  const cols = [...SHOTS.map((at) => [`${at} ms`, `${at}`]), ["reduced", "reduced"]];
  const head = cols.map(([label]) => `<th>${label}</th>`).join("");
  const rows = ANIMATED.map(
    (v) => `<tr><th>${v}</th>${cols.map(([, key]) => `<td><img src="${img(`${v}-${key}.png`)}"></td>`).join("")}</tr>`,
  ).join("");
  const html = `<!doctype html><meta charset="utf-8"><style>
    body { margin: 16px; font: 14px system-ui, sans-serif; background: #fff; }
    table { border-collapse: collapse; } th { padding: 4px 8px; font-weight: 600; }
    td { border: 1px solid #e3eaee; padding: 0; } img { width: 150px; display: block; }
  </style><table><tr><th></th>${head}</tr>${rows}</table>`;
  const page = await browser.newPage({ viewport: { width: 1100, height: 600 }, deviceScaleFactor: 1 });
  await page.setContent(html, { waitUntil: "load" });
  await page.locator("table").screenshot({ path: path.join(FRAMES, "contact-sheet.png") });
  await page.close();
}

// --- 5. công làm -------------------------------------------------------------

function effort() {
  const lines = (file) =>
    fs
      .readFileSync(path.join(HERE, "src", file), "utf8")
      .split("\n")
      .filter((l) => l.trim() && !l.trim().startsWith("//") && !l.trim().startsWith("*") && !l.trim().startsWith("/*")).length;
  const runSrc = fs.readFileSync(__filename, "utf8");
  const fn = (name) => {
    const start = runSrc.indexOf(`function ${name}(`);
    const end = runSrc.indexOf("\n}\n", start);
    return runSrc.slice(start, end).split("\n").filter((l) => l.trim() && !l.trim().startsWith("//")).length + 1;
  };
  return {
    note: "Số dòng mã (bỏ dòng trống + chú thích). Phần chung (khung, SVG bọc lớp, CSS điểm xoay) mọi biến thể đều cần.",
    shared: { "naomi-frame.tsx": lines("_parts/naomi-frame.tsx"), "spikeCss()": fn("spikeCss"), "celebrateMarkup()": fn("celebrateMarkup") },
    css: { "keyframesCss()": fn("keyframesCss") },
    mini: { "naomi-mini.tsx": lines("_parts/naomi-mini.tsx"), "tracks.ts": lines("_parts/tracks.ts") },
    motion: { "naomi-motion.tsx": lines("_parts/naomi-motion.tsx"), "tracks.ts": lines("_parts/tracks.ts") },
  };
}

// --- main -------------------------------------------------------------------

async function main() {
  const { chromium } = require("playwright");
  if (args.has("--sheet")) {
    const browser = await chromium.launch({ channel: "chrome" });
    await contactSheet(browser);
    await browser.close();
    log("đã ghép frames/contact-sheet.png");
    return;
  }
  const result = {
    date: new Date().toISOString(),
    commit: execSync("git rev-parse --short HEAD", { cwd: REPO, encoding: "utf8" }).trim(),
    motion: MOTION_VERSION,
    next: require(path.join(FRONTEND, "node_modules", "next", "package.json")).version,
    chrome: null,
    csp: cspHeader(),
    choreography,
  };
  let server;
  let browser;
  try {
    if (!args.has("--skip-build")) {
      ensureMotion();
      generate();
      build();
    }
    result.firstLoad = await bundleStats();
    server = await serve();
    browser = await chromium.launch({ channel: "chrome" });
    result.chrome = browser.version();
    result.transfer = {};
    for (const v of VARIANTS) result.transfer[v] = await transfer(browser, v);
    log("dung lượng xong");
    result.inspect = {};
    for (const v of ANIMATED) result.inspect[v] = await inspect(browser, v);
    result.reduced = {};
    for (const v of ANIMATED) result.reduced[v] = await reducedMotion(browser, v);
    log("reduced-motion xong");
    for (const v of ANIMATED) await shots(browser, v);
    await contactSheet(browser);
    log("ảnh khung xong");
    result.cpu = {};
    for (const rate of THROTTLE) {
      for (const v of VARIANTS) {
        result.cpu[`${v}@${rate}x`] = await cpu(browser, v, rate);
        log(`cpu ${v}@${rate}x: task ${result.cpu[`${v}@${rate}x`].median.task} ms`);
      }
    }
    result.effort = effort();
  } finally {
    if (browser) await browser.close();
    if (server) server.kill();
    if (!args.has("--keep") && fs.existsSync(TARGET)) {
      fs.rmSync(GROUP, { recursive: true, force: true });
      log(`đã xóa ${path.relative(REPO, GROUP)}`);
    }
  }
  fs.writeFileSync(path.join(HERE, "results.json"), `${JSON.stringify(result, null, 2)}\n`);
  summary(result);
}

function summary(r) {
  const kb = (b) => (b / 1024).toFixed(1);
  const base = r.transfer.static;
  console.log("\nbiến thể | First Load JS gzip | Δ JS tải thật | Δ CSS | CSP | reduced");
  for (const v of VARIANTS) {
    const t = r.transfer[v];
    const red = r.reduced?.[v];
    console.log(
      `${v.padEnd(7)} | ${kb(r.firstLoad[v].gzipBytes)} KB | ${kb(t.js.gzip - base.js.gzip)} KB | ${kb(t.css.gzip - base.css.gzip)} KB | ${t.violations.length} vi phạm | ${red ? (red.anyMoved || red.anyRunning ? "ĐỘNG" : "tĩnh") : "—"}`,
    );
  }
  console.log("\nCPU luồng chính mỗi lần phản ứng (trung vị, ms) — task / script / style");
  for (const key of Object.keys(r.cpu)) {
    const m = r.cpu[key].median;
    console.log(`${key.padEnd(10)} ${m.task} / ${m.script} / ${m.style} — khung ${m.frames}, p95 ${m.p95} ms, >25ms: ${m.over25}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
