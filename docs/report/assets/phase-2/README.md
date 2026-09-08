# Bằng chứng Phase 2 — Core Platform

## Tổng duyệt stack production (07/09/2026)

Chạy **đúng** `infra/docker-compose.prod.yml` trên máy dev, không phải một bản rút gọn: image build từ target `production`, không bind mount mã nguồn, chỉ nginx mở cổng, TLS bật. Khác máy chủ thật đúng hai điểm — `DOMAIN=localhost` và chứng chỉ tự ký thay cho Let's Encrypt.

Mục đích: mọi lỗi cấu hình lộ ra ở đây thay vì lộ ra trên VPS lúc đang vội. Nó đã bắt được một lỗi thật, xem mục "Lỗi phát hiện được" bên dưới.

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `prod-stack-ps.txt` | 7 service healthy; chính sách restart; danh sách cổng publish; đếm bind mount; kích thước image production | 4 — Xây dựng hệ thống |
| `nginx-tls-headers.txt` | Chuyển hướng 80 → 443, 6 header bảo mật, `/healthz`, tài liệu API trả 404 ở production | 4 và 6 — Bảo mật |
| `luong-hoc-vien-qua-https.txt` | Đăng ký → tìm khóa học → enroll → lưu tiến độ → đọc lại đúng vị trí, tất cả qua nginx + HTTPS | 4 và 5 — Kiểm thử |
| `bundle-khong-ten-mien.txt` | Bundle production không chứa địa chỉ backend nào; cùng một image phục vụ hai host khác nhau; đối chứng với bundle dev vẫn gọi tuyệt đối | 4 — Xây dựng hệ thống |
| `luong-gate-qua-tunnel.txt` | Đúng luồng gate Phase 2 chạy qua URL công khai, xác thực TLS bật | 4 và 5 — Kiểm thử |
| `phase2-01-trang-chu-tunnel.png` | Trang chủ trên URL công khai | 4 |
| `phase2-02-danh-sach-khoa-hoc-tunnel.png` | Danh sách khóa học có tìm kiếm và bộ lọc | 4 |
| `phase2-03-khoa-hoc-cua-toi-tunnel.png` | "Khóa học của tôi" sau khi enroll | 4 |
| `phase2-04-player-tunnel.png` | **Player quay lại đúng 5:12 = 312 giây đã lưu** — bằng chứng của yêu cầu "thoát rồi vào lại đúng vị trí cũ" | 4 và 5 |
| `phase2-05-dang-ky-tunnel.png` | Form đăng ký | 4 |
| `phase2-06-khu-giang-vien-tunnel.png` | Khu giảng viên, đăng nhập bằng tài khoản seed | 4 |
| `phase2-07-tao-khoa-hoc-tunnel.png` | Form tạo khóa học mới | 4 |

### Đã chứng minh được

- `scripts/deploy.sh` chạy trọn từ volume trắng: build → 8 migration Alembic → 7 service healthy → exit 0. Chạy **hai lần**, lần hai sau khi `down -v`.
- Chỉ nginx publish cổng (80, 443). Postgres, Redis, backend, frontend không ra khỏi mạng compose.
- Không container ứng dụng nào có bind mount — thứ đang chạy đúng là thứ đã build.
- Mọi service đặt `restart: unless-stopped`.
- nginx khởi động được **một mình**, trả 502 trong lúc chờ upstream thay vì chết theo. Đây là điều kiện để `init-tls.sh` xin được chứng chỉ trên máy chủ chưa build image lần nào.
- Backend chạy được với `R2_*` và `GOOGLE_*` để trống — đúng trạng thái của một VPS mới dựng.
- Image production: frontend 398 MB (Next standalone), backend không có pytest/ruff (đã kiểm: `python -m pytest` trong container trả "No module named pytest").

## URL công khai qua Cloudflare Quick Tunnel (08/09/2026)

Cùng stack production ấy, thêm một service `cloudflared` (`infra/docker-compose.tunnel.yml`), cho ra một URL Internet thật: `https://<ngẫu nhiên>.trycloudflare.com`, chứng chỉ do **Google Trust Services** cấp cho `trycloudflare.com`, đi qua edge Cloudflare Hong Kong. Mọi lệnh kiểm tra dưới đây **bật xác thực TLS** — không có `-k`, không bỏ qua chứng chỉ.

