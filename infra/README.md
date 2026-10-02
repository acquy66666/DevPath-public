# Infra — Docker Compose, Nginx, deploy

Toàn bộ hệ thống chạy bằng một lệnh `docker compose up` ở máy dev và trên VPS.

## Cấu trúc

```
docker-compose.yml       Máy dev: postgres (pgvector), redis, minio, backend, worker, beat, grading-worker, frontend
docker-compose.prod.yml  VPS: thêm nginx + certbot, bỏ cổng DB, bỏ bind mount
docker-compose.tunnel.yml  Overlay: thêm cloudflared, cho stack production một URL công khai
.env.prod.example        Mẫu biến môi trường cho VPS
postgres/init/           SQL chạy một lần khi volume rỗng (CREATE EXTENSION)
nginx/templates/         vhost, `${DOMAIN}` do entrypoint của image điền bằng envsubst
nginx/snippets/          Header proxy và header bảo mật dùng chung
scripts/init-tls.sh      Xin chứng chỉ Let's Encrypt lần đầu
scripts/deploy.sh        Build → migrate → khởi động → đợi healthy
scripts/tunnel.sh        Bật/tắt URL công khai tạm, in URL ra màn hình
loadtest/                k6 vào stack production: trang danh sách + một lớp nộp code cùng lúc (Phase 6)
backup/                  Service sao lưu: pg_dump mỗi đêm lên bucket private, giữ N bản; image dựng từ chính image Postgres
scripts/restore-db.sh    Khôi phục: vào CSDL phụ trong lúc site chạy, rồi đổi tên thay CSDL đang chạy (giữ bản cũ)
monitor/                 Giám sát trên host: mỗi phút kiểm container, site, chứng chỉ, đĩa; báo qua ntfy (systemd timer)
scripts/install-monitor.sh  Cài/gỡ timer của monitor (cần sudo)
../grader/proxy/          Proxy Docker API: container duy nhất cầm socket, chỉ cho worker chấm bài làm việc chấm bài
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
| http://minio.localhost:9000 | MinIO — storage S3 thay R2 trên máy dev (xem mục bên dưới) |

Tám service; bảy cái có healthcheck, nên `docker compose ps` phân biệt được "đang chạy" với "chạy được việc". Riêng `beat` không có, vì nó chỉ phát lịch chứ không nhận việc nên không trả lời `inspect ping` (lý do ghi trong compose). `backend` chỉ khởi động sau khi Postgres và Redis healthy; `frontend` chỉ khởi động sau khi backend trả `/api/v1/health`.

Mã nguồn `backend/` và `frontend/` được bind mount nên sửa file là reload, không cần build lại. Chỉ build lại khi đổi `pyproject.toml`, `package.json` hoặc `Dockerfile`:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Xóa sạch dữ liệu (Postgres, Redis, MinIO) để dựng lại từ đầu — script khởi tạo extension chỉ chạy khi volume rỗng:

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
- **Frontend cần hai URL backend — ở máy dev.** Server Component gọi `http://backend:8000` (tên service trong mạng compose), còn trình duyệt không phân giải được tên đó nên phải gọi `http://localhost:8000`. Hai biến `API_BASE_URL_INTERNAL` và `NEXT_PUBLIC_API_BASE_URL` tách đúng hai phía này; `frontend/lib/api/client.ts` chọn theo `typeof window`. Ở `docker-compose.prod.yml` thì phía trình duyệt để rỗng: nginx đưa `/api` về backend trên cùng origin, nên bundle không chứa tên miền nào.

## Ảnh backend có ffmpeg

`worker` chuyển mã video bằng ffmpeg, và `backend`/`worker` dùng chung một image (compose build một lần thay vì hai), nên container API cũng mang theo ffmpeg — thêm khoảng 250 MB, đổi lại không phải bảo trì hai Dockerfile. Thêm dependency Python hay đổi Dockerfile thì phải build lại:

```bash
docker compose -f infra/docker-compose.yml up -d --build backend worker
```

## Object storage trên máy dev: MinIO thay cho R2

Từ 18/09/2026, stack dev có thêm service `minio`: một server S3 chạy ngay trên máy, đứng thay Cloudflare R2. Các biến `R2_*` để trống trong `infra/.env` thì tự trỏ vào nó, nên upload video, avatar và transcript chạy được ngay trên một bản clone mới, không cần tài khoản nào. Code chỉ nói giao thức S3, không biết mình đang nói chuyện với MinIO hay R2. `docker-compose.prod.yml` **không** có MinIO; production vẫn dùng R2.

