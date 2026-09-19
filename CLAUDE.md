# E-Learning Platform — Khóa luận tốt nghiệp

Nền tảng học trực tuyến kiểu Udemy tích hợp AI: chấm mã nguồn tự động trong Docker sandbox, hybrid recommender, chatbot RAG trợ giảng.

## Tài liệu bắt buộc đọc trước khi làm việc

- [Đề cương khóa luận](de-cuong-khoa-luan-elearning.md) — nguồn chân lý về phạm vi tính năng
- [Kiến trúc hệ thống](docs/architecture.md)
- [Thiết kế CSDL](docs/database-design.md)
- [Kế hoạch tổng thể](docs/plan/00-overview.md) — trạng thái dự án nằm ở checkbox trong các file phase
- [Workflow phát triển](docs/workflow.md)

## Tech stack (đã chốt trong đề cương — không tự ý thay đổi)

| Thành phần | Công nghệ |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS + shadcn/ui, TanStack Query |
| Backend | FastAPI (Python 3.12+), SQLAlchemy 2.x async, Pydantic v2 |
| CSDL | PostgreSQL 16 + Redis (cache, session, leaderboard, queue broker) |
| Hàng đợi | Celery (worker chấm bài, sinh embedding, gửi mail) |
| Chấm bài | Docker sandbox — xem skill `sandbox-grading` (BẮT BUỘC khi đụng vào grader) |
| AI | Gemini API (RAG chatbot, sinh quiz), embedding cho recommender |
| Video | HLS, object storage Cloudflare R2 |
| Thanh toán | VNPay/MoMo sandbox |
| Triển khai | Docker Compose trên VPS |

## Cấu trúc monorepo

```
E-learning/
├── backend/          # FastAPI
│   ├── app/{api/v1,core,models,schemas,services,workers}/
│   ├── tests/api/
│   └── scripts/      # seed.py, seed_interactions.py, ingest_course.py, rebuild_recommendations.py, bench_grading.py, rebuild_course_stats.py, lock.sh (sẽ có: eval_recommender.py)
├── frontend/         # Next.js — scaffold bằng create-next-app, xem frontend/README.md
├── grader/           # runner/, images/<language>/, tests/fixtures/
├── infra/            # docker-compose.yml, nginx/, scripts/
├── docs/             # Tài liệu thiết kế + kế hoạch (tiếng Việt)
├── .githooks/        # pre-push chặn force-push/xóa main
└── de-cuong-khoa-luan-elearning.md
```

Mỗi thư mục cấp 1 có README riêng nêu nguyên tắc và trạng thái — đọc trước khi làm việc trong đó.

## Quy ước

- **Mở đầu mỗi phiên làm việc:** chạy skill `start-session` (hoặc `/start-session`) trước khi làm bất cứ việc gì — nó xác định phase hiện tại, task kế tiếp và trạng thái git.
- **Ngôn ngữ:** code, tên biến, commit message bằng tiếng Anh; tài liệu trong `docs/` và giao tiếp với user bằng tiếng Việt. UI song ngữ ưu tiên tiếng Việt.
- **Backend layering:** router → service → model. Router không chứa business logic. Xem skill `fastapi-endpoint`.
- **Dependency backend:** thêm/bỏ ở `pyproject.toml`, rồi sinh lại `backend/requirements.lock` bằng `scripts/lock.sh` (lệnh ở `backend/README.md`) — không sửa lock bằng tay; CI fail nếu hai file lệch nhau.
- **Schema change:** luôn qua Alembic migration, xem skill `db-migration`. Cập nhật `docs/database-design.md` cùng lúc.
- **Test:** pytest cho backend (bắt buộc với service + endpoint mới), Vitest/Playwright cho frontend ở phase 6. TDD với logic phức tạp (grading, recommender, payment).
- **Commit:** Conventional Commits (`feat:`, `fix:`, `docs:`...), branch `feature/<tên>`, merge về `main` khi phase hoàn thành demo được.
- **Sau khi xong một task trong plan:** tick checkbox trong file `docs/plan/phase-*.md` tương ứng ngay trong cùng phiên làm việc.
- **Bảo mật sandbox là bất khả xâm phạm:** mọi thay đổi liên quan chạy code người dùng phải qua checklist trong skill `sandbox-grading`.

