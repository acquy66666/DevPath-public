# Hướng dẫn tự chạy và trình bày DevPath trước giáo viên

Tài liệu này phục vụ đúng một việc: **đứng trước giáo viên và cho hệ thống chạy mà không vấp**. Nó gồm chuỗi lệnh kèm giải thích, kịch bản bấm chuột theo thứ tự, danh sách nút không được bấm, và câu trả lời cho những câu chắc chắn bị hỏi.

**Từ 18/10/2026 buổi trình bày chạy trên tên miền thật `https://devpath-01.me`**, không còn trên `localhost`. Đó là **stack production** (`infra/docker-compose.prod.yml`, project compose `devpath-demo`) chạy trên chính máy này. Cloudflare đưa người xem vào qua named tunnel, nên giáo viên mở được từ máy hay điện thoại của mình. Cách dựng từ đầu nằm ở [huong-dan-ten-mien-va-tunnel.md](huong-dan-ten-mien-va-tunnel.md). Tài liệu này chỉ lo phần vận hành và trình bày. Lần chạy trọn luồng vàng trên tên miền thật để chốt mốc này: [gvhd-milestone.txt](report/assets/phase-6/gvhd-milestone.txt).

Tài liệu bổ trợ:

- [huong-dan-chay-va-docker.md](huong-dan-chay-va-docker.md): cấu trúc file và vai trò của Docker
- [huong-dan-du-an.md](huong-dan-du-an.md): sửa từng phần giao diện, luồng một request

Mọi lệnh dưới đây chạy trong **Git Bash** tại `D:\Desktop\E-learning\infra`, trừ khi ghi khác. Để gõ ngắn, đặt một biến cho lệnh compose của stack demo (mỗi lần mở terminal mới phải đặt lại):

```bash
DEMO="docker compose -f docker-compose.prod.yml -f docker-compose.named-tunnel.yml --env-file .env.prod"
```

`.env.prod` có `COMPOSE_PROJECT_NAME=devpath-demo`, nên lệnh này nhắm đúng stack demo chứ không đụng stack dev.

---

## Phần 1 — Hôm trước ngày trình bày

Làm hết, đừng để tới sáng hôm sau.

- [ ] **Diễn thử trọn kịch bản Phần 3 một lần, trên `https://devpath-01.me`, từ một máy khác hoặc điện thoại (mạng 4G).** Đây là việc quan trọng nhất. Lỗi lộ ra lúc diễn thử thì sửa được; lộ ra trước mặt thầy thì không.
- [ ] **Làm mới dữ liệu demo.** Dữ liệu học tập "già" đi theo ngày: nạp từ hơn một ngày trước thì chuỗi ngày học về 0 và bảng xếp hạng tuần trống. Gỡ rồi nạp lại:

  ```bash
  $DEMO exec backend python -m scripts.seed_study --purge
  ```
  ```bash
  $DEMO exec backend python -m scripts.seed_sales --purge
  ```
  ```bash
  ./scripts/seed-demo.sh
  ```

  `seed-demo.sh` nạp lời giảng, banner, đơn hàng 12 tháng, 70 ngày học, mã giảm giá, chứng chỉ, rồi nhúng tài liệu cho trợ giảng AI. Chạy lại nhiều lần không sinh trùng.