| Thứ | Giá trị |
|---|---|
| API S3 | `http://minio.localhost:9000`, bucket `devpath-media` (đọc ẩn danh được, ghi phải có chữ ký) |
| Xem bên trong bucket | Không có console web: bản MinIO cộng đồng bỏ console từ 2025, image vẫn truyền `--console-address :9001` nhưng không gì nghe ở đó (cổng 9001 trong compose từ 18/09 tới 02/10/2026 dẫn vào khoảng không). Dùng `mc` có sẵn trong container — lệnh ngay dưới bảng |
| Dữ liệu | volume `minio_data`, còn nguyên qua các lần restart |

```bash
docker compose -f infra/docker-compose.yml exec minio sh -c 'mc alias set dev http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc ls --recursive dev/devpath-media'
```

(Alias `local` có sẵn trong image không có khóa, nên `mc ls local/...` treo im lặng — phải khai alias như trên.)

**Vì sao là `minio.localhost` chứ không phải `minio`:** URL ký sẵn chỉ hợp lệ cho đúng một host, và cùng một URL được cả trình duyệt lẫn worker dùng. Trình duyệt dùng nó để PUT file và phát video; worker dùng nó để tải bản gốc và đẩy HLS lên. Chrome và Edge tự đưa mọi `*.localhost` về `127.0.0.1`, nơi cổng 9000 được publish; trong mạng compose, cũng cái tên đó là alias của service. Một tên dùng được cho cả hai phía. Hệ quả:

- mở web bằng **Chrome/Edge** qua `http://localhost:3000`. CORS của MinIO chỉ mở cho đúng origin đó;
- **Trình phân giải của Windows không biết `*.localhost`**, nên script chạy bằng venv trên host không tới được storage. Script nào đụng storage thì chạy trong container: `docker compose exec worker python -m scripts.<tên>`;
- cổng 9000 cố định, không đổi qua biến được, vì nó nằm trong URL đã ký và URL đã lưu. Cổng chỉ bind vào `127.0.0.1`, vì mật khẩu dev nằm ngay trong file compose.

**Image:** `bitnamilegacy/minio:2025.7.23-debian-12-r5`. MinIO đã ngừng phát hành image cho bản cộng đồng: `minio/minio` và `minio/mc` đã bị gỡ khỏi Docker Hub (kiểm tra 18/09/2026), `bitnami/minio` không còn tag nào. Bản Bitnami "legacy" này đông cứng từ tháng 8/2025 và không được cập nhật nữa. Chấp nhận được cho một server thay thế chỉ chạy local trên `127.0.0.1`, không chấp nhận được cho bất cứ chỗ nào khác. Nếu một ngày nó cũng biến mất, chỉ cần thay khối `minio:` trong compose bằng một server S3 khác; app không phải sửa gì.

**Dùng R2 thật từ stack dev:** điền **đủ** các biến `R2_*`, kể cả `R2_ENDPOINT_URL=https://<account id>.r2.cloudflarestorage.com`. Để trống biến nào thì biến đó rơi về MinIO chứ không rơi về R2. Xem [docs/huong-dan-cloudflare-r2.md](../docs/huong-dan-cloudflare-r2.md).

## Worker chấm bài, và proxy đứng giữa nó với Docker

Chấm bài **chính là** khởi động container, nên `grading-worker` phải nói chuyện được với Docker daemon. Nó dùng image riêng (`grading-development` / `grading-production`) vì chỉ nó cần Docker CLI. Nhưng từ 02/10/2026 nó **không cầm `/var/run/docker.sock`** nữa: CLI của nó trỏ `DOCKER_HOST=tcp://docker-proxy:2375`.

**Vì sao:** socket không phải hệ thống phân quyền. Ai cầm nó thì một request — `docker run --privileged -v /:/host` — là thành root trên host. Trước đây worker cầm thẳng socket; các biện pháp giảm thiệt hại (không phục vụ HTTP, không publish cổng, uid 10001, code người nộp chỉ chạy trong container dùng một lần) chỉ làm khó việc chiếm worker, chứ chiếm được rồi thì chiếm luôn host.

**`docker-proxy`** (`grader/proxy/`, Python chỉ thư viện chuẩn) là container **duy nhất** cầm socket, ngồi trên mạng nội bộ `grading-docker` chỉ có nó và worker, không publish cổng. Nó cho qua đúng những gì một lượt chấm cần — lấy từ chính lưu lượng của CLI 29.7 khi runner chấm một bài:

