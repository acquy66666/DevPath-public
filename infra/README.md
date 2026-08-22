# Infra — Docker Compose, Nginx, deploy

Toàn bộ hệ thống chạy bằng một lệnh `docker compose up` ở máy dev và trên VPS.

## Cấu trúc

```
docker-compose.yml       postgres (pgvector), redis, backend, worker, frontend
docker-compose.prod.yml  override cho VPS (nginx, HTTPS, restart policy) — chưa có
postgres/init/           SQL chạy một lần khi volume rỗng (CREATE EXTENSION)
nginx/                   reverse proxy, cấu hình TLS
scripts/                 deploy, backup DB (pg_dump → R2), restore
```

## Chạy stack ở máy dev

```bash
cp infra/.env.example infra/.env
```

```bash
docker compose -f infra/docker-compose.yml up -d
```

Lần đầu mất vài phút để build image. Sau đó:

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:3000 | Frontend Next.js |
| http://localhost:8000/docs | Tài liệu API (tự tắt khi `ENV=production`) |
| localhost:5432 | Postgres — dùng cho Alembic chạy từ venv trên host |
| localhost:6379 | Redis |

Cả năm service đều có healthcheck, nên `docker compose ps` phân biệt được "đang chạy" với "chạy được việc". `backend` chỉ khởi động sau khi Postgres và Redis healthy; `frontend` chỉ khởi động sau khi backend trả `/api/v1/health`.

Mã nguồn `backend/` và `frontend/` được bind mount nên sửa file là reload, không cần build lại. Chỉ build lại khi đổi `pyproject.toml`, `package.json` hoặc `Dockerfile`:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Xóa sạch dữ liệu (Postgres, Redis) để dựng lại từ đầu — script khởi tạo extension chỉ chạy khi volume rỗng:

```bash
docker compose -f infra/docker-compose.yml down -v
```

## Ba điều dễ vấp

- **Hot reload: backend có, frontend không.** Windows không truyền sự kiện file vào máy ảo Linux, nên watcher phải hỏi định kỳ. Backend bật `WATCHFILES_FORCE_POLLING` và reload thật (đã kiểm chứng: sửa file → `WatchFiles detected changes ... Reloading`). Frontend thì **không**: đã thử `watchOptions.pollIntervalMs` trong `next.config.ts` (API chính thức của Next, biến `WATCH_POLL_INTERVAL_MS` do compose truyền vào) lẫn việc bỏ anonymous volume `.next`, Turbopack vẫn không nhận thay đổi — dù `stat` xác nhận mtime mới đã tới trong container. Cấu hình polling được giữ lại vì đúng đắn và tự tắt khi chạy ngoài Docker.

  **Cách làm việc thực tế khi sửa nhiều code frontend:** chạy Next trực tiếp trên host, phần còn lại vẫn trong Docker.

  ```bash
  docker compose -f infra/docker-compose.yml up -d postgres redis backend worker
  ```

  ```bash
  cd frontend && npm run dev
  ```

  Lúc đó `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` trong `.env.local` là đủ, không cần `API_BASE_URL_INTERNAL`. Phải là `localhost` chứ không phải `127.0.0.1`: trình duyệt coi hai tên này là **hai site khác nhau**, mà cookie refresh đặt `SameSite=lax` nên sẽ bị bỏ im lặng khi trang ở `localhost:3000` gọi sang `127.0.0.1:8000` — biểu hiện là đăng nhập xong F5 phát là mất phiên. Container `frontend` vẫn tồn tại để `docker compose up` một lệnh dựng đủ stack như gate Phase 1 yêu cầu; chỉ cần nhớ nó phục vụ bản code tại thời điểm khởi động, sửa xong thì `docker compose restart frontend`.
- **Thêm dependency frontend thì phải `--renew-anon-volumes`.** `node_modules` của container là anonymous volume; `docker compose up --build frontend` dựng image mới nhưng vẫn gắn lại volume cũ, nên gói vừa cài không có trong container và trang chết với `Module not found`. Lệnh đúng:

  ```bash
  docker compose -f infra/docker-compose.yml up -d --build --renew-anon-volumes frontend
  ```
- **Frontend cần hai URL backend.** Server Component gọi `http://backend:8000` (tên service trong mạng compose), còn trình duyệt không phân giải được tên đó nên phải gọi `http://localhost:8000`. Hai biến `API_BASE_URL_INTERNAL` và `NEXT_PUBLIC_API_BASE_URL` tách đúng hai phía này; `frontend/lib/api/client.ts` chọn theo `typeof window`.

## Ảnh backend có ffmpeg

`worker` chuyển mã video bằng ffmpeg, và `backend`/`worker` dùng chung một image (compose build một lần thay vì hai), nên container API cũng mang theo ffmpeg — thêm khoảng 250 MB, đổi lại không phải bảo trì hai Dockerfile. Thêm dependency Python hay đổi Dockerfile thì phải build lại:

```bash
docker compose -f infra/docker-compose.yml up -d --build backend worker
```

Biến `R2_*` truyền từ `infra/.env` vào cả hai service. Để trống thì endpoint upload trả 503 và mọi thứ khác chạy bình thường — xem [docs/huong-dan-cloudflare-r2.md](../docs/huong-dan-cloudflare-r2.md). `R2_ENDPOINT_URL` là lối trỏ sang một server S3 khác (MinIO chạy local chẳng hạn) khi cần thử luồng upload mà chưa có tài khoản Cloudflare.

## Ghi chú vận hành

- Grader cần truy cập Docker daemon để spin sandbox container — đây là quyết định kiến trúc có rủi ro đã biết, xem skill `sandbox-grading` trước khi đụng vào phần mount socket.
- Secrets đi qua `.env` (đã gitignore), không bao giờ commit. Mỗi service có `.env.example` liệt kê biến cần thiết.
- Backup DB tự động là task của [Phase 6](../docs/plan/phase-6-hardening-deploy.md); script restore phải được thử khôi phục thật ít nhất một lần.

## Chưa có gì ở đây

- `docker-compose.prod.yml` và cấu hình `nginx/` — viết khi deploy VPS ở [Phase 2](../docs/plan/phase-2-core-platform.md).
- Service `grader` — thêm ở [Phase 3](../docs/plan/phase-3-code-grading.md) cùng lúc với code grader, qua checklist skill `sandbox-grading`.
- `scripts/` backup và restore DB — [Phase 6](../docs/plan/phase-6-hardening-deploy.md).