- [ ] **Tắt chế độ ngủ.** Settings → Power & sleep → cả "Screen" lẫn "Sleep" đặt **Never**, cắm sạc, không gập máy. Máy ngủ là Docker chết, site trả lỗi 530, và phải chạy script mới dậy lại được.
- [ ] **Kiểm tra mạng.** Máy này là máy chủ: mất mạng là cả site tắt với người xem, không chỉ phần video. Video của 4 khóa mẫu còn lấy từ `test-streams.mux.dev`. Chuẩn bị điện thoại phát 4G.
- [ ] **Đừng chạy `./scripts/deploy.sh` trong 24 giờ trước buổi trình bày.** Nó build lại mọi image. Lần deploy đầu ngày 18/10, Docker Desktop chết giữa lúc build và site trả 530. Cũng đừng `npm ci`, đừng build lại image sandbox.
- [ ] **Đăng nhập Google:** OAuth client đang ở chế độ **Testing**, nên chỉ những email nằm trong *Test users* mới đăng nhập được. Muốn thầy đăng nhập bằng Google của thầy thì làm một trong hai: thêm email của thầy vào *Test users*, hoặc bấm **Publish app** ([huong-dan-ten-mien-va-tunnel.md](huong-dan-ten-mien-va-tunnel.md) mục D1.7).
- [ ] **Tắt RUM của Cloudflare** (mục D1.8 cùng tài liệu), nếu chưa tắt. Không tắt thì site vẫn chạy bình thường, nhưng ai mở DevTools sẽ thấy mỗi trang có một dòng đỏ: Content-Security-Policy chặn script phân tích mà Cloudflare tự chèn vào. Kiểm bằng lệnh `curl` có `Accept: text/html` ở D1.8; `curl` trơn luôn ra 0 nên không nói lên điều gì.
- [ ] **Chuẩn bị tài khoản:** mở `infra/.env.seed-demo` để có mật khẩu admin và giảng viên (Phần 3). Đăng nhập thử từng tài khoản một lần.

---

## Phần 2 — 15 phút trước giờ

Sau mỗi bước có cách kiểm chứng. **Đừng sang bước sau khi bước trước chưa đạt.**

### Bước 1 — Docker đang chạy

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Admin\start-docker.ps1
```

Chỉ cần khi Docker không chạy (máy vừa khởi động, vừa ngủ dậy). Script đẩy thư mục socket cũ của Docker sang một bên rồi mới khởi động daemon; lý do ở [huong-dan-chay-va-docker.md](huong-dan-chay-va-docker.md) mục 3.10. **Tuyệt đối không bấm icon Docker Desktop.** Lần đầu có thể treo; chạy lại lần hai.

✅ Đạt khi in ra `DOCKER DA SAN SANG`.

### Bước 2 — Stack demo đang chạy, stack dev đang dừng

```bash
docker compose -f docker-compose.yml stop
```

Dừng stack dev cho đỡ RAM (máy 8 GB). Nó đang dừng rồi thì lệnh này không làm gì.

```bash
$DEMO up -d --no-build
```

Các service chạy lâu của stack demo đều có `restart: unless-stopped`, nên sau khi Docker sống lại chúng thường tự lên. Lệnh này để chắc ăn: thiếu service nào thì nó dựng lại từ image có sẵn. `--no-build` cấm build lại.

```bash
$DEMO ps
```

✅ Đạt khi 13 dòng đều `Up`, và mọi dòng có healthcheck đều `(healthy)`. `beat`, `certbot` và `cloudflared` không có healthcheck nên chỉ ghi `Up`. Còn `(health: starting)` thì chờ thêm 30 giây.

### Bước 3 — Chỉ có một connector cloudflared

```bash
docker ps --format '{{.Image}}  {{.Names}}' | grep cloudflared
```

✅ Đạt khi in **đúng một dòng**: `cloudflare/cloudflared:2026.9.1  devpath-demo-cloudflared-1`. Thấy thêm một container image `cloudflare/cloudflared:latest` (sinh ra khi lỡ chạy lệnh mẫu của dashboard) thì `docker stop` + `docker rm` nó ngay. Cloudflare chia request cho mọi connector, và connector lạc này không nằm trong mạng của stack: đo 18/10, 15/15 request rơi vào nó đều thành 502.

### Bước 4 — Hỏi từ bên ngoài, qua Cloudflare

```bash
curl -s https://devpath-01.me/api/v1/health/ready
```

✅ Đạt khi có `"status":"ready"`. Request này đi đúng đường của người xem: Cloudflare → tunnel → nginx → backend → CSDL + Redis.

```bash
curl -s "https://devpath-01.me/api/v1/courses?page_size=1"
```

✅ Đạt khi có `"total":4`.

### Bước 5 — Mở sẵn các tab

| Tab | Địa chỉ | Dùng lúc nào |
|---|---|---|
| 1 | `https://devpath-01.me` | Toàn bộ kịch bản, vai học viên |
| 2 | `https://devpath-01.me/dang-nhap` trong **cửa sổ ẩn danh** | Giảng viên, rồi admin (Chặng 10–11). Mỗi cửa sổ giữ một phiên riêng |
| 3 | Git Bash ở `infra/`, đã đặt `DEMO` | Chặng 5: lệnh IPN giả lập |

