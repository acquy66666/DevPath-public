# Chạy DevPath, cấu trúc file, và vai trò của Docker

Tài liệu này trả lời ba câu: **chạy trang web thế nào**, **file nằm ở đâu và vì sao**, và **Docker đóng vai trò gì trong dự án**. Mọi con số trong đây đều đo trực tiếp từ hệ thống đang chạy, không phải ước lượng.

Muốn biết **sửa màu, sửa chữ, sửa giới hạn ở đâu** thì xem [huong-dan-du-an.md](huong-dan-du-an.md) — tài liệu đó bổ trợ cho tài liệu này chứ không trùng.

---

# Phần 1 — Chạy trang web

## 1.1 Chuẩn bị, chỉ làm một lần

```bash
cp infra/.env.example infra/.env
```

File `.env` chứa cổng và khóa truy cập; nó bị `.gitignore` nên không bao giờ lên GitHub. Để nguyên giá trị mặc định là chạy được — các biến `R2_*` để trống chỉ làm chức năng upload video trả lỗi 503, mọi thứ khác vẫn bình thường.

## 1.2 Bốn bước mỗi lần chạy

**Bước 1 — Bật Docker.** Trên máy này phải dùng script, không bấm icon (lý do ở mục 3.10):

```bash
powershell -ExecutionPolicy Bypass -File C:\Users\Admin\start-docker.ps1
```

Script chạy xong sẽ in `DOCKER DA SAN SANG`. Nếu chưa thấy dòng đó thì đừng làm bước 2.

**Bước 2 — Dựng 5 container.**

```bash
docker compose -f infra/docker-compose.yml up -d
```

Lần đầu mất vài phút vì phải build image; những lần sau khoảng 20–30 giây.

**Bước 3 — Tạo bảng và nạp dữ liệu.** Chỉ cần khi database còn trống:

```bash
cd backend && .venv\Scripts\python.exe -m alembic upgrade head
```

```bash
cd backend && .venv\Scripts\python.exe -m scripts.seed
```

Chạy lại nhiều lần vô hại: `alembic` bỏ qua migration đã chạy, `seed` bỏ qua dữ liệu đã có.

**Bước 4 — Kiểm tra rồi mở trình duyệt.**

```bash
docker compose -f infra/docker-compose.yml ps
```

Cả 5 dòng phải ghi `(healthy)`. Chữ `(health: starting)` nghĩa là còn đang khởi động — chờ thêm 30 giây. Sau đó:

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:3000 | Trang web |
| http://localhost:8000/docs | Tài liệu API tự sinh — **đáng mở cho giáo viên xem** |
| http://localhost:8000/api/v1/health | Kiểm tra backend sống, trả JSON |

## 1.3 Dừng lại

```bash
docker compose -f infra/docker-compose.yml down
```

Lệnh này **giữ nguyên dữ liệu**. Chỉ khi muốn xóa sạch database để dựng lại từ đầu mới thêm `-v`:

```bash
docker compose -f infra/docker-compose.yml down -v
```

`-v` xóa cả volume, tức là mất toàn bộ tài khoản và khóa học đã tạo. Sau đó phải chạy lại bước 3.

## 1.4 Bảng lệnh hay dùng

| Việc cần làm | Lệnh |
|---|---|
| Xem trạng thái | `docker compose -f infra/docker-compose.yml ps` |
| Xem log backend đang chảy | `docker compose -f infra/docker-compose.yml logs -f backend` |
| Khởi động lại một service | `docker compose -f infra/docker-compose.yml restart frontend` |
| Vào trong container backend | `docker compose -f infra/docker-compose.yml exec backend bash` |
| Mở psql trên database | `docker compose -f infra/docker-compose.yml exec postgres psql -U devpath -d devpath` |
| Build lại sau khi đổi Dockerfile | `docker compose -f infra/docker-compose.yml up -d --build` |
| Chạy test | `cd backend && .venv\Scripts\python.exe -m pytest -q` |

---

# Phần 2 — Cấu trúc file

## 2.1 Toàn cảnh

```
E-learning/
├── backend/     API và worker xử lý nền      (Python, FastAPI)
├── frontend/    Giao diện người dùng          (TypeScript, Next.js)
├── grader/      Sandbox chấm code             (Phase 3, còn trống)
├── infra/       Docker, nginx, script deploy
├── docs/        Thiết kế và kế hoạch
└── de-cuong-khoa-luan-elearning.md            Đề cương gốc
```

