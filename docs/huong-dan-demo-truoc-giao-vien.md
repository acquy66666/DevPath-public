# Hướng dẫn tự chạy và trình bày DevPath trước giáo viên

Tài liệu này phục vụ đúng một việc: **đứng trước giáo viên và cho hệ thống chạy mà không vấp**. Nó gồm chuỗi lệnh chạy thủ công kèm giải thích từng lệnh, kịch bản bấm chuột theo thứ tự, danh sách nút không được bấm, và câu trả lời cho những câu chắc chắn bị hỏi.

Hai tài liệu bổ trợ, không trùng nội dung:

- [huong-dan-chay-va-docker.md](huong-dan-chay-va-docker.md) — cấu trúc file và vai trò của Docker
- [huong-dan-du-an.md](huong-dan-du-an.md) — sửa từng phần giao diện, luồng một request

Mọi con số trong tài liệu này đo trực tiếp trên máy, không phải ước lượng.

---

## Phần 1 — Hôm trước ngày demo

Làm hết, đừng để tới sáng hôm sau.

- [ ] **Diễn thử trọn kịch bản Phần 3 một lần.** Đây là việc quan trọng nhất. Lỗi lộ ra lúc diễn thử thì sửa được; lộ ra trước mặt thầy thì không.
- [ ] **Tắt chế độ ngủ.** Settings → Power & sleep → cả "Screen" lẫn "Sleep" đặt **Never**, cắm sạc, không gập máy. Máy ngủ là Docker chết, và chết theo kiểu phải chạy script mới dậy lại được.
- [ ] **Kiểm tra mạng.** Video của 4 khóa mẫu lấy từ Internet (`test-streams.mux.dev`), mất mạng là mất phần phát video. Chuẩn bị sẵn điện thoại phát 4G.
- [ ] **Chuẩn bị dữ liệu tiến độ.** Đăng ký một tài khoản học viên, ghi danh một khóa miễn phí, xem video chừng một phút rồi thoát. Có sẵn dữ liệu này thì màn "vào lại đúng chỗ cũ" diễn được ngay, không phải ngồi chờ trước mặt thầy.
- [ ] **Đặt bookmark trình duyệt** trỏ đúng `http://localhost:3000` — **không phải `127.0.0.1`**. Lý do ở Phần 5, mục 4.
- [ ] **Chạy test một lần** để biết con số thật mà nói (xem Phần 6, câu 7).
- [ ] **Đừng build lại image, đừng chạy `npm ci`** trong vòng 24 giờ trước demo. Cả hai đều phụ thuộc mạng và đều có thể làm hỏng thứ đang chạy tốt.

---

## Phần 2 — Chuỗi lệnh chạy thủ công, 15 phút trước giờ

Bốn bước, chạy tại thư mục gốc `D:\Desktop\E-learning`. Sau mỗi bước có cách kiểm chứng — **đừng sang bước sau khi bước trước chưa đạt**.

