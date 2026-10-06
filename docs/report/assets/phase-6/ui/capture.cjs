/**
 * Ảnh giao diện cho chương 4 của báo cáo — chụp lại từ đầu, đúng font, đúng
 * giao diện sau đợt UX 02/10 (lý do: docs/report/assets/README.md mục 3.1).
 *
 *   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/ui/capture.cjs
 *
 * Chạy vào một stack đang bật (mặc định stack dev ở localhost), đã có đủ dữ
 * liệu demo theo bảng "Dữ liệu demo đầy đủ" trong README gốc, kể cả
 * `scripts.seed_community`. Mỗi vai đăng nhập đúng một lần bằng form thật,
 * phiên được thu hồi khi chụp xong vai đó.
 *
 * Biến môi trường:
 *   BASE_URL / API_URL   mặc định http://localhost:3000 và http://localhost:8000.
 *                        Trên stack production cả hai là https://<DOMAIN>.
 *   ONLY                 regex trên tên ảnh, để chụp lại một phần.
 *   CHROME_CHANNEL       mặc định "chrome" (Chrome cài trên máy); "" = Chromium
 *                        của Playwright.
 *   SKIP_STAGE=1         bỏ phần cần dựng khóa học tạm (sinh quiz AI, hàng đợi
 *                        duyệt) — phần này gọi Gemini và cần `docker compose`
 *                        để dọn bằng scripts.purge_e2e.
 *   COMPOSE_FILE         compose file của stack để dọn (mặc định infra/docker-compose.yml).
 *   SEED_*_PASSWORD      mật khẩu tài khoản seed nếu không phải mặc định của stack dev.
 *
 * Việc ghi dữ liệu trong lúc chụp, và vì sao chấp nhận được:
 *   - hocvien07 làm quiz "Kiểm tra: ép kiểu" và nộp bài "đếm số chẵn" (một
 *     lần sai, một lần đúng) — để có ảnh màn hình làm bài thật. Thuộc tài
 *     khoản seed_interactions, bị gỡ cùng tài khoản khi dọn dữ liệu demo.
 *   - một giảng viên dùng một lần (@e2e.devpath.example) dựng khóa "Git cho
 *     người mới bắt đầu", sinh quiz bằng Gemini và gửi duyệt; scripts.purge_e2e
 *     xóa sạch ở cuối.
 */
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const { chromium, request: playwrightRequest } = require("@playwright/test");

const BASE = (process.env.BASE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const API = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const OUT = process.env.OUT_DIR ?? __dirname;
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const CHANNEL = process.env.CHROME_CHANNEL ?? "chrome";
const COMPOSE_FILE =
  process.env.COMPOSE_FILE ?? path.resolve(__dirname, "../../../../..", "infra/docker-compose.yml");

const COURSE = "python-co-ban-cho-nguoi-moi-bat-dau";
const LEARNER_PASSWORD = process.env.SEED_LEARNER_PASSWORD ?? "devpath-learner";
const ACCOUNTS = {
  // Ghi danh khóa Python, chủ các phiên trợ giảng AI demo, người hỏi một câu
  // được giảng viên trả lời (scripts.seed_community), có gợi ý cá nhân.
  learner: { email: "hocvien07@seed.devpath.example", password: LEARNER_PASSWORD },
  // Giỏ có khóa Python nâng cao (mã PYTHON30 áp được) và danh sách yêu thích.
  shopper: { email: "hocvien25@seed.devpath.example", password: LEARNER_PASSWORD },
  // Lịch sử học 70 ngày (scripts.seed_study): XP, chuỗi ngày, chứng chỉ.
  buyer: {
    email: "nguoimua31@sales.devpath.example",
    password: process.env.SEED_BUYER_PASSWORD ?? "devpath-buyer",
  },
  instructor: {
    email: "khoa.tran@devpath.example",
    password: process.env.SEED_INSTRUCTOR_PASSWORD ?? "devpath-instructor",
  },
  admin: {
    email: process.env.SEED_ADMIN_EMAIL ?? "admin@devpath.example",
    password: process.env.SEED_ADMIN_PASSWORD ?? "devpath-admin",
  },
};

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 375, height: 812 };

const results = [];

/** Vai này có ảnh nào được chọn không — để ONLY không đăng nhập thừa. */
function wants(...names) {
  return !ONLY || names.some((name) => ONLY.test(name));
}