Mỗi thư mục cấp 1 có `README.md` riêng nói rõ nguyên tắc và trạng thái của phần đó.

## 2.2 Backend — bốn tầng, mỗi tầng một việc

```
backend/app/
├── api/v1/      Router:   URL nào gọi hàm nào. KHÔNG chứa logic nghiệp vụ
├── services/    Service:  logic nghiệp vụ, quyết định ranh giới transaction
├── models/      Model:    mô tả bảng trong database
├── schemas/     Schema:   hình dạng JSON vào và ra, Pydantic kiểm tra tự động
├── core/        Cấu hình, kết nối DB, bảo mật, dependency dùng chung
└── workers/     Tác vụ chạy nền qua Celery (hiện có: chuyển mã video)
```

**Một tính năng luôn nằm rải ở bốn file cùng tên.** Ví dụ chức năng đánh giá khóa học:

| File | Việc nó làm |
|---|---|
| `models/review.py` | Bảng `reviews`: cột, khóa ngoại, ràng buộc 1–5 sao |
| `schemas/reviews.py` | Nhận vào cái gì, trả ra cái gì; chặn rating ngoài 1–5 |
| `services/reviews.py` | Ai được đánh giá, tính lại điểm trung bình của khóa học |
| `api/v1/reviews.py` | 4 endpoint `GET/PUT/DELETE .../reviews/me` và `GET .../reviews` |

Muốn hiểu bất kỳ tính năng nào, đọc đúng bốn file cùng tên đó là đủ.

**Vì sao tách ra thay vì viết gọn một chỗ:** chỉ tầng service là đáng kiểm thử, và nó là tầng duy nhất không cần biết HTTP. Logic nằm trong router thì muốn test phải dựng request giả; nằm trong service thì chỉ cần gọi một hàm Python bình thường. Khác biệt đó nghe nhỏ cho tới lúc có ba mươi endpoint.

Hai thư mục còn lại trong `backend/`:

- `alembic/versions/` — mỗi lần đổi cấu trúc database sinh ra một file ở đây. Không bao giờ sửa database bằng tay.
- `tests/` — 473 test, chạy bằng `pytest`.

## 2.3 Frontend — route chính là thư mục

Next.js App Router lấy **đường dẫn thư mục làm URL**. `app/ho-so/page.tsx` chính là trang `/ho-so`.

```
frontend/
├── app/
│   ├── (marketing)/   Trang công khai: chủ, danh sách và chi tiết khóa học
│   ├── (auth)/        Đăng nhập, đăng ký
│   ├── (learn)/       Màn hình học: trình phát video, ghi chú
│   ├── (dashboard)/   Khu giảng viên
│   └── layout.tsx     Khung bao ngoài toàn bộ trang
├── components/        Component theo miền; components/ui là thư viện shadcn
└── lib/api/           Gọi backend, mỗi domain một file
```

Hai quy ước dễ bị hỏi:

- **Thư mục trong ngoặc đơn không xuất hiện trên URL.** `(marketing)` chỉ để nhóm các trang dùng chung một layout — trang trong đó có header và footer, trang trong `(auth)` thì không. URL vẫn là `/khoa-hoc`, không phải `/marketing/khoa-hoc`.
- **`"use client"` ở đầu file** nghĩa là component chạy trong trình duyệt. Không có dòng đó thì nó chạy trên server và người dùng chỉ nhận HTML. Mặc định là server; chỉ thêm `"use client"` khi thật sự cần state hoặc sự kiện chuột — ví dụ nút "Đăng ký học" cần biết ai đang đăng nhập.

## 2.4 Vài file ở gốc repo

| File | Vai trò |
|---|---|
| `README.md` | Trang đầu của repo: mô tả, lệnh chạy, trạng thái |
| `CLAUDE.md` | Quy ước dự án |
| `.github/workflows/ci.yml` | 4 job kiểm tra tự động mỗi lần push |
| `.gitignore` | Danh sách không đưa lên GitHub: `.env`, `node_modules`, `.venv` |

---

# Phần 3 — Docker tác động tới dự án thế nào

## 3.1 Không có Docker thì phải cài gì

Hệ thống này cần bốn thứ chạy song song, ngoài code của chính nó:

