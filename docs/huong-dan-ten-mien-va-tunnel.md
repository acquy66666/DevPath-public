# Tên miền thật + Cloudflare Tunnel: đưa DevPath lên mạng mà không cần máy chủ

Làm theo từng bước cho hai task Phase 6: **D0** (tên miền) và **D1** (named tunnel). Kết quả là `https://<tên-miền-của-bạn>` cố định, chứng chỉ thật, đăng nhập Google chạy được, chi phí 0đ. Stack production chạy trên chính máy dev này; Cloudflare đưa người xem vào qua một đường hầm do máy này mở ra ngoài, nên không cần mở cổng router hay có IP tĩnh.

Đây là đường **cho buổi trình bày với GVHD**. Gate của Phase 6 vẫn là máy chủ thật ([huong-dan-deploy-vps.md](huong-dan-deploy-vps.md)); tên miền ở D0 dùng lại được cho máy chủ đó.

| Bước | Ai làm | Mất bao lâu |
|---|---|---|
| D0.1–D0.3 — nhận tên miền (`.me` của Namecheap, hoặc name.com) | **bạn** (tài khoản GitHub, nhà đăng ký) | 10 phút |
| D0.4–D0.7 — chuyển DNS sang Cloudflare | **bạn** (tài khoản Cloudflare) | 10 phút làm, rồi chờ từ vài phút tới 24 giờ |
| D1.1–D1.3 — tạo tunnel, lấy token | **bạn** (dashboard Cloudflare) | 5 phút |
| D1.4–D1.7 — dựng stack, nạp dữ liệu, kiểm | Claude, trên máy này | 20–30 phút (build image) |

Những gì Claude **không** làm thay: tạo tài khoản, đăng nhập, nhập thông tin thanh toán. Những bước đó cần đúng tài khoản của bạn.

---

## D0 — Tên miền `.me` miễn phí và DNS trên Cloudflare

### D0.1. Nhận ưu đãi Namecheap trong GitHub Student Developer Pack

1. Mở https://education.github.com/pack, đăng nhập GitHub (pack đã có từ 08/09/2026).
2. Tìm ưu đãi **Namecheap**: *1 năm tên miền `.me` + 1 chứng chỉ SSL*.
3. Bấm vào ưu đãi. Nó đưa sang trang của Namecheap dành cho sinh viên (**nc.me**), đăng nhập bằng GitHub; ở một số phiên bản thì trang pack cho một mã (**View code**) để nhập lúc thanh toán ở Namecheap. Đi theo cách trang đó đưa ra.

> Nếu tới bước thanh toán mà Namecheap đòi **số thẻ** dù tổng là 0đ: dừng lại, đừng nhập, báo Claude. Theo tài liệu GitHub, ưu đãi này không cần trả tiền năm đầu.

#### Hoặc: name.com thay cho Namecheap

Student Pack còn một ưu đãi của **name.com**: một tên miền miễn phí năm đầu, kèm che thông tin chủ sở hữu và SSL. Trang pack ghi `.live`; trang hỗ trợ của name.com (cập nhật 06/2026) ghi "một trong các đuôi được áp dụng", nên đuôi nào được miễn phí thì xem lúc thanh toán. Mọi bước từ D0.4 trở đi giữ nguyên, vì Cloudflare không quan tâm tên miền mua ở đâu. Ba điểm khác:

- Bấm vào ưu đãi name.com **từ trang pack** trong lúc **chưa đăng nhập name.com**: mã giảm giá tự áp, không phải gõ.
- Điền thông tin liên hệ thật. ICANN bắt name.com gửi email xác minh, và không bấm xác minh thì tên miền có thể bị tạm khóa sau ít ngày.
- Chọn đuôi có trong danh sách miễn phí, ví dụ `devpath-<tên bạn>.live`. Đuôi nào cũng chạy được với tunnel và với đăng nhập Google.

### D0.2. Chọn tên

- Ngắn, dễ đọc lên khi trình bày, không dấu, không gạch dưới. Ví dụ: `devpath.me` (nếu còn), `devpath-<tên bạn>.me`, `<tên bạn>-devpath.me`.
- Tên miền gốc (không có `www`, không có tên miền con) là gọn nhất: tunnel và đăng nhập Google đều trỏ thẳng vào nó.
- Ghi lại tên đã chọn. Mọi bước sau gọi nó là `<tên-miền>`.

### D0.3. Hoàn tất đăng ký, và tắt gia hạn tự động

Thanh toán 0đ. Vào **Domain List → Manage** của tên miền vừa có, tắt **Auto-Renew**: năm thứ hai Namecheap tính tiền (các nguồn ước khoảng 20 USD). Hạn một năm là đủ cho khóa luận.

### D0.4. Thêm tên miền vào Cloudflare (gói Free)