Đủ để đóng gate demo của Phase 2 mà không tốn đồng nào và không cần tên miền. Chi tiết được và không được: header của `infra/docker-compose.tunnel.yml`.

### Đã chứng minh được

- Luồng gate chạy trọn qua URL công khai: đăng ký → tìm khóa học → enroll → lưu tiến độ 312s → vào lại đúng vị trí (`luong-gate-qua-tunnel.txt`).
- **Trên trình duyệt thật**, không phải chỉ bằng script: đăng nhập bằng form, player quay lại đúng 5:12, khu giảng viên mở được bằng tài khoản seed.
- Cookie refresh đặt trên chính host của tunnel, `HttpOnly` + `Secure` — hệ quả trực tiếp của việc bundle không còn mang tên miền.
- Console trình duyệt chỉ có một lỗi, và là lỗi đúng: `401` từ `/api/v1/auth/refresh` với khách chưa đăng nhập. Nó cũng là bằng chứng trình duyệt gọi API trên origin của tunnel.

### Chỉ máy chủ thật mới chứng minh được

- Xin chứng chỉ Let's Encrypt qua thử thách HTTP-01, và vòng gia hạn tự động — đều cần một tên miền công khai gọi ngược về được. Tunnel dùng chứng chỉ của Cloudflare nên không chạm tới đường này.
- Cả stack tự dậy sau khi máy chủ reboot. Chính sách `unless-stopped` đã đặt đúng trên cả 7 container, nhưng chưa reboot thật lần nào.
- Đăng nhập Google: redirect URI phải đăng ký trước, mà URL tunnel là ngẫu nhiên.
- URL ổn định. Tunnel đổi URL sau mỗi lần khởi động và chỉ sống khi máy này bật — đủ cho một link gửi đi xem, không đủ cho buổi bảo vệ.

### Một chỗ chưa đúng, đã biết

`frontend/app/layout.tsx` đặt `metadataBase` từ `NEXT_PUBLIC_SITE_URL`, mặc định `http://localhost:3000`. Trên tunnel thì canonical và thẻ Open Graph trỏ về localhost. Chỉ ảnh hưởng metadata SEO, không ảnh hưởng chức năng; sửa khi có tên miền thật ở Phase 6.

### Lỗi phát hiện được nhờ buổi tổng duyệt

**Ba tài khoản do seed tạo không đăng nhập được.** Seed ghi thẳng vào bảng `users` nên không đi qua kiểm tra nào, còn `/auth/login` lại kiểm địa chỉ bằng `EmailStr`; `email-validator` xếp `.local` vào nhóm tên miền dành riêng và từ chối. Kết quả: `admin@devpath.local` và hai giảng viên tồn tại trong database nhưng API trả 422 cho mọi lần đăng nhập — trong khi chặng 8 của kịch bản demo bảo đăng nhập đúng bằng một trong số đó.

Sửa bằng cách đổi sang `.example` (RFC 2606 dành riêng cho tài liệu, không ai sở hữu được, và validator chấp nhận), kèm test hồi quy `test_every_seeded_account_can_be_typed_into_the_login_form` khẳng định mọi email seed phải qua được đúng schema mà endpoint login dùng.

Đáng ghi vào báo cáo: lỗi này không test đơn vị nào bắt được, vì nó nằm ở khe giữa hai đường ghi dữ liệu vào cùng một bảng.

## Cách tái tạo

```bash
cd infra && cp .env.prod.example .env.prod
```

Điền `DOMAIN=localhost`, `POSTGRES_PASSWORD`, `JWT_SECRET`, rồi đặt chứng chỉ tự ký vào volume `letsencrypt` (bước đầu của `scripts/init-tls.sh`), sau đó:

```bash
COMPOSE_PROJECT_NAME=devpath-prodtest ./scripts/deploy.sh --seed
```

Đặt tên project khác để volume của bản chạy thử không đè lên database của máy dev. Trên VPS thì không cần — ở đó chỉ có một stack.

Các bước còn lại của gate Phase 2 (đăng nhập Google, tạo khóa học, ảnh chụp player đang phát) thu khi deploy lên VPS thật; xem `docs/huong-dan-deploy-vps.md` mục 5.