| Cho qua | Điều kiện |
|---|---|
| `HEAD/GET /_ping` | — |
| `POST /containers/create` | Body phải là một sandbox: image trong danh sách (`devpath-sandbox-python:v1`), tên `devpath-grading-<hex>`, nhãn đúng `devpath.grading=1`, user `10001:10001`, `NetworkMode none`, rootfs read-only, `CapDrop ALL`, `no-new-privileges`, memory/CPU/pids/CPU-time dưới trần nền tảng, swap = memory, `/tmp` là tmpfs `noexec` có giới hạn, log driver `none`, và **đúng một** bind mount read-only `<workspace>/devpath-grading-xxxxxxxx/code` là thư mục thật (không phải symlink). Mọi trường khác phải ở giá trị zero — trường Docker thêm sau này bị chặn cho tới khi có người quyết nó vô hại |
| `start` / `attach` / `wait` / `kill` / `json` / `DELETE` một container | Daemon xác nhận container mang nhãn `devpath.grading=1` (proxy hỏi `inspect` trước khi chuyển tiếp). `start` kiểm lại nguồn mount vì daemon mount lúc start chứ không phải lúc create |

Mọi thứ khác là **403**: `exec` (vào Postgres chẳng hạn), pull/build image, liệt kê container, network, volume, prune, swarm. Mỗi kết nối chỉ một request (`Connection: close`), body có `Transfer-Encoding` hay hai `Content-Length` bị từ chối — body đã kiểm đúng là body daemon đọc. `docker compose logs docker-proxy` ghi mỗi request một dòng, `allowed` hay `DENIED: <luật>`.

**Vì sao tự viết thay vì dùng proxy có sẵn** (`tecnativa/docker-socket-proxy` và họ hàng): chúng lọc theo endpoint. Mở `containers` + `POST` cho runner là mở luôn một `create` có `Privileged: true` và bind-mount `/` — đúng request cần chặn. Rủi ro nằm trong body của một endpoint, nên phải đọc body.

**Còn lại sau proxy:** worker bị chiếm vẫn tạo được sandbox (đúng mọi bất biến) và chạy code tùy ý *trong* sandbox — thứ học viên nào cũng làm được bằng cách nộp bài. Khe hở giữa lần kiểm symlink cuối và lúc daemon mount vẫn còn về lý thuyết; thứ lọt qua được là một view read-only các tệp uid 10001 đọc được, trong container không mạng.

Kiểm: `grader/tests/test_docker_proxy_policy.py` (từng luật, trên body thật đã ghi lại), `test_docker_proxy_server.py` (HTTP, smuggling, half-close của attach), `test_docker_proxy_live.py` (tấn công qua proxy vào daemon thật). CI chạy lại toàn bộ bộ verdict + 7 ca tấn công sandbox **xuyên qua proxy**, và đỏ nếu service nào khác ngoài `docker-proxy` cầm socket.

### Trước lần chấm đầu tiên: build image sandbox

Runner khởi động container với `--pull never`, nên thiếu image là một lỗi hệ thống kêu to chứ không phải một lần tải ngầm:

```bash
docker build -t devpath-sandbox-python:v1 grader/images/python
```

### Hai hàng đợi, hai worker

| Service | Hàng đợi | Concurrency | Vì sao tách |
|---|---|---|---|
| `worker` | `media,celery` | `CELERY_CONCURRENCY` (mặc định 1) | Một lần chuyển mã ffmpeg ăn trọn một core hàng chục phút |
| `grading-worker` | `grading` | `GRADING_CONCURRENCY` (mặc định 2) | Bài nộp ngắn, và có người đang ngồi nhìn màn hình chờ |

Chung một hàng đợi thì một bài giảng vừa upload sẽ chặn mọi bài nộp phía sau. **`GRADING_CONCURRENCY` là con số phải sửa khi đổi VPS:** mỗi bài chấm giữ một container 0.5 CPU / 256 MB, nên 2 là trần của máy 2 vCPU — phần còn lại dành cho Postgres, Redis và API.

### Một đường dẫn phải giống nhau ở hai phía

`DEVPATH_GRADING_WORKSPACE=/var/lib/devpath-grading`, và đúng đường dẫn đó được bind-mount 1:1 vào worker. Lý do: daemon phân giải `--mount source=` **trên host**, nên thư mục chứa bài nộp phải tồn tại ở cả hai nơi dưới cùng một tên. Thiếu nó thì mọi bài nộp đều hỏng với `bind source path does not exist` — đã gặp thật, xem `docs/report/assets/phase-3/grading-queue.txt`.

