---
name: db-migration
description: Use when creating or changing PostgreSQL schema, SQLAlchemy models, or Alembic migrations — naming conventions, migration workflow, and the rule to keep docs/database-design.md in sync.
---

# Thay đổi schema CSDL

## Quy ước đặt tên

- Bảng: snake_case, số nhiều (`courses`, `lesson_progress`, `quiz_questions`).
- PK: `id UUID` default `gen_random_uuid()`. FK: `<bảng_số_ít>_id`.
- Mọi bảng có `created_at`, `updated_at` (timezone-aware, server default `now()`).
- Enum nghiệp vụ dùng `String` + constraint hoặc Python Enum map sang varchar — tránh Postgres ENUM (khó migrate).
- Tiền: `NUMERIC(12,2)`, đơn vị VND. Không bao giờ dùng float.
- Index: đặt tên `ix_<bảng>_<cột>`; thêm index cho mọi FK dùng trong filter/join thường xuyên.
- Soft delete chỉ dùng khi nghiệp vụ cần (courses bị gỡ nhưng học viên đã mua vẫn học được) — cột `deleted_at` nullable.

## Workflow bắt buộc

1. Sửa/thêm model trong `backend/app/models/`.
2. `alembic revision --autogenerate -m "add_<thing>"` — message snake_case, mô tả đúng thay đổi.
3. **Đọc lại file migration được sinh ra** — autogenerate hay sót: index, server_default, constraint đổi tên. Sửa tay nếu cần.
4. `alembic upgrade head` trên DB dev, xác nhận không lỗi.
5. Kiểm tra `alembic downgrade -1` rồi `upgrade head` lại nếu migration có gì phức tạp hơn add column.
6. **Cập nhật `docs/database-design.md`** cùng commit — file này là tài liệu nộp kèm khóa luận, không được lệch với schema thật.
7. Nếu bảng mới cần dữ liệu demo → cập nhật seed script trong `backend/scripts/seed.py`.

## Cấm

- Sửa migration đã chạy trên máy khác/đã commit — luôn tạo revision mới.
- Đổi schema thủ công bằng SQL ngoài Alembic.
