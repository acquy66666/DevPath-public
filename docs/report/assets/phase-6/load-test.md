# Load test nhẹ — trang danh sách và một lớp nộp code cùng lúc

Ngày đo: 02/10/2026, 12:26–12:44 giờ VN · Phase 6, task "Load test nhẹ (locust/k6): trang danh sách, submit code 20 đồng thời"

Công cụ: **k6 2.3.0** · kịch bản ở [`infra/loadtest/`](../../../../infra/loadtest/) · số liệu thô (JSON tóm tắt của k6) ở [`load-test/`](load-test/)

## Đo trên cái gì

**Stack production, không phải stack dev.** Stack dev chạy uvicorn `--reload` một tiến trình, bật log SQL và `next dev` biên dịch theo yêu cầu — đo trên đó là đo công cụ phát triển. Nên stack đo là chính `infra/docker-compose.prod.yml`, dựng trên máy dev dưới tên project riêng (`devpath-prodtest`, volume tách khỏi stack dev; stack dev tạm dừng trong lúc đo):

| Thành phần | Cấu hình khi đo |
|---|---|
| nginx 1.27 | TLS (chứng chỉ tự ký cho `localhost`), HTTP/2, header bảo mật — đúng template production |
| frontend | Next.js 16 bản standalone, **một tiến trình Node** |
| backend | uvicorn **2 worker** (`UVICORN_WORKERS=2`), `ENV=production` |
| grading-worker | image `grading-production` (uid 10001), `GRADING_CONCURRENCY=2`, sandbox 0,5 CPU / 128 MB mỗi container |
| Postgres 16 + pgvector, Redis 7 | như production |
| Dữ liệu | `scripts.seed` + `scripts.seed_interactions` → **24 khóa đã xuất bản** (2 trang danh sách), tìm "python" ra 4 khóa |

**Máy:** Windows 11, Docker Desktop (Engine 29.7.2, containerd snapshotter), máy ảo Linux **8 CPU / 7,8 GB**. k6 chạy trong container trên chính mạng compose và gọi `https://nginx`, nên thứ được đo là máy chủ chứ không phải đường mạng từ Windows vào Docker; đổi lại k6 dùng chung CPU với thứ nó đo.

**Đây chưa phải máy chủ thật.** VPS dự kiến là 2 vCPU / 4 GB. Kịch bản viết để chạy lại nguyên vẹn trên VPS (`./loadtest/run.sh catalogue|class`, mặc định trỏ vào project `devpath` và `.env.prod`) — việc đó thuộc task deploy.

## Hai kịch bản

**Duyệt danh sách** (`catalogue.js`). Mỗi người ảo (VU) lặp: trang `/khoa-hoc` + API `/api/v1/courses` → nghỉ 1 s → trang tìm `?q=python` + API tìm kiếm → nghỉ 1 s → trang 2 → nghỉ 1 s. Trang là thứ trình duyệt xin nginx (Next render phía server, gọi API qua mạng compose); API được gọi riêng qua nginx để tách được phần nào là API, phần nào là render. Tài nguyên tĩnh bỏ ra ngoài: nginx phục vụ từ đĩa với cache một năm, trình duyệt tải một lần. Bốn mức: 10, 25, 50, 100 VU, mỗi mức 60 giây.

**Một lớp nộp bài** (`submissions.js`). `scripts.stage_load_test` dựng một khóa miễn phí với một bài tập Python 5 test case (2 mẫu + 3 ẩn, chương trình `a + b`) và 21 học viên đã ghi danh. Học viên thứ 21 nộp **một mình** trước (`mot-minh`) — làm nóng sandbox, và cho con số "hàng đợi rỗng". Giây thứ 20, **20 học viên còn lại bấm "Nộp bài" cùng lúc** (`lop-hoc`), mỗi người mở **đúng WebSocket mà trang nộp bài mở** (`/api/v1/submissions/{id}/events`, subprotocol `bearer`) và chờ tới khi nó báo `done`. Thời gian đo là thứ học viên thấy: từ lúc bấm tới lúc verdict hiện. Chạy hai lần, rồi hai lần nữa với **25 người duyệt danh sách song song**.

