# Bằng chứng Phase 4 — AI Features ⭐

Phase đang chạy. Bảng dưới là gate cuối phase (chép từ [kế hoạch](../../../plan/phase-4-ai-features.md)) và chỗ bằng chứng sẽ nằm — dòng nào chưa có tệp thì việc tương ứng chưa làm.

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Bảng precision@k / recall@k, script tái tạo được | `recommender-eval.md` (script `backend/scripts/eval_recommender.py`) | chưa có |
| 3–5 hội thoại chatbot có trích nguồn, kèm 1 ca từ chối ngoài phạm vi | — | chưa có |
| Bộ 20 câu hỏi đánh giá chatbot + bảng kết quả | — | chưa có |
| Ví dụ quiz sinh tự động kèm nhận xét chất lượng | — | chưa có |
| Screenshot khối gợi ý của 2 user sở thích khác nhau | — | chưa có |

## Ngoài gate, đã thu

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `recommendation-batch.txt` | Job hằng đêm chạy thật: 4 key `rec:v1:user:*` trong Redis, TTL ~48 giờ, điểm `0,7071 = 1/√2` kiểm được bằng tay, log beat đọc đúng lịch 03:00. Kèm phần "chưa đo, nói thẳng": chưa có precision@k vì CSDL dev chỉ có 5 tương tác | 4 — Xây dựng hệ thống |
| `hnsw-index.txt` | `EXPLAIN (ANALYZE, BUFFERS)` chứng minh planner **thật sự** chọn `ix_doc_chunks_embedding`: 1,33 ms / 1239 buffer so với 5,89 ms / 9055 buffer khi tắt index scan, trên 3000 chunk. Kèm phần "chưa đo, nói thẳng": chưa đo recall của tìm kiếm xấp xỉ | 4 — Xây dựng hệ thống, và 5 — Kiểm thử & đánh giá |

Lý do tệp này tồn tại dù gate không đòi: một index HNSW dựng sai lớp toán tử không báo lỗi, Postgres chỉ lặng lẽ quét tuần tự. "Có index trong `\d doc_chunks`" không phải bằng chứng; dòng `Index Scan using ix_doc_chunks_embedding` trong kế hoạch thực thi mới là.

Sơ đồ pipeline RAG và recommender **không** vẽ ở đây — theo kế hoạch, mọi hình vẽ dồn về Phase 7.
