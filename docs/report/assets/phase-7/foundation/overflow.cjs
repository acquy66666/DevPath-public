// Task "Nền" (Phase 7): horizontal overflow at 360/375/1440px on every route,
// as a guest, a learner, an instructor and the admin -- plus screenshots of the
// header, footer, menus and a few component-heavy pages.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/foundation/overflow.cjs
//
// ROLES=guest,student,instructor,admin picks who to measure (default: all four).
// BASE (default http://localhost:3000) and API (default http://localhost:8000)
// point at the dev stack. Accounts default to the seed ones; override with
// STUDENT_EMAIL/STUDENT_PASSWORD, INSTRUCTOR_EMAIL/SEED_INSTRUCTOR_PASSWORD,
// ADMIN_EMAIL/SEED_ADMIN_PASSWORD. Reads only: every session it opens, in the
// browser or over the API, is signed out at the end. Exit 1 on any overflow.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const OUT = __dirname;
const SHOTS = path.join(OUT, "shots");
fs.mkdirSync(SHOTS, { recursive: true });

const ACCOUNTS = {
  student: {
    email: process.env.STUDENT_EMAIL || "nguoimua08@sales.devpath.example",
    password: process.env.STUDENT_PASSWORD || "devpath-buyer",
  },
  instructor: {
    email: process.env.INSTRUCTOR_EMAIL || "khoa.tran@devpath.example",
    password: process.env.SEED_INSTRUCTOR_PASSWORD || "devpath-instructor",
  },
  admin: {
    email: process.env.ADMIN_EMAIL || "admin@devpath.example",
    password: process.env.SEED_ADMIN_PASSWORD || "devpath-admin",
  },
};
const WIDTHS = [360, 375, 1440];

// --- API: find real ids to visit ------------------------------------------

async function apiLogin({ email, password }) {
  const r = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`API login ${email}: ${r.status}`);
  const body = await r.json();
  const cookie = (r.headers.getSetCookie?.() ?? []).map((c) => c.split(";")[0]).join("; ");
  return { token: body.access_token, cookie };
}

async function apiLogout(session) {
  await fetch(`${API}/api/v1/auth/logout`, { method: "POST", headers: { cookie: session.cookie } }).catch(() => {});
}

async function get(pathname, token) {
  const r = await fetch(`${API}${pathname}`, { headers: token ? { authorization: `Bearer ${token}` } : {} });
  if (!r.ok) throw new Error(`GET ${pathname}: ${r.status}`);
  return r.json();
}

async function discover() {
  const catalogue = await get("/api/v1/courses?page_size=12");
  const slug = catalogue.items[0]?.slug;

  /** Signed in over the API for one question, and signed out whatever happens. */
  async function as(account, ask) {
    const session = await apiLogin(account);
    try {
      return await ask(session.token);
    } finally {
      await apiLogout(session);
    }
  }

  const lessons = {};
  let learnSlug = null;
  const cert = await as(ACCOUNTS.student, async (token) => {
    const mine = await get("/api/v1/enrollments/me?page=1", token);
    // The course with the most kinds of lesson: video, article, quiz, code.
    for (const e of mine.items) {
      const curriculum = await get(`/api/v1/courses/${e.course.id}/curriculum`, token);
      const all = curriculum.sections.flatMap((s) => s.lessons);
      const types = new Set(all.map((l) => l.type));
      if (!learnSlug || types.size > Object.keys(lessons).length) {
        learnSlug = e.course.slug;
        for (const k of Object.keys(lessons)) delete lessons[k];
        for (const l of all) lessons[l.type] ??= l.id;
      }
    }
    return mine.items.find((e) => e.certificate_code)?.certificate_code ?? null;
  });

  const taught = await as(ACCOUNTS.instructor, (token) => get("/api/v1/courses/me?page=1&page_size=5", token));
  const statements = await as(ACCOUNTS.admin, (token) =>
    get("/api/v1/admin/payouts/statements", token).catch(() => ({ items: [] })),
  );

  return {
    slug,
    cert,
    learnSlug,
    lessons,
    courseId: taught.items[0]?.id ?? null,
    statementId: (statements.items ?? statements)[0]?.id ?? null,
  };
}

// --- Pages -------------------------------------------------------------------

