# Kho bằng chứng — chỉ mục và lượt rà soát

Thư mục này là nguyên liệu cho Phase 7 (viết báo cáo). Mỗi `phase-N/README.md` là chỉ mục **gate → tệp** của phase đó, [`decisions.md`](decisions.md) là nhật ký quyết định kỹ thuật cho chương 4, [`khao-sat-nen-tang-tham-chieu.md`](khao-sat-nen-tang-tham-chieu.md) là bảng khảo sát cho chương 1–2.

Tệp này ghi **lượt rà soát kho** theo gate cuối Phase 6 ("mở `docs/report/assets/` đối chiếu với bảng bằng chứng trong skill `thesis-report` — thiếu gì đo/chụp lại ngay"). **Lượt 1: 05/10/2026**, làm trên máy dev khi chưa có VPS, nên còn một lượt cuối sau khi deploy.

## 1. Bảng bằng chứng của skill `thesis-report` → tệp

| Phase | Skill đòi | Tệp | Trạng thái |
|---|---|---|---|
| 1 | Bảng khảo sát nền tảng tham chiếu | `khao-sat-nen-tang-tham-chieu.md` | có |
| 1 | Ảnh `docker compose ps` đủ service | `phase-1/compose-ps.png` (5 service, 20/08); `phase-2/prod-stack-ps.txt` (prod 7 service, 07/09); `phase-6/rustfs-compose.txt` (prod 12 service healthy, 05/10) | có, nhưng ảnh là của stack 20/08. **Chụp lại trên VPS** |
| 1 | Ảnh CI xanh | `phase-1/ci-green.png`, `phase-3/ci-xanh.txt`, `phase-6/test-summary.md` (CI 05/10, 6 job) | có. Ảnh Phase 1 là ảnh **render từ text** (repo private); cần giao diện GitHub thật thì chụp tay ở Phase 7 |
| 1 | Dump schema | `phase-1/schema.sql` (3 bảng) → **`phase-6/schema-final.sql`** (41 bảng, head `abb01d258134`) | **thêm 05/10** |
| 2 | Screenshot đăng ký → học video | `phase-2/phase2-0*-tunnel.png` (7 ảnh); `phase-6/e2e/01–08` | có. **Ảnh Phase 2 sai font** (mục 3.1) |
| 2 | Ghi chú quyết định JWT/OAuth, HLS, R2 | `decisions.md` § Phase 2; storage chốt lại 05/10 (§ Storage cho production, § RustFS vào compose) | có |
| 3 | Bảng đo thời gian chấm | `phase-3/benchmark.md` (máy dev 8 CPU) | có; đo lại trên VPS 2 vCPU là task mở |
| 3 | Log demo đủ 7 verdict | `phase-3/verdicts.txt` | có |
| 3 | Output test tấn công sandbox | `phase-3/attack-tests.txt`; qua proxy: `phase-6/docker-socket-proxy.txt` | có; chạy lại trên VPS là task mở |
| 3 | Screenshot chấm realtime | `phase-3/per-test-realtime-*.png`, `demo-gate-*.png`; `phase-6/e2e/06-nop-code-dung.png` | có. **Ảnh Phase 3 sai font** |
| 4 | Precision@k / recall@k | `phase-4/recommender-eval.md` + `.txt` | có |
| 4 | Hội thoại chatbot có trích nguồn + 1 ca từ chối | `phase-4/chatbot-demo.txt` + 4 ảnh | có. **Ảnh sai font** |
| 4 | Quiz sinh tự động + đánh giá chất lượng | `phase-4/quiz-demo.txt` + 7 ảnh, `quiz-generation.txt` | có. **Ảnh sai font** |
| 5 | Screenshot thanh toán sandbox end-to-end | `phase-5/pay-1…7-*.png`; `phase-6/e2e/03–04` | có. **Ảnh Phase 5 sai font** |
| 5 | Log IPN đã che dữ liệu nhạy cảm | `phase-5/vnpay-e2e.txt` §6 | có, **của IPN giả lập** — IPN thật chờ VNPay khai URL |
| 5 | Chứng chỉ PDF mẫu | `phase-5/certificate-sample.pdf` + `.png` | có (PDF do WeasyPrint vẽ, không dính lỗi font của web) |
| 5 | Dashboard instructor + admin | `phase-5/dashboards.txt` + 4 ảnh | có. **Ảnh sai font** |
| 6 | Kết quả load test | `phase-6/load-test.md` + JSON | có (stack production dựng trên máy dev) |
| 6 | URL demo chạy trên VPS | — | **chưa** — chờ VPS |
| 6 | Bảng tổng hợp test | **`phase-6/test-summary.md`** | **thêm 05/10** |
| 6 | Rà soát lần cuối toàn bộ kho | tệp này | lượt 1 xong 05/10; lượt cuối sau VPS |