## Kết quả 1 — trang danh sách

Thời gian phản hồi (ms): trung vị / p95 / p99. 0 request lỗi ở mọi mức.

| VU | Throughput | Trang `/khoa-hoc` | Trang tìm kiếm | Trang 2 | API danh sách | API tìm kiếm |
|---:|---:|---|---|---|---|---|
| 10 | 15,7 req/s | 35 / 87 / 253 | 31 / 52 / 80 | 38 / 66 / 80 | 7 / 13 / 16 | 8 / 13 / 16 |
| 25 | 39,4 req/s | 34 / 74 / 292 | 28 / 74 / 106 | 35 / 67 / 79 | 7 / 11 / 14 | 8 / 13 / 19 |
| 50 | 79,3 req/s | 32 / 108 / 567 | 23 / 59 / 83 | 31 / 68 / 102 | 7 / 11 / 15 | 7 / 13 / 18 |
| 100 | **148,6 req/s** | 87 / **282** / 953 | 27 / 211 / 639 | 74 / 169 / 367 | 7 / 10 / 12 | 8 / 17 / 358 |

CPU giữa mỗi mức (một ảnh `docker stats`; 100% = một lõi):

| VU | frontend | backend (2 worker) | nginx | Postgres |
|---:|---:|---:|---:|---:|
| 10 | 16% | 17% | 3% | 3% |
| 25 | 27% | 67% | 5% | 6% |
| 50 | 59% | 58% | 16% | 11% |
| 100 | **101%** | 89% | 16% | 19% |

RAM ở 100 VU: frontend 354 MiB, backend 242 MiB (cả hai worker), Postgres 110 MiB, nginx 17 MiB, Redis 14 MiB.

## Kết quả 2 — 20 học viên nộp cùng lúc

| Lượt | Nộp (POST) trung vị / chậm nhất | Một mình: bấm → verdict | Cả lớp: trung vị | p90 | Người cuối cùng | Đúng |
|---|---|---:|---:|---:|---:|---:|
| Lớp học, lần 1 | 246 / 306 ms | 3,44 s | 25,9 s | 41,8 s | 45,1 s | 21/21 |
| Lớp học, lần 2 | 299 / 385 ms | 3,24 s | 19,2 s | 32,1 s | 35,4 s | 21/21 |
| Lớp học + 25 người duyệt, lần 1 | 454 / 642 ms | 3,44 s | 21,9 s | 36,8 s | 40,2 s | 21/21 |
| Lớp học + 25 người duyệt, lần 2 | 259 / 482 ms | 3,04 s | 22,4 s | 44,9 s | 49,5 s | 21/21 |

Người duyệt trong lúc lớp nộp bài: trang `/khoa-hoc` 35 / 98 / 456 ms và 33 / 82 / 266 ms (so với 34 / 74 / 292 ms khi 25 người duyệt mà không ai nộp bài); API 8 / 16 / 34 và 8 / 15 / 20 ms; 0 request lỗi trong 12.057 request.

**Đối chứng từ bên trong.** `scripts.bench_grading` (công cụ đo của Phase 3) chạy trên cùng stack production, cùng 20 bài × 5 test case, đo bằng kênh tiến độ Redis thay vì qua nginx:

| | Trung bình | p50 | p90 | Chậm nhất |
|---|---:|---:|---:|---:|
| Tổng (nộp → verdict) | 18,69 s | 18,45 s | 30,74 s | 34,66 s |
| Chờ hàng đợi | 15,27 s | 15,16 s | 27,38 s | 30,93 s |
| Chấm (worker chạy) | 3,43 s | 3,36 s | 3,65 s | 3,72 s |

Cả đợt 35,1 s · 34,2 bài/phút · **685 ms mỗi test case** (302 ms chương trình chạy bên trong + 384 ms dựng/dọn container) · một mình 3,11 s. Phase 3 đo 630 ms/case ở cùng 2 slot (`phase-3/benchmark.md`).

