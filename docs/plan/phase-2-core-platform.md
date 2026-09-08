# Phase 2 — Core Platform (tuần 3–5, 07/09 → 27/09)

**Mục tiêu:** vòng đời khóa học hoàn chỉnh không kèm tiền: đăng ký → giảng viên tạo khóa học → học viên enroll (miễn phí) → xem video có lưu tiến độ.

## Tuần 3 — Auth & user

- [x] Đăng ký/đăng nhập email + password (bcrypt), JWT access + refresh token (refresh lưu httpOnly cookie)
- [x] OAuth Google (authorization code flow) — merge account theo email
- [x] Phân quyền `student`/`instructor`/`admin`; dependency `require_role`; user tự nâng cấp lên instructor qua form đơn giản
- [x] Trang profile, đổi mật khẩu, upload avatar (R2 presigned URL — làm luôn để tái dùng cho video)
- [x] Test: auth flow, refresh, phân quyền

## Tuần 4 — Quản lý khóa học (instructor)

- [x] CRUD khóa học (draft → pending_review → published; admin duyệt làm ở phase 5, tạm auto-approve có feature flag)
- [x] Curriculum builder: section + lesson, sắp xếp kéo-thả (position), loại lesson: video/article
- [x] Upload video: presigned URL lên R2 → job Celery transcode HLS (ffmpeg) → cập nhật `video_assets.status`
- [x] Trang chi tiết khóa học public (SSR, SEO meta) + đánh dấu lesson preview

## Tuần 5 — Trải nghiệm học viên

- [x] Danh sách khóa học: full-text search (tsvector), lọc category/giá/rating, phân trang
- [x] Enroll khóa học miễn phí; trang "Khóa học của tôi"
- [x] Video player HLS (hls.js): lưu `last_position_s` (heartbeat ~10s), tốc độ phát, đánh dấu lesson hoàn thành
- [x] Ghi chú theo timestamp + bookmark lesson
- [x] Review & rating khóa học (chỉ khi đã enroll)
- [x] Seed data thật: ≥3 khóa học lập trình có video + curriculum đầy đủ
- [ ] Đăng ký **GitHub Student Developer Pack** — mở khóa cùng lúc ba thứ đang chặn: GitHub Pro (ruleset bảo vệ `main`, tồn từ [Phase 1](phase-1-foundation.md)), $200 credit DigitalOcean, và tên miền `.me` miễn phí một năm. Duyệt mất vài ngày nên nộp trước, đừng chờ tới lúc cần
- [x] Bỏ tên miền ra khỏi bundle frontend: trình duyệt gọi `/api` **tương đối cùng origin** thay vì `NEXT_PUBLIC_API_BASE_URL` tuyệt đối (`frontend/lib/api/client.ts`). Không có bước này thì mỗi lần URL công khai đổi đều phải build lại image frontend — mà URL của tunnel thì đổi sau mỗi lần khởi động
  - Xong: `NEXT_PUBLIC_API_BASE_URL` để rỗng nghĩa là "cùng origin với trang". Bundle production không còn địa chỉ tuyệt đối nào (`docs/report/assets/phase-2/bundle-khong-ten-mien.txt`); cùng một image phục vụ được cả `https://localhost` lẫn `https://127.0.0.1`, luồng học viên chạy trọn trên host mà image chưa từng biết. Stack dev không đổi vì ở đó không có nginx
- [x] URL demo công khai tạm bằng **Cloudflare Quick Tunnel** (`cloudflared tunnel --url`): HTTPS thật, không cần tài khoản, không cần tên miền, **0đ**. Đủ để gửi link cho GVHD và kiểm luồng thật từ máy khác
  - Xong: `infra/docker-compose.tunnel.yml` + `infra/scripts/tunnel.sh`. Chạy `./scripts/deploy.sh` rồi `./scripts/tunnel.sh` là có URL. Chứng chỉ do Google Trust Services cấp, xác thực TLS bật khi kiểm tra

> **Deploy lên VPS thật đã dời sang [Phase 6](phase-6-hardening-deploy.md)** và sẽ làm bằng credit của Student Pack, chi phí thật 0đ. Lý do dời: giai đoạn này chỉ cần *demo được*, chưa cần *trình bày*, nên không đáng bỏ tiền thuê máy chủ chạy không suốt hai tháng. Cấu hình production **đã tổng duyệt trọn vẹn** bằng chính `docker-compose.prod.yml` (bằng chứng: `docs/report/assets/phase-2/`) — thứ còn thiếu duy nhất là cái máy chủ, không phải phần việc kỹ thuật nào.

## Gate cuối phase

- [x] Demo end-to-end trên **URL công khai** (tunnel là đủ): đăng ký bằng email → tìm khóa học → enroll → xem video → thoát → vào lại đúng vị trí cũ — chạy cả bằng script (`luong-gate-qua-tunnel.txt`) lẫn trên trình duyệt thật: player quay lại đúng 5:12 = 312 giây đã lưu (`phase2-04-player-tunnel.png`)
  - Đăng nhập Google **không** nằm trong gate này: redirect URI phải đăng ký cố định ở Google Cloud Console, mà URL tunnel thì ngẫu nhiên. Chuyển sang gate Phase 6, khi đã có tên miền thật
- [x] Test pass: auth, course CRUD, enroll, progress — 472 passed, 2 skipped (`docs/report/assets/phase-2/pytest.txt`)
- [x] Thu bằng chứng vào `docs/report/assets/phase-2/`: screenshot luồng đăng ký, tạo khóa học, player đang phát + tiến độ; ghi 1–2 dòng cho mỗi quyết định kỹ thuật đáng nhớ vào `decisions.md` (nguyên liệu chương 4, **chưa viết báo cáo**)
  - 6 file văn bản + 7 ảnh chụp trên URL công khai, và các mục Phase 2 trong `decisions.md`. Ảnh chụp lại trên tên miền thật ở Phase 6 nếu báo cáo cần bản đẹp hơn