Thư mục đó còn phải **ghi được bởi uid 10001**. Daemon tự tạo nguồn bind-mount còn thiếu với quyền `root:root 755`, nên trên máy trắng worker production (uid 10001) không tạo nổi thư mục tạm và mọi bài nộp kết thúc bằng lỗi hệ thống (`PermissionError`). Worker dev chạy bằng root nên không bao giờ lộ ra; load test Phase 6 là lần đầu worker production chấm bài và bắt được nó (`docs/report/assets/phase-6/load-test.md`). Giờ `docker-compose.prod.yml` có service `grading-workspace` chạy một lần trước worker: `chown 10001:10001` + `chmod 700` rồi thoát — không có bước tay nào để quên.

Trên VPS còn cần `DOCKER_GID` trong `.env.prod` — cho `docker-proxy` (uid 10001) mở được socket:

```bash
getent group docker | cut -d: -f3
```

## Ghi chú vận hành

- Grader cần truy cập Docker daemon để spin sandbox container — xem mục trên và skill `sandbox-grading` trước khi đụng vào phần mount socket.
- Secrets đi qua `.env` (đã gitignore), không bao giờ commit. Mỗi service có `.env.example` liệt kê biến cần thiết.
- Backup DB: service `backup` (mục bên dưới). Đã khôi phục thật một lần trên stack dev, 02/10/2026 — `docs/report/assets/phase-6/db-backup-restore.txt`.

## URL công khai không cần máy chủ

Từ Phase 2 tới Phase 5, dự án cần một link người khác mở được nhưng **chưa cần** một máy chủ đứng suốt ngày. Cloudflare Quick Tunnel cho đúng chừng đó, miễn phí, không tài khoản, không tên miền:

```bash
./scripts/deploy.sh
```

```bash
./scripts/tunnel.sh
```

Script in ra `https://<ngẫu nhiên>.trycloudflare.com`. Chứng chỉ là của Cloudflare và hợp lệ thật — trình duyệt không cảnh báo gì.

`./scripts/tunnel.sh --url` in lại URL của tunnel đang chạy, `--stop` tắt tunnel mà giữ nguyên stack.

Tunnel trỏ vào **nginx**, không trỏ thẳng vào Next: `/api` phải về backend trên cùng origin với trang, và nginx chính là thứ làm điều đó đúng. Trỏ vào `frontend:3000` sẽ ra một trang mở được nhưng 404 ở mọi lời gọi API.

Ba giới hạn, biết trước thì không bực: URL đổi sau mỗi lần container khởi động lại; tunnel sống đúng bằng thời gian máy này bật; đăng nhập Google không chạy vì redirect URI phải đăng ký trước. Đăng nhập bằng mật khẩu gánh được cả buổi demo.

## Deploy lên VPS

Stack production là **file riêng**, không phải override. Override chỉ thêm được vào danh sách chứ không bỏ bớt, mà hai thứ bắt buộc phải biến mất trên VPS — cổng Postgres/Redis publish ra ngoài và bind mount mã nguồn — lại đúng là những mục không gỡ được bằng override.

Khác biệt so với máy dev:

- **Chỉ nginx mở cổng.** Postgres, Redis, API và Next chỉ nhìn thấy nhau trong mạng compose, nên tường lửa chỉ phải nghĩ về 2 cổng thay vì 6.
- **Image dựng từ target `production`:** không reloader, không pytest/ruff, Next chạy bản `next build` standalone chứ không phải `next dev`.
- **Không bind mount.** Thứ đang chạy đúng là thứ đã build — điều kiện để rollback có ý nghĩa.
- `restart: unless-stopped` khắp nơi, nên VPS khởi động lại là site tự lên.

### Yêu cầu trước

| Thứ | Ghi chú |
|---|---|
| VPS Ubuntu 22.04+ | 2 vCPU / 4 GB là vừa cho cấu hình mặc định trong `.env.prod.example` |
| Docker Engine + plugin compose | Bản chính chủ của Docker, không phải `docker.io` của distro |
| Tên miền | Bản ghi A trỏ về IP VPS **trước khi** xin chứng chỉ |
| Cổng 80 và 443 mở | ACME là một request HTTP đi vào từ Let's Encrypt; không có gì thay thế được |