### Bước 1 — Bật Docker

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Admin\start-docker.ps1
```

| Thành phần | Nghĩa |
|---|---|
| `powershell` | Gọi trình thông dịch PowerShell để chạy file `.ps1` |
| `-ExecutionPolicy Bypass` | Tạm bỏ chính sách chặn chạy script, **chỉ cho lần chạy này**, không đổi cài đặt hệ thống |
| `-File <đường dẫn>` | File script cần chạy |

Script đẩy thư mục socket cũ của Docker sang một bên rồi mới khởi động daemon — vòng qua lỗi Windows 1920 mô tả ở [huong-dan-chay-va-docker.md](huong-dan-chay-va-docker.md) mục 3.10. **Tuyệt đối không bấm icon Docker Desktop.**

✅ Đạt khi in ra `DOCKER DA SAN SANG`.

### Bước 2 — Dựng 5 container

```bash
docker compose -f infra/docker-compose.yml up -d --wait
```

| Thành phần | Nghĩa |
|---|---|
| `docker compose` | Chạy nhiều container cùng lúc theo mô tả trong một file |
| `-f infra/docker-compose.yml` | Chỉ định file mô tả; thiếu cờ này Docker báo không tìm thấy compose file |
| `up` | Tạo và khởi động các service, dùng lại image sẵn có chứ **không** build lại |
| `-d` | Chạy nền, trả lại con trỏ dòng lệnh. Bỏ `-d` thì Ctrl+C sẽ tắt luôn cả stack |
| `--wait` | **Chặn cho tới khi mọi healthcheck xanh.** Nhờ nó không phải ngồi gõ `ps` để đoán xem đã lên chưa |

Thứ tự khởi động do `depends_on` quyết định: `postgres` + `redis` → chờ healthy → `backend` + `worker` → chờ backend healthy → `frontend`.

✅ Đạt khi lệnh tự thoát không báo lỗi. Khoảng 20–40 giây.

### Bước 3 — Kiểm chứng hai tầng

```bash
docker compose -f infra/docker-compose.yml ps
```

Xem trạng thái từng service. Cả 5 dòng phải ghi `(healthy)`. Chữ `(health: starting)` nghĩa là còn đang khởi động — chờ thêm 30 giây.

```bash
curl -s "http://localhost:8000/api/v1/courses?page_size=3"
```

**Đây mới là phép thử thật.** `-s` tắt thanh tiến trình cho output sạch. Phải làm bước này vì `(healthy)` của backend chỉ chứng minh tiến trình còn sống — endpoint `/health` cố ý **không** chạm database. Chỉ khi `/courses` trả về `"total":4` mới chắc là migration đã chạy và dữ liệu đã có.

✅ Đạt khi thấy `"total":4`.

Nếu `total` bằng 0 hoặc lệnh báo lỗi thì database còn trắng, chạy hai lệnh sau. Bản PowerShell:

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
```

Tạo toàn bộ bảng. Alembic đọc chuỗi kết nối từ `app/core/config.py` chứ không phải từ `alembic.ini`, nên **bắt buộc đứng ở thư mục `backend`**. Migration đã chạy rồi thì nó bỏ qua, chạy lại vô hại.

```powershell
.\.venv\Scripts\python.exe -m scripts.seed
```

Nạp 1 admin, 2 giảng viên, 8 danh mục và 4 khóa học kèm mục lục đầy đủ. `-m scripts.seed` chạy `scripts/seed.py` **dưới dạng module** để các lệnh `import app...` bên trong tìm được đường. Script idempotent: chạy lần hai không nhân đôi dữ liệu.

> Trong Git Bash phải đổi dấu `\` thành `/` — bash coi `\S` là ký tự thoát nên `.venv\Scripts\python.exe` sẽ biến thành `.venvScriptspython.exe`. Bản Git Bash: `cd backend && ./.venv/Scripts/python.exe -m alembic upgrade head`. Ngược lại, PowerShell 5.1 không có toán tử `&&`, phải dùng `;`.

### Bước 4 — Mở sẵn ba tab

| Tab | Địa chỉ | Dùng lúc nào |
|---|---|---|
| 1 | `http://localhost:3000` | Toàn bộ kịch bản demo |
| 2 | `http://localhost:8000/docs` | Chặng 9 — tài liệu API tự sinh |
| 3 | `http://localhost:8000/api/v1/health` | Dự phòng khi bị hỏi "backend có sống không" |

Mở tab 1 bằng **`localhost`**, không phải `127.0.0.1`.

---

## Phần 3 — Kịch bản demo, 9 chặng

Tài khoản có sẵn (mật khẩu hard-code trong seed, chỉ dùng ở máy local):

| Email | Mật khẩu | Vai trò | Dùng để |
|---|---|---|---|
| `khoa.tran@devpath.local` | `devpath-instructor` | instructor | Chặng 8 — khu giảng viên |
| `mai.anh@devpath.local` | `devpath-instructor` | instructor | Dự phòng |
| `admin@devpath.local` | `devpath-admin` | admin | **Không dùng để demo** — chưa có giao diện quản trị, đăng nhập vào thì màn hình y hệt khách vãng lai |

Học viên thì tự đăng ký tại chỗ — chính nó là màn diễn luồng đăng ký.

**Chặng 1 · Trang chủ (30 giây).** Mở `http://localhost:3000`, giới thiệu tên hệ thống. Vào catalog bằng chữ **"Khóa học" trên thanh header** — hai nút to giữa trang đang `disabled`, bấm không có gì xảy ra.

