# DevPath — Nền tảng học lập trình trực tuyến

Khóa luận tốt nghiệp: nền tảng e-learning kiểu Udemy tích hợp AI — chấm mã nguồn tự động trong Docker sandbox, hybrid recommender, chatbot RAG trợ giảng.

## Tech stack

| Lớp | Công nghệ |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS + shadcn/ui, TanStack Query |
| Backend | FastAPI (Python 3.12+), SQLAlchemy 2.x async, Pydantic v2 |
| CSDL | PostgreSQL 16 (pgvector) + Redis |
| Hàng đợi | Celery — worker chấm bài, sinh embedding, gửi mail |
| AI | Gemini API (RAG chatbot, sinh quiz), embedding cho recommender |
| Hạ tầng | Docker Compose trên VPS, Nginx, Cloudflare R2 |

## Cấu trúc

```
.
├── backend/     FastAPI + Celery worker      → backend/README.md
├── frontend/    Next.js App Router           → frontend/README.md
├── grader/      Judge worker + sandbox image → grader/README.md
├── infra/       Docker Compose, Nginx, deploy→ infra/README.md
└── docs/        Tài liệu thiết kế & kế hoạch
```

## Tài liệu

- [Đề cương khóa luận](de-cuong-khoa-luan-elearning.md) — phạm vi tính năng
- [Kiến trúc hệ thống](docs/architecture.md)
- [Thiết kế CSDL](docs/database-design.md)
- [Kế hoạch 14 tuần](docs/plan/00-overview.md) — trạng thái dự án nằm ở checkbox trong các file phase
- [Workflow phát triển](docs/workflow.md)

## Chạy trên một máy mới

Chỉ cần **Git** và **Docker** (Docker Desktop trên Windows/macOS, Docker Engine + plugin Compose v2 trên Linux). Không cần cài Python hay Node: backend, frontend, CSDL và mọi script đều chạy trong container. Docker nên được cấp **≥ 4 GB RAM** (cả stack dev dùng ~2,4 GB) và cần **~10 GB đĩa trống** (image ~5,5 GB). Các bước dưới đây đã chạy thử trên một bản clone mới tinh ngày 02/10/2026 ([bằng chứng](docs/report/assets/phase-6/fresh-machine.txt)).

**1. Lấy mã nguồn và tạo tệp cấu hình.** Để nguyên giá trị mặc định là chạy được; upload video/ảnh tự dùng MinIO trong stack.

```bash
git clone https://github.com/acquy66666/DevPath.git && cd DevPath
```

```bash
cp infra/.env.example infra/.env
```

**2. Build image sandbox chấm bài.** Không phải service compose mà là image để worker chấm bài dựng một container cho mỗi lượt nộp; thiếu nó thì mọi bài nộp ra lỗi hệ thống.

```bash
docker build -t devpath-sandbox-python:v1 grader/images/python
```

