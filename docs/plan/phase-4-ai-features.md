# Phase 4 — AI Features ⭐ (tuần 9–10, 19/10 → 01/11)

**Mục tiêu:** điểm nhấn 2 + 3: hybrid recommender, chatbot RAG, sinh quiz bằng AI.

> Mọi call LLM đi qua adapter (`backend/app/services/llm.py`) — đổi model/provider không sửa business code. Luôn xử lý lỗi/quota: timeout, retry, fallback thông báo tử tế.

## Dọn nợ trước khi đi tiếp (thêm 18/09/2026)

Từ đợt rà tồn đọng ngày 18/09. Vì sao từng dòng tồn tại và sửa thế nào: [don-no-2026-09-18.md](don-no-2026-09-18.md). Làm hết mục này trước các task tuần 9 bên dưới, mỗi dòng một phiên, một PR. Hai lỗi grader thuộc Phase 3 nhưng ghi ở đây: thêm checkbox vào file Phase 3 đã đóng sẽ kéo `start-session` lùi về Phase 3.

- [x] Đóng việc dở: key Gemini vào `infra/.env.prod.example` (compose prod đọc mà file mẫu không có), merge PR #31, dọn nhánh đã merge
- [x] MLE bị chấm thành TLE khi Docker trả `State.OOMKilled=false` — `classify` đọc thêm thời gian sống container, exit 137 trước điểm giữa soft/hard CPU limit là MLE (skill `sandbox-grading`, TDD) — `docs/report/assets/phase-3/oom-classification.txt`
- [x] `run_grading` không chấm lại submission đã `done`/`error` khi Celery giao lại job — trước đây lần giao lại hỏng ở ràng buộc `ck_submissions_verdict_requires_done`, hết retry thì bị park thành `error` và mất verdict; nay trả `AlreadyFinished` + phát lại event kết thúc, và `park_submission` không ghi đè bài đã có kết quả (skill `sandbox-grading`, TDD)
- [x] MinIO trong compose dev thay R2 — mở khóa upload video/avatar/transcript trên máy dev, 0đ, không đụng compose prod (`bitnamilegacy/minio` vì image chính thức đã bị gỡ; host `minio.localhost` dùng chung cho trình duyệt và container) — `docs/report/assets/phase-4/dev-storage-minio.txt`
- [x] Ingest xóa chunk của bài học không còn chữ (trước đây chỉ đếm `skipped`, chunk cũ vẫn tìm thấy được); report có thêm `removed` (TDD) — `docs/report/assets/phase-4/rag-ingest.txt` mục 5
- [x] Đồng bộ tài liệu với thực tế (~12 file) + ghi các món nợ hoãn chưa có chủ vào checkbox Phase 5/6 — 11 checkbox mới ở mục "Nợ hoãn lại" của `phase-6-hardening-deploy.md`, ghi chú ingest ở task duyệt khóa của Phase 5
- [x] Build tái lập được: lockfile backend, pin `ubuntu-24.04` + action Node 24 trước mốc 19/10, pin tag image, CI guard cho `importorskip` — `backend/requirements.lock` sinh bằng `scripts/lock.sh` (`uv --universal`), CI fail nếu lock lệch `pyproject.toml`; action v7
- [x] Lỗi UX làm vấp demo (2 nút `disabled` ở trang chủ, `/khoa-hoc` trắng trang khi backend chết, lỗi avatar nói về video) + `courses.duration_total_s` không bao giờ được cập nhật — `/khoa-hoc` hóa ra đã có `error.tsx` từ 23/08 (thử lại khi dừng backend: không trắng); `services/course_stats.py` + `scripts/rebuild_course_stats.py` (TDD) — `docs/report/assets/phase-4/course-stats-rebuild.txt`

## Tuần 9 — RAG chatbot + sinh quiz