1. Tạo tài khoản miễn phí ở https://dash.cloudflare.com/sign-up (email + mật khẩu), xác nhận email.
2. Trong dashboard: **Add a domain** (hoặc *Onboard a domain*), nhập `<tên-miền>`, chọn **Free**.
3. Cloudflare quét các bản ghi DNS có sẵn. **Xóa mọi bản ghi `A`/`AAAA`/`CNAME` của tên miền gốc (`@`) và của `www`.** Tên miền nhận qua nc.me được tạo sẵn 4 bản ghi `A` trỏ vào GitHub Pages (`185.199.108.153` … `185.199.111.153`, đo trên `devpath-01.me` 17/10/2026), có khi kèm `CNAME www → <tên>.github.io`. Để lại thì chúng giành tên miền gốc với tunnel. Tunnel sẽ tự tạo bản ghi của nó ở D1.
4. Cloudflare cho **hai nameserver**, dạng `ada.ns.cloudflare.com` và `bob.ns.cloudflare.com`. Giữ tab này mở.

### D0.5. Đổi nameserver sang Cloudflare

1. Namecheap → **Domain List** → **Manage** ở `<tên-miền>`.
2. Nếu **DNSSEC** đang bật (mục *Advanced DNS*), tắt trước. Tên miền mới mặc định là tắt.
3. Tab **Domain**, mục **NAMESERVERS**: đổi từ *Namecheap BasicDNS* sang **Custom DNS**, nhập đúng hai nameserver Cloudflare cho, bấm dấu ✓ xanh để lưu.

**Nếu mua ở name.com:** **My Domains** → bấm vào tên miền → **Manage Nameservers**, xóa các dòng `ns*.name.com` có sẵn, thêm hai nameserver của Cloudflare, rồi lưu. DNSSEC (mục *DNSSEC Management*) phải để trống, như với Namecheap.

### D0.6. Chờ Cloudflare kích hoạt

Quay lại Cloudflare, bấm **Check nameservers**. Trạng thái chuyển từ *Pending* sang **Active** trong vài phút, có khi tới 24–48 giờ; Cloudflare gửi email khi xong.

### D0.7. Kiểm và báo Claude

Trong PowerShell hoặc Git Bash:

```bash
nslookup -type=NS <tên-miền>
```

Ra hai dòng `*.ns.cloudflare.com` là xong D0. Gửi Claude **tên miền** (không cần gửi gì khác).

---

## D1 — Named tunnel tới stack production trên máy này

### D1.1. Tạo tunnel trong dashboard Cloudflare

1. Dashboard Cloudflare → **Networking → Tunnels** → **Create a tunnel**.
2. Loại connector: **Cloudflared**. Tên: `devpath-demo`. **Create Tunnel**.
3. Màn hình cài connector hiện một lệnh có dạng `cloudflared ... --token eyJ...`. Chọn môi trường **Docker** cho dễ đọc. **Chỉ chép chuỗi token** (phần dài bắt đầu bằng `eyJ` ngay sau `--token`) và **đừng chạy lệnh đó**: stack của dự án tự chạy cloudflared với token này. Bấm tiếp.

> Nếu dashboard bắt tạo "Zero Trust organization" hay chọn gói: chọn gói **Free**. Tài liệu Cloudflare ghi gói Free có một bước "billing" nhưng không trừ tiền. Nếu bị đòi số thẻ mà bạn không có hoặc không muốn nhập: dừng, báo Claude. Còn đường tạo tunnel bằng dòng lệnh `cloudflared` (đăng nhập qua trình duyệt, không qua màn đó).

### D1.2. Trỏ tên miền vào nginx của stack

Trong tunnel vừa tạo → tab **Routes** (bản cũ gọi là *Public Hostname*) → **Add route → Published application**:

| Ô | Giá trị |
|---|---|
| Subdomain | để trống |
| Domain | `<tên-miền>` |
| Path | để trống |
| Service URL | `https://nginx:443` |

Rồi mở **Additional application settings → TLS** → bật **No TLS Verify** → lưu.

Vì sao `https://nginx:443` và *No TLS Verify*: nginx của stack phục vụ HTTPS bằng một chứng chỉ tự ký, vì Let's Encrypt không gọi ngược được về máy dev. Đoạn cloudflared → nginx nằm trong mạng Docker; chứng chỉ người xem thấy là chứng chỉ thật của Cloudflare. Trỏ vào `http://nginx:80` thì nginx chuyển hướng sang https, rồi Cloudflare lại gửi về http, và trình duyệt quay vòng mãi.

Cloudflare tự tạo bản ghi DNS (CNAME tới `<id>.cfargotunnel.com`). Nếu nó báo trùng một bản ghi đã có của tên miền gốc thì xóa bản ghi cũ ở **DNS → Records** rồi thêm route lại.

### D1.3. Gửi token cho Claude, nhưng không qua chat

Token là **mật khẩu của tên miền**: ai có nó là phục vụ được `<tên-miền>` từ máy của họ. Đừng dán vào chat. Tự mở tệp `infra/.env.prod` (D1.4 sẽ tạo) và dán vào dòng `TUNNEL_TOKEN=`. Tệp này nằm trong `.gitignore`.

