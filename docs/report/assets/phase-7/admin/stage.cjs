// Shared by capture.cjs and check.cjs: the throwaway accounts and content the
// admin screens are shown on. Everything is on @e2e.devpath.example accounts
// and removed by `purge()` (scripts.purge_e2e; reports go with their reporter,
// reviews with their author).
//
// What `stage()` writes:
//   - an instructor "Nguyễn Hải Yến" with three courses:
//       "Git từ số 0…"  sent for review, backdated 4 days (a long wait);
//       "SQL thực chiến…" sent for review 1 day ago, no description and an
//                         empty chapter (the quick check flags both);
//       "Docker cho lập trình viên" published (status set in the database,
//                         so no Gemini quota is spent on ingest);
//   - a learner "Phạm Gia Bảo" who enrols in the Docker course and leaves a
//     one-star review, then is locked by the seeded admin;
//   - a learner "Đỗ Minh Thư" who reports that review as offensive and the
//     Docker course as misleading.
const { execFileSync } = require("child_process");
const path = require("path");
const shared = require("../instructor/stage.cjs");

const { call, login, psql } = shared;
const PASSWORD = "devpath-admin-ui-1";
const ADMIN_EMAIL = "admin@devpath.example";
const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD || "devpath-admin";
const COMPOSE = path.join(shared.REPO, "infra/docker-compose.yml");

function accounts(stamp) {
  return {
    teacher: `quan-tri-gv-${stamp}@e2e.devpath.example`,
    author: `quan-tri-hv1-${stamp}@e2e.devpath.example`,
    reporter: `quan-tri-hv2-${stamp}@e2e.devpath.example`,
  };
}

function purge() {
  execFileSync("docker", ["compose", "-f", COMPOSE, "exec", "-T", "backend", "python", "-m", "scripts.purge_e2e"], {
    stdio: "inherit",
  });
}

async function register(email, fullName) {
  return (await call(null, "POST", "/auth/register", { email, password: PASSWORD, full_name: fullName })).access_token;
}

async function stage(stamp) {
  const who = accounts(stamp);
  const t = await register(who.teacher, "Nguyễn Hải Yến");
  await call(t, "POST", "/users/me/instructor");
  const categories = await call(null, "GET", "/categories");
  const all = categories.flatMap((c) => [c, ...(c.children || [])]);
  const category = all.find((c) => /git|công cụ|devops/i.test(c.name)) ?? all[0];

  // 1. Waiting four days: complete, so the quick check passes.
  const git = await call(t, "POST", "/courses", {
    title: "Git từ số 0: làm việc nhóm không sợ xung đột",
    category_id: category.id,
    subtitle: "Từ commit đầu tiên tới rebase, pull request và gỡ xung đột khi làm nhóm.",
    description:
      "Khóa học cho người mới: cài Git, hiểu ba vùng làm việc, nhánh và cách gộp.\n\n**Học xong bạn sẽ**\n\n- Dùng Git hằng ngày mà không phải tra lệnh\n- Gỡ được xung đột khi gộp nhánh",
    price: 349000,
    level: "beginner",
  });
  const g1 = await call(t, "POST", `/courses/${git.id}/sections`, { title: "Bắt đầu với Git" });
  const intro = await call(t, "POST", `/sections/${g1.id}/lessons`, {
    title: "Ba vùng: thư mục làm việc, staging, kho",
    type: "article",
    article_content: "Mọi thay đổi đi qua ba chỗ: thư mục làm việc, vùng staging và kho.\n\n```bash\ngit add tep.txt\ngit commit -m \"Lần đầu\"\n```",
  });
  await call(t, "PATCH", `/lessons/${intro.id}`, { is_preview: true });
  await call(t, "POST", `/sections/${g1.id}/lessons`, { title: "Commit đầu tiên", type: "video" });
  const g2 = await call(t, "POST", `/courses/${git.id}/sections`, { title: "Nhánh và gộp nhánh" });
  await call(t, "POST", `/sections/${g2.id}/lessons`, { title: "Tạo nhánh và chuyển nhánh", type: "video" });
  await call(t, "POST", `/sections/${g2.id}/lessons`, { title: "Kiểm tra chương 2", type: "quiz" });
  await call(t, "POST", `/courses/${git.id}/submit`);

  // 2. Waiting one day, with what admins send courses back for.
  const sql = await call(t, "POST", "/courses", {
    title: "SQL thực chiến với PostgreSQL",
    category_id: category.id,
    price: 0,
    level: "intermediate",
  });
  const q1 = await call(t, "POST", `/courses/${sql.id}/sections`, { title: "Truy vấn cơ bản" });
  await call(t, "POST", `/sections/${q1.id}/lessons`, { title: "SELECT và WHERE", type: "video" });
  await call(t, "POST", `/courses/${sql.id}/sections`, { title: "JOIN" });
  await call(t, "POST", `/courses/${sql.id}/submit`);
  psql(`update courses set updated_at = now() - interval '4 days 2 hours' where id = '${git.id}'`);
  psql(`update courses set updated_at = now() - interval '1 day 3 hours' where id = '${sql.id}'`);

  // 3. On sale, for the review and the reports.
  const docker = await call(t, "POST", "/courses", {
    title: "Docker cho lập trình viên",
    category_id: category.id,
    subtitle: "Đóng gói ứng dụng vào container và chạy cả hệ thống bằng Compose.",
    price: 0,
  });
  const d1 = await call(t, "POST", `/courses/${docker.id}/sections`, { title: "Container là gì" });
  await call(t, "POST", `/sections/${d1.id}/lessons`, { title: "Image và container", type: "video" });
  psql(`update courses set status = 'published', published_at = now() where id = '${docker.id}'`);

  const a = await register(who.author, "Phạm Gia Bảo");
  await call(a, "POST", `/courses/${docker.id}/enroll`);
  const review = await call(a, "PUT", `/courses/${docker.id}/reviews/me`, {
    rating: 1,
    comment: "Giảng viên dạy như đọc tài liệu, ai học khóa này là phí thời gian. Đừng mua!!!",
  });

  const r = await register(who.reporter, "Đỗ Minh Thư");
  await call(r, "POST", "/reports", {
    target_type: "review",
    target_id: review.id,
    reason: "offensive",
    details: "Lời lẽ công kích giảng viên, không nói gì về nội dung khóa học.",
  });
  await call(r, "POST", "/reports", {
    target_type: "course",
    target_id: docker.id,
    reason: "misleading",
    details: "Mô tả nói có Compose nhưng chưa có bài nào về Compose.",
  });

  const admin = await login(ADMIN_EMAIL, ADMIN_PASSWORD);
  const authorId = (await call(a, "GET", "/auth/me")).id;
  await call(admin, "POST", `/admin/users/${authorId}/lock`);
  await call(admin, "POST", "/auth/logout").catch(() => {});

  return { who, git, sql, docker, review };
}

module.exports = { ...shared, PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD, accounts, purge, stage };
