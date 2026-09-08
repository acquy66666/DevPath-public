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

### Đã chứng minh được

- `scripts/deploy.sh` chạy trọn từ volume trắng: build → 8 migration Alembic → 7 service healthy → exit 0. Chạy **hai lần**, lần hai sau khi `down -v`.
- Chỉ nginx publish cổng (80, 443). Postgres, Redis, backend, frontend không ra khỏi mạng compose.
- Không container ứng dụng nào có bind mount — thứ đang chạy đúng là thứ đã build.
- Mọi service đặt `restart: unless-stopped`.
- nginx khởi động được **một mình**, trả 502 trong lúc chờ upstream thay vì chết theo. Đây là điều kiện để `init-tls.sh` xin được chứng chỉ trên máy chủ chưa build image lần nào.
- Backend chạy được với `R2_*` và `GOOGLE_*` để trống — đúng trạng thái của một VPS mới dựng.
- Image production: frontend 398 MB (Next standalone), backend không có pytest/ruff (đã kiểm: `python -m pytest` trong container trả "No module named pytest").

### Chỉ máy chủ thật mới chứng minh được

- Xin chứng chỉ Let's Encrypt qua thử thách HTTP-01, và vòng gia hạn tự động — đều cần một tên miền công khai gọi ngược về được.
- Cả stack tự dậy sau khi máy chủ reboot. Chính sách `unless-stopped` đã đặt đúng trên cả 7 container, nhưng chưa reboot thật lần nào.
- Ảnh chụp màn hình trang chạy trên URL công khai. Chưa chụp: bằng chứng có giá trị cho báo cáo là trang chạy trên tên miền thật với ổ khóa xanh, không phải `https://localhost` kèm cảnh báo chứng chỉ tự ký.

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
