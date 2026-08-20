# Bằng chứng Phase 1 — Foundation

Thu ngày **20/08/2026**, tại thời điểm vượt gate Phase 1. Toàn bộ số liệu trong thư mục này lấy từ hệ thống đang chạy thật, không dựng lại.

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `compose-ps.png` | Năm service healthy sau `docker compose up` | 4 — Xây dựng hệ thống |
| `docker-compose-ps.txt` | Output gốc của ảnh trên | — |
| `ci-green.png` | CI xanh trên `main` và trên PR #2 | 5 — Kiểm thử & đánh giá |
| `ci-runs.txt` | Output gốc của ảnh trên | — |
| `frontend-home.png` | Trang chủ gọi được API backend (badge "Hoạt động") | 4 |
| `schema.sql` | Dump schema sau migration `576c29b76f4e` | 3 — Phân tích & thiết kế |

## Cách tái tạo

Dump schema:

```bash
docker compose -f infra/docker-compose.yml exec -T postgres pg_dump -U devpath -d devpath --schema-only --no-owner --no-privileges
```

Trạng thái service và CI:

```bash
docker compose -f infra/docker-compose.yml ps
```

```bash
gh run list --branch main --workflow CI --limit 5
```

## Ghi chú khi dùng lại ảnh ở Phase 7

- `compose-ps.png` và `ci-green.png` được **render từ output text thật** trong `*.txt` cùng thư mục, không phải ảnh chụp cửa sổ terminal. Lý do: repo private nên không mở được giao diện Actions bằng công cụ tự động; text gốc giữ lại để đối chiếu. Nếu báo cáo cần đúng giao diện GitHub thì chụp tay ở bước viết chương.
- `frontend-home.png` là ảnh chụp trình duyệt thật tại `localhost:3000`. Hai chi tiết của môi trường dev còn trong ảnh, cân nhắc chụp lại ở Phase 7 khi có bản deploy: chỉ báo Next.js Dev Tools ở góc dưới trái, và phần chữ đang hiển thị bằng font dự phòng thay vì Geist.
- Schema trong `schema.sql` mới có 3 bảng đầu; ERD ở Phase 7 vẽ theo schema tại thời điểm đóng băng tính năng, không theo file này.

## Trạng thái gate

| Điều kiện gate | Kết quả |
|---|---|
| `docker compose up` chạy đủ stack | ✅ 5/5 service healthy |
| Frontend gọi được backend | ✅ badge "Hoạt động", `/api/v1/health` trả `{"status":"ok"}` |
| Backend nối được DB/Redis | ✅ migration chạy trên Postgres; task Celery `ping` đi trọn vòng qua Redis |
| CI xanh trên `main` | ✅ hai run gần nhất đều `success` |