---

## Phần 3 — Kịch bản trình bày, 12 chặng (~30 phút)

Tài khoản:

| Email | Mật khẩu | Vai trò | Dùng ở |
|---|---|---|---|
| tự đăng ký tại chỗ | tự đặt | học viên | Chặng 4–8 |
| tài khoản Google của bạn (nằm trong *Test users*) | — | học viên | Chặng 4, 9 |
| `nguoimua08@sales.devpath.example` | `devpath-buyer` | học viên có 70 ngày lịch sử | Chặng 9: XP, chuỗi ngày, chứng chỉ |
| `khoa.tran@devpath.example` | `SEED_INSTRUCTOR_PASSWORD` trong `infra/.env.seed-demo` | giảng viên | Chặng 10 |
| `admin@devpath.example` | `SEED_ADMIN_PASSWORD` trong `infra/.env.seed-demo` | admin | Chặng 11 |

Mật khẩu admin và giảng viên của stack demo là chuỗi ngẫu nhiên, không nằm trong repo. Mật khẩu `devpath-buyer` thì nằm trong repo, nên tài khoản người mua chỉ dùng cho demo.

**Chặng 1 · Trang chủ trên tên miền thật (30 giây).** Mở `https://devpath-01.me`. Chỉ vào ổ khóa: chứng chỉ thật của Cloudflare, mở được từ mọi máy. Banner, hàng "Khóa học mới". Câu nói kèm: đây là stack production, cùng file compose sẽ chạy trên VPS, đi vào qua Cloudflare named tunnel nên chi phí 0đ.

**Chặng 2 · Tìm kiếm tiếng Việt (1 phút).** Ở `/khoa-hoc`, gõ **`lap trinh`** không dấu → vẫn ra khóa có dấu "Lập trình". Dưới nền là `to_tsvector('simple', unaccent(...))`, trọng số A/B/C cho tiêu đề / phụ đề / mô tả, xếp hạng bằng `ts_rank`. Chọn Giá = "Miễn phí" thì còn 3/4 khóa. Mỗi trạng thái lọc là một URL chia sẻ được.

**Chặng 3 · Trang chi tiết (1 phút).** Mở khóa "Cấu trúc dữ liệu & giải thuật với Python" (499.000 ₫). Chuột phải → View Source: nội dung nằm sẵn trong HTML (SSR), có canonical và Open Graph trỏ `https://devpath-01.me`. Cuộn xuống khối **"Khóa học tương tự"**: đó là phần content-based của hệ gợi ý (embedding Gemini, cosine trên pgvector).

**Chặng 4 · Đăng ký, hoặc đăng nhập bằng Google (1 phút).** `/dang-ky`: họ tên, email, mật khẩu ≥ 8 ký tự. Xong thì tự đăng nhập. Nói kèm: bcrypt; access token sống 15 phút trong bộ nhớ; refresh token nằm trong cookie HttpOnly và xoay vòng mỗi lần dùng. Có thì diễn thêm **"Đăng nhập bằng Google"** ở `/dang-nhap` bằng tài khoản Google trong *Test users*: redirect URI cố định `https://devpath-01.me/api/v1/auth/google/callback`, chống CSRF bằng cookie `state`. Đây là thứ mà URL tunnel ngẫu nhiên trước kia không làm được.

**Chặng 5 · Mua khóa có phí qua VNPay (3 phút).** Vẫn tài khoản vừa đăng ký:

1. Trang khóa 499.000 ₫ → **"Thêm vào giỏ hàng"** → biểu tượng giỏ trên header nhảy số → **"Xem giỏ hàng"**.
2. Nhập mã **`CHAOMUNG50`** → tổng còn 249.500 ₫. Có thể thử `HETHAN` hoặc `HETLUOT` để thấy hai lời từ chối khác nhau.
3. **"Thanh toán qua VNPay"** → trình duyệt sang **trang sandbox thật của VNPay** (`sandbox.vnpayment.vn`), với URL do server ký HMAC-SHA512. VNPay nhận URL đó, tức là mã merchant hợp lệ và chữ ký khớp. **Không nhập thẻ** (Phần 4).
4. Lấy mã đơn ở tab 3. Thanh địa chỉ không có mã: VNPay đổi ngay URL đã ký thành một `token` của họ (đo 18/10). Đơn vừa tạo là đơn chờ thanh toán mới nhất:

   ```bash
   $DEMO exec postgres psql -U devpath -Atc "select code from orders where status = 'pending' order by created_at desc limit 1"
   ```

   Rồi gửi IPN cho mã đó (dạng `DP261018HQARRC`):

   ```bash
   $DEMO exec backend python -m scripts.simulate_vnpay_ipn DP...
   ```

   Lệnh này ký callback server-to-server (IPN) bằng đúng secret mà backend dùng, rồi gửi vào `/api/v1/payments/vnpay/ipn`. Phải thấy `IPN trả  : 200 {"RspCode":"00","Message":"Confirm Success"}` và dòng cuối ghi `paid`.
5. Ở tab 1, mở `https://devpath-01.me/thanh-toan/ket-qua?vnp_TxnRef=DP…` → **"Thanh toán thành công"**, có mã đơn, mã giao dịch VNPay, dòng giảm giá CHAOMUNG50 → "Vào học ngay". Trên trang VNPay **đừng bấm "Quay lại"**: nó mở hộp "Hủy thanh toán"; bấm "Đóng" là thoát ra được.

Câu nói kèm: **chỉ IPN được quyền nói là đã trả tiền**. Trang kết quả chỉ lấy mã đơn rồi hỏi lại API, vì tham số trình duyệt mang về, người dùng tự sửa được. Thứ tự kiểm: chữ ký → đơn → số tiền → trạng thái → mã phản hồi. Ghi danh, trừ lượt mã giảm giá và bỏ khỏi giỏ nằm trong cùng một transaction. VNPay gửi lại IPN thì lần sau trả `02` và không đổi gì. Vì sao giả lập IPN: xem Phần 6, câu 3.

**Chặng 6 · Học, lưu tiến độ (3 phút).** Ở trang học:

1. Bấm Play, đổi tốc độ 1.5×, xem tới khoảng giây 40 rồi **Pause**.
2. **F5** → video tua đúng về chỗ cũ.
3. Gõ một ghi chú → nó hiện kèm nhãn `mm:ss`; tua đi chỗ khác rồi bấm nhãn → video nhảy về đúng giây đó.
4. "Đánh dấu hoàn thành" → thanh tiến độ nhích lên.

Nhịp tim 10 giây một lần, cộng với lưu khi pause, khi chuyển tab và khi rời trang, nên vị trí không bao giờ mất quá 10 giây.

**Chặng 7 · Trợ giảng AI (2 phút).** Ghi danh khóa **Python cơ bản** (miễn phí) → trang học → tab **"Trợ giảng AI"**. Hỏi:

- *"Dòng if \_\_name\_\_ == "\_\_main\_\_": dùng để làm gì?"* → chữ hiện dần (SSE, qua cả Cloudflare lẫn nginx), có số `[1]`. Bấm số đó thì bài nguồn mở ngay bên cạnh.
- *"Thủ đô của nước Úc là thành phố nào?"* → trợ giảng từ chối, vì chỉ trả lời từ tài liệu của khóa.

Câu nói kèm: RAG trên pgvector. Truy vấn top-k lọc khóa đã xuất bản và người hỏi đã ghi danh **ngay trong câu SQL**. Đo trên bộ 20 câu × 3 lần: 58/60 đạt, bài đúng xếp hạng 1 ở 42/42, từ chối sạch 18/18. Mỗi người chỉ được hỏi một câu mỗi 3 giây.

**Chặng 8 · Chấm code tự động (3 phút).** Khóa Python, chương "Rẽ nhánh và vòng lặp", bài **"Bài tập: đếm số chẵn"**. Dán lời giải *cố tình sai*:

```python
n = int(input())
a = list(map(int, input().split()))
print(sum(1 for x in a if x % 2 == 0 and x > 0))
```