**Chặng 2 · Tìm kiếm tiếng Việt (2 phút).** Ở `/khoa-hoc`, gõ **`lap trinh`** không dấu vào ô Tìm kiếm rồi bấm "Lọc" — vẫn ra khóa có dấu "Lập trình". Đây là điểm đáng khoe nhất của phần catalog: `to_tsvector('simple', unaccent(...))` với trọng số A/B/C cho tiêu đề / phụ đề / mô tả, xếp hạng bằng `ts_rank`. Chọn thêm Giá = "Miễn phí" thì còn 3/4 khóa. Chỉ vào thanh địa chỉ: mỗi trạng thái lọc là một URL chia sẻ được, và form dùng `method="get"` nên bộ lọc vẫn chạy cả khi tắt JavaScript.

**Chặng 3 · Trang chi tiết (1 phút).** Mở `/khoa-hoc/python-co-ban-cho-nguoi-moi-bat-dau`. Chuột phải → View Source để chứng minh nội dung nằm sẵn trong HTML đầu tiên: server-side render, có canonical và thẻ Open Graph cho SEO.

**Chặng 4 · Đăng ký (1 phút).** `/dang-ky` — họ tên, email, mật khẩu tối thiểu 8 ký tự. Đăng ký xong tự đăng nhập và về trang chủ. Nói kèm: mật khẩu băm bcrypt, access token sống 15 phút giữ trong bộ nhớ, refresh token nằm trong cookie HttpOnly nên JavaScript không đọc được.

**Chặng 5 · Ghi danh (30 giây).** Về trang chi tiết khóa Python, bấm **"Đăng ký học miễn phí"** → tự nhảy sang `/hoc/python-co-ban-cho-nguoi-moi-bat-dau`.

**Chặng 6 · ĐINH CỦA BUỔI DEMO, lưu tiến độ (3 phút).** Ở trang học:

1. Bấm Play, đổi tốc độ phát sang 1.5×.
2. Xem tới khoảng giây 40 rồi **bấm Pause** — pause là mốc lưu chắc chắn nhất.
3. **F5 tải lại trang** → video tua đúng về chỗ cũ.
4. Đóng tab, mở lại `/hoc/python-co-ban-cho-nguoi-moi-bat-dau` **không kèm `?bai=`** → tự mở đúng bài đang học dở.

Giải thích: nhịp tim 10 giây một lần, cộng với lưu khi pause, khi chuyển tab và khi rời trang — ba mốc đó khiến vị trí không bao giờ mất quá 10 giây.

**Chặng 7 · Ghi chú, bookmark, đánh giá (2 phút).** Vẫn ở trang học: gõ một ghi chú, nó hiện kèm nhãn `mm:ss`; tua video đi chỗ khác rồi **bấm vào nhãn thời gian** — video nhảy về đúng giây đó và tự phát. Bấm "Đánh dấu để xem lại", rồi "Đánh dấu hoàn thành" → thanh tiến độ nhích lên dạng `2/12 bài · 17%`. Quay lại trang chi tiết khóa học, cuộn xuống mục Đánh giá: vì đã ghi danh nên form hiện ra — chọn sao, gõ nhận xét, gửi. F5 thấy điểm trung bình ở đầu trang đã đổi.

**Chặng 8 · Khu giảng viên (3 phút).** Bấm avatar → Đăng xuất. Đăng nhập `khoa.tran@devpath.local` / `devpath-instructor` → menu avatar mọc thêm mục **"Khóa học tôi dạy"** → `/giang-day` đã có sẵn 2 khóa để nói chuyện. Mở một khóa, tới thẻ "Nội dung khóa học": **giữ chuột vào tay nắm 6 chấm và kéo một bài học sang chương khác** — thứ tự lưu ngay, không có nút Lưu. Diễn thêm bản bàn phím: chọn tay nắm, bấm Space, mũi tên lên/xuống, Space lần nữa — có thông báo tiếng Việt cho trình đọc màn hình. Cuối cùng bấm "Gửi duyệt" ở thẻ Trạng thái → badge nhảy sang "đã xuất bản" và mọc link "Xem trang công khai →".

