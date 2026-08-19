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

## Cấu trúc monorepo (dự kiến)

```
E-learning/
├── backend/          # FastAPI: app/{api,core,models,schemas,services,workers}
├── frontend/         # Next.js: app/, components/, lib/
├── grader/           # Judge worker + Dockerfile sandbox images per language
├── infra/            # docker-compose.yml, nginx, deploy scripts
├── docs/             # Tài liệu thiết kế + kế hoạch (tiếng Việt)
└── de-cuong-khoa-luan-elearning.md
```

## Quy ước

- **Ngôn ngữ:** code, tên biến, commit message bằng tiếng Anh; tài liệu trong `docs/` và giao tiếp với user bằng tiếng Việt. UI song ngữ ưu tiên tiếng Việt.
- **Backend layering:** router → service → model. Router không chứa business logic. Xem skill `fastapi-endpoint`.
- **Schema change:** luôn qua Alembic migration, xem skill `db-migration`. Cập nhật `docs/database-design.md` cùng lúc.
- **Test:** pytest cho backend (bắt buộc với service + endpoint mới), Vitest/Playwright cho frontend ở phase 6. TDD với logic phức tạp (grading, recommender, payment).
- **Commit:** Conventional Commits (`feat:`, `fix:`, `docs:`...), branch `feature/<tên>`, merge về `main` khi phase hoàn thành demo được.
- **Sau khi xong một task trong plan:** tick checkbox trong file `docs/plan/phase-*.md` tương ứng ngay trong cùng phiên làm việc.
- **Bảo mật sandbox là bất khả xâm phạm:** mọi thay đổi liên quan chạy code người dùng phải qua checklist trong skill `sandbox-grading`.

## Trạng thái hiện tại

- Giai đoạn: **Phase 0 — scaffolding xong, chưa viết code.** Bước tiếp theo: Phase 1 trong [docs/plan/phase-1-foundation.md](docs/plan/phase-1-foundation.md).
