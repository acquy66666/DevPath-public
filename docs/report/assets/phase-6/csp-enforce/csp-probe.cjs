/**
 * Content-Security-Policy trên một stack production đang chạy: đi qua mọi vai
 * (khách, học viên mới, giảng viên, admin) bằng Chrome thật, ghi lại mọi vi
 * phạm CSP trình duyệt báo -- cả khi header còn là Report-Only lẫn khi đã
 * enforce -- và kiểm từng thứ dễ bị CSP làm hỏng thật sự còn chạy: video HLS
 * phát được, Monaco + worker, trợ giảng AI trả lời qua SSE, ảnh đại diện PUT
 * thẳng lên bucket bằng URL ký sẵn, sang VNPay, sang Google, PDF chứng chỉ.
 *
 *   cd infra && set -a && . ./.env.seed-demo && set +a && cd ..
 *   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/csp-enforce/csp-probe.cjs
 *
 * Luồng vàng (đăng ký → mua → học → nộp code qua WebSocket → chứng chỉ) là
 * việc của E2E (`frontend/e2e/golden-flow.spec.ts`), spec đó cũng đỏ khi có
 * vi phạm; script này phủ phần còn lại của site.
 *
 * Biến môi trường:
 *   BASE_URL           mặc định https://devpath-01.me
 *   SEED_ADMIN_PASSWORD, SEED_INSTRUCTOR_PASSWORD   tài khoản seed của stack
 *   COMPOSE_PROJECT    mặc định devpath-demo -- tìm container để đọc một mã
 *                      chứng chỉ và dọn bằng scripts.purge_e2e
 *   LABEL              tên lượt chạy, thành tên tệp kết quả (mặc định "run")
 *   CHROME_CHANNEL     mặc định "chrome"; "" = Chromium của Playwright
 *   HEADED=1           có cửa sổ
 *
 * Ghi dữ liệu: một học viên dùng một lần (@e2e.devpath.example) ghi danh khóa
 * Python miễn phí, hỏi trợ giảng một câu (một lượt Gemini), đổi ảnh đại diện,
 * tạo một đơn chờ thanh toán; scripts.purge_e2e xóa sạch ở cuối. Giảng viên
 * và admin seed chỉ xem, phiên của họ bị thu hồi khi xong.
 */
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");

const { chromium } = require("@playwright/test");

const BASE = (process.env.BASE_URL ?? "https://devpath-01.me").replace(/\/$/, "");
const PROJECT = process.env.COMPOSE_PROJECT ?? "devpath-demo";
const LABEL = process.env.LABEL ?? "run";
const CHANNEL = process.env.CHROME_CHANNEL ?? "chrome";
const PYTHON = "python-co-ban-cho-nguoi-moi-bat-dau";
const VNPAY = /^https:\/\/sandbox\.vnpayment\.vn\//;
/**
 * Beacon analytics của Cloudflare: edge của Cloudflare tự chèn vào mọi trang
 * của zone bật RUM (zone Free bật sẵn). Không phải của site, và policy chặn nó
 * là đúng ý (infra/nginx/snippets/security-headers.conf) -- nên đếm riêng,
 * không tính là vi phạm của site. Tắt RUM trong dashboard thì nó biến mất.
 */
const EDGE_BEACON = /https:\/\/static\.cloudflareinsights\.com\/beacon/;
const fromEdge = (v) => EDGE_BEACON.test(v.blockedURI ?? "") || EDGE_BEACON.test(v.text ?? "");
const ACCOUNTS = {
  instructor: {
    email: "khoa.tran@devpath.example",
    password: process.env.SEED_INSTRUCTOR_PASSWORD ?? "devpath-instructor",
  },
  admin: {
    email: "admin@devpath.example",
    password: process.env.SEED_ADMIN_PASSWORD ?? "devpath-admin",
  },
};

const steps = [];
const violations = [];
const pageErrors = [];
const policies = new Map();
let current = "(chưa vào bước nào)";

function log(...parts) {
  console.log(new Date().toISOString().slice(11, 19), ...parts);
}

