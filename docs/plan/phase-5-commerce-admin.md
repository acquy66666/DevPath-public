# Phase 5 — Commerce, Gamification & Admin (tuần 11–12, 02/11 → 15/11)

**Mục tiêu:** khép kín vòng thương mại (giỏ hàng → thanh toán → sở hữu khóa học), gamification, và bộ công cụ quản trị.

## Tuần 11 — Thanh toán & thương mại

- [x] Giỏ hàng + wishlist (API + UI)
- [ ] Coupon: validate (hạn, lượt dùng, phạm vi), áp vào order
- [ ] VNPay sandbox: tạo payment URL → redirect → IPN handler (verify chữ ký HMAC, idempotent theo `provider_txn_id`) → order `paid` → tự động enroll các khóa trong order
- [ ] `payment_events` append-only log mọi IPN; trang kết quả thanh toán (thành công/thất bại/đang xử lý)
- [ ] Test: giả lập IPN hợp lệ/sai chữ ký/trùng lặp — cả 3 case phải đúng
- [ ] MoMo sandbox (nếu còn thời gian — mục cắt giảm số 1)
- [ ] Dashboard doanh thu instructor: doanh thu theo thời gian, học viên mới, tỉ lệ hoàn thành per khóa học

## Tuần 12 — Gamification, Q&A, Admin

- [ ] XP events (hoàn thành lesson/quiz/bài code AC lần đầu) + streak theo ngày hoạt động
- [ ] Leaderboard Redis sorted set (tuần/tháng/toàn thời gian) + trang leaderboard
- [ ] Chứng chỉ PDF khi hoàn thành 100%: job Celery sinh PDF (weasyprint) + mã QR → trang verify công khai `/cert/{code}`
- [ ] Q&A theo lesson: thread + reply + upvote; badge "giảng viên trả lời"; notification khi được trả lời
- [ ] Thông báo in-app (chuông + danh sách)
- [ ] Admin: duyệt/từ chối khóa học (bỏ auto-approve flag của phase 2), quản lý user (khóa/mở), xử lý reports
  - **Duyệt khóa học phải gọi `enqueue_ingest`** như `submit_for_review` đang làm khi auto-approve bật (`backend/app/services/courses.py`). Tắt auto-approve mà endpoint duyệt quên việc này thì không còn gì nạp khóa học vào kho chatbot. Viết test: duyệt → một job ingest được xếp hàng (ghi 19/09/2026, đợt dọn nợ)
- [ ] Admin dashboard: doanh thu sàn, DAU, khóa học hot; quản lý category, coupon toàn sàn, banner trang chủ

## Gate cuối phase

- [ ] Demo end-to-end: thêm giỏ hàng → áp coupon → VNPay sandbox → thanh toán → vào học ngay
- [ ] Học viên hoàn thành khóa → nhận chứng chỉ PDF, quét QR verify được
- [ ] Admin duyệt khóa học mới trước khi hiện công khai
- [ ] Thu bằng chứng vào `docs/report/assets/phase-5/`: screenshot luồng thanh toán VNPay end-to-end, log IPN (đã che dữ liệu nhạy cảm), chứng chỉ PDF mẫu + trang verify, dashboard instructor và admin
