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
- [x] UI chat trong trang học: khung chat, hiển thị nguồn (link nhảy tới lesson), lịch sử phiên — tab "Trợ giảng AI" cạnh mục lục; `[n]` thành nút mở bài bên cạnh mà khung chat giữ nguyên; Dừng/Hỏi lại; backend thêm `citations` vào tin nhắn để phiên cũ vẫn biết `[2]` là bài nào (không migration, TDD) — `docs/report/assets/phase-4/chat-ui.txt`
  - Để lại cho task đánh giá chatbot: model tự viết ví dụ code không có trong tài liệu và không trích nguồn (`chat-ui.txt` §6)
- [x] Quiz model + attempt flow: làm quiz tính giờ (giờ tính ở backend), tự chấm, xem giải thích
- [x] Sinh quiz AI: instructor chọn lesson → Gemini sinh N câu (JSON mode) → instructor duyệt/sửa từng câu trước khi publish — `POST /quizzes/{id}/generate` + `/quiz-questions/{id}/approve`; cột `ai_generated`/`reviewed_at` (migration `ca9e1c7ffdbb`); còn câu AI chưa duyệt thì 409 `QUIZ_NEEDS_REVIEW`; mọi câu qua `check_question_shape`, xáo phương án, `key_warning` khi lời giải thích nói về phương án khác; model `gemini-3.5-flash-lite` chọn bằng số đo (30/30 đáp án đúng, 3,0 s) — `docs/report/assets/phase-4/quiz-generation.txt`
  - Để lại cho gate cuối phase: học viên làm chính quiz vừa sinh trên trình duyệt + ảnh chụp (`quiz-generation.txt` §8)
- [x] Đánh giá chatbot: bộ 20 câu hỏi test trên khóa học seed, chấm đúng/sai/có trích nguồn — bộ câu hỏi + bảng kết quả lưu vào `docs/report/assets/phase-4/` — `scripts/eval_chatbot.py` (20 câu × 3 lần qua đúng `prepare_answer`, chấm máy + đọc tay, 11 câu thăm dò ngưỡng); kho làm dày trước bằng 12 lời giảng (`scripts/seed_transcripts.py`, 4 → 15/17 bài có chữ); kết quả cuối 58/60, bài đúng hạng 1 ở 42/42, từ chối sạch 18/18; sửa lỗi câu từ chối vẫn gắn số nguồn (3/18 → 0/18, `chat.is_refusal` + quy tắc 3 có câu mở đầu nguyên văn, TDD); **không đặt ngưỡng** vì câu hợp lệ (0,633) thấp hơn câu phải từ chối (0,692); cho phép ví dụ mã ghép từ tài liệu, câu dẫn phải ghi nguồn — `docs/report/assets/phase-4/chatbot-eval.txt`
  - Kèm hai việc `rag-ingest.txt` mục 4 còn nợ: đối chiếu `CHARS_PER_TOKEN = 3,5` với `countTokens` trên chính các chunk đã sinh, và bấm publish trên UI rồi xem worker nhận job ingest (đường Celery đầu-cuối chưa ai thử trên máy dev) — xong: kho thật 3,41 ký tự/token, ước thấp 2,5%, giữ 3,5 vì chunk lớn nhất 557/2048 token (`token-estimate.txt`); xuất bản → worker nhận job sau 0,34 s, nạp 16 chunk (gọi đúng endpoint của nút, chưa bấm chuột vì cần mật khẩu) — `rag-ingest.txt` mục 6
  - Để lại cho gate cuối phase: q14 (câu nối tiếp mơ hồ) bị từ chối nhầm 1/6 lượt sau khi sửa prompt — đo kỹ nếu gặp lại; ảnh chụp hội thoại chạy script với `--keep` rồi chụp trên UI

## Tuần 10 — Hybrid recommender

- [x] Content-based: embedding title+description+category cho mọi course → cosine similarity ("khóa học tương tự" trên trang chi tiết) — bảng `course_embeddings` (migration `17e181ed9f26`, một vector/khóa, `source_text` nguyên văn để chạy lại không tốn quota), nhúng bằng `taskType=SEMANTIC_SIMILARITY` (hai vế cùng loại, khác `doc_chunks`), `GET /courses/{id}/similar` công khai xếp theo cosine với lọc `published`/đã gỡ/khác model **trong chính câu truy vấn**; publish → `embed_courses_task(course_id)`, beat 02:30 → cả catalogue (bắt khóa sửa mô tả mà không republish); chạy tay bằng `python -m scripts.rebuild_course_embeddings [slug] [--dry-run]` (TDD, 21+8 test) — `docs/report/assets/phase-4/content-based.txt`
  - Chưa chạy thật với Gemini: `infra/.env` đã mất `GEMINI_API_KEY` (trùng byte-for-byte với `.env.example`) — mọi thứ khác đo trên Postgres thật với vector dựng tay, chi tiết ở `content-based.txt` mục 0 và 2
  - Để lại cho task UI: khối "Khóa học tương tự" trên trang chi tiết (checkbox riêng bên dưới) — endpoint đã sẵn sàng
- [x] Collaborative: implicit matrix (enroll=1, completed=2, rating cao=3) → item-based CF hoặc ALS (thư viện `implicit`)
- [x] Hybrid blend + fallback: user mới → content-based theo lịch sử xem + phổ biến theo danh mục — `services/hybrid.py` trộn bằng **Reciprocal Rank Fusion** (k = 60) chứ không cộng điểm thô: đo được điểm collaborative chạy 0,02–5,79 (một tổng) còn cosine content-based chạy 0,747–0,892, và content-based cho **mọi** khóa ít nhất 0,747 nên cộng vào sẽ đè tín hiệu thật. Cache lên `rec:v2` vì mỗi mục mang thêm `sources`; dự phòng phổ biến-theo-danh-mục chèn lúc phục vụ (`popular_courses`), lấp cả ba cảnh: user mới, mô hình không có gì, danh sách bị cắt ngắn. Hàng lấp chỗ mang `score` = 0 và `because` = null. (TDD, 12+8+3+14 test mới) — `docs/report/assets/phase-4/hybrid-blend.txt`
  - **Hybrid kém hơn CF đơn thuần trên chỉ số cụm giả lập: 0,8056 so với 0,8333.** Không chỉnh trọng số để kéo lên, vì thước đo ấy thiên vị CF (dữ liệu được sinh ra từ chính cấu trúc cụm). Đổi lại, mô phỏng từng khóa ở trạng thái vừa xuất bản: CF gợi ý được **0/24**, hybrid **24/24**, mỗi khóa tới 13–35 trong 48 học viên. Con số 0/24 không tinh chỉnh được — thông tin không có trong ma trận
  - Để lại cho `eval_recommender.py`: trọng số 1,0/1,0 và k = 60 mới chỉ là mặc định; precision@k trên tập held-out là nơi trả lời con số 0,8056
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