## 2. Chương 5 (Kiểm thử & đánh giá) cần gì → tệp

| Mục chương 5 | Tệp | Ghi chú |
|---|---|---|
| Test coverage, tổng hợp test | `phase-6/test-summary.md`, `phase-6/coverage-backend.txt` | 2.239 ca tự động trên CI 05/10, 0 đỏ; coverage backend 94,5 % (dòng 95,4 %, nhánh 88,8 %) |
| Benchmark chấm bài | `phase-3/benchmark.md`, `phase-6/load-test.md` (lớp 20 người), `phase-6/docker-socket-proxy.txt` (chi phí proxy ~4 %) | số trên VPS 2 vCPU: chờ |
| Bảo mật sandbox | `phase-3/attack-tests.txt`, `sandbox-image.txt`, `runner-core.txt`, `oom-classification.txt`, `phase-6/docker-socket-proxy.txt` | |
| Bảo mật ứng dụng | `phase-6/security-review.txt`, `security-review-codebase.txt`, `refresh-leeway.txt` | |
| Recommender | `phase-4/recommender-eval.md` (warm + cold-start, held-out), `hybrid-blend.txt`, `interaction-seed.txt` | đo trên dữ liệu giả lập — **đo lại nếu cần thì phải làm trước khi gỡ dữ liệu giả** |
| Chatbot | `phase-4/chatbot-eval.md` (20 câu × 3), `chatbot-eval-truoc-sua.md` | |
| Sinh quiz | `phase-4/quiz-generation.txt` (60 câu chấm tay), `quiz-demo.txt` | |
| E2E | `phase-6/e2e-golden-flow.txt` | |
| Hiệu năng | `phase-6/load-test.md`, `phase-4/hnsw-index.txt`, `phase-6/sse-through-nginx.txt` | |
| Kết quả triển khai VPS | — | **chưa** — có tổng duyệt prod trên máy dev (`phase-2/`, `monitoring.txt`, `db-backup-restore.txt`, `rustfs-compose.txt`) |

## 3. Phát hiện của lượt rà 05/10

### 3.1. Gần như mọi ảnh giao diện đều sai font

Trước 02/10, cả site hiển thị bằng font dự phòng có chân (Times New Roman/Georgia) vì `--font-sans: var(--font-sans)` tự tham chiếu trong `globals.css`. E2E tìm ra và sửa lỗi này ngày 02/10 (`phase-6/e2e-golden-flow.txt`). Mọi ảnh chụp trước ngày đó mang font sai:

| Thư mục | Ảnh giao diện sai font |
|---|---|
| `phase-1/` | 1 (`frontend-home.png`; hai ảnh còn lại render từ text) |
| `phase-2/` | 7 |
| `phase-3/` | 13 |
| `phase-4/` | 16 |
| `phase-5/` | 28 (trừ `certificate-sample.png`, render từ PDF) |
| **Tổng** | **65** |

Ảnh đúng font hiện có: `phase-6/e2e/` (8 ảnh, theo luồng vàng, nhưng là tài khoản/khóa E2E như "Python nhập môn E2E khoa-…" và còn nút dev của Next) và `phase-6/ux/` (12 ảnh ghép trước | sau, không dùng làm hình minh họa độc lập được).

Giao diện cũng đã đổi sau 02/10 (header, trang chi tiết khóa học, ảnh bìa dự phòng, trang chủ — `phase-6/ux-polish.txt`). Nên kể cả không lỗi font, ảnh cũ cũng không còn khớp sản phẩm.

**Giá trị bằng chứng của ảnh cũ không đổi**: chúng chứng minh tính năng chạy được vào đúng ngày đó, nên vẫn giữ. Nhưng chương 4 cần ảnh của sản phẩm cuối, nên **phải chụp lại**. Việc này đã thành task mới trong kế hoạch Phase 6 (mục 5).

### 3.2. Đối chiếu 20 tính năng của đề cương với ảnh hiện có

"Bằng chứng chạy" là log hoặc mô tả chạy thật; "ảnh đúng font" là ảnh dùng được cho chương 4 ngay hôm nay.