// --- Thu vi phạm ------------------------------------------------------------

/**
 * Ba đường, vì không đường nào tự nó đủ: sự kiện `securitypolicyviolation`
 * cho chi tiết (chỉ thị, URI bị chặn, Report-Only hay enforce), console của
 * trang cho những gì trình duyệt tự in, console của worker cho những vi phạm
 * xảy ra bên trong worker (Monaco, hls.js), nơi tài liệu không nghe được.
 */
async function watch(context) {
  await context.exposeBinding("__devpathCsp", ({ page }, event) => {
    violations.push({ step: current, via: "event", page: strip(page.url()), ...event });
  });
  await context.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (e) => {
      if (typeof window.__devpathCsp !== "function") return;
      window.__devpathCsp({
        disposition: e.disposition,
        effectiveDirective: e.effectiveDirective,
        blockedURI: e.blockedURI,
        sourceFile: e.sourceFile,
        lineNumber: e.lineNumber,
        sample: e.sample,
      });
    });
  });
  const fromConsole = (via, where) => (message) => {
    const text = message.text();
    if (/Content Security Policy/i.test(text)) {
      violations.push({ step: current, via, page: strip(where()), text });
    }
  };
  context.on("page", (page) => {
    page.on("console", fromConsole("console", () => page.url()));
    page.on("worker", (worker) =>
      worker.on("console", fromConsole("worker-console", () => worker.url())),
    );
    page.on("pageerror", (error) => {
      pageErrors.push({ step: current, page: strip(page.url()), error: String(error).split("\n")[0] });
    });
    page.on("response", (response) => {
      if (!response.request().isNavigationRequest() || response.frame() !== page.mainFrame()) return;
      if (!response.url().startsWith(BASE) || current.startsWith(CONTROL)) return;
      const headers = response.headers();
      for (const name of ["content-security-policy", "content-security-policy-report-only"]) {
        if (!headers[name]) continue;
        // Nhiều header cùng tên đến nối bằng \n.
        for (const value of headers[name].split("\n")) {
          const key = `${name}: ${value}`;
          const seen = policies.get(key) ?? { count: 0, pages: [] };
          seen.count += 1;
          if (seen.pages.length < 3) seen.pages.push(strip(response.url()));
          policies.set(key, seen);
        }
      }
    });
  });
}

function strip(url) {
  return url.startsWith(BASE) ? url.slice(BASE.length) || "/" : url;
}

// --- Bước --------------------------------------------------------------------

async function step(name, run) {
  current = name;
  const started = Date.now();
  const before = violations.length;
  try {
    // Một bước treo không được giữ cả lượt (và bỏ dọn dữ liệu ở cuối).
    let timer;
    const note = await Promise.race([
      run(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("quá 3 phút")), 180_000);
      }),
    ]).finally(() => clearTimeout(timer));
    steps.push({ name, ok: true, ms: Date.now() - started, note: note ?? null });
    log("ok  ", name, note ? `— ${note}` : "", (() => {
      const fresh = violations.slice(before);
      const own = fresh.filter((v) => !fromEdge(v)).length;
      return fresh.length ? `(vi phạm: site ${own}, beacon Cloudflare ${fresh.length - own})` : "";
    })());
  } catch (error) {
    const message = String(error).split("\n")[0];
    steps.push({ name, ok: false, ms: Date.now() - started, error: message });
    log("FAIL", name, message);
  }
}

async function settle(page, ms = 800) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(ms);
}

async function open(page, url) {
  const response = await page.goto(`${BASE}${url}`, { waitUntil: "domcontentloaded" });
  await settle(page);
  // Cuộn hết trang để ảnh lazy cũng được tải.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 600) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
    window.scrollTo(0, 0);
  });
  await settle(page, 300);
  return response?.status();
}

async function visit(page, url) {
  await step(`xem ${url}`, async () => {
    const status = await open(page, url);
    if (status && status >= 500) throw new Error(`HTTP ${status}`);
    return `HTTP ${status}`;
  });
}

/** Chờ form thuộc về React rồi mới bấm -- bấm sớm là trình duyệt tự gửi GET. */
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

