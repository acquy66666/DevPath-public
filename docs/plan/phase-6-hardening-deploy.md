# Phase 6 — Hardening & Deploy (tuần 13, 16/11 → 22/11)

**Mục tiêu:** biến sản phẩm "chạy được" thành sản phẩm "chạy ổn định trên VPS công khai". Kết thúc phase là **đóng băng tính năng** — từ Phase 7 trở đi chỉ sửa lỗi chặn demo, không thêm tính năng mới.

> Đây là phase cuối cùng còn viết code. Mọi bằng chứng cho báo cáo phải đầy đủ trước khi rời phase này, vì Phase 7 không dựng lại môi trường để đo lại.

## Kiểm thử & bảo mật

- [ ] Rà soát bảo mật: authorization mọi endpoint (ownership!), rate limit auth + submit + chat, CORS, security headers, secrets không nằm trong repo
- [ ] Chạy `/security-review` trên toàn bộ code và xử lý findings
- [ ] E2E test các luồng vàng (Playwright): đăng ký → mua → học → nộp code → chứng chỉ
- [ ] Load test nhẹ (locust/k6): trang danh sách, submit code 20 đồng thời — số liệu vào `docs/report/assets/phase-6/load-test.md`
- [ ] Sửa bug UX tồn đọng; empty state, loading, mobile responsive các trang chính

## Vận hành

- [ ] **Dựng máy chủ thật và deploy lần đầu** — bằng credit DigitalOcean và tên miền `.me` của GitHub Student Developer Pack, chi phí thật **0đ**. Chạy `docs/huong-dan-deploy-vps.md` từ mục 0b. Dời từ Phase 2 sang đây vì giai đoạn trước chỉ cần demo được, chưa cần trình bày; cấu hình production đã tổng duyệt xong từ tuần 5 (`docs/report/assets/phase-2/`)
- [ ] Bật đăng nhập Google trên tên miền thật — redirect URI cố định, thứ mà URL tunnel ngẫu nhiên ở Phase 2 không làm được
- [ ] Backup DB tự động (cron `pg_dump` → R2); script restore đã thử khôi phục thật một lần
- [ ] Monitoring tối thiểu: uptime check + log tập trung (docker logging) + alert đơn giản
- [ ] Rà lại `.env.example`, README chạy dự án, script seed chạy sạch trên máy trắng

## Gate cuối phase (= đóng băng tính năng)

- [ ] URL demo công khai chạy ổn định trên **tên miền thật**, tự khởi động lại sau khi reboot VPS (chứng chỉ Let's Encrypt và lần reboot đầu tiên là hai thứ chỉ máy chủ thật mới chứng minh được)
- [ ] Luồng vàng chạy lại đủ trên tên miền thật, lần này **có đăng nhập Google** — chụp lại screenshot cho báo cáo
- [ ] Toàn bộ test (unit + E2E + test bảo mật sandbox) xanh trong CI
- [ ] **Kiểm tra kho bằng chứng:** mở `docs/report/assets/` đối chiếu với bảng bằng chứng trong skill `thesis-report` — thiếu gì đo/chụp lại ngay tuần này, sang Phase 7 là quá muộn
- [ ] Tag git `phase-6-done` — mốc code hoàn chỉnh dùng để viết báo cáo
