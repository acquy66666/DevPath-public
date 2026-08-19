# Phase 1 — Foundation (tuần 1–2, 24/08 → 06/09)

**Mục tiêu:** nền móng vững để 12 tuần sau chỉ tập trung viết tính năng. Kết thúc phase: `docker compose up` chạy đủ stack, ERD chốt, wireframe các màn chính.

## Khảo sát & thiết kế

- [ ] Khảo sát 2–3 nền tảng tham chiếu (Udemy, Coursera, CodeLearn.io) — ghi bảng so sánh tính năng vào `docs/report/assets/` (dùng cho chương 1)
- [ ] Chốt danh sách use case theo 3 nhóm người dùng (từ đề cương mục 5) — vẽ use case diagram
- [ ] ERD chi tiết từ [database-design.md](../database-design.md) — vẽ mermaid/draw.io, review lại quan hệ N-N và các cột trạng thái
- [ ] Wireframe màn chính: trang chủ, danh sách + chi tiết khóa học, player, trang nộp code, dashboard giảng viên, admin (Figma hoặc giấy — không cầu toàn)

## Khung dự án

- [ ] `git init`, tạo repo GitHub, branch protection main
- [ ] Monorepo skeleton: `backend/`, `frontend/`, `grader/`, `infra/` theo cấu trúc trong CLAUDE.md
- [ ] Backend: FastAPI + SQLAlchemy async + Alembic + pytest chạy được; endpoint `/health`; cấu hình bằng pydantic-settings (`.env`)
- [ ] Frontend: Next.js + TypeScript + Tailwind + shadcn/ui; layout khung (header/footer); gọi được `/health`
- [ ] `infra/docker-compose.yml`: postgres (kèm pgvector), redis, backend, frontend, worker — up một lệnh
- [ ] Migration đầu tiên: bảng `users`, `categories`, `courses` (đủ để phase 2 bắt đầu)
- [ ] CI GitHub Actions: lint + test backend & frontend trên mỗi PR
- [ ] Seed script skeleton (`backend/scripts/seed.py`) — tài khoản admin, vài category

## Gate cuối phase

- [ ] `docker compose up` → mở được frontend, frontend gọi được backend, backend nối được DB/Redis
- [ ] CI xanh trên main
- [ ] ERD + wireframe + use case đã lưu vào `docs/report/assets/`
- [ ] Cập nhật chương 1 + 3 (phần thiết kế) của báo cáo — dàn ý là đủ