async function signIn(page, account) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await hydrated(page);
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const response = await answered;
  if (!response.ok()) throw new Error(`đăng nhập ${account.email}: HTTP ${response.status()}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 45_000 });
}

async function signOut(context) {
  await context.request.post(`${BASE}/api/v1/auth/logout`).catch(() => {});
}

async function getJson(context, url) {
  const response = await context.request.get(`${BASE}/api/v1${url}`);
  if (!response.ok()) throw new Error(`GET ${url}: HTTP ${response.status()}`);
  return response.json();
}

/** Ảnh PNG 96×96 thật (bucket nhận theo content type, backend không vẽ lại). */
function png(size = 96) {
  const row = Buffer.alloc(1 + size * 3);
  const raw = [];
  for (let y = 0; y < size; y += 1) {
    row[0] = 0;
    for (let x = 0; x < size; x += 1) {
      row[1 + x * 3] = 40 + x;
      row[2 + x * 3] = 90 + y;
      row[3 + x * 3] = 200;
    }
    raw.push(Buffer.from(row));
  }
  const chunk = (type, data) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(zlib.crc32(body));
    return Buffer.concat([length, body, crc]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 2;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(Buffer.concat(raw))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// --- Docker (chỉ đọc một mã chứng chỉ và dọn) ------------------------------

function container(service) {
  const id = execFileSync(
    "docker",
    ["ps", "-q", "--filter", `label=com.docker.compose.project=${PROJECT}`, "--filter", `label=com.docker.compose.service=${service}`],
    { encoding: "utf8" },
  ).trim();
  if (!id) throw new Error(`không thấy container ${service} của project ${PROJECT}`);
  return id.split("\n")[0];
}

function certificateCode() {
  const sql = "select code from certificates where pdf_key is not null order by issued_at desc limit 1";
  return execFileSync(
    "docker",
    ["exec", container("postgres"), "sh", "-c", `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "${sql}"`],
    { encoding: "utf8" },
  ).trim();
}

function purge() {
  return execFileSync("docker", ["exec", container("backend"), "python", "-m", "scripts.purge_e2e"], {
    encoding: "utf8",
  }).trim();
}

// --- Từng vai ----------------------------------------------------------------

const CONTROL = "đối chứng";
let control = null;

/**
 * Bộ thu có thật sự nghe thấy vi phạm không: 0 vi phạm chỉ có nghĩa khi nó
 * bắt được một vi phạm cố ý. Trang chủ được trả lại với một policy chặt hơn
 * (Report-Only, để trang vẫn chạy): script-src không có 'unsafe-inline' thì
 * mọi script nội tuyến của Next vi phạm, img-src 'none' thì mọi ảnh.
 */
async function controlRun(context) {
  await step(`${CONTROL}: bộ thu bắt được vi phạm cố ý`, async () => {
    const page = await context.newPage();
    await page.route(`${BASE}/`, async (route) => {
      const response = await route.fetch();
      const headers = { ...response.headers() };
      delete headers["content-security-policy"];
      delete headers["content-security-policy-report-only"];
      headers["content-security-policy-report-only"] = "script-src 'self'; img-src 'none'";
      await route.fulfill({ response, headers });
    });
    const before = violations.length;
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    await settle(page, 1_500);
    await page.close();
    const caught = violations.splice(before);
    const via = (name) => caught.filter((v) => v.via === name).length;
    control = {
      policy: "script-src 'self'; img-src 'none' (Report-Only)",
      event: via("event"),
      console: via("console"),
      directives: [...new Set(caught.map((v) => v.effectiveDirective).filter(Boolean))],
    };
    if (!control.event || !control.console) {
      throw new Error(`bộ thu điếc: ${JSON.stringify(control)}`);
    }
    return `sự kiện ${control.event}, console ${control.console}, chỉ thị ${control.directives.join(", ")}`;
  });
}

async function guest(browser, courses) {
  const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
  await watch(context);
  await controlRun(context);
  const page = await context.newPage();

  for (const url of ["/", "/khoa-hoc", "/khoa-hoc?q=python", "/bang-xep-hang", "/chinh-sach-bao-mat", "/tro-thanh-giang-vien", "/dang-ky", "/khong-co-trang-nay"]) {
    await visit(page, url);
  }
  for (const course of courses) await visit(page, `/khoa-hoc/${course.slug}`);

  await step("chứng chỉ công khai + PDF", async () => {
    const code = certificateCode();
    await open(page, `/cert/${code}`);
    await page.getByText("Chứng chỉ hợp lệ").waitFor();
    const link = page.getByRole("link", { name: "Tải chứng chỉ PDF" });
    const href = await link.getAttribute("href");
    // Mở thẳng trong một tab: trình xem PDF của Chrome là tài liệu mang
    // chính header CSP của response, nên `object-src 'none'` có thể chặn nó.
    const tab = await context.newPage();
    const download = tab.waitForEvent("download", { timeout: 8_000 }).catch(() => null);
    const response = await tab.goto(new URL(href, BASE).href).catch((error) => ({ error }));
    const downloaded = await download;
    let shown = "?";
    if (downloaded) shown = "tải về (Chrome không mở trong tab)";
    else {
      await tab.waitForTimeout(3_000);
      await tab.screenshot({ path: path.join(__dirname, `${LABEL}-pdf.png`) });
      shown = await tab.evaluate(() => {
        const embed = document.querySelector("embed");
        return embed ? `trình xem PDF (${embed.getAttribute("type")})` : document.contentType;
      });
    }
    const status = response && !response.error ? response.status() : "đang tải";
    await tab.close();
    return `${code}, PDF HTTP ${status}, ${shown}`;
  });

  await step("nút Google trên /dang-nhap dẫn sang Google", async () => {
    await open(page, "/dang-nhap");
    const google = page.getByRole("link", { name: /Google/ });
    if ((await google.count()) === 0) return "không có nút Google (GOOGLE_LOGIN_ENABLED tắt)";
    await google.first().click();
    await page.waitForURL((url) => url.hostname === "accounts.google.com", { timeout: 30_000 });
    return new URL(page.url()).hostname;
  });

  await context.close();
}

async function student(browser, courses) {
  const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
  await watch(context);
  const page = await context.newPage();
  const email = `csp-${Date.now().toString(36)}@e2e.devpath.example`;
  const python = courses.find((course) => course.slug === PYTHON);
  const paid = courses.find((course) => Number(course.price) > 0);
  const lessons = (await getJson(context, `/courses/${python.id}/curriculum`)).sections.flatMap((s) => s.lessons);
  const byType = (type) => lessons.find((lesson) => lesson.type === type);

  await step("đăng ký tài khoản học viên", async () => {
    await page.goto(`${BASE}/dang-ky`, { waitUntil: "domcontentloaded" });
    await hydrated(page);
    await page.getByLabel("Họ và tên").fill("Học Viên Kiểm CSP");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Mật khẩu").fill(`csp-${Date.now()}-probe`);
    await page.getByRole("button", { name: "Tạo tài khoản" }).click();
    // Sign-up lands on the welcome page since Phase 7 group 7; on the home page before.
    await page.waitForURL((url) => ["/", "/chao-mung"].includes(url.pathname), { timeout: 45_000 });
    await settle(page);
    return email;
  });

  await visit(page, "/");

  await step("ghi danh khóa Python miễn phí", async () => {
    await open(page, `/khoa-hoc/${PYTHON}`);
    await page.getByRole("button", { name: "Đăng ký học miễn phí" }).click();
    await page.getByRole("link", { name: "Vào học" }).first().waitFor();
  });

  await step("phát video HLS", async () => {
    await open(page, `/hoc/${PYTHON}?bai=${byType("video").id}`);
    const video = page.locator("video").first();
    await video.waitFor();
    await video.evaluate((v) => {
      v.muted = true;
      return v.play();
    });
    await page.waitForFunction(() => (document.querySelector("video")?.currentTime ?? 0) > 2, null, {
      timeout: 45_000,
    });
    return await video.evaluate((v) => `currentTime ${v.currentTime.toFixed(1)} s, src ${v.currentSrc.slice(0, 5)}…`);
  });

  await step("trợ giảng AI trả lời qua SSE", async () => {
    await page.getByRole("tab", { name: "Trợ giảng AI" }).click();
    const box = page.getByLabel("Câu hỏi cho trợ giảng AI");
    await box.fill("Biến trong Python là gì?");
    const answered = page.waitForResponse((r) => /\/chat-sessions\/[^/]+\/messages$/.test(r.url()) && r.request().method() === "POST", { timeout: 60_000 });
    await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
    const response = await answered;
    // Không chờ `response.finished()`: với một luồng SSE trang tự đọc,
    // Playwright không bao giờ trả về (đo 18/10: treo 20 phút, câu trả lời
    // đã lưu sau 1,5 s). Chờ đúng câu panel đọc cho trình đọc màn hình khi
    // nhận được `done`.
    await page.getByText("Trợ giảng đã trả lời xong.").waitFor({ state: "attached", timeout: 90_000 });
    if (await page.getByText(/chưa được lưu/).count()) throw new Error("câu trả lời không được lưu");
    return `HTTP ${response.status()} ${response.headers()["content-type"]}`;
  });

  await step("bài đọc", async () => {
    await open(page, `/hoc/${PYTHON}?bai=${byType("article").id}`);
  });

  await step("Monaco + chạy thử trong sandbox", async () => {
    await open(page, `/hoc/${PYTHON}?bai=${byType("code_exercise").id}`);
    const editor = page.locator(".monaco-editor").first();
    await editor.waitFor({ timeout: 30_000 });
    await editor.click();
    await page.keyboard.type("# csp ");
    const ran = page.waitForResponse((r) => r.request().method() === "POST" && /\/trial-runs$/.test(r.url()), { timeout: 60_000 });
    await page.getByRole("button", { name: "Chạy thử" }).click();
    const response = await ran;
    await page.getByText("Chạy thử — không tính vào lịch sử").waitFor({ timeout: 90_000 });
    const workers = page.workers().map((worker) => worker.url().split(":")[0]);
    return `run HTTP ${response.status()}, worker: ${workers.join(", ") || "không có"}`;
  });

  await step("đổi ảnh đại diện (PUT lên bucket bằng URL ký sẵn)", async () => {
    await open(page, "/ho-so");
    const put = page.waitForResponse((r) => r.request().method() === "PUT" && r.url().includes("/devpath-media/"), { timeout: 30_000 });
    await page.locator('input[type="file"]').first().setInputFiles({ name: "avatar.png", mimeType: "image/png", buffer: png() });
    const response = await put;
    await page.waitForResponse((r) => r.url().endsWith("/users/me/avatar/complete") && r.ok(), { timeout: 30_000 });
    await page.waitForFunction(
      () => [...document.images].some((img) => img.src.includes("/devpath-media/avatars/") && img.complete && img.naturalWidth > 0),
      null,
      { timeout: 30_000 },
    );
    return `PUT HTTP ${response.status()}, ảnh mới hiện`;
  });

  for (const url of ["/khoa-hoc-cua-toi", "/thong-bao", "/yeu-thich", "/bang-xep-hang"]) await visit(page, url);

  await step("giỏ hàng → sang VNPay với URL đã ký", async () => {
    await open(page, `/khoa-hoc/${paid.slug}`);
    await page.getByRole("button", { name: "Thêm vào giỏ hàng" }).click();
    await page.getByRole("link", { name: "Xem giỏ hàng" }).waitFor();
    await open(page, "/gio-hang");
    // Trang ngân hàng là site của người khác: đứng thay nó, như E2E.
    await page.route(VNPAY, (route) => route.fulfill({ contentType: "text/html; charset=utf-8", body: "<h1>VNPay (giả lập)</h1>" }));
    await page.getByRole("button", { name: "Thanh toán qua VNPay" }).click();
    await page.waitForURL(VNPAY, { timeout: 30_000 });
    return new URL(page.url()).hostname;
  });

  await signOut(context);
  await context.close();
}

async function staff(browser, role, urls) {
  const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
  await watch(context);
  const page = await context.newPage();
  await step(`đăng nhập ${role}`, () => signIn(page, ACCOUNTS[role]));
  for (const url of await urls(page)) await visit(page, url);
  await signOut(context);
  await context.close();
}

// --- Chạy --------------------------------------------------------------------

(async () => {
  const browser = await chromium.launch({
    headless: !process.env.HEADED,
    ...(CHANNEL ? { channel: CHANNEL } : {}),
  });
  const started = new Date();
  let purged = null;
  try {
    const listing = await (await fetch(`${BASE}/api/v1/courses?page_size=50`)).json();
    const courses = listing.items;
    const python = courses.find((course) => course.slug === PYTHON);
    log(`${BASE}: ${courses.length} khóa`);

    await guest(browser, courses);
    await student(browser, courses);
    await staff(browser, "instructor", async (page) => {
      await open(page, "/giang-day");
      const editors = await page
        .locator('a[href^="/giang-day/"]')
        .evaluateAll((links) => links.map((a) => a.getAttribute("href")).filter((h) => /^\/giang-day\/[0-9a-f-]{36}$/.test(h)));
      return ["/giang-day", ...new Set(editors), "/giang-day/thong-ke", "/giang-day/hoi-dap", "/giang-day/moi"];
    });
    await staff(browser, "admin", async () => [
      "/quan-tri",
      "/quan-tri/khoa-hoc",
      `/quan-tri/khoa-hoc/${python.id}`,
      "/quan-tri/bao-cao",
      "/quan-tri/nguoi-dung",
      "/quan-tri/danh-muc",
      "/quan-tri/ma-giam-gia",
      "/quan-tri/banner",
    ]);
  } finally {
    await browser.close();
    try {
      purged = purge();
    } catch (error) {
      purged = `DỌN HỎNG: ${error}`;
    }
  }

  const failed = steps.filter((s) => !s.ok);
  const site = violations.filter((v) => !fromEdge(v));
  const edge = violations.filter(fromEdge);
  const result = {
    label: LABEL,
    base: BASE,
    started: started.toISOString(),
    browser: CHANNEL || "chromium",
    policies: Object.fromEntries(policies),
    control,
    steps,
    violations: site,
    edgeInjected: edge,
    pageErrors,
    purged,
  };
  const out = path.join(__dirname, `${LABEL}.json`);
  fs.writeFileSync(out, `${JSON.stringify(result, null, 2)}\n`);

  console.log("\n=== Header CSP trên các trang đã mở ===");
  for (const [policy, seen] of policies) {
    console.log(`${seen.count}×  ${policy}\n      vd. ${seen.pages.join(", ")}`);
  }
  console.log(`\n=== ${steps.length} bước, ${failed.length} hỏng ===`);
  for (const s of failed) console.log(`  HỎNG ${s.name}: ${s.error}`);
  console.log(`\n=== ${site.length} vi phạm CSP của site ===`);
  for (const v of site) {
    console.log(`  [${v.step}] ${v.via} ${v.page} ${v.disposition ?? ""} ${v.effectiveDirective ?? ""} ${v.blockedURI ?? ""} ${v.text ?? ""}`);
  }
  const edgeDispositions = [...new Set(edge.map((v) => v.disposition).filter(Boolean))];
  console.log(
    `\n=== ${edge.length} lần beacon Cloudflare (edge chèn) bị policy chặn/báo ` +
      `(${new Set(edge.map((v) => v.page)).size} trang, ${edgeDispositions.join("/") || "—"}) ===`,
  );
  console.log(`\n=== ${pageErrors.length} lỗi JS không bắt ===`);
  for (const e of pageErrors) console.log(`  [${e.step}] ${e.page}: ${e.error}`);
  console.log(`\npurge_e2e: ${purged}`);
  console.log(`→ ${path.relative(process.cwd(), out)}`);
  process.exitCode = failed.length || site.length ? 1 : 0;
})();