| Thành phần | Vì sao cần | Cài tay trên Windows |
|---|---|---|
| PostgreSQL 16 | Database chính | Cài được, nhưng còn thiếu extension |
| `pgvector` | Lưu vector embedding cho AI ở Phase 4 | Phải biên dịch hoặc tìm bản binary rời |
| Redis | Hàng đợi công việc cho Celery | **Không có bản chính thức cho Windows** |
| ffmpeg 7.x | Chuyển mã video sang HLS | Tải rời, tự thêm vào PATH |

Docker thay toàn bộ danh sách đó bằng một lệnh. Đó là tác động lớn nhất và cũng dễ thấy nhất.

Kiểm chứng ngay trong hệ thống đang chạy:

```
Extension trong Postgres: vector, pg_trgm, unaccent, plpgsql
ffmpeg trong image backend: 7.1.5
```

## 3.2 Năm container và việc của từng cái

| Container | Image | Việc |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` (621 MB) | Database. Bản pgvector nên có sẵn kiểu vector |
| `redis` | `redis:7-alpine` (57.8 MB) | Hàng đợi việc cho worker |
| `backend` | `devpath-backend:dev` (1.08 GB) | API FastAPI, cổng 8000 |
| `worker` | **cùng image với backend** | Celery, chạy việc nặng: chuyển mã video |
| `frontend` | `devpath-frontend:dev` (1.34 GB) | Next.js, cổng 3000 |

**`backend` và `worker` dùng chung một image** — Docker build một lần thay vì hai. Hệ quả: container API cũng mang theo ffmpeg dù không dùng tới, tốn thêm khoảng 250 MB. Đổi lại không phải bảo trì hai Dockerfile. Đây là một đánh đổi có chủ đích, nói ra được thì tốt.

## 3.3 Mạng nội bộ — tên service chính là hostname

Docker Compose tạo một mạng riêng tên `devpath_default` và cắm cả 5 container vào đó. Trong mạng này, **tên service là tên miền dùng được luôn**:

```
Từ trong container backend:
  postgres  ->  172.18.0.3
  redis     ->  172.18.0.2
```

Vì vậy chuỗi kết nối trong `docker-compose.yml` viết là `@postgres:5432` chứ không phải `@localhost:5432`. Mỗi container có không gian mạng riêng, `localhost` bên trong backend là chính nó, không phải máy Windows.

**Đây là gốc rễ của một chuyện hay bị hỏi: vì sao frontend cần hai URL backend?**

- Server Component chạy **bên trong** container → gọi `http://backend:8000`
- Trình duyệt chạy **trên máy bạn** → không phân giải nổi tên `backend`, phải gọi `http://localhost:8000`

Hai biến `API_BASE_URL_INTERNAL` và `NEXT_PUBLIC_API_BASE_URL` tách đúng hai phía đó; `frontend/lib/api/client.ts` chọn theo `typeof window`. Trên VPS thì gộp làm một vì nginx đưa cả hai về chung một domain.

## 3.4 Dữ liệu sống ở đâu

Container bị xóa là mất sạch những gì ghi bên trong nó. Nên dữ liệu cần giữ được đặt trong **named volume** — vùng lưu trữ Docker quản lý, tồn tại độc lập với container:

```
devpath_postgres_data    toàn bộ database (hiện 9.2 MB)
devpath_redis_data       hàng đợi việc
```

Hệ quả thực tế cần nhớ:

| Lệnh | Dữ liệu |
|---|---|
| `docker compose down` | **Còn nguyên** |
| `docker compose down -v` | **Mất hết**, phải seed lại |
| Xóa container bằng tay | Còn nguyên, volume không dính dáng |

Redis bật `--appendonly yes` để việc đang xếp hàng không bay mất khi khởi động lại.

## 3.5 Healthcheck — "đang chạy" khác "chạy được việc"

Mỗi service có một phép thử định kỳ. Backend tự gọi `/api/v1/health` của chính nó, Postgres chạy `pg_isready`, frontend thử `fetch` trang chủ.

Nhờ đó `depends_on` mới có nghĩa: backend chỉ khởi động **sau khi Postgres trả lời được truy vấn**, chứ không phải sau khi container Postgres vừa hiện ra. Không có healthcheck thì backend hay chết ngay lúc khởi động vì kết nối vào một database chưa sẵn sàng.

Thứ tự thực tế lúc `up -d`:

```
redis + postgres  →  (chờ healthy)  →  backend + worker  →  (chờ backend healthy)  →  frontend
```