function log(...parts) {
  console.log(new Date().toISOString().slice(11, 19), ...parts);
}

// --- Trình duyệt ----------------------------------------------------------

async function newContext(browser, viewport = DESKTOP) {
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: viewport === PHONE ? 2 : 1,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    isMobile: viewport === PHONE,
    hasTouch: viewport === PHONE,
  });
  // Nút công cụ của `next dev` ở góc dưới trái không thuộc sản phẩm.
  await context.addInitScript(() => {
    const hide = () => {
      if (document.getElementById("__hide-next-dev")) return;
      const style = document.createElement("style");
      style.id = "__hide-next-dev";
      style.textContent = "nextjs-portal{display:none!important}";
      document.documentElement.appendChild(style);
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hide);
    else hide();
  });
  return context;
}

async function settle(page, ms = 600) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(ms);
}

async function open(page, url) {
  await page.goto(`${BASE}${url}`, { waitUntil: "domcontentloaded" });
  await settle(page);
}

/** Một ảnh. Hỏng thì ghi lại rồi đi tiếp, để một màn lỗi không mất cả lượt. */
async function shot(page, name, prepare, { fullPage = false, clip, settleMs = 400 } = {}) {
  if (ONLY && !ONLY.test(name)) return;
  const started = Date.now();
  try {
    if (prepare) await prepare(page);
    if (settleMs) await settle(page, settleMs);
    else await page.evaluate(() => document.fonts.ready);
    const file = path.join(OUT, `${name}.png`);
    await page.screenshot({ path: file, fullPage, clip, animations: "disabled" });
    results.push({ name, url: page.url().replace(BASE, ""), ok: true, ms: Date.now() - started });
    log("ok  ", name);
  } catch (error) {
    if (process.env.DEBUG_DIR) {
      await page
        .screenshot({ path: path.join(process.env.DEBUG_DIR, `${name}-FAIL.png`), fullPage: true })
        .catch(() => {});
    }
    results.push({ name, url: page.url().replace(BASE, ""), ok: false, error: String(error).split("\n")[0] });
    log("FAIL", name, String(error).split("\n")[0]);
  }
}

/** Cuộn để phần tử nằm sát mép trên (chừa `gap` px), kể cả khi nó đã thấy được. */
async function scrollTo(locator, gap = 24) {
  await locator.evaluate((element, offset) => {
    const top = element.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top, behavior: "instant" });
  }, gap + 64);
}

async function signIn(context, account) {
  const page = await context.newPage();
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  // Bấm trước khi React gắn sự kiện thì trình duyệt tự gửi form kiểu GET —
  // mật khẩu lên URL. Chờ form thật sự thuộc về React đã.
  // `next dev` đôi khi dựng lại trang sau lỗi hydration và có lúc hai bản
  // form cùng nằm trong DOM: chờ tới khi còn đúng một.
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return (
        forms.length === 1 &&
        Object.keys(forms[0]).some((key) => key.startsWith("__reactProps"))
      );
    },
    null,
    { timeout: 60_000 },
  );
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const response = await answered;
  if (!response.ok()) throw new Error(`đăng nhập ${account.email}: ${response.status()}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 45_000 });
  await settle(page);
  return page;
}

/** Thu hồi phiên: cookie refresh nằm trong context, gửi kèm request này. */
async function signOut(context) {
  await context.request.post(`${API}/api/v1/auth/logout`).catch(() => {});
}

// --- API (dựng dữ liệu tạm) -----------------------------------------------

async function api(request, method, url, { token, data } = {}) {
  const response = await request.fetch(`${API}/api/v1${url}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    data,
    timeout: 120_000,
  });
  if (!response.ok()) {
    throw new Error(`${method} ${url}: ${response.status()} ${await response.text()}`);
  }
  return response.status() === 204 ? {} : response.json();
}

async function apiLogin(request, account) {
  return (await api(request, "POST", "/auth/login", { data: account })).access_token;
}

// --- Từng vai ---------------------------------------------------------------

