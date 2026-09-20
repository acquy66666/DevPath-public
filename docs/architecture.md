# Kiến trúc hệ thống

## Sơ đồ tổng thể

```mermaid
flowchart LR
    subgraph Client
        W[Next.js Web App]
    end
    subgraph VPS["VPS — Docker Compose"]
        N[Nginx reverse proxy] --> W2[Next.js SSR]
        N --> A[FastAPI]
        A --> P[(PostgreSQL)]
        A --> R[(Redis)]
        A -->|enqueue| Q[Celery Queue - Redis broker]
        Q --> G[Grader Worker]
        G -->|docker run| S[Sandbox Containers<br/>network=none, cgroup limits]
        Q --> BW[Background Worker<br/>embedding, mail, certificate]
        A --> GM[Gemini API]
        BW --> GM
    end
    W --> N
    A --> R2[Cloudflare R2<br/>video HLS + assets]
    W -->|HLS segments| R2
    A --> PAY[VNPay / MoMo sandbox]
```

## Các thành phần

| Thành phần | Vai trò | Ghi chú |
|---|---|---|
| Next.js | UI, SSR trang public (SEO), client app cho trải nghiệm học | Không có business logic |
| FastAPI | REST API duy nhất, auth JWT, authorization | Layering: router → service → model |
| PostgreSQL | Nguồn chân lý dữ liệu | Full-text search bằng `tsvector` (đủ cho phạm vi khóa luận, khỏi cần Elasticsearch) |
| Redis | Cache, session/refresh token, leaderboard (sorted set), rate limit, Celery broker, pub/sub tiến độ chấm bài | |
| Celery workers | Job async: chấm bài, sinh embedding, sinh chứng chỉ PDF, gửi mail | Queue riêng cho grading (ưu tiên) và background |
| Grader | Nhận job, điều phối Docker sandbox, tổng hợp verdict | Chi tiết bảo mật: skill `sandbox-grading` |
| Cloudflare R2 | Video HLS, thumbnail, tài liệu | Egress miễn phí; upload qua presigned URL |
| Gemini API | Chatbot RAG, sinh quiz | Free tier; luôn có fallback khi API lỗi/quota |

## Ba luồng kỹ thuật trọng điểm

### 1. Chấm mã nguồn (⭐ điểm nhấn 1)

```
Submit code → API validate + tạo submission(pending) → Celery queue "grading"
→ Grader worker → docker run (image theo ngôn ngữ, cô lập hoàn toàn)
→ chạy từng test case → verdict per test → update DB
→ Redis pub/sub → client nhận realtime (WebSocket, fallback polling)

Lỗi phía hệ thống (SE) được thử lại 3 lần rồi "đỗ" hàng nộp bài lại ở trạng thái
`error` kèm lý do — không bao giờ ghi thành verdict. Sai, chậm, tràn bộ nhớ là
câu trả lời về bài nộp nên không thử lại.
```

**Pub/sub là lời kể, cơ sở dữ liệu là nguồn chân lý.** Redis pub/sub không có bộ
nhớ: phát cho ai đang nghe tại đúng khoảnh khắc đó, không hàng đợi, không phát
lại, không xác nhận. Nên WebSocket `/submissions/{id}/events` **mở đầu bằng một
snapshot đọc từ Postgres** và cứ 10 giây im lặng lại đọc thêm một cái. Một cơ
chế trả lời cả bốn hỏng hóc: client vào muộn, thông điệp mất lúc subscription
chưa sẵn sàng, kết nối Redis đứt, worker chết để lại dòng `running`.

Vì vậy "fallback polling" tồn tại ở hai tầng, không phải một: Redis chết thì
socket tự hạ cấp thành vòng đọc CSDL; WebSocket không mở được thì client chuyển
sang `GET /submissions/{id}`. Cả hai đường phát ra cùng một kiểu dữ liệu, và
kiểu ấy không có trường nào chứa output hay input — nên luật "test case ẩn
không rời máy chủ" không cần thêm bộ lọc nào trên đường realtime.

### 2. Chatbot RAG (⭐ điểm nhấn 3)

```
Ingest (async khi giảng viên upload): transcript/tài liệu → chunk (~500 token, overlap)
→ Gemini embedding → lưu pgvector
Query: câu hỏi học viên → embed → similarity search top-k (lọc theo course_id)
→ prompt Gemini kèm context + system prompt trợ giảng → trả lời có trích nguồn bài học
```

- Dùng **pgvector** ngay trong PostgreSQL — không thêm vector DB riêng.
- Chat history lưu DB (`chat_sessions`, `chat_messages`), giới hạn context window theo phiên: 6 tin gần nhất đi vào prompt, tài liệu chỉ gửi kèm lượt hiện tại.
- **Top-k chỉ lấy chunk của khóa đang `published` mà người hỏi đã ghi danh**, và điều kiện này nằm *trong câu truy vấn* (JOIN `courses` + EXISTS `enrollments`), không chỉ ở bước kiểm tra trước đó — unpublish cố ý giữ chunk lại để xuất bản lại khỏi tốn quota.
- Câu trả lời **stream bằng SSE** (`sources` → `delta`… → `done`/`error`); mọi lời từ chối (chưa ghi danh, rate limit, hết quota trước khi bắt đầu) là mã trạng thái thường vì xảy ra trước byte đầu tiên. Gemini có thể hỏng *giữa chừng* sau khi đã trả 200 — lúc đó không lưu gì, học viên thấy `error` và hỏi lại.
- Model sinh câu trả lời chọn bằng số đo (`gemini-3.5-flash-lite`), cấu hình qua `GEMINI_CHAT_MODEL`. Chi tiết và số liệu: `docs/report/assets/phase-4/chat-api.txt`.