| # | Tính năng (đề cương §5) | Bằng chứng chạy | Ảnh đúng font |
|---|---|---|---|
| 1 | Đăng ký/đăng nhập, OAuth Google, JWT | `phase-2/luong-hoc-vien-qua-https.txt`, `phase-6/security-*.txt` | `e2e/01` (đăng ký). **Google: chưa có ảnh nào** — chờ tên miền |
| 2 | Duyệt & tìm kiếm khóa học | `phase-2/luong-gate-qua-tunnel.txt` | `ux/08`, `ux/10` (ảnh ghép) |
| 3 | Video HLS, tiến độ, tốc độ, **phụ đề** | `phase-2/phase2-04-player-tunnel.png` (312 s), `phase-4/dev-storage-minio.txt` | **không có**. **Phụ đề: cắt** (user chốt 05/10, xem 3.4) |
| 4 | Nộp code, chấm sandbox realtime ⭐ | `phase-3/*`, `phase-6/e2e-golden-flow.txt` | `e2e/06` |
| 5 | Quiz có tính giờ | `phase-4/quiz-demo.txt` | không có |
| 6 | Chatbot RAG ⭐ | `phase-4/chatbot-demo.txt`, `chat-ui.txt` | không có |
| 7 | Gợi ý hybrid ⭐ | `phase-4/recommendations-demo.txt` | không có |
| 8 | Ghi chú theo timestamp, đánh dấu bài | ghi chú task trong `docs/plan/phase-2-core-platform.md` | **chưa từng có ảnh** (CSDL dev: 0 ghi chú, 0 bookmark) |
| 9 | Q&A theo bài, upvote | ghi chú task trong `docs/plan/phase-5-commerce-admin.md` | **chưa từng có ảnh** (0 câu hỏi) |
| 10 | Chứng chỉ PDF + QR | `phase-5/certificate-demo.txt` + PDF | `e2e/07–08` |
| 11 | Streak, XP, leaderboard | ghi chú task trong `phase-5-commerce-admin.md` | **chưa từng có ảnh** |
| 12 | Giỏ, thanh toán, mã giảm giá, wishlist | `phase-5/vnpay-e2e.txt`, `payment-ipn.txt` | `e2e/03–04` (giỏ không mã), `ux/05`; **wishlist chưa từng có ảnh** |
| 13 | Tạo khóa học, curriculum kéo-thả, upload video | `phase-2/`, `phase-4/dev-storage-minio.txt` | `ux/11–12` (ảnh ghép 375 px); trình soạn ở màn rộng không có |
| 14 | Tạo bài tập code | `phase-3/README.md` § Trình soạn | không có |
| 15 | Sinh quiz bằng AI ⭐ | `phase-4/quiz-demo.txt` | không có |
| 16 | Dashboard giảng viên | `phase-5/dashboards.txt` | không có |
| 17 | Trả lời Q&A, thông báo | `phase-5/course-review-gate.txt` (thông báo duyệt khóa) | **hộp thư Q&A và chuông thông báo chưa từng có ảnh** (0 thông báo) |
| 18 | Duyệt khóa, quản lý người dùng, báo cáo | `phase-5/admin-moderation.txt`, `course-review-gate.txt` | `ux/04` (ảnh ghép); **trang người dùng và báo cáo chưa từng có ảnh** |
| 19 | Dashboard toàn sàn | `phase-5/dashboards.txt`, `admin-dashboard.txt` | không có |
| 20 | Danh mục, banner, mã giảm giá toàn sàn | `phase-5/admin-dashboard.txt` | không có |

Mọi tính năng (trừ phụ đề, đã cắt) đều có bằng chứng chạy thật. Chỗ thiếu là ảnh: **chỉ 4/20 có ảnh đúng font dùng được ngay**, và **7 màn hình chưa từng được chụp ở bất kỳ phase nào** (ghi chú/bookmark, Q&A cả hai phía, thông báo, XP + bảng xếp hạng, wishlist, trang người dùng/báo cáo của admin).

### 3.3. Đã sửa trong lượt này

