# DevPath — Nền tảng học lập trình trực tuyến

Khóa luận tốt nghiệp: nền tảng e-learning kiểu Udemy tích hợp AI — chấm mã nguồn tự động trong Docker sandbox, hybrid recommender, chatbot RAG trợ giảng.

## Tech stack

| Lớp | Công nghệ |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS + shadcn/ui, TanStack Query |
| Backend | FastAPI (Python 3.12+), SQLAlchemy 2.x async, Pydantic v2 |
| CSDL | PostgreSQL 16 (pgvector) + Redis |
| Hàng đợi | Celery — worker chấm bài, sinh embedding, gửi mail |
| AI | Gemini API (RAG chatbot, sinh quiz), embedding cho recommender |
| Hạ tầng | Docker Compose trên VPS, Nginx, Cloudflare R2 |

## Cấu trúc

```
.
├── backend/     FastAPI + Celery worker      → backend/README.md
├── frontend/    Next.js App Router           → frontend/README.md
├── grader/      Judge worker + sandbox image → grader/README.md
├── infra/       Docker Compose, Nginx, deploy→ infra/README.md
└── docs/        Tài liệu thiết kế & kế hoạch
```

## Tài liệu

- [Đề cương khóa luận](de-cuong-khoa-luan-elearning.md) — phạm vi tính năng
- [Kiến trúc hệ thống](docs/architecture.md)
- [Thiết kế CSDL](docs/database-design.md)
- [Kế hoạch 14 tuần](docs/plan/00-overview.md) — trạng thái dự án nằm ở checkbox trong các file phase
- [Workflow phát triển](docs/workflow.md)

## Trạng thái

**Phase 1 — Foundation.** Backend FastAPI đã chạy được (`/api/v1/health`, pytest xanh) — xem [backend/README.md](backend/README.md). Kế tiếp: Next.js, `docker compose`, migration đầu tiên và CI, theo [phase-1-foundation.md](docs/plan/phase-1-foundation.md). Hướng dẫn chạy cả hệ thống bằng một lệnh sẽ bổ sung vào đây khi `infra/docker-compose.yml` xong.

## Quy ước

- Code, tên biến, commit message: tiếng Anh. Tài liệu trong `docs/`: tiếng Việt. UI: tiếng Việt.
- Commit theo Conventional Commits; nhánh `main` được bảo vệ bằng hook `.githooks/pre-push` (chặn force-push và xóa nhánh). Sau khi clone phải chạy:

```bash
git config core.hooksPath .githooks
```