**Chặng 9 · Tài liệu API (1 phút).** Mở `http://localhost:8000/docs` — Swagger sinh tự động từ Pydantic v2, 11 nhóm endpoint. Bấm "Try it out" trên `POST /api/v1/auth/login` để gọi API sống ngay tại chỗ. Câu chốt: tài liệu này không bao giờ lệch code, vì nó **là** code.

---

## Phần 4 — Bốn thứ đừng bấm

| Thứ | Chuyện gì xảy ra | Nói gì nếu bị hỏi |
|---|---|---|
| Hai nút to giữa trang chủ | `disabled`, bấm không có gì | Đường vào catalog là link "Khóa học" trên header |
| Nút "Chọn video để tải lên" | Lỗi 503 `STORAGE_NOT_CONFIGURED` vì chưa gắn bucket R2 | Phần 6, câu 2 |
| Nút đổi ảnh đại diện | Cũng 503, và câu thông báo lại nói về *video* vì dùng chung mã lỗi | Phần 6, câu 3 |
| Nút "Mua khóa học" ở khóa 499.000₫ | Nút mờ kèm dòng "Thanh toán đang được hoàn thiện" | **Đây là điểm cộng chứ không phải lỗi** — Phần 6, câu 4 |

Nút "Đăng nhập bằng Google" **không hiện** trên máy này: component tự trả về `null` khi thiếu `NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=true`. Đó là thiết kế có chủ đích để không mời người dùng bấm vào thứ chắc chắn lỗi — nên ở đây không có bẫy.

---

## Phần 5 — Sự cố giữa buổi

**1. Docker chết vì máy ngủ.** Đừng bấm icon Docker Desktop. Chạy lại Bước 1 rồi Bước 2. Dữ liệu không mất vì nằm trong named volume `devpath_postgres_data`.

**2. Video không phát, khung báo đỏ.** Mất mạng. Bật 4G điện thoại. Phần còn lại của hệ thống — đăng nhập, tìm kiếm, ghi danh, ghi chú — vẫn chạy bình thường vì toàn bộ dữ liệu nằm trong Docker trên máy.

**3. Trang trắng, console báo `Failed to fetch`.** Backend chưa lên. Kiểm tra `http://localhost:8000/api/v1/health`. Lưu ý `/khoa-hoc` **không** sống sót khi backend chết — chỉ trang chủ mới có try/catch.

**4. Đăng nhập xong F5 là mất phiên.** Đang mở bằng `127.0.0.1`. Trình duyệt coi `127.0.0.1` và `localhost` là hai site khác nhau, mà cookie refresh đặt `SameSite=lax` nên bị bỏ im lặng. Mở lại bằng `localhost:3000`.

**5. `port is already allocated`.** Có tiến trình khác giữ cổng. Sửa `POSTGRES_PORT` / `BACKEND_PORT` / `FRONTEND_PORT` trong `infra/.env` rồi `up -d` lại. Bẫy: đổi `POSTGRES_PORT` sẽ làm hỏng lệnh alembic và seed chạy từ venv, vì mặc định trong config là `localhost:5432`.

**6. `Module not found` sau khi đổi `package.json`.** `docker compose up -d` dùng lại image cũ. Phải chạy:

```bash
docker compose -f infra/docker-compose.yml up -d --build --renew-anon-volumes frontend
```

`--build` dựng lại image, `--renew-anon-volumes` vứt bỏ `node_modules` cũ nằm trong anonymous volume. Thiếu một trong hai cờ là lỗi còn nguyên. **Đừng chạy lệnh này ngay trước giờ demo** — nó cần mạng và mất vài phút.

**Nếu bị hỏi câu không trả lời được:** nói "chỗ này em phải mở code xem lại" rồi mở ra tìm thật. Tìm được câu trả lời trong repo của mình chính là thứ đang được đánh giá.

---

## Phần 6 — Câu hỏi chắc chắn bị hỏi

