# Bằng chứng Phase 4 — AI Features ⭐

Phase đang chạy. Bảng dưới là gate cuối phase (chép từ [kế hoạch](../../../plan/phase-4-ai-features.md)) và chỗ bằng chứng sẽ nằm — dòng nào chưa có tệp thì việc tương ứng chưa làm.

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Bảng precision@k / recall@k, script tái tạo được | `recommender-eval.md` (script `backend/scripts/eval_recommender.py`) | chưa có |
| 3–5 hội thoại chatbot có trích nguồn, kèm 1 ca từ chối ngoài phạm vi | `chat-api.txt` §2–§3 | một phần — đã có qua API (một phiên 3 lượt có trích nguồn, câu nối tiếp và 1 ca từ chối, cùng 6 câu so model). Còn thiếu ảnh chụp vì UI chat chưa dựng |
| Bộ 20 câu hỏi đánh giá chatbot + bảng kết quả | — | chưa có |
| Ví dụ quiz sinh tự động kèm nhận xét chất lượng | — | chưa có |
| Screenshot khối gợi ý của 2 user sở thích khác nhau | `interaction-seed.txt` §4 | một nửa — đã có hai danh sách khác nhau lấy qua HTTP, còn thiếu ảnh chụp vì khối "Gợi ý cho bạn" chưa dựng |

## Ngoài gate, đã thu

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `embedding-model.txt` | Chọn model embedding bằng số đo: `gemini-embedding-001` vs `gemini-embedding-2` — bản 2 **bỏ qua `taskType`** (cosine giữa vector DOCUMENT và QUERY = 1,000000) nên chọn bản 001 (0,893094). Kèm đo token tiếng Việt bằng `countTokens` (3,92 ký tự/token có dấu, 2,32 với mã nguồn) — cơ sở cho `CHARS_PER_TOKEN` | 4 — Xây dựng hệ thống |
| `rag-ingest.txt` | Ingest chạy thật trên 24 khóa: 26 chunk, lần chạy thứ hai tốn **0 quota**. Truy hồi thật: câu trong phạm vi d≈0,30, câu ngoài phạm vi d≈0,52 — cách biệt đủ để đặt ngưỡng từ chối. Kèm phần "chưa đo": 43/69 bài học không có chữ vì nội dung thật là video | 4 — Xây dựng hệ thống, và 5 — Kiểm thử & đánh giá |
| `interaction-seed.txt` | 48 học viên giả lập theo 4 cụm sở thích, 190 tương tác, 24 khóa: 48/48 người có gợi ý (trước là 1/4), tỷ lệ top-3 đúng cụm **0,8333** so với mức ngẫu nhiên 0,2500. Kèm hai lần đột biến cố ý chứng minh test bắt được lỗi, và hai học viên khác cụm lấy thật qua HTTP | 4 — Xây dựng hệ thống, và 5 — Kiểm thử & đánh giá |
| `recommendation-batch.txt` | Job hằng đêm chạy thật: 4 key `rec:v1:user:*` trong Redis, TTL ~48 giờ, điểm `0,7071 = 1/√2` kiểm được bằng tay, log beat đọc đúng lịch 03:00. Kèm phần "chưa đo, nói thẳng": chưa có precision@k vì CSDL dev chỉ có 5 tương tác | 4 — Xây dựng hệ thống |
| `dev-storage-minio.txt` + `dev-minio-upload-playback.png` | MinIO trong compose dev thay R2 (0đ). Upload video/avatar trước trả 503, giờ **chạy thật qua trình duyệt**: PUT cross-origin 200, sai `Content-Type` bị 403, worker chuyển mã HLS 3,7 s, hls.js phát được. Kèm lý do chọn host `minio.localhost` và việc image MinIO chính thức đã bị gỡ khỏi Docker Hub | 4 — Xây dựng hệ thống (môi trường phát triển) |
| `chat-api.txt` | API chat RAG chạy thật. **Chọn model sinh bằng số đo**: `gemini-3.5-flash-lite` có TTFT 1,2–1,5 s, so với ~6 s của `3.5-flash`, còn `3.8-flash` gặp 503/429 trên free tier. Token "suy nghĩ" bị trừ vào `maxOutputTokens`: 188/200 token. Luồng SSE qua HTTP: nguồn tới sau 0,5 s, chữ đầu sau 1,6 s. **Hạ khóa về nháp thì truy vấn gọi thẳng trả 0 dòng dù 4 chunk vẫn nằm trong bảng.** Đột biến từng điều kiện lọc đều làm test đỏ. Câu nối tiếp: gộp hai truy vấn đưa bài đúng lên hạng 1 ở 5/5 ca. Gemini **hỏng giữa chừng** bằng JSON trần sau HTTP 200, gặp hai lần thật. Kèm mục "chưa đo": chưa qua nginx, chưa đặt ngưỡng từ chối | 4 — Xây dựng hệ thống, và 5 — Kiểm thử & đánh giá |
| `hnsw-index.txt` | `EXPLAIN (ANALYZE, BUFFERS)` chứng minh planner **thật sự** chọn `ix_doc_chunks_embedding`: 1,33 ms / 1239 buffer so với 5,89 ms / 9055 buffer khi tắt index scan, trên 3000 chunk. Kèm phần "chưa đo, nói thẳng": chưa đo recall của tìm kiếm xấp xỉ | 4 — Xây dựng hệ thống, và 5 — Kiểm thử & đánh giá |

Lý do tệp này tồn tại dù gate không đòi: một index HNSW dựng sai lớp toán tử không báo lỗi, Postgres chỉ lặng lẽ quét tuần tự. "Có index trong `\d doc_chunks`" không phải bằng chứng; dòng `Index Scan using ix_doc_chunks_embedding` trong kế hoạch thực thi mới là.

Sơ đồ pipeline RAG và recommender **không** vẽ ở đây — theo kế hoạch, mọi hình vẽ dồn về Phase 7.