function routes(d) {
  const learn = (type) => (d.lessons[type] ? `/hoc/${d.learnSlug}?bai=${d.lessons[type]}` : null);
  return {
    guest: [
      "/",
      "/khoa-hoc",
      "/khoa-hoc?q=khongtimthayxyz",
      `/khoa-hoc/${d.slug}`,
      "/bang-xep-hang",
      d.cert ? `/cert/${d.cert}` : null,
      "/cert/KHONGCOMANAY0000",
      "/dang-nhap",
      "/dang-ky",
      "/chao-mung",
      "/tro-thanh-giang-vien",
      "/chinh-sach-bao-mat",
      "/khoa-hoc-cua-toi",
      "/khong-co-trang-nay",
    ],
    student: [
      "/",
      "/khoa-hoc-cua-toi",
      "/gio-hang",
      "/yeu-thich",
      "/thong-bao",
      "/ho-so",
      "/chao-mung",
      "/bang-xep-hang",
      `/khoa-hoc/${d.slug}`,
      learn("video"),
      learn("article"),
      learn("quiz"),
      learn("code_exercise"),
      "/thanh-toan/ket-qua?vnp_TxnRef=KHONGCO",
    ],
    instructor: [
      "/giang-day",
      "/giang-day/thong-ke",
      "/giang-day/hoi-dap",
      "/giang-day/cap-bac",
      "/giang-day/moi",
      d.courseId ? `/giang-day/${d.courseId}` : null,
    ],
    admin: [
      "/quan-tri",
      "/quan-tri/doanh-thu",
      "/quan-tri/xep-hang",
      "/quan-tri/cap-giang-vien",
      "/quan-tri/thanh-toan",
      d.statementId ? `/quan-tri/thanh-toan/${d.statementId}` : null,
      "/quan-tri/loi-nhuan",
      "/quan-tri/khoa-hoc",
      "/quan-tri/bao-cao",
      "/quan-tri/nguoi-dung",
      "/quan-tri/danh-muc",
      "/quan-tri/ma-giam-gia",
      "/quan-tri/banner",
    ],
  };
}

/** Screenshots: [role, width, url-or-predicate, name, action?]. */
const SHOOT = [
  ["guest", 360, "/", "header-khach-360"],
  ["guest", 360, "/", "menu-dien-thoai-360", "mobile-menu"],
  ["guest", 1440, "/", "header-khach-1440"],
  ["guest", 375, "/dang-nhap", "dang-nhap-375"],
  ["guest", 1440, "/chinh-sach-bao-mat", "footer-1440", "footer"],
  ["guest", 375, "/chinh-sach-bao-mat", "footer-375", "footer"],
  ["guest", 1440, "/khoa-hoc", "khoa-hoc-1440"],
  ["student", 360, "/khoa-hoc-cua-toi", "header-hoc-vien-360"],
  ["student", 1440, "/khoa-hoc-cua-toi", "menu-tai-khoan-1440", "user-menu"],
  ["student", 1440, "/gio-hang", "gio-hang-1440"],
  ["student", 1440, "/ho-so", "ho-so-1440"],
  ["student", 1440, (u) => u.includes("bai=") && u.includes(SHOT_LESSON), "hoc-code-1440"],
  ["student", 375, "/bang-xep-hang", "bang-xep-hang-375"],
  ["instructor", 1440, "/giang-day", "giang-day-1440"],
  ["instructor", 1440, "/giang-day/thong-ke", "thong-ke-1440"],
  ["admin", 1440, "/quan-tri", "quan-tri-1440"],
  ["admin", 1440, "/quan-tri/loi-nhuan", "loi-nhuan-dialog-1440", "dialog"],
  ["admin", 375, "/quan-tri/nguoi-dung", "nguoi-dung-375"],
];
let SHOT_LESSON = "\0";

// --- Browser ------------------------------------------------------------------

async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  // Skeletons give way to data a beat after the last response.
  await page.waitForTimeout(600);
}

async function signIn(context, account) {
  const page = await context.newPage();
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  // Clicking before React owns the form submits it as a GET: wait for one form with React props.
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  const response = await answered;
  if (!response.ok()) throw new Error(`đăng nhập ${account.email}: ${response.status()}`);
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
  return page;
}

async function signOut(page) {
  await page
    .evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API)
    .catch(() => {});
}

