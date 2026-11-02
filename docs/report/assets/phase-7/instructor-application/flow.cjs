// Real flow on the dev stack: a learner applies, the admin approves, the
// learner reaches /giang-day without reloading. Plus one rejection.
//
// Run from the repository root with the dev stack up. The admin clicks the
// first card with the learner's name, so clear earlier runs' accounts first:
//   (cd infra && docker compose exec -T backend python -m scripts.purge_e2e)
//   OUT=<folder for screenshots> NODE_PATH=frontend/node_modules \
//     node docs/report/assets/phase-7/instructor-application/flow.cjs
// Signs the seed admin in once (10 sign-ins / 15 min per email). Leaves two
// @e2e.devpath.example accounts behind: purge_e2e removes them.
const { chromium } = require("playwright");
const path = require("path");

const WEB = "http://localhost:3000";
const API = "http://localhost:8000/api/v1";
const OUT = process.env.OUT;
const PASSWORD = "mat-khau-e2e-du-dai";
const stamp = Date.now().toString(36);

async function register(request, name) {
  const email = `ungvien-${name}-${stamp}@e2e.devpath.example`;
  const r = await request.post(`${API}/auth/register`, {
    data: { email, password: PASSWORD, full_name: name === "a" ? "Ứng Viên Duyệt" : "Ứng Viên Từ Chối" },
  });
  if (!r.ok()) throw new Error(`register ${r.status()} ${await r.text()}`);
  return email;
}

async function signedInPage(browser, email, password, viewport) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const login = await page.request.post(`${API}/auth/login`, { data: { email, password } });
  if (!login.ok()) throw new Error(`login ${email} ${login.status()} ${await login.text()}`);
  return page;
}

