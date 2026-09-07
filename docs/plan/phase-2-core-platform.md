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
- [ ] Deploy lần đầu lên VPS (docker compose + nginx + HTTPS)
  - Cấu hình đã tổng duyệt trọn vẹn bằng chính `docker-compose.prod.yml` trên máy dev (bằng chứng: `docs/report/assets/phase-2/`). Còn chờ VPS + tên miền để chạy `docs/huong-dan-deploy-vps.md`; hai thứ chưa chứng minh được nếu không có máy chủ thật là chứng chỉ Let's Encrypt và lần reboot đầu tiên.

## Gate cuối phase

- [ ] Demo end-to-end trên VPS: đăng ký Google → tìm khóa học → enroll → xem video → thoát → vào lại đúng vị trí cũ
- [x] Test pass: auth, course CRUD, enroll, progress — 472 passed, 2 skipped (`docs/report/assets/phase-2/pytest.txt`)
- [ ] Thu bằng chứng vào `docs/report/assets/phase-2/`: screenshot luồng đăng ký/đăng nhập Google, tạo khóa học, player đang phát + tiến độ; ghi 1–2 dòng cho mỗi quyết định kỹ thuật đáng nhớ vào `decisions.md` (nguyên liệu chương 4, **chưa viết báo cáo**)
