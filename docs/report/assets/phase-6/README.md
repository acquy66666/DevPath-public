# Bằng chứng Phase 6 — Hardening & Deploy

Chỉ mục dựng ngày 05/10/2026 trong lượt rà kho bằng chứng (lượt 1). Phase chưa đóng: các task cần máy chủ thật còn mở. Phase 6 khác các phase trước ở chỗ phần lớn bằng chứng là **diễn tập stack production trên máy dev**, vì chưa có VPS. Mỗi tệp ghi rõ nó chạy trên stack nào. Bảng tổng hợp cho cả kho và danh sách còn thiếu nằm ở [`../README.md`](../README.md).

## Gate cuối phase

| Gate đòi | Tệp | Trạng thái 05/10 |
|---|---|---|
| URL demo công khai trên tên miền thật, tự khởi động lại sau reboot VPS | — | **chưa** — chờ task "Dựng máy chủ thật". Đã có tổng duyệt `docker-compose.prod.yml` trên máy dev (`../phase-2/`, `monitoring.txt`, `rustfs-compose.txt`) |
| Luồng vàng chạy lại trên tên miền thật, có đăng nhập Google, chụp lại ảnh | `e2e-golden-flow.txt` + `e2e/` (stack dev và CI) | **chưa** trên tên miền thật. Luồng vàng tự động đã xanh trên dev và CI; Google chỉ chạy được khi có redirect URI cố định |
| Toàn bộ test (unit + E2E + bảo mật sandbox) xanh trong CI | `test-summary.md` | **có tại 05/10** — CI run 37263170818 (commit `0bae373`), 6/6 job xanh. Kiểm lại trên commit được tag |
| Kiểm tra kho bằng chứng | `../README.md` | **lượt 1 xong 05/10** — còn một lượt cuối sau khi có VPS |
| Tag `phase-6-done` | — | chưa |

