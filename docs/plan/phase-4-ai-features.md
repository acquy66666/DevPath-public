# Phase 4 — AI Features ⭐ (tuần 9–10, 19/10 → 01/11)

**Mục tiêu:** điểm nhấn 2 + 3: hybrid recommender, chatbot RAG, sinh quiz bằng AI.

> Mọi call LLM đi qua adapter (`backend/app/services/llm.py`) — đổi model/provider không sửa business code. Luôn xử lý lỗi/quota: timeout, retry, fallback thông báo tử tế.

## Tuần 9 — RAG chatbot + sinh quiz

- [ ] Bật pgvector, bảng `doc_chunks` (index HNSW)
- [ ] Pipeline ingest: transcript video (giảng viên upload .srt/.txt) + article → chunk ~500 token overlap → Gemini embedding → lưu (job Celery, chạy khi content published)
- [ ] API chat: embed câu hỏi → top-k theo course_id → prompt trợ giảng (chỉ trả lời trong phạm vi khóa học, kèm trích nguồn bài học) → stream response
- [ ] UI chat trong trang học: khung chat, hiển thị nguồn (link nhảy tới lesson), lịch sử phiên
- [ ] Quiz model + attempt flow: làm quiz tính giờ (giờ tính ở backend), tự chấm, xem giải thích
- [ ] Sinh quiz AI: instructor chọn lesson → Gemini sinh N câu (JSON mode) → instructor duyệt/sửa từng câu trước khi publish
- [ ] Đánh giá chatbot: bộ 20 câu hỏi test trên khóa học seed, chấm đúng/sai/có trích nguồn — bảng vào báo cáo

## Tuần 10 — Hybrid recommender

- [ ] Content-based: embedding title+description+category cho mọi course → cosine similarity ("khóa học tương tự" trên trang chi tiết)
- [ ] Collaborative: implicit matrix (enroll=1, completed=2, rating cao=3) → item-based CF hoặc ALS (thư viện `implicit`)
- [ ] Hybrid blend + fallback: user mới → content-based theo lịch sử xem + phổ biến theo danh mục
- [ ] Batch Celery beat hằng đêm → cache top-N vào Redis; API `/recommendations`
- [ ] UI: khối "Gợi ý cho bạn" (trang chủ), "Khóa học tương tự" (trang chi tiết), "Học tiếp theo" (sau khi hoàn thành)
- [ ] Seed thêm dữ liệu tương tác giả lập (script tạo ~50 user với hành vi enroll/rating theo cụm sở thích) để đo lường
- [ ] `backend/scripts/eval_recommender.py`: precision@k, recall@k trên held-out — số liệu + phương pháp vào báo cáo chương 5

## Gate cuối phase

- [ ] Demo: hỏi chatbot nội dung có trong khóa học → trả lời đúng kèm nguồn; hỏi ngoài phạm vi → từ chối lịch sự
- [ ] Demo: 2 user sở thích khác nhau thấy gợi ý khác nhau
- [ ] Precision@k / recall@k đo được, script tái tạo được
- [ ] Sinh quiz từ 1 bài giảng thật, instructor duyệt và học viên làm được
