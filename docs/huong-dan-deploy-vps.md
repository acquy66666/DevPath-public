# Đưa DevPath lên VPS

Từng bước cho lần deploy đầu tiên, và cho mọi lần cập nhật sau đó. Viết để làm theo được lúc đang mệt, không phải để đọc hiểu.

Cấu hình trong `infra/` đã được **tổng duyệt trọn vẹn trên máy dev**: đúng `docker-compose.prod.yml`, đúng image target `production`, đúng nginx + TLS, chạy từ volume trắng tới trang web phục vụ được và luồng học viên đi hết. Xem `docs/report/assets/phase-2/README.md` để biết cái gì đã được chứng minh và cái gì chỉ máy chủ thật mới chứng minh được.

## Trả bao nhiêu tiền cho việc này: 0đ

Kế hoạch đã chốt **không thuê máy chủ** cho tới Phase 6 ([lý do ở 00-overview.md, nguyên tắc 4](plan/00-overview.md)). Hai chặng, cả hai đều miễn phí:

| Chặng | Dùng gì | Được gì | Không được gì |
|---|---|---|---|
| Phase 2–5 | **Cloudflare Quick Tunnel** trỏ vào stack chạy trên máy dev | URL `https://….trycloudflare.com` có chứng chỉ thật, không cần tài khoản, không cần tên miền | URL đổi sau mỗi lần khởi động, chỉ sống khi máy dev bật, giới hạn 200 request đồng thời. Đăng nhập Google không chạy được vì redirect URI phải cố định |
| Phase 6 | **GitHub Student Developer Pack**: $200 credit DigitalOcean + tên miền `.me` miễn phí 1 năm | Đúng mọi thứ trong tài liệu này, tên miền thật, chứng chỉ Let's Encrypt thật | Phải nộp hồ sơ sinh viên và chờ duyệt vài ngày — nộp sớm |

Cùng cái pack đó còn cho GitHub Pro, thứ đang chặn ruleset bảo vệ `main` từ Phase 1. Một lần đăng ký gỡ được ba nút thắt.

Tài liệu này viết cho chặng thứ hai. Mọi bước đều không phụ thuộc nhà cung cấp — DigitalOcean, VPS Việt Nam hay máy nào khác đều chạy y hệt, chỉ khác chỗ bấm nút tạo máy.

---

## 0. Cần có trước khi bắt đầu

| Thứ | Ghi chú |
|---|---|
| VPS Linux, 2 vCPU / 4 GB RAM trở lên | Cấu hình trong `.env.prod` (2 uvicorn worker, 1 luồng transcode) đặt theo mức này |
| Tên miền, bản ghi **A** đã trỏ về IP của VPS | Bắt buộc **trước** khi xin chứng chỉ: Let's Encrypt xác thực bằng cách gọi HTTP ngược về máy này |
| Cổng 80 và 443 mở | Cổng 80 không bỏ được — thử thách ACME luôn đi qua HTTP, kể cả khi gia hạn |
| Docker Engine + plugin Compose trên VPS | `curl -fsSL https://get.docker.com \| sh` |

Kiểm tra DNS đã lan xong chưa, làm từ máy bất kỳ:

```bash
dig +short devpath.example.com
```

Ra đúng IP của VPS thì mới đi tiếp. Sai bước này thì bước 3 sẽ thất bại và đốt một lượt trong hạn mức 5 lần/tuần của Let's Encrypt cho mỗi tên miền.

### 0b. Chọn máy chủ — bốn điều kiện không thương lượng

| Điều kiện | Vì sao dự án này cần |
|---|---|
| **Ảo hóa KVM**, không phải OpenVZ/LXC | Phase 3 chấm bài bằng cách chạy container Docker cách ly cho mã nguồn của người lạ. Trên VPS dạng container, Docker lồng trong đó hoặc không chạy, hoặc chạy mà không cách ly thật — tức là mất luôn điểm nhấn của khóa luận. Hỏi thẳng nhà cung cấp trước khi trả tiền |
| **4 GB RAM**, không phải 2 | `deploy.sh` build image **ngay trên máy chủ**, và `next build` một mình đã ngốn khoảng 2 GB. Máy 2 GB sẽ bị OOM killer giết giữa lúc build |
| **Ubuntu 24.04 LTS** | Mọi lệnh trong tài liệu này viết cho nó |
| Băng thông không cần lớn | Video HLS đi thẳng từ Cloudflare R2 tới trình duyệt, không qua VPS. Cái chạy trên VPS chỉ là HTML và JSON |

Đĩa 40–50 GB là thừa đủ. Không cần IPv6, không cần load balancer, không cần snapshot trả phí.

### 0c. Chuẩn bị máy chủ vừa mua

Đăng nhập lần đầu bằng `ssh root@<IP>` với mật khẩu nhà cung cấp gửi, rồi làm một lượt:

```bash
adduser devpath && usermod -aG sudo devpath
```

