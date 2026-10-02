# Phase 6 — Hardening & Deploy (tuần 13, 16/11 → 22/11)

**Mục tiêu:** biến sản phẩm "chạy được" thành sản phẩm "chạy ổn định trên VPS công khai". Kết thúc phase là **đóng băng tính năng** — từ Phase 7 trở đi chỉ sửa lỗi chặn demo, không thêm tính năng mới.

> Đây là phase cuối cùng còn viết code. Mọi bằng chứng cho báo cáo phải đầy đủ trước khi rời phase này, vì Phase 7 không dựng lại môi trường để đo lại.

## Kiểm thử & bảo mật

- [x] Rà soát bảo mật: authorization mọi endpoint (ownership!), rate limit auth + submit + chat, CORS, security headers, secrets không nằm trong repo — xong 01/10: test ma trận 159 route, 0 lỗ phân quyền; sửa 5 lỗi thật (IP giả qua `X-Forwarded-For`, auth chưa có rate limit, `/_next/static/` mất header, `deploy.sh --seed` không chuyển mật khẩu seed vào container, CORS `*`/JWT ngắn/schema mở ở production) — `docs/report/assets/phase-6/security-review.txt`
- [x] Chạy `/security-review` trên toàn bộ code và xử lý findings — xong 01/10: rà 4 mảng song song + lọc dương tính giả độc lập; 3 lỗ thật đã sửa kèm test (HIGH chiếm trước tài khoản qua liên kết Google, MEDIUM đơn chờ thanh toán không hết hạn → vượt giới hạn coupon, MEDIUM open redirect `?next=/\evil`); sandbox/storage/SSRF/SQL/XSS/hạ tầng sạch — `docs/report/assets/phase-6/security-review-codebase.txt`
- [x] E2E test các luồng vàng (Playwright): đăng ký → mua → học → nộp code → chứng chỉ — xong 02/10: một spec đi trọn luồng của học viên trên UI thật vào cả stack compose (VNPay: URL đã ký được kiểm, IPN ký trong container; code chấm trong sandbox thật), tự dọn dữ liệu bằng `scripts.purge_e2e`; xanh trên máy dev và trên CI (job riêng dựng stack từ số không, 1 passed 35,8 s, không cần chạy lại); tìm ra 2 lỗi font đã sửa (toàn site là Times New Roman, chữ Việt hai dấu vỡ ở trang chứng chỉ) — `docs/report/assets/phase-6/e2e-golden-flow.txt`
- [ ] Load test nhẹ (locust/k6): trang danh sách, submit code 20 đồng thời — số liệu vào `docs/report/assets/phase-6/load-test.md`
- [ ] Sửa bug UX tồn đọng; empty state, loading, mobile responsive các trang chính

## Vận hành

- [ ] **Dựng máy chủ thật và deploy lần đầu** — máy **Azure for Students** ($100 credit) hoặc **Oracle Cloud Always Free**, tối thiểu **2 vCPU / 4 GB RAM**, kèm tên miền `.me` của GitHub Student Developer Pack, chi phí thật **0đ**. (Credit DigitalOcean của pack đã hết hạn 31/07/2026 — DigitalOcean rút khỏi pack.) Chạy `docs/huong-dan-deploy-vps.md` từ mục 0b. Dời từ Phase 2 sang đây vì giai đoạn trước chỉ cần demo được, chưa cần trình bày; cấu hình production đã tổng duyệt xong từ tuần 5 (`docs/report/assets/phase-2/`)
- [ ] Bật đăng nhập Google trên tên miền thật — redirect URI cố định, thứ mà URL tunnel ngẫu nhiên ở Phase 2 không làm được
- [ ] Backup DB tự động (cron `pg_dump` → R2); script restore đã thử khôi phục thật một lần
- [ ] Monitoring tối thiểu: uptime check + log tập trung (docker logging) + alert đơn giản
- [ ] Rà lại `.env.example`, README chạy dự án, script seed chạy sạch trên máy trắng
- [ ] Bật **enforce** cho Content-Security-Policy: hiện đang `Content-Security-Policy-Report-Only` (`infra/nginx/snippets/security-headers.conf`, từ 01/10). Chạy luồng vàng trên tên miền thật, console không có vi phạm nào → đổi tên header và bỏ dòng `frame-ancestors` riêng

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
- [ ] Kiểm luồng SSE của trợ giảng AI chạy **qua nginx** của `docker-compose.prod.yml`: chữ phải tới dần chứ không dồn một cục ở cuối. Backend đã gửi `X-Accel-Buffering: no`, nhưng stack dev không có nginx nên chưa ai thấy tận mắt (`docs/report/assets/phase-4/chat-api.txt` §8)
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