### Lần đầu

```bash
git clone https://github.com/acquy66666/DevPath.git && cd DevPath/infra
```

```bash
cp .env.prod.example .env.prod && chmod 600 .env.prod
```

Điền `DOMAIN`, `ACME_EMAIL`, `POSTGRES_PASSWORD`, `JWT_SECRET` (hai cái sau sinh bằng `openssl rand`, đừng tự nghĩ ra). Compose từ chối khởi động nếu thiếu, và backend từ chối khởi động nếu `JWT_SECRET` vẫn là giá trị dev.

```bash
./scripts/init-tls.sh --staging
```

Chạy `--staging` trước: CA thử nghiệm của Let's Encrypt không giới hạn số lần, nên nếu DNS chưa kịp lan hoặc tường lửa còn chặn thì thử lại thoải mái. Trình duyệt sẽ báo chứng chỉ không tin cậy — đúng như mong đợi. Khi thấy nó chạy trót lọt thì chạy lại **không có** `--staging` để lấy chứng chỉ thật.

```bash
./scripts/deploy.sh --seed
```

`--seed` chỉ dùng lần đầu: nó tạo admin, 8 danh mục và 4 khóa học mẫu. Nhớ đặt `SEED_ADMIN_PASSWORD` và `SEED_INSTRUCTOR_PASSWORD` trong môi trường trước khi chạy, nếu không mật khẩu mặc định sẽ nằm trên một máy có mặt trên Internet.

### Những lần sau

```bash
git fetch origin && git log --oneline HEAD..origin/main
```

```bash
git merge --ff-only origin/main && ./scripts/deploy.sh
```

`deploy.sh` cố tình **không** tự `git pull`: chọn commit nào lên production là một quyết định, script tự fetch là lấy mất quyết định đó. Thứ tự bên trong là build → migrate → khởi động → đợi healthy, và nó thoát với mã lỗi kèm `docker compose ps` nếu sau 3 phút còn service chưa healthy.

Thứ tự "migrate trước, khởi động sau" hợp với loại thay đổi dự án này hay làm (thêm bảng, thêm cột nullable). Migration **xóa hoặc đổi tên** thì phải đi hai bước: deploy code chịu được cả hai hình dạng trước, rồi mới migrate.

### Chứng chỉ tự gia hạn

Service `certbot` dậy 12 tiếng một lần, gia hạn thứ gì còn dưới 30 ngày và không làm gì trong phần lớn thời gian còn lại. nginx chỉ đọc tệp chứng chỉ lúc (re)load, nên entrypoint của nó có một vòng lặp reload mỗi 6 giờ. Trước 02/10/2026 không có vòng này và mục này ghi "deploy lần kế tiếp là đủ" — tức chứng chỉ đã gia hạn nằm im trên đĩa, còn bản trong bộ nhớ hết hạn 90 ngày sau lần đầu nếu không ai deploy (diễn tập: `docs/report/assets/phase-6/monitoring.txt`, kịch bản E). Monitor kiểm đúng chứng chỉ **đang được phục vụ**, báo khi còn dưới 14 ngày. Reload ngay, không chờ vòng:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -s reload
```

### Kiểm tra khi có sự cố

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f --tail 100 backend
```

Cột `Health` trong `ps` là câu trả lời của chính healthcheck, không phải phỏng đoán — `running (unhealthy)` nghĩa là container sống nhưng không làm được việc, và đó thường là biến môi trường sai chứ không phải code hỏng.

## Giám sát, log, cảnh báo

**Log** — mọi service ghi stdout, Docker gom lại; anchor `x-logging` trong `docker-compose.prod.yml` xoay vòng 5 tệp × 10 MB mỗi container (tệp cũ nén gzip), vì mặc định Docker giữ log không giới hạn. Một lệnh đọc cả stack, có giờ: `docker compose ... logs -t --since 1h`. CI đỏ nếu một service mới quên anchor. Giới hạn biết trước: container bị thay khi deploy mang log của nó đi theo — có sự cố thì đọc log **trước khi** deploy lại.

**Monitor** (`monitor/devpath_monitor.py`, chỉ thư viện chuẩn) chạy **trên host** bằng systemd timer mỗi phút, không chạy trong container: đọc health của container là nói chuyện với Docker daemon, mà trên host này đúng một container cầm socket — `docker-proxy`, và nó chỉ cho worker chấm bài làm đúng việc chấm bài (mục trên). Mỗi lượt kiểm:

- mọi service compose khai `restart: unless-stopped`/`always` đang chạy và healthcheck không đỏ; container bị Docker tự dựng lại kể từ lượt trước thì báo một lần (`RestartCount`);
- `https://DOMAIN/`, `/api/v1/health` và `/api/v1/courses?page_size=1` hỏi qua nginx ở `127.0.0.1:443` với đúng tên miền (TLS + định tuyến nằm trong đường đi). Cái thứ ba vì `/health` cố ý không chạm CSDL: diễn tập tắt Postgres thì trang chủ vẫn 200, `/health` vẫn 200, chỉ danh mục trả 500;
- chứng chỉ nginx đang phục vụ xác thực được và còn ≥ `MONITOR_CERT_MIN_DAYS` (14) ngày;
- đĩa chứa dữ liệu Docker còn ≥ `MONITOR_DISK_MIN_FREE_PERCENT` (10) %.

Một vấn đề phải thấy ở **2 lượt liên tiếp** mới báo (container bị thay lúc deploy không phải sự cố), nhắc lại mỗi 6 giờ, và có tin "đã ổn lại" kèm thời gian. Tin gửi tới ntfy (`MONITOR_NTFY_URL`, không cần tài khoản); gửi không được thì nằm trong outbox chờ lượt sau. Trạng thái ở `/var/lib/devpath-monitor/state.json`. Cài: `sudo ./scripts/install-monitor.sh`; xem: `journalctl -u devpath-monitor -f` hoặc `python3 monitor/devpath_monitor.py status`. Thứ monitor không thấy được là chính cái máy này chết — việc đó của uptime check bên ngoài (runbook mục 4b). Unit test: `python -m pytest infra/monitor` (job backend của CI); bản cài thật chạy trên systemd của runner trong job deploy-config.

## Sao lưu và khôi phục CSDL

Service `backup` (`backup/devpath_backup.py`) dump CSDL mỗi đêm lúc `BACKUP_HOUR` giờ Việt Nam lên `BACKUP_BUCKET` và giữ `BACKUP_KEEP` bản mới nhất. Bốn quyết định đáng biết:

- **Image dựng từ chính `pgvector/pgvector:pg16`** của service `postgres`, nên `pg_dump`/`pg_restore` luôn cùng major version với server: `pg_dump` cũ hơn server thì từ chối chạy, mới hơn thì viết ra bản mà server cũ có thể không đọc được — kiểu lỗi chỉ lộ ra vào đêm cần khôi phục. Đổi tag của hai service cùng lúc. Image gốc dừng bằng `SIGINT` (fast shutdown của Postgres); Dockerfile đặt lại `SIGTERM` cho Python.
- **Bucket riêng, private.** Bucket media cho tải ẩn danh; bản dump chứa email và hash mật khẩu. Service từ chối nếu hai tên trùng nhau. Ở máy dev, `R2_*` trống thì nó ghi vào bucket `devpath-backups` của MinIO, tự tạo private.
- **Giữ theo số bản, không theo tuổi**: đồng hồ sai hay một tháng không có backup cũng không làm nó xóa bản cuối cùng. Chỉ xóa đúng object do chính nó đặt tên (`postgres/<db>-<giờ UTC>.dump`).
- **Mỗi bản được đọc lại trước khi tải lên** (`pg_restore --list` phải thấy `alembic_version`) và mang sha256 trong metadata; khôi phục thì kiểm lại sha256.

Khởi động mà bản mới nhất đã quá 24 giờ (máy tắt lúc 02:00, hay đêm trước lỗi) thì chạy ngay; lỗi thì thử lại sau 30 phút. Healthcheck đỏ khi quá 26 giờ không có bản thành công, nên `deploy.sh` và `ps` thấy được. Production thiếu nơi lưu thì service đứng yên, unhealthy và nói lý do — muốn chạy không backup phải ghi `BACKUP_ENABLED=false`.

Ở máy dev, service nằm sau profile `backup` (không tự chạy theo `up`):

```bash
docker compose --profile backup run --rm backup backup
```

```bash
docker compose --profile backup run --rm backup list
```

Khôi phục là `scripts/restore-db.sh` — trên VPS như runbook (`docs/huong-dan-deploy-vps.md`, mục 7b), trên máy dev với `COMPOSE_FILE=docker-compose.yml`. Unit test của phần tự quyết (đặt tên, xoay vòng, lịch, chọn nơi lưu, health): `python -m pytest infra/backup`, chạy trong job backend của CI.