function check(cond, msg) {
  if (!cond) throw new Error(`FAIL: ${msg}`);
  console.log(`ok - ${msg}`);
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const setup = await browser.newContext();
  const a = await register(setup.request, "a");
  const b = await register(setup.request, "b");

  // --- Learner A applies -----------------------------------------------
  const learner = await signedInPage(browser, a, PASSWORD, { width: 1440, height: 900 });
  await learner.goto(`${WEB}/tro-thanh-giang-vien`);
  await learner.getByLabel("Giới thiệu ngắn về bạn (không bắt buộc)").fill(
    "Mình dạy Python ở trung tâm 3 năm.\nMuốn mở khóa cho người mới.",
  );
  await learner.screenshot({ path: path.join(OUT, "1-learner-form-1440.png"), fullPage: true });
  await learner.getByRole("button", { name: "Gửi yêu cầu" }).click();
  await learner.getByRole("heading", { name: "Yêu cầu đang chờ duyệt" }).waitFor();
  check(true, "learner sees pending state after sending");
  await learner.screenshot({ path: path.join(OUT, "2-learner-pending-1440.png"), fullPage: true });

  // Before approval, /giang-day says not an instructor.
  await learner.goto(`${WEB}/giang-day`);
  await learner.getByText("Bạn chưa phải giảng viên", { exact: true }).waitFor();
  check(true, "/giang-day refuses while pending");
  await learner.waitForTimeout(2000);
  check(await learner.getByText("Bạn chưa phải giảng viên", { exact: true }).count() === 1, "gate stays put (no refresh loop)");
  await learner.screenshot({ path: path.join(OUT, "2b-learner-gate-1440.png") });
  await learner.goto(`${WEB}/tro-thanh-giang-vien`);
  await learner.getByRole("heading", { name: "Yêu cầu đang chờ duyệt" }).waitFor();

  // Learner B applies through the API, to be rejected.
  const bPage = await signedInPage(browser, b, PASSWORD, { width: 360, height: 800 });
  const bToken = (await (await bPage.request.post(`${API}/auth/refresh`)).json()).access_token;
  const sent = await bPage.request.post(`${API}/users/me/instructor-application`, {
    headers: { Authorization: `Bearer ${bToken}` },
    data: {},
  });
  check(sent.status() === 201, "learner B applied with no introduction");

  // --- Admin decides ---------------------------------------------------
  const admin = await signedInPage(browser, "admin@devpath.example", "devpath-admin", {
    width: 1440,
    height: 900,
  });
  await admin.goto(`${WEB}/quan-tri`);
  await admin.getByText("Yêu cầu làm giảng viên").first().waitFor();
  await admin.screenshot({ path: path.join(OUT, "3-admin-overview-1440.png"), fullPage: true });
  const navLink = admin.getByRole("navigation", { name: "Khu vực quản trị" }).getByRole("link", { name: /Duyệt giảng viên/ });
  const navText = await navLink.innerText();
  check(/\d/.test(navText), `nav badge shows a count ("${navText.replace(/\s+/g, " ")}")`);
  await navLink.click();
  await admin.getByRole("heading", { name: "Duyệt giảng viên", level: 1 }).waitFor();
  await admin.getByRole("article", { name: "Yêu cầu của Ứng Viên Duyệt" }).first().waitFor();
  await admin.screenshot({ path: path.join(OUT, "4-admin-queue-1440.png"), fullPage: true });

  await admin.getByRole("button", { name: "Duyệt Ứng Viên Duyệt làm giảng viên" }).first().click();
  await admin.getByText(/Đã duyệt Ứng Viên Duyệt/).waitFor();
  check(true, "admin approved A");

  await admin.getByRole("button", { name: "Từ chối yêu cầu của Ứng Viên Từ Chối" }).first().click();
  await admin.getByLabel("Lý do từ chối").fill("Bạn bổ sung kinh nghiệm dạy hoặc chủ đề định dạy rồi gửi lại nhé.");
  await admin.screenshot({ path: path.join(OUT, "5-admin-rejecting-1440.png"), fullPage: true });
  await admin.getByRole("button", { name: "Từ chối yêu cầu", exact: true }).click();
  await admin.getByText(/Đã từ chối yêu cầu của Ứng Viên Từ Chối/).waitFor();
  check(true, "admin rejected B with a reason");

  // --- Learner A, same tab, follows the notification ---------------------
  await learner.getByRole("button", { name: /Thông báo/ }).click();
  const item = learner.getByText(/Yêu cầu trở thành giảng viên của bạn đã được duyệt/).first();
  await item.waitFor({ timeout: 70_000 });
  await learner.screenshot({ path: path.join(OUT, "6-learner-bell-1440.png") });
  await item.click();
  await learner.waitForURL(/\/giang-day/);
  await learner.getByText("Bạn chưa phải giảng viên", { exact: true }).waitFor({ state: "detached", timeout: 15_000 }).catch(() => {});
  await learner.waitForTimeout(1500);
  const refused = await learner.getByText("Bạn chưa phải giảng viên", { exact: true }).count();
  check(refused === 0, "A reaches /giang-day from the notification without reloading");
  await learner.screenshot({ path: path.join(OUT, "7-learner-teaching-1440.png"), fullPage: true });

  // --- Learner B sees the reason, at 360 px ---------------------------------
  await bPage.goto(`${WEB}/tro-thanh-giang-vien`);
  await bPage.getByText("Yêu cầu trước chưa được duyệt").waitFor();
  check(await bPage.getByText("Bạn bổ sung kinh nghiệm dạy").count() > 0, "B sees the rejection reason");
  check(await bPage.getByRole("button", { name: "Gửi lại yêu cầu" }).count() === 1, "B may apply again");
  const overflow = await bPage.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  check(overflow <= 0, `no horizontal overflow at 360 (${overflow})`);
  await bPage.screenshot({ path: path.join(OUT, "8-learner-rejected-360.png"), fullPage: true });

  // Admin queue at 360 px.
  await admin.setViewportSize({ width: 360, height: 800 });
  await admin.getByRole("button", { name: "Tất cả" }).click();
  await admin.waitForTimeout(800);
  const adminOverflow = await admin.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  check(adminOverflow <= 0, `admin queue has no horizontal overflow at 360 (${adminOverflow})`);
  await admin.screenshot({ path: path.join(OUT, "9-admin-queue-all-360.png"), fullPage: true });

  await browser.close();
  console.log(`accounts: ${a} ${b}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
