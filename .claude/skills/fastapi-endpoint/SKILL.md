---
name: fastapi-endpoint
description: Use when adding or modifying any FastAPI REST endpoint in backend/ — enforces router/service layering, Pydantic schemas, auth dependencies, error format, and pytest coverage for the e-learning platform.
---

# Thêm / sửa endpoint FastAPI

## Cấu trúc bắt buộc

```
backend/app/
├── api/v1/<domain>.py      # Router — chỉ khai báo route, gọi service, KHÔNG chứa business logic
├── services/<domain>.py    # Business logic, transaction boundary
├── models/<domain>.py      # SQLAlchemy models
├── schemas/<domain>.py     # Pydantic: <Entity>Create, <Entity>Update, <Entity>Out
└── core/deps.py            # Dependencies dùng chung (get_db, get_current_user, require_role)
```

## Checklist khi thêm endpoint

1. **Schema trước:** định nghĩa Pydantic request/response trong `schemas/`. Response model luôn tường minh (`response_model=`), không trả ORM object trực tiếp.
2. **Service:** viết hàm service nhận `AsyncSession` + tham số đã validate. Raise `HTTPException` từ service chỉ khi bất khả kháng — ưu tiên raise domain exception và map ở exception handler chung.
3. **Router:** prefix theo REST chuẩn (`/api/v1/courses`, `/api/v1/courses/{course_id}/lessons`). Method đúng ngữ nghĩa (POST tạo → 201, DELETE → 204).
4. **Phân quyền:** dùng dependency — `get_current_user` (bắt buộc đăng nhập), `require_role("instructor")`, `require_role("admin")`. Endpoint public phải là quyết định có chủ đích, ghi rõ trong docstring.
5. **Ownership check:** giảng viên chỉ sửa được khóa học của mình; học viên chỉ xem được nội dung đã enroll. Check trong service, không check trong router.
6. **Phân trang:** mọi endpoint trả list dùng `page`/`page_size` (mặc định 20, max 100), response bọc `{items, total, page, page_size}`.
7. **Test:** thêm test trong `backend/tests/api/test_<domain>.py` — tối thiểu: happy path, 401 khi chưa đăng nhập, 403 sai role/ownership, 404, validation 422. Dùng httpx `AsyncClient` + fixture DB transaction rollback.
8. Chạy `pytest` và xác nhận pass trước khi báo xong.

## Định dạng lỗi thống nhất

```json
{ "detail": { "code": "COURSE_NOT_FOUND", "message": "..." } }
```

Mã lỗi UPPER_SNAKE, frontend dựa vào `code` chứ không parse `message`.