- [x] Bật pgvector, bảng `doc_chunks` (index HNSW)
- [x] Pipeline ingest **bài viết**: article → chunk ~500 token có overlap → Gemini embedding → lưu (job Celery, chạy khi content published)
- [x] Pipeline ingest **transcript video**: giảng viên upload .srt/.txt lên R2 → đọc về, đi tiếp cùng đường ống trên — qua API (`PUT /lessons/{id}/transcript`) để đọc thử trước khi giữ; đọc lỗi thì giữ chunk cũ — `docs/report/assets/phase-4/transcript-ingest.txt`
- [x] API chat: embed câu hỏi → top-k theo course_id → prompt trợ giảng (chỉ trả lời trong phạm vi khóa học, kèm trích nguồn bài học) → stream response. **Bắt buộc:** top-k chỉ lấy chunk của khóa đang `published` và người hỏi đã ghi danh — unpublish cố ý không xóa chunk (xem `docs/plan/don-no-2026-09-18.md`, Phiên 4) — điều kiện nằm trong chính câu truy vấn; SSE `sources`/`delta`/`done`/`error`; bảng `chat_sessions`/`chat_messages` (migration `42fff7804290`); model `gemini-3.5-flash-lite` chọn bằng số đo — `docs/report/assets/phase-4/chat-api.txt`
  - Để lại cho task đánh giá chatbot: ngưỡng điểm từ chối không cần gọi model (chưa đặt, lý do ở `chat-api.txt` §8). Kiểm SSE qua nginx của compose prod đã ghi thành checkbox ở mục "Nợ hoãn lại" của Phase 6
- [ ] UI chat trong trang học: khung chat, hiển thị nguồn (link nhảy tới lesson), lịch sử phiên
- [x] Quiz model + attempt flow: làm quiz tính giờ (giờ tính ở backend), tự chấm, xem giải thích
- [ ] Sinh quiz AI: instructor chọn lesson → Gemini sinh N câu (JSON mode) → instructor duyệt/sửa từng câu trước khi publish
- [ ] Đánh giá chatbot: bộ 20 câu hỏi test trên khóa học seed, chấm đúng/sai/có trích nguồn — bộ câu hỏi + bảng kết quả lưu vào `docs/report/assets/phase-4/`
  - Kèm hai việc `rag-ingest.txt` mục 4 còn nợ: đối chiếu `CHARS_PER_TOKEN = 3,5` với `countTokens` trên chính các chunk đã sinh, và bấm publish trên UI rồi xem worker nhận job ingest (đường Celery đầu-cuối chưa ai thử trên máy dev)

## Tuần 10 — Hybrid recommender

- [ ] Content-based: embedding title+description+category cho mọi course → cosine similarity ("khóa học tương tự" trên trang chi tiết)
- [x] Collaborative: implicit matrix (enroll=1, completed=2, rating cao=3) → item-based CF hoặc ALS (thư viện `implicit`)
- [ ] Hybrid blend + fallback: user mới → content-based theo lịch sử xem + phổ biến theo danh mục
- [x] Batch Celery beat hằng đêm → cache top-N vào Redis; API `/recommendations`
- [ ] UI: khối "Gợi ý cho bạn" (trang chủ), "Khóa học tương tự" (trang chi tiết), "Học tiếp theo" (sau khi hoàn thành)
- [x] Seed thêm dữ liệu tương tác giả lập (script tạo ~50 user với hành vi enroll/rating theo cụm sở thích) để đo lường
- [ ] `backend/scripts/eval_recommender.py`: precision@k, recall@k trên held-out — output script lưu vào `docs/report/assets/phase-4/recommender-eval.md`, ghi rõ lệnh chạy để tái tạo

## Gate cuối phase

- [ ] Demo: hỏi chatbot nội dung có trong khóa học → trả lời đúng kèm nguồn; hỏi ngoài phạm vi → từ chối lịch sự
- [ ] Demo: 2 user sở thích khác nhau thấy gợi ý khác nhau
- [ ] Precision@k / recall@k đo được, script tái tạo được
- [ ] Sinh quiz từ 1 bài giảng thật, instructor duyệt và học viên làm được
- [ ] Thu bằng chứng vào `docs/report/assets/phase-4/`: bảng precision@k/recall@k, 3–5 hội thoại chatbot có trích nguồn (kể cả 1 ca từ chối ngoài phạm vi), ví dụ quiz sinh tự động kèm nhận xét chất lượng, screenshot khối gợi ý của 2 user khác nhau
