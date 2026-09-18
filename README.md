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

Ba tài liệu đi kèm:

- [docs/huong-dan-chay-va-docker.md](docs/huong-dan-chay-va-docker.md) — chạy trang web từng bước, cấu trúc file, và vai trò của Docker trong dự án
- [docs/huong-dan-du-an.md](docs/huong-dan-du-an.md) — sửa từng phần của giao diện, luồng một request, và những chỗ dễ vấp
- [docs/huong-dan-demo-truoc-giao-vien.md](docs/huong-dan-demo-truoc-giao-vien.md) — chuỗi lệnh chạy thủ công kèm giải thích, kịch bản demo 10 chặng, và câu trả lời cho những câu chắc chắn bị hỏi

## Trạng thái

**Phase 4 — AI Features ⭐ đang chạy.** Phase 1–3 đã đóng (tag `phase-1-done`, `phase-2-done`, `phase-3-done`). Trạng thái chi tiết nằm ở checkbox trong [docs/plan/](docs/plan/00-overview.md); tóm tắt cập nhật nhất ở mục "Trạng thái hiện tại" của [CLAUDE.md](CLAUDE.md).

- **Nền tảng (Phase 2):**
  - đăng ký/đăng nhập (email + Google), phân quyền 3 vai trò;
  - giảng viên tạo khóa học và dựng mục lục kéo-thả, upload video kèm worker chuyển mã HLS;
  - tìm kiếm toàn văn tiếng Việt, ghi danh khóa miễn phí, trình phát nhớ vị trí, ghi chú, đánh dấu, đánh giá.
- **Chấm mã nguồn (Phase 3):**
  - sandbox Docker cô lập (không mạng, không đặc quyền, rootfs chỉ đọc, timeout hai lớp), đủ 7 verdict;
  - 7 ca tấn công sandbox đều bị chặn;
  - hàng đợi Celery riêng, tiến độ từng test theo thời gian thực qua WebSocket.
- **AI (Phase 4, đang làm):**
  - đã có quiz tính giờ và gợi ý khóa học item-based chạy hằng đêm;
  - dữ liệu RAG đã nạp từ bài viết vào pgvector;
  - còn chatbot, sinh quiz bằng AI, content-based và đánh giá precision@k.

Storage trên máy dev là MinIO chạy trong compose (xem [infra/README.md](infra/README.md)). Production dùng Cloudflare R2. Hạ tầng deploy (compose production, nginx, HTTPS) đã viết và được CI kiểm chứng, nhưng **chưa deploy lên máy chủ thật** — việc đó thuộc Phase 6.

## Quy ước

- Code, tên biến, commit message: tiếng Anh. Tài liệu trong `docs/`: tiếng Việt. UI: tiếng Việt.
- Commit theo Conventional Commits, mỗi task một nhánh `feature/<tên>` và một PR. Nhánh `main` có hai lớp bảo vệ:
  - ruleset `protect-main` phía GitHub (chặn force-push và xóa nhánh; không ai bypass được);
  - hook `.githooks/pre-push`, lớp nhanh báo lỗi ngay trên máy trước khi tốn công push. Sau khi clone phải bật hook bằng lệnh:

```bash
git config core.hooksPath .githooks
```
