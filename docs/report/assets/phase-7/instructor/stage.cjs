// Shared by capture.cjs and check.cjs: the throwaway instructor, their four
// courses and a learner's question (see capture.cjs for what is written), the
// API and database helpers, and the sign-in form. Everything it creates is on
// @e2e.devpath.example accounts; `purge()` removes it with scripts.purge_e2e.
const path = require("path");
const { execFileSync } = require("child_process");

const API = process.env.API || "http://localhost:8000";
const BASE = process.env.BASE || "http://localhost:3000";
const REPO = process.env.REPO || path.resolve(__dirname, "../../../../..");
const COMPOSE = path.join(REPO, "infra/docker-compose.yml");
const PASSWORD = "devpath-teach-1";
const ADMIN_EMAIL = "admin@devpath.example";
const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD || "devpath-admin";
const KHOA = { email: "khoa.tran@devpath.example", password: process.env.SEED_INSTRUCTOR_PASSWORD || "devpath-instructor" };

function accounts(stamp) {
  return {
    teacher: `giang-day-${stamp}@e2e.devpath.example`,
    learner: `hoc-vien-${stamp}@e2e.devpath.example`,
  };
}

let made = false;
function exec(...args) {
  return execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", ...args], { encoding: "utf8" });
}
function psql(sql) {
  return exec("postgres", "psql", "-U", "devpath", "-Atc", sql).trim();
}
function purge() {
  if (!made) return;
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function call(token, method, pathname, body) {
  const headers = {};
  if (body) headers["content-type"] = "application/json";
  if (token) headers.authorization = `Bearer ${token}`;
  const r = await fetch(`${API}/api/v1${pathname}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${method} ${pathname}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}
async function login(email, password) {
  return (await call(null, "POST", "/auth/login", { email, password })).access_token;
}

async function formReady(page) {
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 120_000 },
  );
}
async function signIn(page, email, password) {
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  await formReady(page);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 60_000 });
}

async function stage(TEACHER) {
  const registered = await call(null, "POST", "/auth/register", {
    email: TEACHER,
    password: PASSWORD,
    full_name: "Lê Thu Hà",
  });
  made = true;
  const t = registered.access_token;
  await call(t, "POST", "/users/me/instructor");
  return t;
}

async function stageCourses(t) {
  const categories = await call(null, "GET", "/categories");
  const python =
    categories.flatMap((c) => [c, ...(c.children || [])]).find((c) => /python/i.test(c.name)) ?? categories[0];

  // 1. Published, with every lesson type.
  const main = await call(t, "POST", "/courses", {
    title: "Python cho phân tích dữ liệu",
    category_id: python.id,
    subtitle: "Đọc, làm sạch và tóm tắt dữ liệu bằng Python thuần.",
    description: "Bạn sẽ đọc tệp CSV, lọc và gom nhóm dữ liệu, rồi in báo cáo ngắn.\n\n- Đọc tệp\n- Lọc và gom nhóm\n- In báo cáo",
    price: 0,
    level: "beginner",
  });
  const s1 = await call(t, "POST", `/courses/${main.id}/sections`, { title: "Làm quen với dữ liệu" });
  const video = await call(t, "POST", `/sections/${s1.id}/lessons`, { title: "Dữ liệu dạng bảng là gì", type: "video" });
  await call(t, "PATCH", `/lessons/${video.id}`, { is_preview: true });
  const article = await call(t, "POST", `/sections/${s1.id}/lessons`, {
    title: "Đọc tệp CSV bằng module csv",
    type: "article",
    article_content: "Module `csv` đọc từng dòng thành một danh sách.\n\n```python\nimport csv\n```",
  });
  const s2 = await call(t, "POST", `/courses/${main.id}/sections`, { title: "Lọc và đếm" });
  await call(t, "POST", `/sections/${s2.id}/lessons`, { title: "Vòng lặp qua từng dòng", type: "video" });
  const code = await call(t, "POST", `/sections/${s2.id}/lessons`, { title: "Bài tập: đếm số chẵn", type: "code_exercise" });
  const exercise = await call(t, "POST", `/lessons/${code.id}/code-exercise`, {
    statement_md: "Đọc một số nguyên `n` rồi in ra số lượng số chẵn trong khoảng từ 1 tới `n`.",
    starter_code: "n = int(input())\n# Viết code của bạn ở đây\n",
  });
  for (const [input, expected, hidden, weight] of [
    ["10", "5", false, 1],
    ["1", "0", true, 2],
    ["999999", "499999", true, 2],
  ]) {
    await call(t, "POST", `/code-exercises/${exercise.id}/test-cases`, {
      input,
      expected_output: expected,
      is_hidden: hidden,
      score_weight: weight,
    });
  }
  const quizLesson = await call(t, "POST", `/sections/${s2.id}/lessons`, { title: "Kiểm tra: ép kiểu", type: "quiz" });
  const quiz = await call(t, "POST", `/lessons/${quizLesson.id}/quiz`, { pass_score: 70 });
  const questions = [
    ["Hàm input() trong Python luôn trả về kiểu dữ liệu nào?", ["Số thực", "Chuỗi", "Boolean", "Số nguyên"], 1],
    ["Kết quả của biểu thức int(12.9) là bao nhiêu?", ["12.9", "12", "Lỗi", "13"], 1],
    ['Để chuyển chuỗi "12.5" thành số nguyên bằng int(), cần làm gì trước?', ["Dùng round()", "Cộng thêm 1", "Không thể chuyển", "Qua float trước"], 3],
    ["Khi làm việc với tiền, nên dùng kiểu gì để tránh sai số?", ["str", "float", "int", "Decimal"], 3],
  ];
  const ids = [];
  for (const [question, options, correct_index] of questions) {
    const q = await call(t, "POST", `/quizzes/${quiz.id}/questions`, {
      question,
      options,
      correct_index,
      explanation: "Xem lại bài “Ép kiểu và những cái bẫy quen thuộc”.",
    });
    ids.push(q.id);
  }
  psql(`update quiz_questions set ai_generated = true, reviewed_at = now() where id in ('${ids[0]}', '${ids[1]}')`);
  psql(`update quiz_questions set ai_generated = true, reviewed_at = null where id in ('${ids[2]}', '${ids[3]}')`);
  psql(`update courses set status = 'published', published_at = now() where id = '${main.id}'`);

  // 2. Draft.
  const draft = await call(t, "POST", "/courses", {
    title: "Trực quan hóa dữ liệu với matplotlib",
    category_id: python.id,
    price: 299000,
  });
  const ds = await call(t, "POST", `/courses/${draft.id}/sections`, { title: "Biểu đồ đầu tiên" });
  await call(t, "POST", `/sections/${ds.id}/lessons`, { title: "Vẽ biểu đồ đường", type: "video" });

  // 3. Sent back by the admin.
  const rejected = await call(t, "POST", "/courses", {
    title: "Kiểm thử Python với pytest",
    category_id: python.id,
    subtitle: "Viết test tự động cho code Python: fixture, parametrize và mock.",
    price: 0,
  });
  const rs = await call(t, "POST", `/courses/${rejected.id}/sections`, { title: "Test đầu tiên" });
  await call(t, "POST", `/sections/${rs.id}/lessons`, { title: "Cài pytest và chạy thử", type: "video" });
  await call(t, "POST", `/courses/${rejected.id}/sections`, { title: "Fixture" });
  await call(t, "POST", `/courses/${rejected.id}/submit`);
  const admin = await login(ADMIN_EMAIL, ADMIN_PASSWORD);
  await call(admin, "POST", `/admin/courses/${rejected.id}/reject`, {
    reason: "Chương 2 chưa có bài nào, và mô tả chưa nói học viên cần biết Python tới đâu.",
  });
  await call(admin, "POST", "/auth/logout").catch(() => {});

  // 4. Nothing in it yet.
  const empty = await call(t, "POST", "/courses", { title: "Thuật toán đồ thị với Python", category_id: python.id });

  return { main, draft, rejected, empty, article, code, quizLesson };
}

async function ask(LEARNER, courseId, lessonId) {
  const registered = await call(null, "POST", "/auth/register", {
    email: LEARNER,
    password: PASSWORD,
    full_name: "Phạm Gia Bảo",
  });
  const l = registered.access_token;
  await call(l, "POST", `/courses/${courseId}/enroll`);
  await call(l, "POST", `/lessons/${lessonId}/qa-threads`, {
    title: "Đọc tệp CSV có dấu tiếng Việt thì bị lỗi UnicodeDecodeError",
    body: "Em làm theo bài nhưng tệp của em lưu bằng Excel, mở ra thì báo lỗi ở dòng đầu tiên. Em có cần đổi gì khi mở tệp không ạ?",
  });
}


module.exports = { API, BASE, REPO, PASSWORD, KHOA, accounts, psql, purge, call, login, signIn, formReady, stage, stageCourses, ask };