async function guest(browser) {
  if (!wants("01-khach-trang-chu", "02-khach-tim-kiem-khoa-hoc", "03-khach-chi-tiet-khoa-hoc", "04-khach-chi-tiet-khoa-hoc-muc-luc", "05-khach-dang-nhap", "06-khach-trang-chu-khoa-hoc-moi", "07-khach-trang-chu-375", "08-khach-chi-tiet-khoa-hoc-375")) return;
  const context = await newContext(browser);
  const page = await context.newPage();

  await open(page, "/");
  await shot(page, "01-khach-trang-chu");

  await open(page, "/khoa-hoc?q=python");
  await shot(page, "02-khach-tim-kiem-khoa-hoc");

  await open(page, `/khoa-hoc/${COURSE}`);
  await shot(page, "03-khach-chi-tiet-khoa-hoc");
  await shot(page, "04-khach-chi-tiet-khoa-hoc-muc-luc", async (p) => {
    await scrollTo(p.getByRole("heading", { name: "Nội dung khóa học" }).first());
  });

  await open(page, "/dang-nhap");
  await shot(page, "05-khach-dang-nhap");

  await open(page, "/");
  await shot(page, "06-khach-trang-chu-khoa-hoc-moi", async (p) => {
    await scrollTo(p.getByRole("heading", { name: "Khóa học mới" }).first());
  });
  await context.close();

  const phone = await newContext(browser, PHONE);
  const mobile = await phone.newPage();
  await open(mobile, "/");
  await shot(mobile, "07-khach-trang-chu-375");
  await open(mobile, `/khoa-hoc/${COURSE}`);
  await shot(mobile, "08-khach-chi-tiet-khoa-hoc-375");
  await phone.close();
}

