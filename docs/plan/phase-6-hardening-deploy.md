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

- [ ] **Dựng máy chủ thật và deploy lần đầu** — máy **Azure for Students** ($100 credit) hoặc **Oracle Cloud Always Free**, tối thiểu **2 vCPU / 4 GB RAM**, kèm tên miền `.me` của GitHub Student Developer Pack, chi phí thật **0đ**. (Credit DigitalOcean của pack đã hết hạn 31/07/2026 — DigitalOcean rút khỏi pack.) Chạy `docs/huong-dan-deploy-vps.md` từ mục 0b. Dời từ Phase 2 sang đây vì giai đoạn trước chỉ cần demo được, chưa cần trình bày; cấu hình production đã tổng duyệt xong từ tuần 5 (`docs/report/assets/phase-2/`)
- [ ] Bật đăng nhập Google trên tên miền thật — redirect URI cố định, thứ mà URL tunnel ngẫu nhiên ở Phase 2 không làm được
- [ ] Backup DB tự động (cron `pg_dump` → R2); script restore đã thử khôi phục thật một lần
- [ ] Monitoring tối thiểu: uptime check + log tập trung (docker logging) + alert đơn giản
- [ ] Rà lại `.env.example`, README chạy dự án, script seed chạy sạch trên máy trắng

## Nợ hoãn lại từ Phase 2–4 (ghi 19/09/2026)

Từ đợt rà tồn đọng 18/09 ([don-no-2026-09-18.md](don-no-2026-09-18.md), Phiên 5). Đây là những việc tài liệu các phase trước đã hứa "để Phase 6" hoặc "chưa làm, ghi để nhắc" mà chưa có checkbox nào nhận.

**Sandbox chấm bài** (skill `sandbox-grading`):

- [ ] Proxy cho Docker socket: `grading-worker` chỉ được `create`/`start`/`inspect`/`kill`/`rm` thay vì cầm nguyên `/var/run/docker.sock` (`infra/README.md`, mục "Worker chấm bài, và cái socket nó cầm")
- [ ] Chạy lại 7 ca tấn công sandbox trên VPS thật, kèm chạy `eat_memory.py` 50 lần để xem có kẹt sát trần bộ nhớ tới hết wall như trên Docker Desktop không (3/80 lần — `docs/report/assets/phase-3/oom-classification.txt` mục 8)
- [ ] Đo lại `GRADING_CONCURRENCY` trên máy 2 vCPU thật. Benchmark đã có đo trên máy dev 8 CPU (`phase-3/benchmark.md`)
- [ ] Quyết định có làm nhánh polling nhích từng test không: hiện worker ghi `submission_results` một lần lúc cuối nên nhánh dự phòng đứng yên tới khi xong (`phase-3/per-test-realtime.txt`)
- [ ] `submissions.peak_memory_mb` luôn `None` (`backend/app/workers/grading.py`): đo thật từ cgroup trước khi container bị xóa, hoặc bỏ cột

**Vận hành & frontend:**

- [ ] Endpoint readiness kiểm tra được DB + Redis. `/health` hiện cố ý không chạm DB
- [ ] Job dọn object mồ côi trong bucket: URL đã ký mà không ai upload, bài học bị xóa (`backend/README.md`, mục "Trạng thái")
- [ ] `metadataBase` lấy từ `NEXT_PUBLIC_SITE_URL`, nhưng compose prod và Dockerfile chưa truyền biến này nên canonical/Open Graph trên production sẽ trỏ `http://localhost:3000`. Cần truyền `https://${DOMAIN}` lúc build image frontend
- [ ] Race refresh-token khi mở hai tab sau thời gian dài không dùng: thêm khoảng ân hạn (leeway) phía backend (`frontend/README.md`, mục Auth)
- [ ] Quyết định storage cho production: Cloudflare R2 (cần khai thẻ thanh toán) hay tự host. MinIO đã ngừng phát hành image bản cộng đồng (kiểm 18/09/2026), nên tự host MinIO nghĩa là tự build từ source hoặc chọn server S3 khác

**Dữ liệu trước buổi bảo vệ:**

- [ ] Gỡ dữ liệu tương tác giả lập bằng `python -m scripts.seed_interactions --purge` (20 khóa `cum-*` + 48 học viên giả). Để lại thì catalog hiện 24 khóa thay vì 4 và làm hỏng kịch bản demo. **Chạy sau khi đã thu xong số đo precision@k**

## Gate cuối phase (= đóng băng tính năng)

- [ ] URL demo công khai chạy ổn định trên **tên miền thật**, tự khởi động lại sau khi reboot VPS (chứng chỉ Let's Encrypt và lần reboot đầu tiên là hai thứ chỉ máy chủ thật mới chứng minh được)
- [ ] Luồng vàng chạy lại đủ trên tên miền thật, lần này **có đăng nhập Google** — chụp lại screenshot cho báo cáo
- [ ] Toàn bộ test (unit + E2E + test bảo mật sandbox) xanh trong CI
- [ ] **Kiểm tra kho bằng chứng:** mở `docs/report/assets/` đối chiếu với bảng bằng chứng trong skill `thesis-report` — thiếu gì đo/chụp lại ngay tuần này, sang Phase 7 là quá muộn
- [ ] Tag git `phase-6-done` — mốc code hoàn chỉnh dùng để viết báo cáo