## Điều đọc được

**1. Load test tìm ra một lỗi làm hỏng toàn bộ việc chấm bài trên production — và đã sửa.** Lượt chạy thử đầu tiên (3 học viên): mọi bài nộp kết thúc `error` sau ~46 s (ba lần thử, nghỉ 15 s rồi 30 s). Log worker:

```
grading failed for submission 8d6522d4-… (attempt 3): PermissionError: [Errno 13]
Permission denied: '/var/lib/devpath-grading/devpath-grading-ptmleeds'
```

Thư mục workspace `/var/lib/devpath-grading` do Docker daemon **tự tạo** khi bind-mount một nguồn chưa tồn tại — với quyền `root:root 755`. Worker production chạy uid 10001 (cố ý, xem `backend/Dockerfile`) nên không tạo nổi thư mục tạm của bài nộp. Worker dev chạy bằng root nên chưa bao giờ lộ ra; CI không dựng stack production đủ để chấm bài. Nghĩa là **trên VPS mới, mọi bài nộp sẽ là lỗi hệ thống ngay từ bài đầu tiên.** Sửa trong `docker-compose.prod.yml`: service `grading-workspace` chạy một lần trước worker (`chown 10001:10001` + `chmod 700`, rồi thoát; worker `depends_on … service_completed_successfully`) — không có bước tay nào trong runbook để quên. Sau sửa: `10001:10001 700`, 4/4 bài AC, rồi 84/84 bài AC qua bốn lượt đo. 700 là đủ: sandbox chỉ thấy thư mục `code/` của chính nó, daemon là root.

**2. Thứ học viên chờ là hàng đợi, không phải sandbox — giống hệt Phase 3, giờ đo từ ngoài vào.** Một mình: ~3 s. Hai mươi người cùng bấm: người ở giữa chờ ~20 s, người cuối 35–50 s, trong đó 15 s trung bình là nằm chờ tới lượt và chỉ ~3,4 s là được chấm. Công thức `20 bài × 5 case × 0,685 s / 2 slot ≈ 34 s` khớp con số đo, nên dự đoán được: lớp 40 người → người cuối ~70 s. Núm vặn là `GRADING_CONCURRENCY`, và trên VPS 2 vCPU nó vẫn là 2 — nên con số này sẽ không tốt hơn trên VPS. Trang nộp bài đã nói thật "đang chờ tới lượt chấm" (Phase 3); với buổi thực hành đông người, đây là giới hạn cần nói ra chứ không phải lỗi.

**3. Đường production cộng thêm rất ít.** Đo từ ngoài (k6 → nginx TLS → API → WebSocket) và đo từ trong (`bench_grading`) lệch nhau chưa tới một giây: 19,2 / 35,4 s so với 18,5 / 34,7 s. Nộp bài (POST) dưới 0,65 s kể cả khi 20 người bấm cùng lúc và 25 người khác đang duyệt.

**4. Chấm bài không làm chậm người khác.** Trong lúc lớp nộp bài, người duyệt danh sách thấy p95 74 → 82–98 ms, API 11 → 15–16 ms, 0 lỗi. Sandbox bị giới hạn 0,5 CPU mỗi container và chỉ có 2 container cùng lúc — đúng thiết kế "để phần còn lại cho Postgres, Redis và API".

**5. Trần của trang danh sách là một tiến trình Node, và nó ở xa.** API đứng yên ở 7 ms trung vị từ 10 tới 100 VU. Trang render tăng tuyến tính tới 100 VU (148,6 req/s ≈ 89 trang/s), và ở 100 VU frontend chạm **101% CPU** — một lõi đầy, Node một luồng — đúng lúc đuôi dài ra (p99 ~1 s). Backend lúc đó mới dùng 89% của 200%. Một trang danh sách nặng 134 KB, trong đó 72 KB là payload RSC để hydrate, trong khi JSON của API chỉ 8 KB: chi phí là render + tuần tự hóa React, không phải dữ liệu. Ở quy mô khóa luận không cần làm gì; khi cần thì chạy thêm một bản frontend sau nginx (upstream hai server) hoặc cache trang danh sách không tham số.