Chép khóa SSH của máy bạn lên (chạy **ở máy Windows**, không phải trên VPS):

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh devpath@<IP> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Chưa có khóa thì `ssh-keygen -t ed25519` trước. Sau đó tắt đăng nhập bằng mật khẩu — quét mật khẩu SSH là việc diễn ra liên tục trên mọi IP công khai:

```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && sudo systemctl restart ssh
```

> Mở **một cửa sổ SSH mới** kiểm tra vào được bằng khóa **trước khi** đóng cửa sổ đang mở. Sai file cấu hình mà đã thoát hết phiên thì chỉ còn console cứu hộ của nhà cung cấp.

Tường lửa — đúng ba cổng:

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw --force enable
```

Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker devpath
```

Đăng xuất, đăng nhập lại để nhóm `docker` có hiệu lực, rồi kiểm: `docker run --rm hello-world`.

Swap 2 GB — bảo hiểm cho lúc build, gần như không dùng tới lúc chạy:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Đặt múi giờ cho log dễ đọc khi đối chiếu với lúc demo:

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

### 0d. Nếu tên miền đặt ở Cloudflare

Để bản ghi A ở chế độ **DNS only** (đám mây xám), **không** bật proxy (đám mây cam) — ít nhất cho tới khi có chứng chỉ:

- Bật proxy thì chứng chỉ trình duyệt nhìn thấy là của Cloudflare, không phải của bạn; `init-tls.sh` vẫn có thể xin được nhưng thêm một tầng có thể hỏng ngay hôm bảo vệ.
- Chế độ SSL **Flexible** của Cloudflare cộng với header HSTS mà nginx đang gửi sẽ tạo vòng lặp chuyển hướng. Nếu sau này muốn bật proxy thì phải đặt SSL mode là **Full (strict)**.

---

## 1. Lấy mã nguồn về máy chủ

```bash
git clone https://github.com/<tài-khoản>/E-learning.git devpath
```

```bash
cd devpath/infra
```

Deploy chạy **đúng commit đang checkout**, không phải `origin/main` — `scripts/deploy.sh` cố tình không `git pull` (xem mục 6).

## 2. Điền biến môi trường

```bash
cp .env.prod.example .env.prod && chmod 600 .env.prod
```

Mở `.env.prod` và điền. Năm giá trị bắt buộc, phần còn lại có mặc định dùng được:

| Biến | Cách lấy |
|---|---|
| `DOMAIN` | Tên miền trần, không `https://`, không dấu `/` cuối |
| `ACME_EMAIL` | Email nhận cảnh báo khi gia hạn chứng chỉ hỏng |
| `POSTGRES_PASSWORD` | `openssl rand -base64 32` — sinh ra, đừng tự nghĩ |
| `JWT_SECRET` | `openssl rand -hex 32`. Backend từ chối khởi động ở production nếu còn giá trị mặc định của máy dev |
| `DOCKER_GID` | `getent group docker \| cut -d: -f3` trên chính máy chủ. Worker chấm bài chạy uid 10001 nên phải ở trong nhóm này mới mở được socket Docker |

`GOOGLE_*` và `R2_*` để trống được: đăng nhập Google và upload video sẽ trả 503, phần còn lại của trang chạy bình thường. Điền sau rồi deploy lại lúc nào cũng được — nhưng lưu ý `GOOGLE_LOGIN_ENABLED` **nướng vào bundle lúc build**, nên đổi nó là phải build lại image frontend, không phải chỉ restart. Riêng địa chỉ API thì không: trình duyệt gọi `/api` cùng origin với trang, nên image không mang tên miền nào và đổi tên miền không cần build lại.

Redirect URI đăng ký ở Google Cloud Console phải khớp từng ký tự:

```
https://<DOMAIN>/api/v1/auth/google/callback
```

## 2b. Build image sandbox chấm bài

Chỉ làm một lần cho mỗi máy chủ, và phải làm **trước** bài nộp đầu tiên:

```bash
docker build -t devpath-sandbox-python:v1 grader/images/python
```

Runner khởi động sandbox với `--pull never` — cố ý: giữa lúc chấm bài mà đi tải
image từ mạng là thứ không bao giờ nên xảy ra. Thiếu image thì mọi bài nộp nhận
lỗi hệ thống, thử lại 3 lần rồi dừng ở trạng thái `error` kèm lời nhắn cho học
viên, và log worker nói rõ thiếu image.

Kiểm tra worker chấm bài thấy được daemon:

```bash
docker compose -f docker-compose.prod.yml exec grading-worker docker version
```

Báo `permission denied` là `DOCKER_GID` sai — sửa trong `.env.prod` rồi
`docker compose -f docker-compose.prod.yml up -d grading-worker`.

## 3. Xin chứng chỉ lần đầu

```bash
./scripts/init-tls.sh
```

Script phá thế bí "nginx không khởi động được khi thiếu file chứng chỉ, mà certbot cần nginx đang chạy để trả lời thử thách": đặt một chứng chỉ tự ký sống 1 ngày, dựng nginx trên nó, gọi Let's Encrypt lấy chứng chỉ thật, rồi reload.