## Tệp

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `security-review.txt` | Rà soát bảo mật (01/10): ma trận phân quyền 159 route, 0 lỗ; sửa 5 lỗi thật (IP giả qua `X-Forwarded-For`, auth chưa rate limit, `/_next/static/` mất header, `deploy.sh --seed` không chuyển mật khẩu seed, CORS/JWT/schema mở ở production) | 5 — Kiểm thử, và mục bảo mật |
| `security-review-codebase.txt` | `/security-review` toàn bộ code (01/10): 3 lỗ thật đã sửa kèm test — HIGH chiếm trước tài khoản qua liên kết Google, MEDIUM đơn chờ thanh toán không hết hạn, MEDIUM open redirect `?next=/\evil` | 5 — Kiểm thử, và mục bảo mật |
| `e2e-golden-flow.txt` + `e2e/` (8 ảnh) | E2E Playwright đăng ký → mua → học → nộp code → chứng chỉ trên cả stack; xanh trên dev và CI; tìm ra 2 lỗi font. **Ảnh giao diện đúng font duy nhất theo trình tự luồng**, nhưng là tài khoản/khóa E2E và còn nút dev của Next | 4 và 5 |
| `load-test.md` + `load-test/` | k6 trên stack production dựng ở máy dev: API danh sách 7 ms trung vị từ 10 tới 100 VU, trang tới 148,6 req/s; lớp 20 người nộp: 84/84 AC, người cuối 35–50 s. Tìm ra lỗi production (workspace chấm bài root:root) | 5 — Kiểm thử & đánh giá |
| `ux-polish.txt` + `ux/` (12 ảnh trước \| sau) | Rà 47 trang × 2 bề rộng × 5 vai bằng đo `scrollWidth`: tràn ngang 14/94 → 0/94; thẻ giá lên đầu trang trên điện thoại, ảnh bìa dự phòng, trang chủ bỏ thẻ "Kết nối backend" | 4 — Xây dựng hệ thống (giao diện) |
| `db-backup-restore.txt` | Service backup (pg_dump cùng version, bucket private, giữ 14 bản theo số) + diễn tập khôi phục thật: 41/41 bảng giống hệt từng dòng, E2E xanh trên bản khôi phục, app dừng ~20 s | 4 — Triển khai và vận hành |
| `monitoring.txt` + `monitoring/drill.log` | Log xoay vòng, monitor trên host (systemd timer) + ntfy, diễn tập 10 kịch bản; tìm ra lỗi production nginx không bao giờ reload chứng chỉ gia hạn | 4 — Triển khai và vận hành |
| `fresh-machine.txt` + `fresh-machine/` | Hai lượt trên bản clone mới: README cũ hỏng ở bước 3, README mới chạy hết, 9 script demo × 2 lần, E2E xanh; tìm ra lỗi production `VNPAY_*` không vào compose prod | 4 — Triển khai |
| `docker-socket-proxy.txt` | Proxy đọc body cho Docker socket: worker chấm bài không còn là root trên host; 267 test qua proxy, diễn tập tấn công từ worker, chi phí ~4 %/lượt | 4, và mục bảo mật sandbox |
| `polling-progress-decision.txt` | Quyết định không commit kết quả từng case (đo ~1,2 ms/case — lý do thật là dòng SE của lượt sắp retry); E2E giờ đỏ nếu verdict không tới qua WebSocket | 4 — Xây dựng hệ thống |
| `peak-memory-decision.txt` | Bỏ cột `submissions.peak_memory_mb`: cgroup v2 không cho đọc mức đỉnh từ bên ngoài; công thức đo từ bên trong để làm sau | 4, và 6 — Hướng phát triển |
| `readiness-endpoint.txt` | `GET /health/ready` (CSDL + Redis, mỗi cái ≤ 2 s, song song) tách khỏi liveness; diễn tập dừng/pause từng phụ thuộc | 4 — Triển khai và vận hành |
| `orphan-sweep.txt` | Dọn object mồ côi: đánh dấu → xóa sau 14 ngày, van an toàn theo prefix; diễn tập 3 đêm trên bucket dev, 3 test đột biến | 4 — Xây dựng hệ thống |
| `sse-through-nginx.txt` + `sse-through-nginx/` | Trợ giảng AI qua nginx production: chữ tới từng mẩu (HTTP/1.1 và Chrome HTTP/2), đối chứng âm khi ép buffer | 4 và 5 |
| `site-url.txt` | Lỗi canonical/`og:url` = `http://localhost:3000` trên image production, sửa bằng build arg + Dockerfile từ chối build thiếu biến | 4 — Triển khai |
| `refresh-leeway.txt` + `refresh-leeway/` | Hai tab chung cookie bị đăng xuất mọi thiết bị (3/3 trên code cũ) → ân hạn 30 s cho token bị xoay; test hai kết nối thật | 4, và mục bảo mật |
| `storage-decision.txt` + `storage-decision/` | Chọn storage production bằng phép thử 20 kiểm: RustFS 20/20, SeaweedFS 20/20; media tự host, backup CSDL lên B2 | 4 — Triển khai |
| `rustfs-compose.txt` + `rustfs-compose/` | RustFS vào cả hai stack: chép 252 object dev (0 lệch), prod dựng thật trên máy dev 21/21 kiểm, Chrome PUT 50 MB qua HTTP/2 | 4 — Triển khai |
| `test-summary.md` | **Bảng tổng hợp test** (thêm 05/10): số test từng bộ trên CI, phân theo phân hệ, coverage backend đo một lần | 5 — Kiểm thử & đánh giá |
| `schema-final.sql` | **Schema CSDL ở head `abb01d258134`** (thêm 05/10): 41 bảng + `alembic_version`, 58 khóa ngoại, 78 CHECK — nguồn để vẽ ERD ở Phase 7. Dump lại nếu có migration mới trước khi tag | 3 — Phân tích & thiết kế |

## Cách tái tạo hai tệp thêm ngày 05/10

Schema (bỏ dòng `\restrict`/`\unrestrict` mà pg_dump 16.10+ chèn token ngẫu nhiên, để hai lần dump so được bằng `diff`):

```bash
docker compose -f infra/docker-compose.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only --no-owner --no-privileges' | grep -v -E '^.(un)?restrict [A-Za-z0-9]+$' > docs/report/assets/phase-6/schema-final.sql
```

Số test và coverage: xem mục "Cách tái tạo" trong `test-summary.md`.