**6. Bài học đo lường: lượt đầu sai gấp năm, và chỉ một con số hiệu chuẩn mới bắt được.** Lượt đo đầu tiên chạy ngay sau khi build ba image production, cùng một vòng `docker stats` liên tục để ghi CPU. Kết quả: trang danh sách "bão hòa" ở 28–30 req/s (trung vị 1,8 s ở 50 VU, 4,3 s ở 100 VU), lớp 20 người xong sau 149 s, một bài một mình 14 s — và một kết luận sai rằng frontend là nút thắt ở 25 VU. Một lệnh `docker run --rm` trơn lúc đó mất 1,0–1,5 s; lúc máy yên chỉ 0,33–0,40 s. Đo lại khi máy yên, không có `docker stats` liên tục (chỉ một ảnh mỗi mức) → các số ở trên, nhanh gấp ~5 lần. Từ đó mỗi lượt đều kèm **mốc hiệu chuẩn trước và sau** (5 lần `docker run --rm`): 0,32–0,39 s ở mọi lượt được giữ lại. Docker Desktop còn chậm đi ~1–2 phút sau mỗi đợt tạo/xóa vài trăm container (một lần đo được 0,6–0,97 s, rồi tự hồi) — nên giữa hai lượt lớp học phải chờ mốc về lại.

## Tái tạo

Stack production thử trên máy dev (trên VPS bỏ qua bước 1–3, dùng stack thật):

```bash
cd infra
# 1. Tệp env riêng (đã bị .gitignore), mật khẩu ngẫu nhiên. DOMAIN=localhost;
#    DOCKER_GID=0 vì socket của Docker Desktop là root:root 660.
P="docker compose -p devpath-prodtest -f docker-compose.prod.yml --env-file .env.prodtest"
$P build
docker compose stop                      # tạm dừng stack dev để không tranh CPU
# 2. CSDL + dữ liệu
$P up -d --wait postgres redis
$P run --rm backend alembic upgrade head
$P run --rm -e SEED_ADMIN_PASSWORD=… -e SEED_INSTRUCTOR_PASSWORD=… backend python -m scripts.seed
$P run --rm backend python -m scripts.seed_interactions
# 3. Chứng chỉ tự ký vào volume letsencrypt (bước đầu của init-tls.sh), rồi cả stack
$P run --rm --entrypoint sh certbot -c "…openssl req -x509 … -subj /CN=localhost"
$P up -d --wait
# 4. Đo
COMPOSE_PROJECT_NAME=devpath-prodtest ENV_FILE=.env.prodtest ./loadtest/run.sh catalogue
COMPOSE_PROJECT_NAME=devpath-prodtest ENV_FILE=.env.prodtest ./loadtest/run.sh class
# 5. Dọn
$P down -v && rm .env.prodtest && docker compose up -d
```

Lần 2 của lớp học ghi vào `load-test/lan-2/` (`OUT=…/lan-2`). `bench_grading`: `$P exec backend python -m scripts.bench_grading --submissions 20 --cases 5`.

## Chưa đo, và vì sao

- **VPS thật** — chưa có máy; chạy lại `run.sh` sau khi deploy (task "Dựng máy chủ thật"). Đặc biệt với lớp học: 2 vCPU phải chia cho sandbox, Postgres, API và Next.
- **Đăng nhập** — có giới hạn theo IP và theo email (task rà soát bảo mật); một máy k6 đăng nhập 20 lần là đo cái giới hạn, không đo hệ thống.
- **Video** — luồng HLS do R2/CDN phục vụ, không đi qua máy chủ.
- **Trợ giảng AI** — giới hạn là quota Gemini free tier, không phải máy chủ; đã đo riêng ở Phase 4 (`phase-4/chat-api.txt`).
- Người dùng ảo nghỉ 1 s giữa hai trang — nặng hơn người thật nhiều lần. Đây là thước đo khả năng chịu tải, không phải dự báo số người dùng.