## 3.6 Bind mount — vì sao sửa backend là reload, frontend thì không

Compose gắn thư mục mã nguồn trên máy vào trong container:

```
../backend  →  /app
```

Sửa file Python trên Windows là file trong container đổi theo, uvicorn thấy và tự nạp lại. Không phải build lại image.

**Nhưng frontend thì không hot reload trong Docker.** Windows chạy nhân Linux trong máy ảo, và sự kiện thay đổi file không đi qua ranh giới đó — Turbopack nhìn thấy một cây thư mục có vẻ như không bao giờ đổi. Cách làm việc thật khi sửa nhiều giao diện: chạy Next trực tiếp trên máy, phần còn lại vẫn trong Docker.

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis backend worker
```

```bash
cd frontend && npm run dev
```

Khi đó `.env.local` chỉ cần `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. Phải là `localhost` chứ **không** phải `127.0.0.1`: trình duyệt coi hai tên đó là hai site khác nhau, mà cookie refresh đặt `SameSite=lax` nên sẽ bị bỏ im lặng — biểu hiện là đăng nhập xong F5 phát là mất phiên.

## 3.7 Hai file compose: máy dev và máy chủ

| | `docker-compose.yml` | `docker-compose.prod.yml` |
|---|---|---|
| Mã nguồn | Bind mount, sửa là reload | Nằm sẵn trong image |
| Cổng mở ra ngoài | 3000, 8000, 5432, 6379 | **Chỉ 80 và 443** (nginx) |
| Image | target `development` | target `production` |
| Khởi động lại | Không | `restart: unless-stopped` |
| nginx + HTTPS | Không | Có, kèm certbot tự gia hạn |

**Vì sao là hai file riêng chứ không phải một file phủ lên file kia:** file phủ chỉ **thêm** được vào danh sách, không bỏ bớt được. Mà hai thứ bắt buộc phải biến mất trên máy chủ — cổng database mở ra Internet và bind mount mã nguồn — lại đúng là những mục không gỡ được bằng cách phủ.

Cùng logic đó áp cho Dockerfile: mỗi file có hai target `development` và `production`, và `production` là target cuối cùng để ai quên chỉ định thì nhận bản an toàn chứ không nhận bản dev server.

## 3.8 Docker không chỉ là môi trường — nó là một tính năng của sản phẩm

Đây là phần quan trọng nhất của khóa luận và cũng là câu trả lời hay nhất cho câu hỏi "Docker tác động thế nào".

Ở Phase 3, khi học viên nộp bài tập lập trình, **hệ thống chạy code của người lạ**. Mỗi bài nộp được thực thi trong một container dùng một lần, với các ràng buộc:

| Cờ | Chặn điều gì |
|---|---|
| `--network none` | Code không gọi được ra Internet |
| `--read-only` | Không ghi được vào hệ thống file |
| `--user nobody` | Không có quyền root |
| `--cap-drop ALL` | Bỏ toàn bộ đặc quyền nhân |
| `--security-opt no-new-privileges` | Không leo thang quyền được |
| `--memory`, `--cpus` | Giới hạn tài nguyên |
| `--pids-limit` | Chặn fork bomb |

Kèm timeout hai lớp: đồng hồ thật ở worker **và** giới hạn CPU trong container.

Không có công nghệ cô lập kiểu container thì chức năng này **không làm được một cách an toàn** — đó là lý do Docker nằm trong đề cương ngay từ đầu chứ không phải chọn cho tiện. Chi tiết ở [grader/README.md](../grader/README.md).

## 3.9 Docker trong kiểm thử tự động

Mỗi lần push code, GitHub Actions dựng Postgres bằng đúng image `pgvector/pgvector:pg16` mà máy dev dùng, rồi chạy toàn bộ test lên đó. Bốn job:

| Job | Kiểm tra |
|---|---|
| Backend | Lint, migration, 473 test |
| Frontend | Lint và build |
| Migrations & seed | Migration lên–xuống–lên trên database trắng, seed chạy **hai lần** để chứng minh chạy lại không sinh thêm dữ liệu |
| Deploy config | Compose production hợp lệ, nginx nhận cấu hình, hai image production build được |

Ý nghĩa: test không chạy trên "database trên máy em" mà trên một database dựng mới tinh mỗi lần. Đó là điều làm cho câu "test xanh" có giá trị.

## 3.10 Lỗi Docker riêng của máy này

