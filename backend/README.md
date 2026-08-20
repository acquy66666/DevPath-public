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

Test auth chạy trên Postgres thật (mỗi test nằm trong một transaction bị rollback, không để lại dữ liệu). Không có Postgres thì nhóm test đó **tự skip** khi chạy ở máy dev, nhưng **fail** khi biến `CI` được đặt — CI không bao giờ xanh nhờ bỏ qua test.

Cấu hình đọc từ biến môi trường hoặc `backend/.env` — copy từ [.env.example](.env.example).

## Auth (Phase 2)

| Endpoint | Mô tả |
|---|---|
| `POST /api/v1/auth/register` | Tạo tài khoản `student`, trả access token + đặt cookie refresh |
| `POST /api/v1/auth/login` | Đăng nhập email + mật khẩu |
| `POST /api/v1/auth/refresh` | Đổi cookie refresh lấy access token mới (có xoay vòng token) |
| `POST /api/v1/auth/logout` | Thu hồi phiên hiện tại, xóa cookie |
| `GET /api/v1/auth/me` | Hồ sơ người đang đăng nhập (`Authorization: Bearer <access_token>`) |

Hai loại token đi hai đường khác nhau:

- **Access token** — JWT HS256, sống 15 phút, trả trong body JSON. Frontend giữ trong bộ nhớ và gửi qua header `Authorization`. Không thu hồi được, nên thời hạn phải ngắn.
- **Refresh token** — chuỗi ngẫu nhiên 48 byte, sống 30 ngày, chỉ đi trong cookie `HttpOnly` giới hạn path `/api/v1/auth`. DB chỉ lưu SHA-256 của nó (bảng `refresh_tokens`), lộ DB cũng không đăng nhập lại được.

**Xoay vòng (rotation):** mỗi lần refresh thành công thì token cũ bị thu hồi và cấp token mới. Token đã thu hồi mà quay lại ⇒ coi như bị đánh cắp: thu hồi **toàn bộ** phiên của user đó, trả `REFRESH_TOKEN_REUSED`.

Mã lỗi: `EMAIL_ALREADY_REGISTERED` (409), `INVALID_CREDENTIALS` (401), `ACCOUNT_LOCKED` (403), `REFRESH_TOKEN_MISSING` / `INVALID_REFRESH_TOKEN` / `REFRESH_TOKEN_REUSED` / `NOT_AUTHENTICATED` (401).

`JWT_SECRET` phải đặt thật khi `ENV=production` — app từ chối khởi động nếu vẫn còn giá trị mặc định trong `.env.example`.

## Trạng thái

Đã có: app factory, `/api/v1/health`, cấu hình pydantic-settings, engine SQLAlchemy async + `get_db`, base model (UUID PK + timestamps), exception handler dùng chung, Alembic đã nối vào `Base.metadata`, auth email + mật khẩu (bảng trên) với `get_current_user`.

Migration: `576c29b76f4e` tạo `users`, `categories`, `courses` cùng ba extension `vector`, `unaccent`, `pg_trgm`; `adab7334f140` thêm `refresh_tokens`. Chạy migration cần Postgres — dựng bằng `docker compose` rồi chạy từ venv trên host:

```bash
.venv\Scripts\python.exe -m alembic upgrade head
```

Sau khi migration chạy xong, nạp dữ liệu tối thiểu (một tài khoản admin, 8 danh mục 2 cấp):

```bash
.venv\Scripts\python.exe -m scripts.seed
```

Script chạy lại bao nhiêu lần cũng được — lần thứ hai trở đi không tạo thêm gì. Mật khẩu admin lấy từ `SEED_ADMIN_PASSWORD` (mặc định `devpath-admin` kèm cảnh báo), email từ `SEED_ADMIN_EMAIL`.

Chưa có: endpoint readiness kiểm tra DB/Redis, OAuth Google, `require_role` và trang profile (task kế tiếp của Phase 2), khóa học seed (Phase 2).