Nếu lỡ lộ: dashboard → tunnel → **Refresh token** (hoặc xóa tunnel, tạo lại).

### D1.4. Tệp `infra/.env.prod`

Claude tạo từ `infra/.env.prod.example`, với secret ngẫu nhiên. Những dòng đáng biết:

| Biến | Giá trị cho máy dev |
|---|---|
| `DOMAIN` | `<tên-miền>` |
| `TUNNEL_TOKEN` | **bạn dán** (D1.3) |
| `GEMINI_API_KEY` | chép từ `infra/.env` (dòng 77) — không có thì trợ giảng AI không trả lời |
| `BACKUP_ENABLED` | `false` — máy dev chưa có nơi lưu backup B2 (runbook VPS mục 2c); để `true` thì `deploy.sh` dừng |
| `DOCKER_GID` | `0` — socket của Docker Desktop là `root:root` (đo ở load test 02/10) |
| `GOOGLE_*` | để trống ở lần đầu; bật ở D1.7 |

Mật khẩu cho tài khoản admin và giảng viên do seed tạo thì **không** nằm trong tệp. Bạn nhập vào terminal ở D1.5 (`SEED_ADMIN_PASSWORD`, `SEED_INSTRUCTOR_PASSWORD`); seed từ chối chạy ở production nếu thiếu.

### D1.5. Dựng stack production

```bash
docker compose -f infra/docker-compose.yml stop
```

Dừng stack dev cho đỡ RAM (máy có 8 GB). Bật lại sau bằng `up -d`. Ảnh sandbox `devpath-sandbox-python:v1` đã có trên máy, nên không cần bước 2b của runbook VPS.

```bash
cd infra && SEED_ADMIN_PASSWORD='<mật khẩu admin>' SEED_INSTRUCTOR_PASSWORD='<mật khẩu giảng viên>' ./scripts/deploy.sh --seed
```

`deploy.sh` thấy `TUNNEL_TOKEN` trong `.env.prod` thì tự thêm `docker-compose.named-tunnel.yml`. Nó build image, migrate, seed, chờ healthy, kiểm API ↔ CSDL/Redis/bucket, chờ cloudflared kết nối. Cuối cùng nó hỏi `https://<tên-miền>/api/v1/health/ready` **từ bên ngoài, qua Cloudflare**; trả lời được là cả đường đi đã thông.

### D1.6. Dữ liệu demo

```bash
cd infra && ./scripts/seed-demo.sh
```

Nạp lời giảng, banner, đơn hàng 12 tháng, 70 ngày học (XP, chuỗi, bảng xếp hạng), mã giảm giá, chứng chỉ, rồi nhúng tài liệu khóa học cho trợ giảng AI và hệ gợi ý. Ngày tháng tính theo lúc chạy, nên **chạy lại vào hôm trước buổi trình bày** (cách gỡ ghi ở đầu script).

### D1.7. Đăng nhập Google trên tên miền thật

1. Google Cloud Console → **APIs & Services → Credentials** → OAuth client (loại *Web application*).
2. **Authorized JavaScript origins**: `https://<tên-miền>`. **Authorized redirect URIs**: `https://<tên-miền>/api/v1/auth/google/callback`.
3. Trong `infra/.env.prod`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_LOGIN_ENABLED=true` (biến cuối nằm trong bundle frontend, nên phải build lại).
4. Chạy lại `./scripts/deploy.sh` (không cần `--seed`).

---

## Hạn chế của đường này, nói thẳng

- **Máy tắt hay ngủ là site tắt.** Docker Desktop trên máy này chết khi máy ngủ. Trước buổi trình bày: tắt chế độ ngủ, cắm sạc, chuẩn bị mạng 4G dự phòng ([huong-dan-demo-truoc-giao-vien.md](huong-dan-demo-truoc-giao-vien.md), Phần 1).
- **Tải lên quá 100 MB bị từ chối** (HTTP 413): gói Free của Cloudflare chặn thân request trên 100 MB, kể cả qua tunnel. Demo bằng video seed, hoặc clip ngắn.
- **Không có backup** (`BACKUP_ENABLED=false`). Đây là bản demo, dữ liệu nạp lại được bằng D1.5–D1.6.
- Tài khoản người mua demo dùng chung mật khẩu ghi trong repo (`nguoimuaNN@sales.devpath.example` / `devpath-buyer`). Ổn cho một địa chỉ demo; không ổn cho người dùng thật.

## Khi có máy chủ thật (D2)

Giữ nguyên tên miền. Trên VPS, để **trống** `TUNNEL_TOKEN`, trỏ bản ghi `A` của `<tên-miền>` về IP máy chủ (chế độ *DNS only*, xem runbook mục 0d), và chạy [huong-dan-deploy-vps.md](huong-dan-deploy-vps.md) từ mục 0b. Ở máy dev: dừng cloudflared, xóa route của tunnel trong dashboard (hoặc xóa luôn tunnel), kẻo hai nơi cùng giành một tên miền.