Trên máy này, **file socket AF_UNIX mà Docker tạo ra thì sau đó không xóa được nữa** (lỗi Windows 1920). Mỗi lần máy ngủ, Docker bị giết và để socket lại; lần bật sau nó phải xóa socket cũ trước khi tạo lại, xóa thất bại nên crash ngay.

Đã kiểm tra và loại trừ: đây **không phải hỏng ổ đĩa** — reparse tag của các file đó đọc ra `0x80000023`, đúng chuẩn `IO_REPARSE_TAG_AF_UNIX`, dữ liệu hoàn toàn lành. Chạy `chkdsk` không giúp gì.

Cách xử lý: luôn bật Docker bằng `C:\Users\Admin\start-docker.ps1`. Script đẩy thư mục socket cũ sang một bên (xóa từng file thì không được, di chuyển cả thư mục thì được) rồi mới khởi động Docker.

**Lưu ý khi demo:** đặt máy không ngủ trong lúc trình bày, vì máy ngủ là Docker chết theo và toàn bộ trang web tắt.

---

# Phần 4 — Sự cố thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| `failed to connect to the docker API` | Docker chưa chạy. Chạy `start-docker.ps1` |
| Docker Desktop hiện màn hình lỗi đỏ | Đã bấm icon thay vì chạy script. Xem mục 3.10 |
| Trang trắng, console báo `Failed to fetch` | Backend chưa lên. Kiểm tra http://localhost:8000/api/v1/health |
| `/khoa-hoc` trống trơn | Chưa chạy seed — bước 3 ở mục 1.2 |
| Đăng nhập xong F5 là mất phiên | Đang mở bằng `127.0.0.1`. Phải dùng `localhost` |
| Sửa file frontend mà trang không đổi | Hot reload không chạy trong Docker trên Windows. Xem mục 3.6 |
| `port is already allocated` | Có thứ khác đang giữ cổng đó. Đổi cổng trong `infra/.env` |
| Container ghi `unhealthy` | Container sống nhưng không làm được việc. Xem log: `docker compose ... logs <tên>` |
| Video không phát | Chưa cấu hình R2, hoặc mất mạng — video mẫu nằm trên Internet |

---

# Phần 5 — Câu hỏi về Docker và câu trả lời

**"Vì sao dùng Docker mà không cài trực tiếp?"**
Hệ thống cần Postgres kèm pgvector, Redis và ffmpeg chạy cùng lúc. Redis không có bản chính thức cho Windows, pgvector phải biên dịch. Docker gói cả bốn thứ vào một lệnh, và quan trọng hơn: máy em, máy CI và máy chủ chạy **cùng một image**, nên "chạy được trên máy em" không còn là câu bào chữa.

**"Container khác máy ảo chỗ nào?"**
Máy ảo giả lập cả phần cứng và chạy một hệ điều hành riêng, nặng hàng GB và khởi động hàng chục giây. Container dùng chung nhân với hệ điều hành chủ, chỉ cô lập tiến trình và hệ thống file — khởi động trong một giây. Trên Windows thì Docker vẫn cần một máy ảo Linux ở dưới, nhưng chỉ một cái duy nhất cho tất cả container.

**"Dữ liệu mất khi tắt container không?"**
Không, vì database nằm trong named volume `devpath_postgres_data`, tồn tại độc lập với container. Chỉ mất khi chạy `down -v`.

**"Nếu database chưa sẵn sàng mà backend đã khởi động thì sao?"**
Không xảy ra, vì `depends_on` dùng điều kiện `service_healthy` chứ không phải chỉ "đã khởi động". Backend đợi tới khi Postgres trả lời được `pg_isready`.

**"Chạy code của học viên có nguy hiểm không?"**
Có, đó là bề mặt tấn công lớn nhất của hệ thống. Vì vậy mỗi bài nộp chạy trong một container dùng một lần, không có mạng, hệ thống file chỉ đọc, không quyền root, bị giới hạn RAM, CPU và số tiến trình. Chi tiết ở mục 3.8.

**"Deploy lên máy chủ có khác gì không?"**
Khác ở ba điểm: chỉ nginx mở cổng ra Internet, image không có bind mount nên thứ đang chạy đúng là thứ đã build, và mọi service tự khởi động lại sau khi máy chủ reboot. Cấu hình đã viết xong và được CI kiểm chứng, nhưng **chưa deploy lên máy chủ thật** vì chưa có VPS và tên miền.
