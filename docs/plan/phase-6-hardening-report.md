# Phase 6 — Hardening, Deploy & Report (tuần 13–14, 16/11 → 29/11)

**Mục tiêu:** sản phẩm chạy ổn định trên VPS công khai + báo cáo hoàn chỉnh + chuẩn bị bảo vệ.

## Tuần 13 — Kiểm thử & hoàn thiện

- [ ] Rà soát bảo mật: authorization mọi endpoint (ownership!), rate limit auth + submit + chat, CORS, security headers, secrets không nằm trong repo
- [ ] Chạy `/security-review` trên toàn bộ code và xử lý findings
- [ ] E2E test các luồng vàng (Playwright): đăng ký → mua → học → nộp code → chứng chỉ
- [ ] Load test nhẹ (locust/k6): trang danh sách, submit code 20 đồng thời — số liệu vào báo cáo
- [ ] Sửa bug UX tồn đọng; empty state, loading, mobile responsive các trang chính
- [ ] Backup DB tự động (cron pg_dump → R2); script restore đã thử
- [ ] Monitoring tối thiểu: uptime check + log tập trung (docker logging) + alert đơn giản

## Tuần 14 — Báo cáo & bảo vệ

- [ ] Hoàn thiện báo cáo theo cấu trúc trong skill `thesis-report` — các chương đã có sẵn nội dung từ mỗi phase, tuần này là tổng hợp + mài giũa
- [ ] Rà lại toàn bộ hình vẽ, bảng số liệu, trích dẫn
- [ ] Slide bảo vệ: 15–20 slide, tập trung 3 điểm nhấn ⭐ + demo live
- [ ] Kịch bản demo 7–10 phút: chuẩn bị sẵn dữ liệu, tài khoản, đường đi bấm; **quay video demo dự phòng** phòng khi mạng/VPS trục trặc hôm bảo vệ
- [ ] Tổng duyệt: nhờ 1–2 bạn dùng thử theo kịch bản, sửa vấp váp cuối

## Gate cuối phase (= sẵn sàng bảo vệ)

- [ ] URL demo công khai chạy ổn định ≥1 tuần
- [ ] Báo cáo in được, đủ chương, số liệu tái tạo được bằng script trong repo
- [ ] Video demo dự phòng đã quay
- [ ] Slide + kịch bản demo đã tổng duyệt