async function learner(browser) {
  if (!wants("10-hoc-vien-goi-y-cho-ban", "11-hoc-vien-video-ghi-chu", "11b-hoc-vien-ghi-chu-theo-moc", "12-hoc-vien-hoi-dap", "13-hoc-vien-tro-giang-ai", "13b-hoc-vien-tro-giang-ai-tu-choi", "14-hoc-vien-chuong-thong-bao", "15-hoc-vien-trang-thong-bao", "16-hoc-vien-quiz-dang-lam", "17-hoc-vien-quiz-ket-qua", "18-hoc-vien-nop-code-dang-cham", "19-hoc-vien-nop-code-sai", "20-hoc-vien-nop-code-dung", "21-hoc-vien-trang-hoc-375")) return;
  const context = await newContext(browser);
  const page = await signIn(context, ACCOUNTS.learner);
  const lessons = await findLessons(page);

  await open(page, "/");
  await shot(page, "10-hoc-vien-goi-y-cho-ban", async (p) => {
    await scrollTo(p.getByRole("heading", { name: "Gợi ý cho bạn" }).first());
  });

  // Video + ghi chú theo mốc thời gian (scripts.seed_community).
  await open(page, `/hoc/${COURSE}?bai=${lessons["Vòng lặp for và range"]}`);
  await shot(page, "11-hoc-vien-video-ghi-chu", async (p) => {
    await p.locator("video").first().evaluate((video) => {
      video.muted = true;
      video.currentTime = 85;
    }).catch(() => {});
    await p.getByRole("tab", { name: /Ghi chú/ }).click();
    await p.waitForTimeout(1500);
  });

  await shot(page, "11b-hoc-vien-ghi-chu-theo-moc", async (p) => {
    await scrollTo(p.getByRole("tab", { name: /Ghi chú/ }), 16);
  });

  // Hỏi đáp: câu hỏi của chính hocvien07, có trả lời của giảng viên.
  await open(page, `/hoc/${COURSE}?bai=${lessons["Ép kiểu và những cái bẫy quen thuộc"]}`);
  await shot(page, "12-hoc-vien-hoi-dap", async (p) => {
    await p.getByRole("tab", { name: /Hỏi đáp/ }).click();
    await p.getByText('int("3.5") báo lỗi nhưng int(3.5) thì không?').first().click();
    await p.waitForTimeout(1200);
    await scrollTo(
      p.getByRole("heading", { name: 'int("3.5") báo lỗi nhưng int(3.5) thì không?' }),
      60,
    );
  });

  // Trợ giảng AI: mở lại phiên demo gate 22/09 — không gọi Gemini. Hai câu
  // trả lời có trích nguồn, rồi hai câu bị từ chối vì ngoài phạm vi.
  await open(page, `/hoc/${COURSE}?bai=${lessons["Đọc hiểu thông báo lỗi"]}`);
  await shot(page, "13-hoc-vien-tro-giang-ai", async (p) => {
    await p.getByRole("tab", { name: /Trợ giảng AI/ }).click();
    await p.getByRole("button", { name: "Lịch sử trò chuyện" }).click();
    await p.getByText("range(1, 10, 2) sinh ra những số nào?").first().click();
    await p.waitForTimeout(1500);
    await scrollChat(p, "top");
  });
  await shot(page, "13b-hoc-vien-tro-giang-ai-tu-choi", async (p) => {
    await scrollChat(p, "bottom");
  });

  // Thông báo.
  await open(page, `/khoa-hoc-cua-toi`);
  await shot(page, "14-hoc-vien-chuong-thong-bao", async (p) => {
    await p.getByRole("button", { name: /^Thông báo/ }).click();
    await p.waitForTimeout(1200);
  });
  await open(page, "/thong-bao");
  await shot(page, "15-hoc-vien-trang-thong-bao");

  // Quiz có giờ: bắt đầu, trả lời, nộp.
  await open(page, `/hoc/${COURSE}?bai=${lessons["Kiểm tra: ép kiểu"]}`);
  await shot(page, "16-hoc-vien-quiz-dang-lam", async (p) => {
    await p.getByRole("button", { name: /Bắt đầu làm bài|Tiếp tục làm bài/ }).click();
    await p.locator("fieldset").first().waitFor();
    await answerQuiz(p, LEARNER_STATE.quizKey);
    await p.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  });
  await shot(page, "17-hoc-vien-quiz-ket-qua", async (p) => {
    await p.getByRole("button", { name: "Nộp bài", exact: true }).click();
    await p.waitForTimeout(2500);
    await p.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  });

  // Nộp code: một lần sai (đang chấm, rồi kết quả), một lần đúng.
  await open(page, `/hoc/${COURSE}?bai=${lessons["Bài tập: đếm số chẵn"]}`);
  await shot(page, "18-hoc-vien-nop-code-dang-cham", async (p) => {
    await typeCode(p, WRONG_SOLUTION);
    await p.getByRole("button", { name: "Nộp bài", exact: true }).click();
    LEARNER_STATE.submittedAt = Date.now();
    // Tiến độ từng test qua WebSocket; bắt khung "Đang chấm test k/n" nếu kịp.
    await p
      .getByText(/Đang chấm test \d+\/\d+/)
      .first()
      .waitFor({ timeout: 30_000 })
      .catch(() => p.getByText(/Đang chấm|Đang chờ/).first().waitFor({ timeout: 10_000 }));
  }, { settleMs: 0 });
  await shot(page, "19-hoc-vien-nop-code-sai", async (p) => {
    await p.getByText(VERDICT_HINT.WA).first().waitFor({ timeout: 90_000 });
    await scrollTo(p.getByText("Kết quả", { exact: true }).first(), 120);
  });
  await shot(page, "20-hoc-vien-nop-code-dung", async (p) => {
    await p.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    // Mỗi học viên một bài nộp mỗi 10 giây (SUBMISSION_COOLDOWN_SECONDS).
    const waited = Date.now() - (LEARNER_STATE.submittedAt ?? 0);
    if (waited < 11_000) await p.waitForTimeout(11_000 - waited);
    await typeCode(p, RIGHT_SOLUTION);
    await p.getByRole("button", { name: "Nộp bài", exact: true }).click();
    await p.getByText(VERDICT_HINT.AC).first().waitFor({ timeout: 90_000 });
    await p.waitForTimeout(1500);
    await scrollTo(p.getByText("Kết quả", { exact: true }).first(), 120);
  });

  await signOut(context);
  await context.close();

  if (!wants("21-hoc-vien-trang-hoc-375")) return;
  const phone = await newContext(browser, PHONE);
  try {
    const mobile = await signIn(phone, ACCOUNTS.learner);
    await open(mobile, `/hoc/${COURSE}?bai=${lessons["Vòng lặp for và range"]}`);
    await shot(mobile, "21-hoc-vien-trang-hoc-375");
  } catch (error) {
    const message = String(error).split("\n")[0];
    results.push({ name: "21-hoc-vien-trang-hoc-375", ok: false, error: message });
    log("FAIL", "21-hoc-vien-trang-hoc-375", message);
  } finally {
    await signOut(phone);
    await phone.close();
  }
}