function measure() {
  const vw = document.documentElement.clientWidth;
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    const b = el.getBoundingClientRect();
    const position = getComputedStyle(el).position;
    if (!b.width || b.right <= vw + 0.5 || position === "fixed") continue;
    // A scroll box only clips an absolutely positioned element when the box
    // is, or contains, its containing block: an `sr-only` label in a table
    // whose scroll box is not `relative` widens the page (found 22/10 on
    // /giang-day/thong-ke). Start the walk at the containing block.
    let p = el.parentElement;
    if (position === "absolute") {
      while (p && getComputedStyle(p).position === "static" && getComputedStyle(p).transform === "none") p = p.parentElement;
    }
    let clipped = false;
    while (p) {
      const o = getComputedStyle(p);
      if (/(hidden|clip|auto|scroll)/.test(o.overflowX) && p.getBoundingClientRect().right <= vw + 0.5) {
        clipped = true;
        break;
      }
      p = p.parentElement;
    }
    if (!clipped) {
      const cls = typeof el.className === "string" ? el.className.split(" ").slice(0, 4).join(".") : "";
      out.push(`${el.tagName.toLowerCase()}.${cls} right=${b.right.toFixed(1)} "${(el.textContent || "").trim().slice(0, 30)}"`);
    }
  }
  return { sw: document.documentElement.scrollWidth, vw, offenders: out.slice(0, 5) };
}

async function act(page, action) {
  if (action === "mobile-menu") {
    await page.getByRole("button", { name: "Mở menu điều hướng" }).click();
    await page.getByRole("menuitem", { name: "Khóa học" }).waitFor();
  } else if (action === "user-menu") {
    await page.getByRole("button", { name: /^Tài khoản:/ }).click();
    await page.getByRole("menuitem", { name: "Đăng xuất" }).waitFor();
  } else if (action === "footer") {
    await page.locator("footer").scrollIntoViewIfNeeded();
  } else if (action === "dialog") {
    await page.getByRole("button", { name: /Thêm khoản chi/ }).first().click();
    await page.getByRole("dialog").waitFor();
  }
  await page.waitForTimeout(450);
}

(async () => {
  const data = await discover();
  SHOT_LESSON = data.lessons.code_exercise ?? "\0";
  const pages = routes(data);
  console.log("data:", JSON.stringify(data));

  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const results = [];
  let overflow = 0;
  const roles = (process.env.ROLES || "guest,student,instructor,admin").split(",");
  for (const role of roles) {
    const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
    const errors = [];
    context.on("page", (p) => {
      p.on("console", (m) => m.type() === "error" && errors.push(`${p.url()} ${m.text().slice(0, 160)}`));
      p.on("pageerror", (e) => errors.push(`${p.url()} ${String(e).slice(0, 160)}`));
    });
    const page = role === "guest" ? await context.newPage() : await signIn(context, ACCOUNTS[role]);
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const url of pages[role].filter(Boolean)) {
        const resp = await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 180_000 });
        await settle(page);
        const r = await page.evaluate(measure);
        const over = r.sw > r.vw;
        overflow += over;
        results.push({ role, width, url, status: resp?.status() ?? null, scrollWidth: r.sw, clientWidth: r.vw, overflow: over, offenders: r.offenders });
        console.log(`${role.padEnd(10)} ${String(width).padStart(4)} ${String(resp?.status()).padEnd(3)} sw=${r.sw}/${r.vw}${over ? " TRÀN" : ""} ${url}${r.offenders.length ? "\n        " + r.offenders.join("\n        ") : ""}`);
        for (const [sRole, sWidth, sUrl, name, action] of SHOOT) {
          const hit = typeof sUrl === "function" ? sUrl(url) : sUrl === url;
          if (sRole !== role || sWidth !== width || !hit) continue;
          if (action) await act(page, action);
          await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: action === "footer" });
          if (action && action !== "footer") await page.keyboard.press("Escape");
        }
      }
    }
    if (role !== "guest") await signOut(page);
    results.push({ role, consoleErrors: errors });
    if (errors.length) console.log(`  ${role}: ${errors.length} lỗi console\n    ${errors.slice(0, 8).join("\n    ")}`);
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "overflow.json"), JSON.stringify({ base: BASE, at: new Date().toISOString(), data, results }, null, 2));
  const views = results.filter((r) => r.width).length;
  console.log(`\n${overflow}/${views} lượt xem tràn ngang`);
  process.exit(overflow ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
