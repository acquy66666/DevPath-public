# Phase 1 — Foundation (tuần 1–2, 24/08 → 06/09)

**Mục tiêu:** nền móng vững để 12 tuần sau chỉ tập trung viết tính năng. Kết thúc phase: `docker compose up` chạy đủ stack, schema CSDL chốt trong `database-design.md`, CI xanh.

## Khảo sát & thiết kế

- [x] Khảo sát 2–3 nền tảng tham chiếu (Udemy, Coursera, CodeLearn.io) — ghi bảng so sánh tính năng vào [`docs/report/assets/khao-sat-nen-tang-tham-chieu.md`](../report/assets/khao-sat-nen-tang-tham-chieu.md) (dùng cho chương 1)
- [x] Rà soát [database-design.md](../database-design.md) đủ để code: quan hệ N-N, các cột trạng thái, index cần thiết — sửa thẳng vào file, **không vẽ sơ đồ** (ERD hình vẽ để Phase 7)

> **Đã dời sang [Phase 8](phase-8-report.md):** use case diagram, ERD hình vẽ, wireframe. Lý do: đây là deliverable của báo cáo, vẽ khi sản phẩm đã hoàn chỉnh thì khớp thực tế và không phải vẽ lại. Phạm vi tính năng lấy trực tiếp từ [đề cương mục 5](../../de-cuong-khoa-luan-elearning.md); giao diện dựng thẳng bằng shadcn/ui khi code Phase 2.

## Khung dự án

- [x] `git init`, tạo repo GitHub, branch protection main — repo private trên gói Free nên GitHub chặn cả ruleset lẫn branch protection (HTTP 403); thay bằng git hook `.githooks/pre-push` chặn force-push và xóa nhánh `main`
- [x] Bật ruleset bảo vệ `main` trên GitHub sau khi có Pro — rules: `non_fast_forward` + `deletion`, không bypass actor
  - Xong 08/09/2026 bằng Student Developer Pack. Ruleset `protect-main`, `enforcement: active`, `bypass_actors: []`, `current_user_can_bypass: never`. Hook `.githooks/pre-push` giữ lại làm lớp báo lỗi nhanh ở máy, không còn là lớp bảo vệ duy nhất
- [x] Monorepo skeleton: `backend/`, `frontend/`, `grader/`, `infra/` theo cấu trúc trong CLAUDE.md
- [x] Backend: FastAPI + SQLAlchemy async + Alembic + pytest chạy được; endpoint `/health`; cấu hình bằng pydantic-settings (`.env`)
- [x] Frontend: Next.js + TypeScript + Tailwind + shadcn/ui; layout khung (header/footer); gọi được `/health`
- [x] `infra/docker-compose.yml`: postgres (kèm pgvector), redis, backend, frontend, worker — up một lệnh
- [x] Migration đầu tiên: bảng `users`, `categories`, `courses` (đủ để phase 2 bắt đầu)
- [x] CI GitHub Actions: lint + test backend & frontend trên mỗi PR
- [x] Seed script skeleton (`backend/scripts/seed.py`) — tài khoản admin, vài category

## Gate cuối phase

- [x] `docker compose up` → mở được frontend, frontend gọi được backend, backend nối được DB/Redis
- [x] CI xanh trên main
- [x] Thu bằng chứng vào [`docs/report/assets/phase-1/`](../report/assets/phase-1/README.md): ảnh chụp `docker compose ps` đủ service, ảnh CI xanh, `schema.sql` dump sau migration đầu tiên