- `decisions.md` thiếu **toàn bộ Phase 5** (giỏ, coupon, VNPay, dashboard, XP/bảng xếp hạng, chứng chỉ, Q&A, thông báo, quản trị) và **5 mục Phase 6 ngày 02/10** (UX, proxy Docker socket, backup, giám sát, máy trắng). Các quyết định này trước đó chỉ nằm trong ghi chú task và `CLAUDE.md` → đã chép vào, kèm đánh đổi.
- `phase-6/` chưa có chỉ mục → `phase-6/README.md`.
- `phase-3/README.md` thiếu `oom-classification.txt` → đã thêm.
- Chưa có schema ở trạng thái cuối (Phase 1 chỉ có 3 bảng) → `phase-6/schema-final.sql`.
- Chưa có bảng tổng hợp test và số coverage → `phase-6/test-summary.md`.
- Các tệp tên trong `phase-1…5/README.md` đều tồn tại (đã kiểm bằng script; các mẫu kiểu `pay-1…7-*.png` khớp đủ số ảnh).

### 3.4. Phạm vi: một tính năng của đề cương chưa làm mà chưa được ghi nhận là cắt

Đề cương §5.1 mục 3 hứa "phụ đề". Player có chọn tốc độ phát nhưng **không hiển thị phụ đề** (`frontend/components/learn/video-player.tsx` không có `<track>`). Đây là mục **cắt giảm số 2** trong [`00-overview.md`](../../plan/00-overview.md). Nhưng khác MoMo (mục số 1, ghi rõ "cắt ngày 01/10"), chưa chỗ nào ghi phụ đề là đã cắt, trong khi các mục cắt giảm 3–6 đều đã làm. **User chốt cắt ngày 05/10**: đã ghi vào `00-overview.md` và `decisions.md` § Chốt phạm vi trước khi đóng băng.

## 4. Thứ tự với task "Gỡ dữ liệu tương tác giả lập"

Gỡ theo đúng thứ tự README là **study → sales → cart → coupons → interactions**. Sau khi gỡ, CSDL dev còn 4 khóa, 3 tài khoản, **0 đơn, 0 lượt ghi danh, 0 mã giảm giá** (`phase-6/fresh-machine.txt` §5). Dashboard, bảng xếp hạng, XP, gợi ý và giỏ hàng mẫu khi đó đều trống. Vì vậy:

1. Chụp lại ảnh giao diện (mục 5) **trước** khi gỡ.
2. Nếu Phase 7 cần chạy lại `eval_recommender`/`eval_chatbot` thì cũng chạy **trước**.
3. Sau khi gỡ, chụp lại riêng danh sách khóa học và trang chủ nếu báo cáo cần hình catalog "sạch" 4 khóa. Hoặc chụp trên VPS, nơi vốn chỉ seed 4 khóa.

## 5. Còn thiếu — phân loại

**Làm được ngay trên máy dev → task mới trong `docs/plan/phase-6-hardening-deploy.md`:**

- Chụp lại bộ ảnh giao diện cho chương 4: font đúng, giao diện sau UX polish, mỗi tính năng ở mục 3.2 ít nhất một ảnh 1440 px, cộng vài ảnh 375 px. Gồm cả 7 màn chưa từng có ảnh.
  - Cần dữ liệu demo cho Q&A, thông báo, ghi chú/bookmark, lịch sử nộp bài (CSDL dev đang 0 dòng ở các bảng này).
  - Script chụp lưu trong repo, để chạy lại nguyên vẹn trên VPS cho gate "luồng vàng trên tên miền thật".
  - Không để nút dev của Next trong ảnh.

**Chờ VPS** (đã là task trong kế hoạch): URL + Let's Encrypt + lần reboot đầu; ảnh đăng nhập Google; 7 ca tấn công + `eat_memory.py` × 50; `GRADING_CONCURRENCY` trên 2 vCPU; `docker compose ps` của VPS; monitor systemd timer + UptimeRobot chạy thật; backup lên B2 chạy thật; console sạch rồi bật enforce CSP. Tùy chọn: chạy lại `infra/loadtest/` trên VPS (kịch bản đã sẵn, mặc định trỏ stack VPS).

**Chờ bên ngoài:** IPN thật của VNPay → bổ sung log đã che vào `phase-5/vnpay-e2e.txt`.

**Đã chốt 05/10** (ảnh hưởng chương 4 và mục hạn chế ở chương 6; ghi ở `decisions.md` § Chốt phạm vi trước khi đóng băng):

1. **Phụ đề video: cắt** (mục cắt giảm số 2, như MoMo). Tệp `.srt` vẫn lưu và vẫn nuôi trợ giảng AI, chỉ không hiển thị trên player.
2. **Chứng chỉ giữ kiểu Udemy**: tự đánh dấu hoàn thành bài quiz/code vẫn được tính (`phase-6/security-review-codebase.txt` §5). Chứng chỉ xác nhận đã đi hết khóa, không xác nhận đã đạt từng bài.
