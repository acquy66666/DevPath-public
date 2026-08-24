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

## Chạy toàn bộ hệ thống

```bash
cp infra/.env.example infra/.env
```

```bash
docker compose -f infra/docker-compose.yml up -d
```

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:3000 | Giao diện |
| http://localhost:8000/docs | Tài liệu API tự sinh |

Nạp dữ liệu mẫu (một admin, 8 danh mục, 2 giảng viên, 4 khóa học có mục lục đầy đủ):

```bash
cd backend && .venv\Scripts\python.exe -m scripts.seed
```

Chi tiết vận hành, cách sửa từng phần của giao diện, và những chỗ dễ vấp: [docs/huong-dan-du-an.md](docs/huong-dan-du-an.md).

## Trạng thái

**Phase 2 — Core Platform, tuần 5.** Đã chạy được đầu-cuối: đăng ký/đăng nhập (email + Google), phân quyền 3 vai trò, giảng viên tạo khóa học và dựng mục lục kéo-thả, upload video lên R2 kèm worker chuyển mã HLS, tìm kiếm toàn văn tiếng Việt, ghi danh khóa miễn phí, trình phát nhớ vị trí, ghi chú theo mốc thời gian, đánh dấu bài, đánh giá & xếp hạng. Hạ tầng deploy (compose production, nginx, HTTPS) đã viết và được CI kiểm chứng nhưng **chưa deploy lên máy chủ thật**.

Kế tiếp: Phase 3 — chấm mã nguồn tự động trong Docker sandbox. Trạng thái chi tiết nằm ở checkbox trong [docs/plan/phase-2-core-platform.md](docs/plan/phase-2-core-platform.md).

## Quy ước

- Code, tên biến, commit message: tiếng Anh. Tài liệu trong `docs/`: tiếng Việt. UI: tiếng Việt.
- Commit theo Conventional Commits; nhánh `main` được bảo vệ bằng hook `.githooks/pre-push` (chặn force-push và xóa nhánh). Sau khi clone phải chạy:

```bash
git config core.hooksPath .githooks
```