**1. "Cho thầy xem đăng nhập bằng Google."**
> Dạ luồng OAuth Google em code xong rồi, có test tự động ở `backend/tests/api/test_google_auth.py`, gồm cả chống CSRF bằng cookie `state`. Trên máy demo em cố ý không bật vì client secret không được nằm trong repo. Hệ thống xử lý đúng: nút bị ẩn đi thay vì để thầy bấm rồi lỗi, còn gọi thẳng API thì trả 503 với mã `GOOGLE_OAUTH_NOT_CONFIGURED` chứ không phải 500.

**2. "Em thử upload một video xem."**
> Dạ luồng upload em làm theo kiểu presigned URL: backend chỉ ký một URL có hạn cho đúng một key rồi đứng ngoài, trình duyệt PUT thẳng lên R2 nên file hàng trăm MB không đi qua FastAPI. Code và test xong rồi, em chưa gắn bucket thật vì Cloudflare bắt khai báo thẻ thanh toán. Thiếu cấu hình thì hệ thống trả 503 `STORAGE_NOT_CONFIGURED` và chỉ đúng chức năng đó hỏng, phần còn lại vẫn chạy.

**3. "Sao đổi ảnh đại diện lại báo lỗi về video?"**
> Dạ avatar dùng lại đúng luồng presigned URL của video nên chung mã lỗi; câu thông báo em viết cho ngữ cảnh video, đây là chỗ em sẽ tách riêng. Về bảo mật thì key upload luôn bị kiểm tra phải nằm trong `avatars/<id-của-chính-mình>` trước khi gắn vào tài khoản, nên không gắn được file của người khác.

**4. "Sao nút mua khóa học bấm không được?"**
> Dạ khóa có phí em để đúng một cái trong dữ liệu mẫu để chứng minh phần hiển thị giá và bộ lọc theo giá chạy được. Thanh toán VNPay/MoMo nằm ở giai đoạn sau theo đề cương. Ở backend em chặn hẳn: hàm ghi danh miễn phí từ chối khóa có giá bằng lỗi 409 `COURSE_NOT_FREE` chứ không lặng lẽ cho qua, vì dòng ghi danh đó chính là dòng mà thanh toán sẽ phải sinh ra.

**5. "Vì sao dùng Docker mà không cài trực tiếp?"**
> Dạ hệ thống cần Postgres kèm pgvector, Redis và ffmpeg chạy song song. Redis không có bản chính thức cho Windows, pgvector phải tự biên dịch. Docker gói cả ba vào một lệnh, và quan trọng hơn: máy em, máy CI và máy chủ chạy **cùng một image**, nên "chạy được trên máy em" không còn là câu bào chữa. Thầy có thể kiểm chứng bằng `docker compose -f infra/docker-compose.yml exec backend ffmpeg -version`.

**6. "Em deploy lên máy chủ thật chưa?"**
> Dạ chưa. Cấu hình deploy em viết xong và CI kiểm chứng được — `infra/docker-compose.prod.yml` chỉ mở cổng 80/443 qua nginx, không publish Postgres/Redis ra ngoài, không bind mount mã nguồn. Em chưa deploy vì chưa có VPS và tên miền. Luồng end-to-end thì em demo được ngay trên máy này, chỉ khác là đăng nhập bằng email thay vì Google.

**7. "Test có bao nhiêu, chạy thế nào?"**
> `cd backend` rồi `./.venv/Scripts/python.exe -m pytest -q`. Đo ngày 07/09/2026: **471 passed, 2 skipped** trong 4 phút 6 giây. Hai test bị skip là các test cần Postgres khi máy không có database — đó là chủ ý, còn trên CI thì không kết nối được là fail, để một service hỏng không bao giờ hiện ra thành build xanh. Trên CI, Postgres được dựng bằng đúng image mà máy dev dùng, migration chạy lên–xuống–lên trên database trắng, và seed chạy hai lần để chứng minh chạy lại không sinh thêm dữ liệu.

**8. "Điểm đánh giá trung bình tính lúc nào?"**
> Dạ tính lại ngay trong cùng transaction với lượt đánh giá, có `SELECT ... FOR UPDATE` trên dòng khóa học để hai người đánh giá cùng lúc không ghi đè nhau. Chi tiết ở [huong-dan-du-an.md](huong-dan-du-an.md) mục 6.