Muốn thử nháp trước cho chắc — hạn mức thoải mái, chứng chỉ trình duyệt không tin:

```bash
./scripts/init-tls.sh --staging
```

Chạy nháp xong thì **xóa chứng chỉ nháp đi** trước khi xin bản thật, nếu không certbot thấy đã có chứng chỉ và bỏ qua:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm --entrypoint sh certbot -c 'rm -rf /etc/letsencrypt/live /etc/letsencrypt/archive /etc/letsencrypt/renewal'
```

Từ đây gia hạn là tự động: service `certbot` dậy hai lần mỗi ngày, gia hạn thứ gì còn dưới 30 ngày, còn lại thì ngủ tiếp.

## 4. Deploy

```bash
./scripts/deploy.sh --seed
```

Lần đầu mất khoảng 5–10 phút, gần hết là build image. Script làm theo thứ tự: build → `alembic upgrade head` bằng một container dùng một lần trên image mới → khởi động → đợi **healthcheck** của từng service, không phải đợi `sleep`.

`--seed` chỉ dùng cho lần đầu. Seed idempotent nên chạy lại không hỏng gì, nhưng cũng chẳng để làm gì.

> **Đổi mật khẩu mặc định của tài khoản seed trước khi seed lên máy chủ công khai.** Seed sẽ in cảnh báo này ra màn hình:
>
> ```bash
> SEED_ADMIN_PASSWORD='...' SEED_INSTRUCTOR_PASSWORD='...' ./scripts/deploy.sh --seed
> ```
>
> Không đặt thì admin của trang có mật khẩu `devpath-admin`, và mật khẩu đó nằm trong repo.

## 5. Nghiệm thu

```bash
curl -s https://<DOMAIN>/api/v1/health
```

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

Bảy service, tất cả `healthy` (riêng `certbot` không có healthcheck nên cột trạng thái trống — đúng như vậy).

Kiểm bằng mắt, theo đúng thứ tự của gate Phase 2:

1. `https://<DOMAIN>` mở được, ổ khóa xanh, không cảnh báo chứng chỉ
2. `http://<DOMAIN>` tự nhảy sang HTTPS
3. `/khoa-hoc` hiện 4 khóa học đã seed
4. Đăng ký một tài khoản → enroll một khóa miễn phí → xem video vài giây → **tải lại trang** → player quay về đúng chỗ đang dở
5. `https://<DOMAIN>/api/docs` trả **404** — tài liệu API tự tắt khi `ENV=production`

Chụp màn hình các bước trên vào `docs/report/assets/phase-2/`; đó là bằng chứng cho chương 4 và chương 5 của báo cáo.

---

## 6. Cập nhật một bản mới

Xem trước cái gì sắp lên, rồi mới đưa lên:

```bash
git fetch origin && git log --oneline HEAD..origin/main
```

```bash
git merge --ff-only origin/main && ./scripts/deploy.sh
```

`deploy.sh` cố tình không tự `pull`: chọn commit nào lên production là một quyết định, và script tự lấy về sẽ giành mất quyền đó.

**Migration chạy trước khi container mới khởi động.** Đúng cho loại thay đổi dự án này hay làm (thêm bảng, thêm cột nullable). Migration **xóa hoặc đổi tên** thì phải đi hai nhịp: deploy code chịu được cả hai hình dạng schema trước, migrate sau.

## 7. Khi có sự cố

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
```

| Triệu chứng | Chỗ nhìn trước |
|---|---|
| Trang trả 502 | `backend` hoặc `frontend` chưa healthy — `ps` rồi `logs` của đúng service đó. nginx cố ý vẫn sống và trả 502 thay vì chết theo |
| Cảnh báo chứng chỉ | `init-tls.sh` dừng giữa chừng, chứng chỉ đang là bản tự ký. Kiểm tra DNS rồi chạy lại |
| 503 khi upload video | `R2_*` còn trống trong `.env.prod` |
| 503 ở nút đăng nhập Google | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` còn trống |
| Backend không khởi động | Xem log dòng đầu: thường là `JWT_SECRET` còn giá trị mặc định |
| Nút Google không hiện | `GOOGLE_LOGIN_ENABLED` nướng vào bundle lúc build — phải build lại frontend, restart không đủ |

Quay về bản trước:

```bash
git checkout <commit-cũ> && ./scripts/deploy.sh
```

Chỉ đúng khi bản mới không kèm migration phá vỡ tương thích. Có migration như vậy thì phải khôi phục cả database, và script backup/restore là việc của Phase 6.

## 8. Những thứ cố ý không có ở đây

- **Backup định kỳ** (`pg_dump` → R2) — Phase 6.
- **Giám sát và cảnh báo** — Phase 6. Hiện tại `restart: unless-stopped` cộng healthcheck đã lo được phần lớn: container chết thì Docker dựng lại, VPS reboot thì cả stack tự lên.
- **CI tự deploy** — cố ý không làm. Với một khóa luận, việc bấm deploy bằng tay là tính năng, không phải thiếu sót.