1. **"Chạy thử"** → qua cả 2 test mẫu (chạy thử chỉ chấm test mẫu, không tính vào lịch sử).
2. **"Nộp bài"** → từng test đổi màu **theo thời gian thực** (WebSocket, đi qua Cloudflare). Kết quả: **Sai kết quả, 50/100**. Qua 2 test mẫu và 2 trong 4 test **ẩn**, trượt 2 test ẩn còn lại (dãy có số âm hoặc số 0). Test ẩn chỉ báo đúng/sai, không lộ đầu vào.
3. Chờ ít nhất 10 giây (cooldown), sửa thành `if x % 2 == 0`, nộp lại → **AC**, bài học tự đánh dấu hoàn thành, cộng 10 XP của bài học và 30 XP thưởng AC.

Câu nói kèm: mỗi test chạy trong một container dùng một lần: không mạng, không root, filesystem chỉ đọc, giới hạn CPU/RAM/số tiến trình, timeout hai lớp. Worker chấm bài không cầm Docker socket mà đi qua một proxy chỉ cho tạo đúng một kiểu sandbox. Bảy kiểu tấn công đều bị chặn, có test trong CI.

**Chặng 9 · XP, chuỗi ngày, bảng xếp hạng, chứng chỉ (2 phút).** Đăng xuất, đăng nhập `nguoimua08@sales.devpath.example` / `devpath-buyer`:

- `/khoa-hoc-cua-toi`: khối thành tích ở đầu trang (XP, chuỗi ngày học). XP là sổ cái chỉ ghi thêm; chuỗi ngày tính theo ngày Việt Nam.
- `/bang-xep-hang`: tuần / tháng / mọi thời gian, giữ trong Redis sorted set, dựng lại được từ sổ cái.
- Mở khóa "Xây dựng REST API với FastAPI" hoặc "Cấu trúc dữ liệu & giải thuật" (tài khoản này đã hoàn thành cả hai) → **"Xem chứng chỉ"** → `/cert/<mã>`: trang **công khai**, ai có mã cũng xác thực được. Có QR và tệp PDF.

Hoặc dùng tài khoản Google đã diễn thử: tài khoản đó đã có chứng chỉ khóa Python từ lần chạy chốt mốc.

**Chặng 10 · Khu giảng viên (3 phút).** Ở cửa sổ ẩn danh, đăng nhập `khoa.tran@devpath.example`:

- `/giang-day/thong-ke`: doanh thu, học viên mới, tỉ lệ hoàn thành theo 7 ngày / 30 ngày / 90 ngày / 12 tháng, có "Xem dạng bảng". Đơn ở Chặng 5 đã nằm trong số liệu.
- Mở một khóa → mục lục: **kéo một bài sang chương khác** bằng tay nắm 6 chấm. Thứ tự lưu ngay, không có nút Lưu. Có bản bàn phím: Space, mũi tên, Space.
- `/giang-day/hoi-dap`: hộp thư câu hỏi của học viên.
- Muốn khoe AI sinh quiz: thêm bài loại *Quiz* → "Sinh câu hỏi bằng AI" từ nội dung bài → giảng viên phải duyệt từng câu trước khi xuất bản. Bước này gọi Gemini và tạo dữ liệu thật trên stack demo.

**Chặng 11 · Khu quản trị (2 phút).** Đăng xuất, đăng nhập `admin@devpath.example` (cùng cửa sổ ẩn danh):

- `/quan-tri`: tổng quan toàn sàn (doanh thu, người dùng hoạt động trong ngày, khóa hot).
- `/quan-tri/khoa-hoc`: hàng đợi duyệt. Khóa giảng viên gửi lên dừng ở "chờ duyệt"; admin duyệt mới xuất bản, và việc nạp tài liệu cho trợ giảng chạy sau khi duyệt.
- `/quan-tri/bao-cao`, `/nguoi-dung`, `/ma-giam-gia`, `/banner`: kiểm duyệt nội dung, khóa tài khoản (thu hồi mọi phiên), mã giảm giá, banner trang chủ.

**Chặng 12 · Hạ tầng và bảo mật (2 phút, nói là chính).** Có thể mở DevTools → Network → một trang bất kỳ để chỉ header `content-security-policy` (enforce từ 18/10) và `strict-transport-security`. Nói:

- Một file compose production, chạy y hệt trên VPS. Ở đây có thêm overlay tunnel; nginx lấy IP thật từ `CF-Connecting-IP`, chỉ tin đúng địa chỉ của cloudflared.
- Monitor, backup CSDL mỗi đêm, readiness endpoint, xoay vòng log. Mỗi thứ có diễn tập ghi trong `docs/report/assets/phase-6/`.
- Tài liệu API (`/docs`) **cố ý tắt ở production**. Muốn xem thì mở trên stack dev.

---

## Phần 4 — Những nút không được bấm

| Thứ | Chuyện gì xảy ra | Nói gì nếu bị hỏi |
|---|---|---|
| Nhập thẻ test / quét QR trên trang VNPay | VNPay chưa khai IPN URL của dự án, nên tiền "trả" xong không ai báo về. Đơn đứng ở *chờ thanh toán*; trang kết quả hỏi lại suốt 90 giây rồi thôi, vẫn báo đang chờ | Phần 6, câu 3 |
| Tải lên video > 100 MB | Bị 413 ngay ở Cloudflare (gói Free chặn thân request > 100 MB, đo thật 18/10) | Đường tunnel có giới hạn này; VPS thì không. Demo upload bằng clip vài MB |
| Nộp code hai lần cách nhau < 10 giây, hỏi trợ giảng hai câu cách nhau < 3 giây | 429, kèm thông báo chờ | Đó là rate limit có chủ đích, chống spam hàng đợi và quota Gemini |
| Cả phòng cùng đăng ký trong một giờ | Cả phòng chung một IP công khai (NAT), mà mỗi IP chỉ được 50 lượt đăng ký/giờ; người thứ 51 nhận 429 | Giới hạn theo IP thật của người dùng (đã sửa sau tunnel); NAT thì không tách được |
| Đăng nhập Google bằng email ngoài *Test users* | Google chặn ("Access blocked"), nếu app chưa Publish | Phần 1 |
| `./scripts/deploy.sh` ngay trước giờ | Build lại mọi image, có lần làm Docker Desktop chết giữa chừng | Không chạy |

---

## Phần 5 — Sự cố giữa buổi

**1. Site báo lỗi 530 / 1033 của Cloudflare.** Cloudflare không thấy connector nào, tức máy ngủ, Docker chết hoặc cloudflared dừng. Làm lại Phần 2 từ Bước 1. Cloudflared khởi động lại thì site trở lại sau khoảng 3 giây (đo 18/10). Dữ liệu không mất, vì nằm trong volume của project `devpath-demo`.

**2. Site báo 502.** Thường là connector thừa (Phần 2, Bước 3). Không phải thì xem `$DEMO ps`: `nginx` hoặc `frontend` có đang `(healthy)` không.

**3. Video không phát.** Mất mạng tới `test-streams.mux.dev`. Bật 4G. Mọi phần khác vẫn chạy.

**4. Trợ giảng AI báo lỗi.** Gemini quá tải hoặc hết quota tạm thời. Adapter tự thử lại khi chưa có chữ nào; nếu đã ra chữ rồi mới hỏng thì báo lỗi và **không lưu** câu trả lời dở. Chờ một phút rồi hỏi lại.

**5. Nộp bài chờ lâu.** Hàng đợi chấm bài chạy 2 bài cùng lúc, mỗi test là một container riêng. Một người nộp mất khoảng 3 giây; cả lớp 20 người nộp cùng lúc thì người cuối chờ 35–50 giây (đo ở load test 02/10).

**Nếu bị hỏi câu không trả lời được:** nói "chỗ này em phải mở code xem lại" rồi mở ra tìm thật. Tìm được câu trả lời trong repo của mình chính là thứ đang được đánh giá.

---

## Phần 6 — Câu hỏi chắc chắn bị hỏi