### 3. Hybrid Recommender (⭐ điểm nhấn 2)

- **Content-based:** embedding (title + subtitle + category + description) → cosine similarity, giải quyết cold-start item — `backend/app/services/content_based.py`, bảng `course_embeddings` (một vector/khóa, không cắt theo chunk như `doc_chunks`: thứ đem so ở đây là cả khóa học). Nhúng bằng `taskType=SEMANTIC_SIMILARITY` vì hai vế cùng loại, trong khi RAG dùng cặp bất đối xứng `RETRIEVAL_DOCUMENT`/`RETRIEVAL_QUERY`. Đọc ra bằng `GET /courses/{id}/similar` (công khai), lọc `published` + chưa gỡ + cùng `embedding_model` **trong chính câu truy vấn**. Nhúng lúc publish và lại lúc 02:30 mỗi đêm — `PATCH` đổi mô tả mà không đụng `status` nên không có nút nào để treo job vào.
- **Collaborative filtering:** implicit feedback (enroll=1, hoàn thành=2, rating ≥4=3, lấy mức mạnh nhất; rating ≤2 kéo về 1) → **item-based CF** (cosine giữa các khóa học) — `backend/app/services/collaborative.py`. Đã cân nhắc ALS (thư viện `implicit`) và không chọn: với vài chục user, vector ẩn của ALS chủ yếu là nhiễu phụ thuộc seed, không kiểm tay được và không giải thích được vì sao gợi ý; item-based thì tất định và mỗi gợi ý kèm khóa học đã "sinh" ra nó.
- **Hybrid:** **Reciprocal Rank Fusion** (Cormack–Clarke–Buettcher 2009, k = 60), không phải weighted blend trên điểm thô — `backend/app/services/hybrid.py`. Lý do đo được: điểm collaborative là một *tổng* chạy 0,02–5,79 còn cosine content-based chạy 0,747–0,892, không cùng thang; và content-based cho **mọi** khóa ít nhất 0,747 nên cộng vào sẽ đè tín hiệu collaborative thật. RRF chỉ dùng thứ hạng. Trọng số hai nửa bằng nhau cho tới khi `eval_recommender.py` đo được. Mỗi gợi ý mang theo `sources` (`collaborative` / `content` / cả hai / `popular`).
- **Fallback:** phổ biến theo danh mục, chèn **lúc phục vụ** chứ không qua cache (`recommendations.popular_courses`) — một luật phủ cả ba cảnh: user mới batch chưa từng thấy, user mô hình không có gì để nói, và user có danh sách bị cắt ngắn bởi vòng kiểm tra lại. Xếp theo lĩnh vực trước, `students_count` sau; danh mục đọc từ `enrollments` để bắt được cả người vừa ghi danh sáng nay. Hàng lấp chỗ mang `score` = 0 và `because` = null: phổ biến không phải điểm của mô hình.
- **Cái giá của hệ lai, đo được:** trên chỉ số "top-3 đúng cụm" của dữ liệu giả lập, hybrid 0,8056 so với collaborative đơn thuần 0,8333. Đổi lại, mô phỏng khóa vừa xuất bản cho thấy CF gợi ý được **0/24** khóa mới còn hybrid **24/24**. Chi tiết: `docs/report/assets/phase-4/hybrid-blend.txt`.
- Tính offline theo batch (Celery beat, mỗi đêm), cache kết quả top-N per user vào Redis. Hai job khác nhau: `embed_courses` 02:30 (giữ `course_embeddings` khớp với catalogue) và `rebuild_recommendations` 03:00 (khớp ma trận tương tác rồi ghi Redis). "Khóa học tương tự" **không** đi qua cache — nó tính từ bảng vector ngay trong request, vì đầu vào là khóa đang xem chứ không phải người đang xem.
- Đánh giá: precision@k, recall@k trên tập held-out từ dữ liệu seed — script tại `backend/scripts/eval_recommender.py`.

## Quyết định kiến trúc đã chốt

| Quyết định | Lý do |
|---|---|
| Monolith FastAPI + workers (không microservices) | Một người làm trong 14 tuần; tách process theo vai trò (API/worker) là đủ "hệ phân tán" để trình bày |
| pgvector thay vì vector DB riêng | Ít moving part, đủ quy mô demo |
| Postgres FTS thay vì Elasticsearch | Như trên |
| WebSocket cho kết quả chấm, fallback polling | Realtime là điểm demo ăn tiền |
| Python-only grading ở v1 | Image per-language thiết kế sẵn chỗ mở rộng |
| Worker chấm bài giữ socket Docker, và là container duy nhất được giữ | Chấm bài *là* việc khởi động container, nên tiến trình chấm phải nói chuyện được với daemon. Socket không phải hệ thống phân quyền: container nào cầm nó cũng khởi động được container tùy ý trên host. Đổi lại, nó không phục vụ HTTP, không mở ra ngoài, và không tự chạy dòng code nào của người nộp — mọi dòng đó chạy trong container dùng một lần mà nó tạo ra |
