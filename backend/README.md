# Backend — FastAPI

REST API duy nhất của hệ thống: auth, quản lý khóa học, học tập, chấm bài, thương mại, AI.

## Cấu trúc

```
app/
├── api/v1/<domain>.py     Router — chỉ khai báo route và gọi service
├── services/<domain>.py   Business logic, ranh giới transaction
├── models/<domain>.py     SQLAlchemy models
├── schemas/<domain>.py    Pydantic: <Entity>Create / Update / Out
├── core/                  Config, deps (get_db, get_current_user, require_role), bảo mật
└── workers/               Celery tasks: embedding, mail, chứng chỉ PDF
tests/api/                 pytest theo domain
scripts/                   seed.py, eval_recommender.py, rebuild_course_stats.py
```

## Nguyên tắc

- **Layering nghiêm ngặt:** router → service → model. Router không chứa business logic, không truy vấn DB trực tiếp.
- **Authorization nằm ở service**, không ở router — kể cả ownership check (giảng viên chỉ sửa khóa học của mình).
- **Schema thay đổi luôn qua Alembic migration**, cập nhật [docs/database-design.md](../docs/database-design.md) trong cùng commit.
- Định dạng lỗi thống nhất: `{"detail": {"code": "COURSE_NOT_FOUND", "message": "..."}}` — frontend dựa vào `code`.

Chi tiết đầy đủ: skill `fastapi-endpoint` và `db-migration` trong `.claude/skills/`.

## Chạy local

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Kiểm tra: `http://127.0.0.1:8000/api/v1/health` và tài liệu API ở `/docs` (tự tắt khi `ENV=production`).

Test và lint:

```bash
.venv\Scripts\python.exe -m pytest
```

```bash
.venv\Scripts\python.exe -m ruff check .
```

Cấu hình đọc từ biến môi trường hoặc `backend/.env` — copy từ [.env.example](.env.example).

## Trạng thái

Đã có: app factory, `/api/v1/health`, cấu hình pydantic-settings, engine SQLAlchemy async + `get_db`, base model (UUID PK + timestamps), exception handler dùng chung, Alembic đã nối vào `Base.metadata`, pytest chạy được với httpx `ASGITransport` (không cần server, không cần DB).

Migration đầu tiên (`576c29b76f4e`) tạo `users`, `categories`, `courses` cùng ba extension `vector`, `unaccent`, `pg_trgm`. Chạy migration cần Postgres — dựng bằng `docker compose` rồi chạy từ venv trên host:

```bash
.venv\Scripts\python.exe -m alembic upgrade head
```

Chưa có: endpoint readiness kiểm tra DB/Redis, auth (Phase 2), seed script.