**1. "Đăng nhập Google có thật không, hay chỉ là nút?"**
> Dạ thật. Redirect URI là `https://devpath-01.me/api/v1/auth/google/callback`, cố định nhờ tên miền thật. `state` chống CSRF nằm trong cookie Secure/HttpOnly. Tài khoản tạo bằng Google không có mật khẩu. Liên kết Google vào một tài khoản email **chưa xác thực** thì hệ thống xóa mật khẩu cũ và thu hồi mọi phiên trước, để không ai chiếm trước được tài khoản của người khác. Ứng dụng đang ở chế độ Testing của Google, nên chỉ email em khai báo mới đăng nhập được.

**2. "Em thử upload một video xem."**
> Dạ luồng upload dùng presigned URL: backend ký một URL có hạn cho đúng một key, **ký luôn cả kích thước và loại file đã khai**, rồi đứng ngoài. Trình duyệt PUT thẳng lên object storage. File khác kích thước một byte là storage trả 403. Storage là RustFS, server S3 tự host, cùng origin với trang. Đổi sang Cloudflare R2 chỉ là đổi biến môi trường. Số vé xin URL còn bị giới hạn theo tài khoản, để không ai làm đầy đĩa. Qua tunnel này thì Cloudflare chặn file trên 100 MB, nên em demo bằng clip nhỏ.

**3. "Sao không thanh toán thật luôn?"**
> Dạ toàn bộ phần của em đã chạy thật: giỏ hàng, mã giảm giá, đơn hàng, URL thanh toán ký HMAC-SHA512 mà sandbox VNPay đã nhận, và xử lý IPN với đủ các nhánh lỗi, có test. Bước còn lại là VNPay phải khai IPN URL của em vào hệ thống của họ; cổng merchant không có ô tự khai, em đã gửi mail cho kỹ thuật VNPay. Vì vậy em ký IPN bằng đúng secret mà server dùng và gửi vào đúng endpoint đó. Server không phân biệt được, nên mọi kiểm tra vẫn chạy thật.

**4. "Em deploy lên máy chủ thật chưa?"**
> Dạ đây là bản production thật: cùng file `docker-compose.prod.yml`, nginx có TLS, Content-Security-Policy enforce, backup, monitor. Chỉ khác là nó chạy trên máy em, và Cloudflare đưa người xem vào qua tunnel thay cho IP của VPS. Máy chủ Azure for Students là bước cuối của giai đoạn này; lúc đó em giữ nguyên tên miền và chỉ đổi DNS.

**5. "Test có bao nhiêu?"**
> CI chạy 2.256 ca tự động (đo 13/10): backend 1.873 ca trên Postgres và Redis thật, 0 skip; grader trên Docker thật, gồm 7 kiểu tấn công sandbox; và E2E Playwright đi trọn luồng đăng ký → mua → học → nộp code → chứng chỉ trên cả stack. Luồng E2E đó em cũng chạy trên chính `https://devpath-01.me`, và nó đỏ nếu trình duyệt báo bất kỳ vi phạm Content-Security-Policy nào của site. Mỗi route API còn có một luật phân quyền trong test; thêm route mà quên luật là test đỏ. Coverage backend 94,5 %.

**6. "Hệ gợi ý đo thế nào?"**
> Dạ hệ lai giữa collaborative filtering item-based và content-based (embedding), trộn bằng Reciprocal Rank Fusion. Em đo bằng cách cắt dữ liệu theo học viên, 5 fold: recall@5 0,884 với người dùng cũ. Với khóa vừa xuất bản chưa có tương tác (cold-start), CF đơn thuần không gợi ý được khóa đó, còn hệ lai đạt recall@5 0,626.

**7. "Vì sao dùng Docker mà không cài trực tiếp?"**
> Dạ hệ thống cần Postgres + pgvector, Redis, ffmpeg, RustFS, và sandbox chấm bài phải là container. Docker gói tất cả vào một lệnh. Quan trọng hơn: máy em, máy CI và máy chủ chạy **cùng một image**, nên "chạy được trên máy em" không còn là câu bào chữa.

**8. "Điểm đánh giá trung bình tính lúc nào?"**
> Dạ tính lại ngay trong cùng transaction với lượt đánh giá, có `SELECT ... FOR UPDATE` trên dòng khóa học, để hai người đánh giá cùng lúc không ghi đè nhau. Chi tiết ở [huong-dan-du-an.md](huong-dan-du-an.md) mục 6.
