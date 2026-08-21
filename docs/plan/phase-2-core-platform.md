# Phase 2 — Core Platform (tuần 3–5, 07/09 → 27/09)

**Mục tiêu:** vòng đời khóa học hoàn chỉnh không kèm tiền: đăng ký → giảng viên tạo khóa học → học viên enroll (miễn phí) → xem video có lưu tiến độ.

## Tuần 3 — Auth & user

- [x] Đăng ký/đăng nhập email + password (bcrypt), JWT access + refresh token (refresh lưu httpOnly cookie)
- [ ] OAuth Google (authorization code flow) — merge account theo email
- [x] Phân quyền `student`/`instructor`/`admin`; dependency `require_role`; user tự nâng cấp lên instructor qua form đơn giản
- [ ] Trang profile, đổi mật khẩu, upload avatar (R2 presigned URL — làm luôn để tái dùng cho video)
- [x] Test: auth flow, refresh, phân quyền

## Tuần 4 — Quản lý khóa học (instructor)

- [ ] CRUD khóa học (draft → pending_review → published; admin duyệt làm ở phase 5, tạm auto-approve có feature flag)
- [ ] Curriculum builder: section + lesson, sắp xếp kéo-thả (position), loại lesson: video/article
- [ ] Upload video: presigned URL lên R2 → job Celery transcode HLS (ffmpeg) → cập nhật `video_assets.status`
- [ ] Trang chi tiết khóa học public (SSR, SEO meta) + đánh dấu lesson preview

## Tuần 5 — Trải nghiệm học viên

- [ ] Danh sách khóa học: full-text search (tsvector), lọc category/giá/rating, phân trang
- [ ] Enroll khóa học miễn phí; trang "Khóa học của tôi"
- [ ] Video player HLS (hls.js): lưu `last_position_s` (heartbeat ~10s), tốc độ phát, đánh dấu lesson hoàn thành
- [ ] Ghi chú theo timestamp + bookmark lesson
- [ ] Review & rating khóa học (chỉ khi đã enroll)
- [ ] Seed data thật: ≥3 khóa học lập trình có video + curriculum đầy đủ
- [ ] Deploy lần đầu lên VPS (docker compose + nginx + HTTPS)

## Gate cuối phase

- [ ] Demo end-to-end trên VPS: đăng ký Google → tìm khóa học → enroll → xem video → thoát → vào lại đúng vị trí cũ
- [ ] Test pass: auth, course CRUD, enroll, progress
- [ ] Thu bằng chứng vào `docs/report/assets/phase-2/`: screenshot luồng đăng ký/đăng nhập Google, tạo khóa học, player đang phát + tiến độ; ghi 1–2 dòng cho mỗi quyết định kỹ thuật đáng nhớ vào `decisions.md` (nguyên liệu chương 4, **chưa viết báo cáo**)