**3. Dựng stack.** Lần đầu mất vài phút để build image. `--wait` chỉ trả về khi mọi service có healthcheck đã healthy.

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
```

**4. Tạo bảng, rồi nạp dữ liệu gốc** (1 admin, 2 giảng viên, 8 danh mục, 4 khóa học có mục lục đầy đủ). Chạy lại bao nhiêu lần cũng được.

```bash
docker compose -f infra/docker-compose.yml exec backend alembic upgrade head
```

```bash
docker compose -f infra/docker-compose.yml exec backend python -m scripts.seed
```

**5. Mở trình duyệt** (Chrome hoặc Edge — video và ảnh tải từ `minio.localhost`, tên mà trình duyệt tự hiểu là máy mình):

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:3000 | Giao diện |
| http://localhost:8000/docs | Tài liệu API tự sinh |
| http://localhost:9001 | Console MinIO (`devpath` / `devpath-minio`) |

| Tài khoản | Mật khẩu | Có từ |
|---|---|---|
| `admin@devpath.example` | `devpath-admin` | `scripts.seed` |
| `khoa.tran@devpath.example`, `mai.anh@devpath.example` (giảng viên) | `devpath-instructor` | `scripts.seed` |
| `hocvien01` … `hocvien48@seed.devpath.example` | `devpath-learner` | `scripts.seed_interactions` |
| `nguoimua01` … `nguoimua40@sales.devpath.example` | `devpath-buyer` | `scripts.seed_sales` |

Mật khẩu mặc định chỉ dành cho máy cá nhân; trên máy có mặt trên Internet, seed từ chối chạy nếu chưa đặt `SEED_*_PASSWORD` (xem [runbook deploy](docs/huong-dan-deploy-vps.md)).

**Tùy chọn — tính năng cần khóa bên ngoài.** Thiếu thì tính năng đó báo "chưa cấu hình", phần còn lại chạy bình thường. Điền vào `infra/.env` rồi `docker compose -f infra/docker-compose.yml up -d`:

- `GEMINI_API_KEY` — trợ giảng AI, sinh quiz, "khóa học tương tự" ([lấy key](https://aistudio.google.com/apikey));
- `VNPAY_TMN_CODE` + `VNPAY_HASH_SECRET` — thanh toán. Đặt hai giá trị bất kỳ là chạy được cả luồng trên máy, với script `simulate_vnpay_ipn <mã đơn>` (chạy trong container như mọi script bên dưới) đóng vai VNPay.

### Dữ liệu demo đầy đủ (tùy chọn)

Thứ tự **có nghĩa**: script sau dùng dữ liệu của script trước. Mỗi script chạy lại không ghi thêm gì. Gõ theo mẫu `docker compose -f infra/docker-compose.yml exec backend python -m scripts.<tên>`:

| # | Script | Thêm gì | Cần |
|---|---|---|---|
| 1 | `seed_transcripts` | Lời giảng cho 12 bài video khóa Python — kho ngữ liệu của trợ giảng AI | `GEMINI_API_KEY` để nạp vào RAG |
| 2 | `seed_banners` | 3 banner ở trang chủ | |
| 3 | `seed_interactions` | 20 khóa giả lập + 48 học viên, để **đo** hệ gợi ý — catalog thành 24 khóa | |
| 4 | `seed_coupons` | 6 mã giảm giá (`CHAOMUNG50`, `PYTHON30`…) | bước 3 |
| 5 | `seed_cart` | Giỏ hàng + yêu thích của `hocvien01/13/25` | bước 3 |
| 6 | `seed_sales` | 77 đơn hàng của 40 người mua trong 12 tháng — dashboard giảng viên và admin | |
| 7 | `seed_study` | 40 người mua học trong 70 ngày — XP, chuỗi ngày, bảng xếp hạng | bước 6 |
| 8 | `issue_certificates` | Cấp và vẽ PDF chứng chỉ cho mọi lượt đã học xong | |
| 9 | `rebuild_recommendations` | Tính ngay gợi ý (job hằng đêm 03:00 cũng làm) | có `GEMINI_API_KEY` thì chạy `rebuild_course_embeddings` trước, không thì chỉ có nửa collaborative |

**Gỡ theo thứ tự ngược lại**, mỗi script thêm `--purge`: `seed_study` → `seed_sales` → `seed_cart` → `seed_coupons` → `seed_interactions`. Đơn hàng là sổ tiền và không bị script nào khác xóa, nên gỡ `seed_interactions` trước `seed_sales` sẽ bị từ chối kèm lời nhắc thứ tự. Gỡ xong còn đúng 4 khóa thật, 3 tài khoản gốc.

Chi tiết từng phần: [infra/README.md](infra/README.md) (stack, cổng, MinIO, sandbox), [backend/README.md](backend/README.md) (chạy backend bằng venv, test, từng script). Ba tài liệu viết cho máy phát triển của dự án:

- [docs/huong-dan-chay-va-docker.md](docs/huong-dan-chay-va-docker.md) — chạy trang web từng bước, cấu trúc file, và vai trò của Docker trong dự án
- [docs/huong-dan-du-an.md](docs/huong-dan-du-an.md) — sửa từng phần của giao diện, luồng một request, và những chỗ dễ vấp
- [docs/huong-dan-demo-truoc-giao-vien.md](docs/huong-dan-demo-truoc-giao-vien.md) — chuỗi lệnh chạy thủ công kèm giải thích, kịch bản demo 10 chặng, và câu trả lời cho những câu chắc chắn bị hỏi

## Trạng thái

**Phase 6 — Hardening & Deploy đang chạy** (Phase 1–5 đã đóng, tag `phase-1-done` … `phase-5-done`). Trạng thái chi tiết nằm ở checkbox trong [docs/plan/](docs/plan/00-overview.md); tóm tắt cập nhật nhất ở mục "Trạng thái hiện tại" của [CLAUDE.md](CLAUDE.md).

- **Nền tảng (Phase 2):** đăng ký/đăng nhập (email + Google), 3 vai trò; giảng viên soạn khóa học, mục lục kéo-thả, upload video chuyển mã HLS; tìm kiếm toàn văn tiếng Việt, trình phát nhớ vị trí, ghi chú, đánh giá.
- **Chấm mã nguồn (Phase 3) ⭐:** sandbox Docker cô lập (không mạng, không đặc quyền, rootfs chỉ đọc, timeout hai lớp), đủ 7 verdict, 7 ca tấn công đều bị chặn; hàng đợi Celery riêng, tiến độ từng test qua WebSocket.
- **AI (Phase 4) ⭐:** trợ giảng RAG trả lời dạng stream có trích nguồn bài học; sinh quiz từ bài giảng, giảng viên duyệt; hệ gợi ý lai collaborative + content-based, đo precision/recall.
- **Thương mại & quản trị (Phase 5):** giỏ hàng, mã giảm giá, thanh toán VNPay sandbox, chứng chỉ PDF có mã xác thực, XP + chuỗi ngày + bảng xếp hạng, Hỏi đáp theo bài, thông báo, dashboard giảng viên và admin, kiểm duyệt.
- **Hardening (Phase 6):** rà soát bảo mật, E2E luồng vàng (Playwright) trong CI, load test, backup CSDL có diễn tập khôi phục, giám sát + cảnh báo. Cấu hình production (compose, nginx, HTTPS) đã viết và được CI kiểm, **chưa lên máy chủ thật** — chờ task dựng VPS.

## Quy ước

- Code, tên biến, commit message: tiếng Anh. Tài liệu trong `docs/`: tiếng Việt. UI: tiếng Việt.
- Commit theo Conventional Commits, mỗi task một nhánh `feature/<tên>` và một PR. Nhánh `main` có hai lớp bảo vệ:
  - ruleset `protect-main` phía GitHub (chặn force-push và xóa nhánh; không ai bypass được);
  - hook `.githooks/pre-push`, lớp nhanh báo lỗi ngay trên máy trước khi tốn công push. Sau khi clone phải bật hook bằng lệnh:

```bash
git config core.hooksPath .githooks
```