## Trạng thái hiện tại

- Giai đoạn: **Phase 4 — AI Features ⭐ đang chạy, 16/28 task** (8/20 task gốc + 8/8 dòng của mục **"Dọn nợ trước khi đi tiếp"** thêm ngày 18/09 ở đầu file phase — mục đó đã xong 19/09; lý do và hướng sửa từng dòng ở [docs/plan/don-no-2026-09-18.md](docs/plan/don-no-2026-09-18.md)). Việc kế tiếp là task chưa tick đầu tiên trong [docs/plan/phase-4-ai-features.md](docs/plan/phase-4-ai-features.md); task nào bị chặn vì chưa có API key Gemini thì bỏ qua và nói rõ lý do — **đã có key từ 18/09/2026** (`GEMINI_API_KEY` trong `infra/.env`, gitignored) — đã xác minh gọi được, 50 model truy cập được, nên các task còn lại không còn bị chặn. Đã xong: bảng `doc_chunks` + index HNSW đã xác nhận bằng `EXPLAIN`, và quiz (bảng `quizzes`/`quiz_questions`/`quiz_attempts`, API soạn + làm bài, panel biên soạn của giảng viên, màn hình làm bài có đồng hồ) — đồng hồ tính ở backend, ân hạn 10 giây, hết giờ là 0 điểm vì không lưu đáp án dở; collaborative filtering item-based (`services/collaborative.py`), và đường ống gợi ý offline (job Celery beat 03:00 → cache Redis TTL 48h → `GET /api/v1/recommendations`, chạy tay bằng `python -m scripts.rebuild_recommendations`), và dữ liệu tương tác giả lập để đo (`scripts/seed_interactions.py` — 20 khóa chia 4 cụm sở thích neo vào 4 khóa seed thật + 48 học viên, hạt giống cố định nên tái tạo được, có `--purge` để gỡ sạch; 190 tương tác, 48/48 người có gợi ý, tỷ lệ top-3 đúng cụm 0,8333 so với mức ngẫu nhiên 0,2500 — `docs/report/assets/phase-4/interaction-seed.txt`). đường ống ingest RAG cho **bài viết** (adapter `services/llm.py` → chunk ~500 token có overlap `services/chunking.py` → `batchEmbedContents` → `doc_chunks`, job Celery đẩy khi publish, chạy tay bằng `python -m scripts.ingest_course --all [--dry-run]`) — model chốt là `gemini-embedding-001` vì `gemini-embedding-2` bỏ qua `taskType`; vector tự chuẩn hóa vì bản cắt 768 chiều có norm ≈ 0,57; chạy lại không tốn quota nhờ so chunk + tên model trước khi nhúng. Và **transcript video** (19/09): giảng viên `PUT /lessons/{id}/transcript` một tệp `.srt`/`.txt` — đi qua API chứ không qua URL đã ký để tệp sai bảng mã bị từ chối ngay (422 kèm câu hướng dẫn); tệp gốc lưu cạnh video trên R2/MinIO, ingest đọc lại và bóc chữ; đọc không được thì giữ chunk cũ (`unreadable`) chứ không coi là hết chữ — `docs/report/assets/phase-4/transcript-ingest.txt`. Kho ngữ liệu vẫn mỏng vì 41/42 video seed là luồng HLS mẫu không có lời giảng. **API chat RAG** (19/09): `services/chat.py` + router `chat.py`, bảng `chat_sessions`/`chat_messages` (migration `42fff7804290`), hỏi là `POST /chat-sessions/{id}/messages` trả SSE `sources` → `delta`… → `done`/`error`; lọc khóa `published` + người hỏi đã ghi danh nằm **trong chính câu truy vấn top-k** (hạ khóa về nháp trên dữ liệu thật: 4 chunk còn trong bảng, truy vấn trả 0 dòng); câu nối tiếp được tìm hai lần (riêng + ghép câu trước) trong một lần gọi nhúng rồi gộp; model sinh `gemini-3.5-flash-lite` thinking `minimal` chọn bằng số đo (3.8-flash 503/429 trên free tier); Gemini có thể trả 200 rồi hỏng giữa chừng bằng JSON trần — adapter thử lại nếu chưa có chữ, còn đã có chữ thì báo `error` và không lưu — `docs/report/assets/phase-4/chat-api.txt`. Giảng viên chủ khóa không hỏi được trợ giảng khóa mình (đúng câu chữ "đã ghi danh"). Chưa đặt ngưỡng điểm từ chối — để task đánh giá chatbot. Content-based của recommender giờ đã mở khóa vì đã có key Gemini. **Phase 3 đã đóng (18/18), tag `phase-3-done`** — để lại: image sandbox `devpath-sandbox-python:v1` (user không đặc quyền, `--network none`, rootfs read-only, cap-drop ALL, timeout hai lớp, OOM đọc từ `State.OOMKilled` và — vì cờ đó có lúc sai trên CI — thêm thời gian sống container: exit 137 trước điểm giữa soft/hard CPU limit là MLE, sửa 18/09), bộ verdict đủ 7 chữ, 7 ca tấn công sandbox với 0 ca thoát trên cả máy dev lẫn CI, bảng + API `code_exercises`/`test_cases`/`submissions`/`submission_results` không rò test ẩn, UI giảng viên soạn bài tập, hàng đợi Celery riêng + rate limit hai cửa, tiến độ realtime Redis pub/sub → WebSocket kèm kết quả per-test, trang nộp bài Monaco (chạy thử + lịch sử), benchmark chốt `GRADING_CONCURRENCY=2` vì công bằng chứ không vì throughput, và AC tự đóng bài học trong cùng transaction với verdict. Hai điều đã biết và chấp nhận: nhánh polling không nhích giữa chừng vì worker ghi `submission_results` một lần lúc cuối (`docs/report/assets/phase-3/per-test-realtime.txt`), và các khóa seed từng mồ côi ở hai tài khoản `@devpath.local` không đăng nhập được (email-validator từ chối domain `.local`) — **đã xử lý 18/09/2026**: `scripts/seed.py` chuyển sang `@devpath.example`, CSDL dev đã `alembic downgrade base` → `upgrade head` → seed lại từ trắng, nên mọi tài khoản seed giờ đăng nhập được. Phase 1 (14/14), Phase 2 (21/21), Phase 3 (18/18) đã đóng, tag `phase-1-done` / `phase-2-done` / `phase-3-done`. Phase 2 để lại: auth email/password + JWT access/refresh, OAuth Google, phân quyền `student`/`instructor`/`admin`, trang hồ sơ + đổi mật khẩu + upload avatar R2, CRUD khóa học, curriculum builder kéo-thả, upload video presigned R2 + worker transcode HLS (trên máy dev storage là MinIO trong compose, host `minio.localhost` — `R2_*` để trống là tự trỏ vào đó, từ 18/09), trang chi tiết khóa học public, danh sách khóa học có full-text search, enroll miễn phí, player HLS lưu tiến độ, ghi chú + bookmark, đánh giá & xếp hạng, seed data thật, và một URL demo công khai chạy bằng Cloudflare Quick Tunnel.
- **Hạ tầng ưu tiên phương án 0đ tới hết Phase 5.** Deploy lên VPS thật đã dời từ Phase 2 sang Phase 6: máy Azure for Students ($100, qua GitHub Student Developer Pack) hoặc Oracle Always Free, cùng tên miền `.me` của pack. Credit DigitalOcean của pack đã hết hạn 31/07/2026. Cấu hình production đã tổng duyệt trọn vẹn bằng chính `infra/docker-compose.prod.yml` trên máy dev (bằng chứng: `docs/report/assets/phase-2/`), runbook ở [docs/huong-dan-deploy-vps.md](docs/huong-dan-deploy-vps.md) — thứ còn thiếu là cái máy chủ, không phải phần việc kỹ thuật nào.
- Kế hoạch đã tách **Phase 7 — Báo cáo**: trong Phase 1–6 không viết báo cáo, chỉ thu bằng chứng vào `docs/report/assets/phase-N/`.
