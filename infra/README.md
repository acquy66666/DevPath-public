# Infra — Docker Compose, Nginx, deploy

Toàn bộ hệ thống chạy bằng một lệnh `docker compose up` ở máy dev và trên VPS.

## Cấu trúc

```
docker-compose.yml       postgres (pgvector), redis, backend, frontend, worker, grader
docker-compose.prod.yml  override cho VPS (nginx, HTTPS, restart policy)
nginx/                   reverse proxy, cấu hình TLS
scripts/                 deploy, backup DB (pg_dump → R2), restore
```

## Ghi chú vận hành

- Grader cần truy cập Docker daemon để spin sandbox container — đây là quyết định kiến trúc có rủi ro đã biết, xem skill `sandbox-grading` trước khi đụng vào phần mount socket.
- Secrets đi qua `.env` (đã gitignore), không bao giờ commit. Mỗi service có `.env.example` liệt kê biến cần thiết.
- Backup DB tự động là task của [Phase 6](../docs/plan/phase-6-hardening-deploy.md); script restore phải được thử khôi phục thật ít nhất một lần.

## Chưa có gì ở đây

`docker-compose.yml` được viết ở task riêng trong [Phase 1](../docs/plan/phase-1-foundation.md), sau khi backend và frontend chạy được độc lập.
