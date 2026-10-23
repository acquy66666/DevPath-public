// Bài đọc: ô soạn có xem trước, thanh công cụ, chèn ảnh -- run through the real
// UI on the dev stack, with screenshots.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/article-editor/run.cjs
//
// Needs the dev stack (infra/docker-compose.yml) with storage. Stages one
// throwaway instructor (@e2e.devpath.example) with a draft course and one
// article lesson through the API, signs in through the real form, then:
// writes, uses the toolbar (and checks Ctrl+Z undoes it), pastes a generated
// PNG as if from the clipboard, waits for it to reach the bucket, checks the
// preview draws it and that an image from another site is shown as a link
// without being fetched, opens full screen, saves, and reads the lesson back.
// `scripts.purge_e2e` removes the account and course at the end; the uploaded
// picture is left to the orphan sweep, like any picture nothing names.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const OUT = __dirname;
const REPO = path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const PASSWORD = "devpath-article-1";
const LESSON_TITLE = "Chạy chương trình Python đầu tiên";
const EXTERNAL = "https://tracker.example/pixel.png";

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

async function call(method, pathname, { token, body } = {}) {
  const r = await fetch(`${API}/api/v1${pathname}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

async function stage() {
  const email = `baidoc-${Date.now().toString(36)}@e2e.devpath.example`;
  const { access_token: token } = await call("POST", "/auth/register", {
    body: { email, password: PASSWORD, full_name: "Giảng Viên Bài Đọc" },
  });
  await call("POST", "/users/me/instructor", { token });
  const categories = await call("GET", "/categories");
  const category = (categories[0].children ?? [])[0] ?? categories[0];
  const course = await call("POST", "/courses", {
    token,
    body: { title: "Khóa thử ô soạn bài đọc", category_id: category.id, price: 0 },
  });
  const section = await call("POST", `/courses/${course.id}/sections`, {
    token,
    body: { title: "Chương 1. Làm quen" },
  });
  const lesson = await call("POST", `/sections/${section.id}/lessons`, {
    token,
    body: { title: LESSON_TITLE, type: "article" },
  });
  await call("POST", "/auth/logout", { token }).catch(() => {});
  return { email, courseId: course.id, lessonId: lesson.id };
}

function purge() {
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function signIn(page, email) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  const answered = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (!(await answered).ok()) throw new Error("đăng nhập thất bại");
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

async function shoot(page, name, options = {}) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  const file = path.join(OUT, `${name}.png`);
  await (options.element ?? page).screenshot({ path: file, ...(options.element ? {} : { fullPage: false }) });
  console.log(`      ảnh ${path.relative(REPO, file)}`);
}

/** Select `text` inside the textarea. */
async function select(area, text) {
  await area.evaluate((el, needle) => {
    const at = el.value.indexOf(needle);
    el.focus();
    el.setSelectionRange(at, at + needle.length);
  }, text);
}

/** Paste a freshly drawn PNG into the textarea, the way Ctrl+V of a screenshot does. */
async function pastePicture(area, filename) {
  await area.evaluate(async (el, name) => {
    const canvas = document.createElement("canvas");
    canvas.width = 720;
    canvas.height = 300;
    const g = canvas.getContext("2d");
    g.fillStyle = "#1e2430";
    g.fillRect(0, 0, 720, 300);
    g.fillStyle = "#2c3443";
    g.fillRect(0, 0, 720, 36);
    for (const [i, c] of ["#ff5f56", "#ffbd2e", "#27c93f"].entries()) {
      g.fillStyle = c;
      g.beginPath();
      g.arc(22 + i * 22, 18, 7, 0, Math.PI * 2);
      g.fill();
    }
    g.font = "20px monospace";
    g.fillStyle = "#9fe3b4";
    g.fillText("$ python3 hello.py", 24, 90);
    g.fillStyle = "#e8edf5";
    g.fillText("Xin chào, DevPath!", 24, 130);
    g.fillStyle = "#9fe3b4";
    g.fillText("$ _", 24, 170);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    const data = new DataTransfer();
    data.items.add(new File([blob], name, { type: "image/png" }));
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }, filename);
}

(async () => {
  const staged = await stage();
  console.log(`staged ${staged.email}, course ${staged.courseId}`);

  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN" });
  const page = await context.newPage();
  const external = [];
  page.on("request", (r) => {
    if (r.url().startsWith("https://tracker.example")) external.push(r.url());
  });
  const puts = [];
  page.on("response", (r) => {
    if (r.request().method() === "PUT" && r.url().includes("/lesson-images/")) puts.push(r.status());
  });

  try {
    await signIn(page, staged.email);
    await page.goto(`${BASE}/giang-day/${staged.courseId}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: `Sửa bài học ${LESSON_TITLE}` }).click();
    const area = page.getByLabel("Nội dung bài đọc");
    await area.waitFor();

    // --- Writing, and the toolbar --------------------------------------------
    await area.fill(
      [
        "## Mở đầu",
        "",
        "Trong bài này bạn sẽ chạy chương trình Python đầu tiên ngay trên máy của mình.",
        "",
        "Mở terminal",
        "Gõ lệnh python3 hello.py",
        "Xem kết quả in ra",
        "",
      ].join("\n"),
    );

    await select(area, "chương trình Python đầu tiên");
    await page.getByRole("button", { name: "Chữ đậm" }).click();
    let value = await area.inputValue();
    check("Nút Chữ đậm bọc đúng phần được chọn", value.includes("**chương trình Python đầu tiên**"));

    await area.press("Control+z");
    value = await area.inputValue();
    check("Ctrl+Z hoàn tác cú bấm thanh công cụ", !value.includes("**") && value.includes("chương trình Python đầu tiên"));
    await select(area, "chương trình Python đầu tiên");
    await area.press("Control+b");
    check("Phím tắt Ctrl+B làm chữ đậm", (await area.inputValue()).includes("**chương trình Python đầu tiên**"));

    await select(area, "Mở terminal\nGõ lệnh python3 hello.py\nXem kết quả in ra");
    await page.getByRole("button", { name: "Danh sách đánh số" }).click();
    value = await area.inputValue();
    check("Danh sách đánh số đánh 1. 2. 3.", value.includes("1. Mở terminal\n2. Gõ lệnh python3 hello.py\n3. Xem kết quả in ra"));

    await select(area, "python3 hello.py");
    await page.getByRole("button", { name: "Code trong dòng" }).click();

    await area.evaluate((el) => el.setSelectionRange(el.value.length, el.value.length));
    await page.getByRole("button", { name: "Bảng" }).click();
    await page.keyboard.type("Lệnh");
    value = await area.inputValue();
    check("Nút Bảng chèn bảng và chọn sẵn ô tiêu đề đầu", value.includes("| Lệnh | Cột 2 |\n| --- | --- |"));

    // --- A picture, pasted -----------------------------------------------------
    await pastePicture(area, "terminal-hello.png");
    await page.waitForFunction(
      (id) => {
        const el = document.getElementById(id);
        return el && el.value.includes("/lesson-images/") && !el.value.includes("Đang tải ảnh lên");
      },
      await area.getAttribute("id"),
      { timeout: 60_000 },
    );
    value = await area.inputValue();
    const picture = value.match(/!\[([^\]]*)\]\(([^)]+)\)/);
    check("Dán ảnh: tải lên bucket rồi thay chỗ giữ bằng địa chỉ thật", Boolean(picture) && puts.every((s) => s === 200) && puts.length === 1, `PUT ${puts.join(",")} → ${picture?.[2]}`);
    check("Mô tả ảnh lấy từ tên tệp", picture?.[1] === "terminal hello", picture?.[1]);
    // Node on Windows does not resolve *.localhost the way Chrome does.
    const fetched = await fetch(picture[2].replace("//minio.localhost:", "//127.0.0.1:"));
    check("Ảnh đọc lại được từ bucket", fetched.ok && fetched.headers.get("content-type") === "image/png", `${fetched.status} ${fetched.headers.get("content-type")}`);

    // An image from somewhere else, to see that it is not fetched.
    await area.evaluate((el) => el.setSelectionRange(el.value.length, el.value.length));
    await area.press("End");
    await page.keyboard.type(`\n\nẢnh từ trang khác: ![ảnh theo dõi](${EXTERNAL})\n`);
    // The lesson panel under its row: title, editor, "học thử", save.
    const panel = area.locator("xpath=ancestor::div[contains(@class,'border-t')][1]");
    await shoot(page, "1-soan-1440", { element: panel });

    // --- Preview ---------------------------------------------------------------
    await page.getByRole("tab", { name: "Xem trước" }).click();
    const preview = page.getByRole("region", { name: "Xem trước bài đọc" });
    await preview.locator("img").first().waitFor();
    const drawn = await preview.locator("img").first().evaluate((img) =>
      img.complete ? img.naturalWidth : new Promise((r) => (img.onload = () => r(img.naturalWidth))),
    );
    check("Xem trước vẽ ảnh đã tải", drawn === 720, `naturalWidth ${drawn}`);
    check("Xem trước hiện bảng thật (remark-gfm)", (await preview.locator("table th").count()) === 2);
    check("Ảnh trang khác thành liên kết", (await preview.getByRole("link", { name: /Ảnh ngoài: ảnh theo dõi/ }).count()) === 1);
    check("Ảnh trang khác không bị tải", external.length === 0, `${external.length} request`);
    await shoot(page, "2-xem-truoc-1440", { element: preview });

    // --- Full screen -----------------------------------------------------------
    await page.getByRole("button", { name: "Toàn màn hình" }).click();
    const both = await page.evaluate(() => {
      const w = document.querySelector('[aria-label="Soạn bài đọc toàn màn hình"] textarea');
      const p = document.querySelector('[aria-label="Xem trước bài đọc"]');
      return Boolean(w && p && w.offsetWidth > 0 && p.offsetWidth > 0);
    });
    check("Toàn màn hình ở 1440 px: soạn và xem trước cạnh nhau", both);
    await shoot(page, "3-toan-man-hinh-1440");
    await page.getByLabel("Nội dung bài đọc").press("Escape");
    check("Esc thoát toàn màn hình", (await page.getByRole("region", { name: "Soạn bài đọc toàn màn hình" }).count()) === 0);

    // --- Save, and read back ---------------------------------------------------
    await page.getByRole("tab", { name: "Soạn" }).click();
    await page.getByRole("button", { name: "Lưu bài học" }).click();
    await page.getByText("Đã lưu bài học.").waitFor({ timeout: 30_000 });
    const saved = await page.evaluate(
      async ({ api, id }) => {
        const refreshed = await fetch(`${api}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
        const { access_token } = await refreshed.json();
        const r = await fetch(`${api}/api/v1/lessons/${id}`, { headers: { authorization: `Bearer ${access_token}` } });
        return (await r.json()).article_content;
      },
      { api: API, id: staged.lessonId },
    );
    check("Lưu xong, bài đọc trên máy chủ chứa đúng địa chỉ ảnh", saved.includes(picture[2]));

    // --- Phone width -----------------------------------------------------------
    await page.setViewportSize({ width: 375, height: 812 });
    await page.getByLabel("Nội dung bài đọc").scrollIntoViewIfNeeded();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    check("375 px: không tràn ngang", overflow <= 0, `${overflow}px`);
    // The page can stay 375 wide while a card inside it scrolls sideways: the
    // editor itself must end inside the lesson panel.
    const spill = await area.evaluate((el) => {
      const panel = el.closest("div.border-t");
      const toolbar = panel.querySelector('[role="toolbar"]');
      const right = panel.getBoundingClientRect().right;
      return Math.round(Math.max(el.getBoundingClientRect().right, toolbar.getBoundingClientRect().right) - right);
    });
    check("375 px: ô soạn và thanh công cụ nằm gọn trong khung bài học", spill <= 0, `${spill}px`);
    await shoot(page, "4-soan-375");
    await page.getByRole("tab", { name: "Xem trước" }).click();
    await page.getByRole("region", { name: "Xem trước bài đọc" }).scrollIntoViewIfNeeded();
    const overflowPreview = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    check("375 px xem trước: bảng cuộn trong khung, trang không tràn", overflowPreview <= 0, `${overflowPreview}px`);
    await shoot(page, "5-xem-truoc-375");
  } finally {
    await page
      .evaluate((api) => fetch(`${api}/api/v1/auth/logout`, { method: "POST", credentials: "include" }), API)
      .catch(() => {});
    await browser.close();
    purge();
  }

  const failed = results.filter((r) => !r.ok);
  fs.writeFileSync(
    path.join(OUT, "results.json"),
    JSON.stringify({ ranAt: new Date().toISOString(), results }, null, 2) + "\n",
  );
  console.log(`\n${results.length - failed.length}/${results.length} passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((error) => {
  console.error(error);
  try {
    purge();
  } catch {}
  process.exit(1);
});
