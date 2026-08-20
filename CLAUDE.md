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
│   └── scripts/      # seed.py, eval_recommender.py, rebuild_course_stats.py
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
- **Schema change:** luôn qua Alembic migration, xem skill `db-migration`. Cập nhật `docs/database-design.md` cùng lúc.
- **Test:** pytest cho backend (bắt buộc với service + endpoint mới), Vitest/Playwright cho frontend ở phase 6. TDD với logic phức tạp (grading, recommender, payment).
- **Commit:** Conventional Commits (`feat:`, `fix:`, `docs:`...), branch `feature/<tên>`, merge về `main` khi phase hoàn thành demo được.
- **Sau khi xong một task trong plan:** tick checkbox trong file `docs/plan/phase-*.md` tương ứng ngay trong cùng phiên làm việc.
- **Bảo mật sandbox là bất khả xâm phạm:** mọi thay đổi liên quan chạy code người dùng phải qua checklist trong skill `sandbox-grading`.

## Trạng thái hiện tại

- Giai đoạn: **Phase 1 — Foundation, gần xong.** Đã xong: khảo sát nền tảng tham chiếu, đặc tả CSDL, repo + hook bảo vệ `main`, khung monorepo, backend FastAPI với `/health`, frontend Next.js, `docker compose` dựng đủ stack, migration đầu tiên (`users`/`categories`/`courses`), CI GitHub Actions. Còn lại: seed script và gate cuối phase — xem [docs/plan/phase-1-foundation.md](docs/plan/phase-1-foundation.md).
- Kế hoạch đã tách **Phase 7 — Báo cáo**: trong Phase 1–6 không viết báo cáo, chỉ thu bằng chứng vào `docs/report/assets/phase-N/`.