// Câu mô tả verdict tổng (frontend/lib/grading/verdicts.ts). Chờ câu này chứ
// không chờ nhãn "Đúng": nhãn ấy hiện ở test 1 khi test sau còn đang chấm.
const VERDICT_HINT = {
  AC: "Chương trình in ra đúng kết quả mong đợi ở mọi test case.",
  WA: "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.",
};

const WRONG_SOLUTION = [
  "n = int(input())",
  "numbers = list(map(int, input().split()))",
  "",
  "print(sum(1 for x in numbers if x > 0 and x % 2 == 0))",
  "",
].join("\n");
const RIGHT_SOLUTION = [
  "n = int(input())",
  "numbers = list(map(int, input().split()))",
  "",
  "print(sum(1 for x in numbers if x % 2 == 0))",
  "",
].join("\n");

async function typeCode(page, code) {
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Delete");
  // insertText, không type: Monaco tự đóng ngoặc khi gõ từng phím.
  await page.keyboard.insertText(code);
}

const LEARNER_STATE = { quizKey: null, submittedAt: null };

/**
 * Đúng mọi câu trừ một, để ảnh kết quả có cả lời giải thích của câu sai.
 * Khớp theo chữ chứ không theo vị trí: trang làm bài xáo thứ tự phương án.
 */
async function answerQuiz(page, key) {
  const questions = page.locator("fieldset");
  const count = await questions.count();
  for (let i = 0; i < count; i += 1) {
    const fieldset = questions.nth(i);
    const legend = (await fieldset.locator("legend").innerText()).trim();
    const known = key?.find((q) => legend.includes(q.question));
    if (!known) {
      await fieldset.getByRole("radio").first().check({ force: true });
      continue;
    }
    const answer =
      i === count - 1 ? known.options.find((o) => o !== known.answer) : known.answer;
    await fieldset.getByLabel(answer, { exact: true }).check({ force: true });
  }
}

