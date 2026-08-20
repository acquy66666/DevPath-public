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

## Chưa có gì ở đây

Thư mục mới chỉ là khung package. FastAPI app, cấu hình pydantic-settings, Alembic và pytest được thêm ở task kế tiếp của [Phase 1](../docs/plan/phase-1-foundation.md).