/** Cuộn khung hội thoại của trợ giảng (một vùng cuộn riêng trong panel). */
async function scrollChat(page, where) {
  await page.evaluate((to) => {
    // Trang học có hai bộ tab; vùng cuộn của hội thoại là vùng cuộn duy nhất
    // còn nội dung tràn khi tab trợ giảng đang mở.
    const boxes = [...document.body.querySelectorAll("*")].filter((el) => {
      const style = getComputedStyle(el);
      return /(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 4;
    });
    for (const box of boxes) box.scrollTop = to === "top" ? 0 : box.scrollHeight;
  }, where);
  await page.waitForTimeout(400);
}

async function findLessons(page) {
  // Mục lục là công khai: id từng bài, đọc qua API.
  const course = await (await page.request.get(`${API}/api/v1/courses/by-slug/${COURSE}`)).json();
  const curriculum = await (
    await page.request.get(`${API}/api/v1/courses/${course.id}/curriculum`)
  ).json();
  const lessons = {};
  for (const section of curriculum.sections) {
    for (const lesson of section.lessons) lessons[lesson.title] = lesson.id;
  }
  return lessons;
}

async function buyer(browser) {
  if (!wants("22-hoc-vien-khoa-hoc-cua-toi-xp", "23-hoc-vien-bang-xep-hang-tuan", "24-khach-xac-thuc-chung-chi")) return;
  const context = await newContext(browser);
  const page = await signIn(context, ACCOUNTS.buyer);

  await open(page, "/khoa-hoc-cua-toi");
  await shot(page, "22-hoc-vien-khoa-hoc-cua-toi-xp");

  await open(page, "/bang-xep-hang");
  await shot(page, "23-hoc-vien-bang-xep-hang-tuan");

  await open(page, "/khoa-hoc-cua-toi");
  const certificate = page.getByRole("link", { name: /Chứng chỉ/ }).first();
  const href = await certificate.getAttribute("href").catch(() => null);
  await signOut(context);
  await context.close();

  if (href) {
    const visitor = await newContext(browser);
    const verify = await visitor.newPage();
    await open(verify, href);
    await shot(verify, "24-khach-xac-thuc-chung-chi");
    await visitor.close();
  }
}

async function shopper(browser) {
  if (!wants("25-hoc-vien-gio-hang-ma-giam-gia", "26-hoc-vien-yeu-thich")) return;
  const context = await newContext(browser);
  const page = await signIn(context, ACCOUNTS.shopper);

  await open(page, "/gio-hang");
  await shot(page, "25-hoc-vien-gio-hang-ma-giam-gia", async (p) => {
    await p.getByLabel("Mã giảm giá").fill("PYTHON30");
    await p.getByRole("button", { name: "Áp dụng" }).click();
    await p.getByText("PYTHON30").first().waitFor();
  });

  await open(page, "/yeu-thich");
  await shot(page, "26-hoc-vien-yeu-thich");

  await signOut(context);
  await context.close();
}

async function instructor(browser) {
  if (!wants("30-giang-vien-khoa-hoc", "31-giang-vien-soan-noi-dung", "32-giang-vien-bai-tap-code", "33-giang-vien-thong-ke", "34-giang-vien-hoi-dap", "35-giang-vien-chuong-thong-bao")) return;
  const context = await newContext(browser);
  const page = await signIn(context, ACCOUNTS.instructor);

  await open(page, "/giang-day");
  await shot(page, "30-giang-vien-khoa-hoc");

  const course = await (await page.request.get(`${API}/api/v1/courses/by-slug/${COURSE}`)).json();
  await open(page, `/giang-day/${course.id}`);
  await shot(page, "31-giang-vien-soan-noi-dung", async (p) => {
    await scrollTo(p.getByRole("button", { name: /Kéo để sắp xếp bài học/ }).first(), 160);
  });
  await shot(page, "32-giang-vien-bai-tap-code", async (p) => {
    const edit = p.getByRole("button", { name: "Sửa bài học Bài tập: đếm số chẵn" });
    await edit.click();
    await p.waitForTimeout(1500);
    await scrollTo(edit, 40);
  });

  await open(page, "/giang-day/thong-ke");
  await shot(page, "33-giang-vien-thong-ke");

  await open(page, "/giang-day/hoi-dap");
  await shot(page, "34-giang-vien-hoi-dap");

  await open(page, "/giang-day");
  await shot(page, "35-giang-vien-chuong-thong-bao", async (p) => {
    await p.getByRole("button", { name: /^Thông báo/ }).click();
    await p.waitForTimeout(1200);
  });

  await signOut(context);
  await context.close();
}

const GIT_ARTICLE = [
  "Git lưu lịch sử dự án thành một chuỗi **commit**. Mỗi commit là ảnh chụp toàn bộ",
  "thư mục làm việc tại một thời điểm, kèm lời nhắn mô tả thay đổi và con trỏ tới",
  "commit cha của nó.",
  "",
  "Quy trình hằng ngày gồm ba bước: sửa tệp, đưa thay đổi vào **vùng chờ** bằng",
  "`git add`, rồi ghi lại bằng `git commit -m \"...\"`. Lệnh `git status` cho biết tệp",
  "nào đã sửa mà chưa vào vùng chờ, còn `git log --oneline` liệt kê các commit.",
  "",
  "Một **nhánh** (branch) chỉ là một con trỏ tới một commit. `git switch -c tinh-nang`",
  "tạo nhánh mới và chuyển sang đó; commit trên nhánh này không ảnh hưởng nhánh `main`.",
  "Làm xong, `git merge tinh-nang` khi đang ở `main` sẽ gộp lịch sử hai nhánh lại.",
  "",
  "Khi hai nhánh cùng sửa một dòng, Git không tự quyết được và báo **xung đột**",
  "(conflict). Người dùng mở tệp, chọn nội dung đúng, rồi `git add` và `git commit`",
  "để hoàn tất việc gộp.",
].join("\n");

/** Khóa học tạm của một giảng viên dùng một lần: sinh quiz AI rồi gửi duyệt. */
async function stagedCourse(browser) {
  if (process.env.SKIP_STAGE) return;
  if (!wants("36-giang-vien-sinh-quiz-ai", "40-admin-hang-doi-duyet", "41-admin-trang-duyet")) return;

  const request = (await browser.newContext()).request;
  const stamp = Date.now().toString(36);
  const teacher = {
    email: `giangvien-anh-${stamp}@e2e.devpath.example`,
    password: `mat-khau-tam-${stamp}-du-dai`,
  };
  const registered = await api(request, "POST", "/auth/register", {
    data: { ...teacher, full_name: "Lê Hoàng Nam" },
  });
  const token = registered.access_token;
  await api(request, "POST", "/users/me/instructor", { token });

  const categories = await api(request, "GET", "/categories");
  const flat = categories.flatMap((c) => [c, ...(c.children ?? [])]);
  const category =
    flat.find((c) => /công cụ|devops|phát triển web|lập trình/i.test(c.name)) ?? flat[0];
  const course = await api(request, "POST", "/courses", {
    token,
    data: {
      title: "Git cho người mới bắt đầu",
      category_id: category.id,
      subtitle: "Commit, nhánh và gộp nhánh — đủ để làm việc nhóm",
      description:
        "Khóa học ngắn về Git: lưu lịch sử bằng commit, làm việc trên nhánh riêng, " +
        "gộp nhánh và xử lý xung đột.",
      price: 0,
    },
  });
  const section = await api(request, "POST", `/courses/${course.id}/sections`, {
    token,
    data: { title: "Chương 1 — Commit và nhánh" },
  });
  const article = await api(request, "POST", `/sections/${section.id}/lessons`, {
    token,
    data: { title: "Commit, nhánh và gộp nhánh", type: "article", article_content: GIT_ARTICLE },
  });
  const quizLesson = await api(request, "POST", `/sections/${section.id}/lessons`, {
    token,
    data: { title: "Kiểm tra: Git cơ bản", type: "quiz" },
  });
  const quiz = await api(request, "POST", `/lessons/${quizLesson.id}/quiz`, {
    token,
    data: { time_limit_s: 600, pass_score: 70 },
  });
  log("Gemini: sinh 5 câu hỏi từ bài đọc…");
  const generated = await api(request, "POST", `/quizzes/${quiz.id}/generate`, {
    token,
    data: { source_lesson_id: article.id, count: 5 },
  });
  log(`Gemini: ${generated.created}/${generated.requested} câu, model ${generated.model}`);

  const context = await newContext(browser);
  const page = await signIn(context, teacher);
  await open(page, `/giang-day/${course.id}`);
  await shot(page, "36-giang-vien-sinh-quiz-ai", async (p) => {
    const edit = p.getByRole("button", { name: "Sửa bài học Kiểm tra: Git cơ bản" });
    await edit.click();
    await p.waitForTimeout(2000);
    await scrollTo(edit, 40);
  });
  await signOut(context);
  await context.close();

  // Duyệt hết câu nháp, xuất bản quiz, gửi khóa đi duyệt.
  for (const question of generated.questions) {
    await api(request, "POST", `/quiz-questions/${question.id}/approve`, { token });
  }
  await api(request, "PATCH", `/quizzes/${quiz.id}`, { token, data: { is_published: true } });
  await api(request, "POST", `/courses/${course.id}/submit`, { token });

  const adminContext = await newContext(browser);
  const admin = await signIn(adminContext, ACCOUNTS.admin);
  await open(admin, "/quan-tri/khoa-hoc");
  await shot(admin, "40-admin-hang-doi-duyet");
  await open(admin, `/quan-tri/khoa-hoc/${course.id}`);
  await shot(admin, "41-admin-trang-duyet");
  await signOut(adminContext);
  await adminContext.close();
}

async function admin(browser) {
  if (!wants("42-admin-tong-quan", "43-admin-bao-cao", "44-admin-nguoi-dung", "45-admin-danh-muc", "46-admin-ma-giam-gia", "47-admin-banner")) return;
  const context = await newContext(browser);
  const page = await signIn(context, ACCOUNTS.admin);

  await open(page, "/quan-tri");
  await shot(page, "42-admin-tong-quan");
  await open(page, "/quan-tri/bao-cao");
  await shot(page, "43-admin-bao-cao");
  await open(page, "/quan-tri/nguoi-dung");
  await shot(page, "44-admin-nguoi-dung");
  await open(page, "/quan-tri/danh-muc");
  await shot(page, "45-admin-danh-muc");
  await open(page, "/quan-tri/ma-giam-gia");
  await shot(page, "46-admin-ma-giam-gia");
  await open(page, "/quan-tri/banner");
  await shot(page, "47-admin-banner");

  await signOut(context);
  await context.close();
}

/**
 * Phiên API của giảng viên chủ khóa cho bài "Kiểm tra: ép kiểu": đọc đáp án
 * (để học viên trả lời đúng có chủ đích, trừ một câu), và tạm đặt giới hạn
 * thời gian — quiz seed không tính giờ, mà ảnh cần thấy đồng hồ. `restore()`
 * trả về đúng giá trị cũ.
 */
async function quizSession() {
  const request = await playwrightRequest.newContext();
  const token = await apiLogin(request, ACCOUNTS.instructor);
  const course = await api(request, "GET", `/courses/by-slug/${COURSE}`);
  const curriculum = await api(request, "GET", `/courses/${course.id}/curriculum`);
  const lesson = curriculum.sections
    .flatMap((s) => s.lessons)
    .find((l) => l.title === "Kiểm tra: ép kiểu");
  const quiz = await api(request, "GET", `/lessons/${lesson.id}/quiz`, { token });
  const questions = await api(request, "GET", `/quizzes/${quiz.id}/questions`, { token });
  const original = quiz.time_limit_s ?? null;
  return {
    key: questions.map((q) => ({
      question: q.question,
      options: q.options,
      answer: q.options[q.correct_index],
    })),
    async limit(seconds) {
      await api(request, "PATCH", `/quizzes/${quiz.id}`, { token, data: { time_limit_s: seconds } });
    },
    async restore() {
      await api(request, "PATCH", `/quizzes/${quiz.id}`, { token, data: { time_limit_s: original } });
      await api(request, "POST", "/auth/logout").catch(() => {});
      await request.dispose();
    },
  };
}

function purgeStaged() {
  if (process.env.SKIP_STAGE || process.env.KEEP_STAGE) return;
  if (!wants("36-giang-vien-sinh-quiz-ai", "40-admin-hang-doi-duyet", "41-admin-trang-duyet")) return;
  try {
    const output = execFileSync(
      "docker",
      ["compose", "-f", COMPOSE_FILE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"],
      { encoding: "utf8" },
    );
    log("purge_e2e:", output.trim().split("\n").slice(-2).join(" | "));
  } catch (error) {
    log("purge_e2e hỏng — chạy tay `python -m scripts.purge_e2e`:", String(error).split("\n")[0]);
  }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  let quiz = null;
  if (wants("16-hoc-vien-quiz-dang-lam", "17-hoc-vien-quiz-ket-qua")) {
    try {
      quiz = await quizSession();
      LEARNER_STATE.quizKey = quiz.key;
      await quiz.limit(600);
    } catch (error) {
      log("không mở được phiên giảng viên cho quiz:", String(error).split("\n")[0]);
    }
  }

  const browser = await chromium.launch({ channel: CHANNEL || undefined });
  try {
    for (const [role, run] of [
      ["khách", guest],
      ["học viên", learner],
      ["người mua", buyer],
      ["giỏ hàng", shopper],
      ["giảng viên", instructor],
      ["admin", admin],
      ["khóa tạm", stagedCourse],
    ]) {
      // Một vai hỏng (thường là đăng nhập) không được làm mất các vai còn lại.
      await run(browser).catch((error) => {
        const message = String(error).split("\n")[0];
        results.push({ name: `(vai ${role})`, ok: false, error: message });
        log("FAIL", `vai ${role}:`, message);
      });
    }
  } finally {
    await browser.close();
    await quiz?.restore().catch((error) => {
      log("CHƯA TRẢ LẠI giới hạn giờ của quiz:", String(error).split("\n")[0]);
    });
    purgeStaged();
  }

  const failed = results.filter((r) => !r.ok);
  // Chạy lại một phần (ONLY) thì gộp vào nhật ký cũ thay vì xóa nó.
  const logFile = path.join(OUT, "capture-log.json");
  let merged = results;
  if (ONLY && fs.existsSync(logFile)) {
    const previous = JSON.parse(fs.readFileSync(logFile, "utf8")).results ?? [];
    const fresh = new Set(results.map((r) => r.name));
    merged = [...previous.filter((r) => !fresh.has(r.name)), ...results].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }
  fs.writeFileSync(
    logFile,
    `${JSON.stringify({ base: BASE, at: new Date().toISOString(), results: merged }, null, 2)}\n`,
  );
  log(`${results.length - failed.length}/${results.length} ảnh`);
  if (failed.length) process.exitCode = 1;
}

main();
