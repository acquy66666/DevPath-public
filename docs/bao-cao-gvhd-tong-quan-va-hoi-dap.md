# DevPath — Báo cáo tiến độ cho giáo viên hướng dẫn

> Tài liệu chuẩn bị cho buổi gặp GVHD (soạn 18/10/2026). Phần A trình bày dự án là gì, đang ở đâu và từng tính năng chạy thế nào. Phần B là các câu giáo viên có thể hỏi để kiểm tra mức hiểu, kèm gợi ý trả lời.
> Số liệu lấy từ repo và các lần đo đã lưu trong `docs/report/assets/`. Đọc một con số ở đây thì nên biết nó nằm ở tệp nào (cột "Bằng chứng").

**Đề tài:** *Xây dựng nền tảng học trực tuyến tích hợp AI với hệ thống chấm mã nguồn tự động và gợi ý khóa học cá nhân hóa.*
**Tên sản phẩm:** DevPath. **Địa chỉ chạy thật:** <https://devpath-01.me>

---

# PHẦN A — DỰ ÁN

## 1. Tổng quan trong một phút

DevPath là một trang **học lập trình trực tuyến**, giống Udemy nhưng có thêm ba thứ mà Udemy không có:

1. **Chấm code tự động.** Học viên viết code Python ngay trên trình duyệt, bấm "Nộp bài". Hệ thống chạy code đó với nhiều bộ dữ liệu thử (test case) trong một "phòng cách ly", rồi báo đúng/sai cho từng test **ngay lúc đang chấm**.
2. **Trợ giảng AI.** Học viên hỏi về bài học; AI trả lời **chỉ dựa trên tài liệu của khóa học**, có ghi nguồn "[1]" bấm vào là mở đúng bài. Hỏi ngoài phạm vi thì AI từ chối.
3. **Gợi ý khóa học cá nhân hóa.** Mỗi người thấy danh sách "Gợi ý cho bạn" khác nhau, dựa trên hành vi học của mọi người và nội dung các khóa.

Ngoài ra là đầy đủ những gì một sàn học trực tuyến cần: tài khoản (có đăng nhập Google), video bài giảng, quiz, ghi chú, hỏi đáp, giỏ hàng + mã giảm giá + thanh toán VNPay, điểm thưởng XP + chuỗi ngày học + bảng xếp hạng, chứng chỉ PDF, khu giảng viên soạn khóa và xem doanh thu, khu quản trị duyệt khóa và xử lý báo cáo vi phạm.

**Ba vai người dùng:** học viên, giảng viên, quản trị viên (admin).

## 2. Đang ở giai đoạn nào

Dự án chia 8 giai đoạn (phase). Mỗi phase có "cổng" (gate): phải demo được thì mới sang phase sau.

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 1 — Nền móng | Thiết kế CSDL, dựng khung dự án, CI | ✅ Xong (tag `phase-1-done`) |
| 2 — Nền tảng chính | Tài khoản, khóa học, video, tiến độ học | ✅ Xong (`phase-2-done`) |
| 3 — Chấm code ⭐ | Sandbox Docker, hàng đợi, kết quả realtime | ✅ Xong (`phase-3-done`) |
| 4 — AI ⭐ | Trợ giảng RAG, sinh quiz, hệ gợi ý | ✅ Xong (`phase-4-done`) |
| 5 — Thương mại & quản trị | Giỏ hàng, VNPay, XP, chứng chỉ, admin | ✅ Xong (`phase-5-done`) |
| 6 — Gia cố & triển khai | Bảo mật, kiểm thử, sao lưu, giám sát, tên miền thật | 🟡 **33/40 việc** — phần chưa xong đều chờ máy chủ thật |
| 7 — Nâng cấp giao diện | Bộ nhận diện riêng, nhân vật linh vật, thiết kế lại các màn | 🔵 Vừa bắt đầu |
| 8 — Báo cáo & bảo vệ | Viết báo cáo, slide, tổng duyệt | ⏳ Chưa |

**Nói ngắn:** tính năng đã đủ: **18/20** tính năng trong đề cương chạy thật. Hai mục bị cắt theo danh sách cắt giảm: thanh toán MoMo (đã có VNPay) và phụ đề trên video (tệp phụ đề vẫn được dùng làm tài liệu cho trợ giảng AI). Site đang chạy ở chế độ production trên tên miền thật `devpath-01.me`. Việc còn lại của Phase 6 là đưa lên máy chủ thật (Azure for Students). Sau đó sang Phase 7 làm đẹp giao diện.

Ngày 18/10 đã chạy trọn "luồng vàng" trên tên miền thật: đăng nhập Google → mua khóa qua VNPay → học → nộp code → nhận chứng chỉ (`docs/report/assets/phase-6/gvhd-milestone.txt`).

## 3. Kiến trúc tổng thể — các bộ phận nói chuyện với nhau thế nào

```
 Trình duyệt ──HTTPS──► Cloudflare ──đường hầm──► nginx (cổng vào, TLS, header bảo mật)
                                                     │
                     ┌───────────────────────────────┼──────────────────────────────┐
                     ▼                               ▼                              ▼
              Next.js (giao diện)            FastAPI (API)                 RustFS (kho tệp:
                                              │      │                      video, ảnh, PDF)
                                              │      └──► Redis (bộ nhớ nhanh: hàng đợi,
                                              │            bảng xếp hạng, giới hạn tần suất)
                                              ▼
                                     PostgreSQL + pgvector (dữ liệu chính + vector AI)
                                              ▲
                    Celery worker ────────────┘  (việc chạy nền: chuyển mã video, nạp tài liệu AI,
                    Grading worker ──► Docker proxy ──► container sandbox (chấm code)
                    Gemini API (Google) ◄── gọi khi cần AI
```

Cách hiểu đơn giản: **Next.js** là "mặt tiền" người dùng nhìn thấy; **FastAPI** là "quầy nghiệp vụ" xử lý mọi yêu cầu; **PostgreSQL** là "kho hồ sơ"; **Redis** là "bảng ghi chú dán tường" cho thứ cần nhanh; **Celery** là "nhân viên hậu trường" làm việc lâu (chấm bài, xử lý video) để người dùng không phải chờ; **Docker** đóng gói từng bộ phận thành "hộp" chạy giống hệt nhau ở mọi máy.

**Tech stack** (chốt trong đề cương):

| Thành phần | Công nghệ | Dùng để làm gì |
|---|---|---|
| Giao diện | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query | Render trang ở server cho SEO; component giao diện; quản lý dữ liệu tải từ API |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic | Nhận request, kiểm dữ liệu vào, đọc/ghi CSDL, quản lý thay đổi cấu trúc bảng |
| CSDL | PostgreSQL 16 + pgvector | 41 bảng nghiệp vụ; tìm kiếm toàn văn; lưu và so khớp vector của AI |
| Bộ nhớ nhanh, hàng đợi | Redis 7, Celery | Hàng đợi việc nền, bảng xếp hạng, cache gợi ý, giới hạn tần suất |
| Chấm code | Docker (container dùng một lần) | Chạy code người dùng trong môi trường cách ly |
| AI | Google Gemini API: `gemini-3.5-flash-lite` (trả lời, sinh quiz), `gemini-embedding-001` (vector 768 chiều) | Trợ giảng, sinh câu hỏi, đo độ giống nội dung |
| Video | ffmpeg → HLS, hls.js | Cắt video thành đoạn nhỏ để phát mượt |
| Kho tệp | RustFS (máy chủ S3 tự host) | Lưu video, ảnh, PDF; đổi sang Cloudflare R2 chỉ bằng cấu hình |
| Thanh toán | VNPay sandbox | Cổng thanh toán Việt Nam |
| Triển khai | Docker Compose, nginx, Cloudflare Tunnel, GitHub Actions (CI) | Chạy toàn bộ hệ thống bằng một lệnh; kiểm tra tự động mỗi lần đẩy code |

**Quy mô code:** 160 endpoint API (tính cả 1 WebSocket), 41 bảng, 29 lần thay đổi cấu trúc CSDL (migration). Hơn 2.250 ca kiểm thử tự động chạy trên CI.

**Cách tổ chức code backend:** ba lớp *router → service → model*. Router chỉ nhận/trả HTTP, mọi luật nghiệp vụ nằm ở service, model mô tả bảng. Nhờ vậy cùng một luật (ví dụ "đã thanh toán thì ghi danh") được dùng ở mọi nơi và kiểm thử được riêng.

---

## 4. Từng tính năng — làm gì, chạy thế nào, dùng kỹ thuật gì

> Mỗi tính năng có bốn phần: **Là gì** · **Chạy thế nào (lời thường)** · **Kỹ thuật & kiến thức** · **Đã kiểm chứng ra sao**.

### 4.1. ⭐ Chấm code tự động trong sandbox, kết quả theo thời gian thực

**Là gì.** Bài học loại "bài tập code" có đề bài, vài test mẫu (thấy được) và test ẩn (không thấy). Học viên viết code Python trong trình soạn thảo Monaco (cùng lõi với VS Code), bấm **"Chạy thử"** (chỉ chấm test mẫu, không lưu) hoặc **"Nộp bài"** (chấm tất cả, có điểm, vào lịch sử).

**Chạy thế nào.**
1. Bấm "Nộp bài" → bài nộp được ghi vào CSDL và **xếp hàng** (như bốc số ở ngân hàng). Trang không bị treo chờ.
2. Một "nhân viên chấm bài" (grading worker) lấy bài ra khỏi hàng. Với **mỗi test case**, nó mở một **phòng cách ly dùng một lần** (container Docker): bỏ code vào, đưa dữ liệu test vào, đợi chương trình in kết quả, so với đáp án, rồi **phá phòng**.
3. Phòng cách ly bị khóa chặt: **không có Internet**, ổ đĩa **chỉ đọc**, không có quyền quản trị, giới hạn 0,5 CPU, 256 MB RAM, tối đa 64 tiến trình, 5 giây CPU (tùy bài). Code có cố phá cũng chỉ phá được căn phòng sắp bị dỡ.
4. Chấm xong test nào, worker **báo ngay** qua Redis → backend đẩy xuống trình duyệt qua **WebSocket** (một đường dây luôn mở). Học viên thấy test 1 xanh, test 2 xanh, test 3 đỏ… lần lượt, không cần tải lại trang.
5. Kết quả tổng là một trong **7 "verdict"**: AC (đúng), WA (sai kết quả), TLE (quá thời gian), MLE (quá bộ nhớ), RE (lỗi khi chạy), CE (lỗi cú pháp), SE (lỗi hệ thống). Đúng hết thì bài học tự đánh dấu hoàn thành và cộng XP.

**Kỹ thuật & kiến thức.**
- **Docker** với các cờ bảo mật: `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, user không phải root (uid 10001), `--memory` = `--memory-swap` (không cho dùng swap để vượt giới hạn RAM), `--pids-limit` (chặn fork bomb), `--ulimit cpu` + timeout ngoài (**timeout hai lớp**: một lớp trong container, một lớp đo đồng hồ ngoài).
- **Docker socket proxy tự viết** (`grader/proxy/`). Worker chấm bài **không cầm** quyền điều khiển Docker trực tiếp (cầm socket Docker gần như là có quyền root trên máy). Mọi lệnh phải qua một proxy chỉ cho tạo **đúng một kiểu** container sandbox với đúng các cờ trên.
- **Hàng đợi Celery** riêng cho chấm bài, chạy 2 bài song song (`GRADING_CONCURRENCY=2`). Con số này chọn bằng benchmark: chạy nhiều hơn thì tổng nhanh hơn chút, nhưng từng người phải chờ lâu hơn.
- **Redis pub/sub + WebSocket** cho kết quả realtime; trang có cơ chế **dự phòng bằng polling** (hỏi lại định kỳ) nếu WebSocket bị chặn.
- **Rate limit hai cửa**: hai lần nộp của một người cách nhau ít nhất 10 giây, và tối đa 40 lần mỗi giờ. Một bài nộp là nhiều container và vài giây máy, nên phải chống spam hàng đợi.
- Kiến thức: hệ điều hành (tiến trình, tín hiệu SIGXCPU/SIGKILL, cgroup), bảo mật (cô lập, nguyên tắc quyền tối thiểu), hệ phân tán (hàng đợi, pub/sub).

**Đã kiểm chứng.**
- **7 kiểu tấn công** đều bị chặn, có test tự động trong CI: đọc tệp ngoài thư mục được cấp, gọi mạng, fork bomb, ghi vào hệ thống tệp gốc, làm đầy `/tmp`, leo thang quyền, tự tắt container của mình. Thêm một bộ test riêng cho giới hạn tài nguyên: ăn hết RAM, vòng lặp vô hạn, chương trình bắt tín hiệu để không chịu dừng, in ra vô tận.
- Đo tải "lớp 20 người cùng nộp": một người nộp xong trong khoảng 3 giây; người cuối chờ 35–50 giây vì xếp hàng (`phase-6/load-test.md`).
- Mỗi test case mất khoảng 0,3–0,7 giây (phần lớn là thời gian dựng và hủy container).

### 4.2. ⭐ Trợ giảng AI (RAG — trả lời dựa trên tài liệu khóa học)

**Là gì.** Trong trang học có tab **"Trợ giảng AI"**. Học viên hỏi bằng tiếng Việt; câu trả lời hiện dần từng chữ, có số **[1], [2]** bấm vào mở đúng bài học được trích. Hỏi chuyện ngoài khóa ("thủ đô nước Úc", "viết bài thơ") thì trợ giảng từ chối.

**Chạy thế nào (ví dụ "mở sách trước khi trả lời").**
1. **Lúc khóa học được duyệt:** hệ thống lấy toàn bộ bài đọc và lời giảng video (tệp `.srt`), cắt thành các **đoạn ~500 "token"** (gối đầu nhau ~75 token để không đứt ý). Mỗi đoạn được Gemini chuyển thành một **vector 768 con số**, như một "tọa độ ý nghĩa": hai đoạn cùng ý thì nằm gần nhau. Các vector lưu vào PostgreSQL (pgvector).
2. **Lúc học viên hỏi:** câu hỏi cũng được chuyển thành vector. CSDL tìm **6 đoạn gần nhất** (top-k = 6) trong đúng khóa đó. Câu hỏi nối tiếp ("cho ví dụ cách sửa đó") được tìm thêm một lần kèm câu trước để hiểu ngữ cảnh.
3. Hệ thống gửi cho Gemini: **luật** ("chỉ trả lời từ các đoạn dưới đây, ghi nguồn bằng [n], không có thì từ chối") + **các đoạn tài liệu** + **câu hỏi**.
4. Câu trả lời được **stream** về trình duyệt bằng **SSE** (Server-Sent Events: server gửi dần từng mẩu), nên chữ hiện ra ngay chứ không phải chờ cả câu.
5. Chỉ học viên **đã ghi danh** mới hỏi được. Điều kiện "khóa đã xuất bản + người hỏi đã ghi danh" nằm **ngay trong câu truy vấn** tìm đoạn tài liệu, nên không thể lấy nhầm tài liệu khóa khác.

**Kỹ thuật & kiến thức.** RAG (Retrieval-Augmented Generation), embedding, độ tương đồng cosine, chỉ mục **HNSW** của pgvector (tìm láng giềng gần đúng, nhanh với nhiều vector), prompt engineering (luật trích dẫn, luật từ chối, chống "prompt injection" kiểu "bỏ qua mọi quy tắc"), SSE streaming, Celery để nạp tài liệu chạy nền, một **lớp adapter** bọc Gemini (đổi nhà cung cấp AI chỉ sửa một chỗ; tự thử lại khi Gemini lỗi tạm thời).

**Đã kiểm chứng.** Bộ 20 câu × 3 lần = 60 lượt: **58/60 đạt**. Bài đúng xếp hạng 1 ở **42/42** câu cần trả lời. Từ chối đúng **18/18** câu ngoài phạm vi, kể cả câu tấn công kiểu "bỏ qua mọi quy tắc…" (`phase-4/chatbot-eval.txt`).

### 4.3. ⭐ Gợi ý khóa học cá nhân hóa (hệ gợi ý lai)

**Là gì.** Trang chủ có khối **"Gợi ý cho bạn"** (khác nhau theo từng người); trang khóa học có **"Khóa học tương tự"**; học xong một khóa có **"Học tiếp theo"**.

**Chạy thế nào.** Hai "chuyên gia" cùng chấm điểm, rồi gộp ý kiến:
- **Lọc cộng tác theo khóa (item-based collaborative filtering).** Chuyên gia "thói quen": *"những ai đã học khóa A thường học cả khóa B"*. Hệ thống tính độ giống giữa các khóa dựa trên những người học chung.
- **Theo nội dung (content-based).** Chuyên gia "nội dung": mỗi khóa (tiêu đề + mô tả + danh mục) thành một vector bằng Gemini; khóa có vector gần nhau là khóa giống nhau.
- **Gộp bằng Reciprocal Rank Fusion (RRF, k = 60).** Không cộng điểm thô, vì hai chuyên gia chấm theo thang khác nhau. Mỗi bên đưa ra **thứ hạng**, khóa nào được cả hai xếp cao thì lên đầu.
- **Người mới chưa có lịch sử:** gợi ý khóa phổ biến theo danh mục.
- Tính sẵn **mỗi đêm lúc 3:00** (Celery beat), lưu vào Redis 48 giờ. Mở trang chỉ việc đọc ra, không tính lại.

**Kỹ thuật & kiến thức.** Hệ gợi ý (collaborative filtering, content-based, hybrid), độ tương đồng cosine, RRF, bài toán **cold-start** (khóa mới chưa ai học), đánh giá bằng **Recall@K** với kiểm định chéo 5 phần (cắt theo học viên).

**Đã kiểm chứng** (`phase-4/recommender-eval.md`):
- Người dùng cũ: **Recall@5 = 0,884**. Đơn thuần theo độ phổ biến chỉ đạt 0,178, còn thấp hơn chọn ngẫu nhiên (0,239).
- Khóa vừa xuất bản (cold-start): lọc cộng tác đơn thuần không gợi ý được khóa đó, còn hệ lai đạt **Recall@5 = 0,626**.
- Chính lần đánh giá này phát hiện một lỗi thật: khóa mới luôn bị đẩy xuống cuối. Sửa bằng cách chỉ đưa top-5 mỗi bên vào bước gộp.

### 4.4. ⭐ Sinh quiz bằng AI (giảng viên duyệt)

**Là gì.** Giảng viên tạo bài quiz, bấm "Sinh câu hỏi bằng AI" → Gemini đọc nội dung bài giảng (bài đọc hoặc lời giảng video) và đề xuất câu hỏi trắc nghiệm.

**Chạy thế nào.** Câu do AI sinh được đánh dấu "nháp". **Quiz còn câu chưa duyệt thì không xuất bản được** (backend trả lỗi 409): giảng viên phải xem, sửa hoặc xóa từng câu. Không có nút "duyệt tất cả" — cố ý, để AI không bao giờ đưa câu sai thẳng tới học viên. Học viên làm quiz có **đồng hồ đếm ngược do server giữ giờ** (tự chỉnh giờ máy cũng vô ích), ân hạn 10 giây, nộp tự chấm.

**Kỹ thuật.** Gemini ở chế độ trả JSON theo schema, kiểm đáp án bằng so khớp từ (bắt được câu có đáp án lệch nội dung), "human-in-the-loop".

**Đã kiểm chứng.** 30/30 câu sinh ra có đáp án đúng, khoảng 3 giây mỗi lượt (`phase-4/quiz-generation.txt`).

### 4.5. Video bài giảng, nhớ tiến độ

**Là gì.** Giảng viên tải video lên; học viên xem, đổi tốc độ, thoát ra vào lại thì **phát tiếp đúng chỗ cũ**.

**Chạy thế nào.**
- **Tải lên:** trình duyệt **không gửi video qua server API**. Server chỉ cấp một **"vé vào cửa có hạn" (presigned URL)**: ký cho đúng một tệp, đúng loại, **đúng kích thước**. Trình duyệt gửi thẳng tệp vào kho lưu trữ; gửi sai kích thước 1 byte là bị từ chối (403).
- **Xử lý:** một worker nền dùng **ffmpeg** chuyển video sang **HLS**: cắt thành nhiều đoạn vài giây kèm một "mục lục" (playlist `.m3u8`). Trình phát (hls.js) tải từng đoạn khi cần, nên tua nhanh và đỡ tốn băng thông.
- **Nhớ tiến độ:** cứ **10 giây** trình duyệt báo vị trí một lần ("nhịp tim"); thêm lúc bấm dừng, chuyển tab, rời trang. Vì vậy không bao giờ mất quá 10 giây.

**Kỹ thuật.** Object storage chuẩn S3 (RustFS), chữ ký AWS SigV4, ffmpeg, HLS. Bảo mật: ffmpeg chỉ được đọc tệp cục bộ, đúng định dạng video (chặn kiểu tấn công giả playlist để đọc tệp trên máy chủ), chỉ nhận đuôi .mp4/.m4v/.mov/.mkv/.webm; giới hạn số lần xin vé tải lên mỗi tài khoản để không ai làm đầy đĩa.

### 4.6. Tìm kiếm khóa học tiếng Việt

**Là gì.** Gõ **"lap trinh"** không dấu vẫn ra "Lập trình". Lọc theo danh mục, giá (miễn phí/có phí), đánh giá; mỗi trạng thái lọc là một đường link chia sẻ được.

**Chạy thế nào.** PostgreSQL bỏ dấu (`unaccent`) cả chữ trong khóa học lẫn chữ người gõ, rồi tìm bằng **full-text search**. Từ khớp ở tiêu đề được điểm cao hơn phụ đề, phụ đề cao hơn mô tả (trọng số A/B/C), xếp theo `ts_rank`.

**Kiến thức.** Chỉ mục toàn văn (cột `search_vector` kiểu tsvector, chỉ mục GIN), chuẩn hóa văn bản tiếng Việt, SSR + SEO (trang chi tiết khóa có sẵn nội dung trong HTML đầu tiên, có thẻ canonical/Open Graph cho máy tìm kiếm).

### 4.7. Tài khoản, đăng nhập Google, phân quyền

**Là gì.** Đăng ký bằng email hoặc **đăng nhập bằng Google**; ba vai học viên / giảng viên / admin.

**Chạy thế nào.**
- Mật khẩu không lưu dạng chữ mà lưu **băm bcrypt** (không đảo ngược được).
- Đăng nhập xong nhận hai thứ:
  - **thẻ ra vào (access token, JWT) sống 15 phút**, giữ trong bộ nhớ trang;
  - **phiếu đổi thẻ (refresh token)**, nằm trong cookie **HttpOnly** (JavaScript không đọc được, nên mã độc XSS không lấy được).
- Mỗi lần đổi thẻ thì phiếu cũng được thay (**xoay vòng**). Nếu một phiếu đã dùng rồi mà bị dùng lại sau 30 giây ân hạn, hệ thống coi là bị đánh cắp và **thu hồi mọi phiên** của người đó.
- **Google OAuth:** bấm nút → sang trang Google → Google gửi lại một mã → server đổi mã lấy thông tin người dùng. Có cookie `state` chống giả mạo (CSRF). Redirect URI cố định nhờ tên miền thật.
- **Giới hạn tần suất (rate limit):** quá 10 lần đăng nhập trong 15 phút cho một email, hoặc 100 lần cho một IP (đếm cả lần đúng) → chặn tạm (HTTP 429); đăng ký 50 lần/giờ/IP.

**Kiến thức.** JWT, OAuth 2.0 / OpenID Connect, bảo mật cookie (HttpOnly, Secure, SameSite), băm mật khẩu, phát hiện token bị đánh cắp, rate limit bằng Redis. Một **test ma trận phân quyền** liệt kê *mọi* route API kèm luật ai được gọi; thêm route mới mà quên khai luật thì test đỏ.

### 4.8. Giỏ hàng, mã giảm giá, thanh toán VNPay

**Là gì.** Thêm khóa có phí vào giỏ, nhập mã (ví dụ `CHAOMUNG50` giảm 50 %), bấm "Thanh toán qua VNPay" → sang trang của VNPay → thanh toán xong được ghi danh.

**Chạy thế nào.**
1. Tạo **đơn hàng** với giá đóng băng tại thời điểm mua.
2. Server tạo **đường link thanh toán có chữ ký HMAC-SHA512**, giống "con dấu": ai sửa số tiền trên link thì chữ ký không khớp, VNPay từ chối.
3. Thanh toán xong, VNPay **gọi thẳng vào server** (gọi là **IPN**). **Chỉ IPN mới được quyền nói "đã trả tiền"**. Trang người dùng quay về chỉ dùng để hiển thị, vì tham số trên trình duyệt thì ai cũng sửa được.
4. Server kiểm theo thứ tự: chữ ký → có đơn không → khớp số tiền → đơn còn chờ không → mã kết quả. Rồi trong **một giao dịch CSDL duy nhất**: đánh dấu đã trả → ghi danh → trừ lượt mã giảm giá → bỏ khỏi giỏ. VNPay gửi lại IPN nhiều lần cũng chỉ xử lý một lần (**idempotent**, khóa dòng `SELECT … FOR UPDATE`).
5. **Đơn 0đ** (mã giảm 100 %) được tất toán ngay, không sang VNPay.

**Giới hạn đã chốt (nói thẳng nếu bị hỏi).** Không làm bước thanh toán thật bằng thẻ test trên VNPay, vì VNPay chưa khai địa chỉ IPN của dự án (cổng merchant không có ô tự khai; đã gửi mail kỹ thuật VNPay). Demo dùng **IPN giả lập**: một script ký callback bằng **đúng khóa bí mật** server dùng và gửi vào **đúng endpoint**, nên mọi bước kiểm vẫn chạy thật. Trang sandbox thật của VNPay **đã nhận** link do server ký, tức mã merchant và chữ ký đều đúng.

**Kiến thức.** Chữ ký số HMAC, giao dịch CSDL (ACID), khóa dòng, idempotency, xử lý cạnh tranh (hai người cùng dùng lượt cuối của mã giảm giá → câu `UPDATE … WHERE used_count < max_uses`).

### 4.9. XP, chuỗi ngày học, bảng xếp hạng

**Là gì.** Hoàn thành bài +10 XP, quiz đạt +20, giải bài code +30; chuỗi ngày học liên tiếp; bảng xếp hạng tuần / tháng / mọi thời gian.

**Chạy thế nào.** XP ghi vào một **"sổ cái" chỉ thêm dòng, không sửa** (`xp_events`). Mỗi việc chỉ cộng một lần (ràng buộc duy nhất trong CSDL). Bảng xếp hạng là **Redis sorted set**, một danh sách luôn được xếp sẵn theo điểm, nên đọc thứ hạng rất nhanh mà không phải cộng dồn lại. Redis mất dữ liệu thì dựng lại được từ sổ cái. Ngày tính theo **giờ Việt Nam**; chuỗi tự về 0 khi đọc nếu bỏ học quá một ngày (không cần job chạy lúc nửa đêm).

### 4.10. Chứng chỉ PDF có mã xác thực

Học xong 100 % bài → tự cấp chứng chỉ: mã 16 ký tự + **QR code**. Ai quét QR hoặc mở `devpath-01.me/cert/<mã>` cũng xác thực được (trang công khai). PDF vẽ bằng **WeasyPrint** (HTML → PDF) trong worker nền. Tên người nhận và tên khóa được "đóng băng" lúc cấp, nên sau này đổi tên khóa thì chứng chỉ cũ không đổi.

### 4.11. Cộng đồng: hỏi đáp, thông báo, đánh giá, ghi chú

- **Hỏi đáp theo bài học** (có upvote, câu trả lời của giảng viên có huy hiệu, đánh dấu "đã giải quyết"). Học viên hỏi thì giảng viên nhận **thông báo**; có người trả lời thì người hỏi nhận thông báo (chuông trên header).
- **Đánh giá & xếp hạng** khóa học: điểm trung bình tính lại ngay trong cùng giao dịch, có khóa dòng để hai người đánh giá cùng lúc không ghi đè nhau.
- **Ghi chú theo mốc thời gian video**: bấm vào nhãn `mm:ss` thì video tua đúng giây đó. Có đánh dấu bài để xem lại.

### 4.12. Khu giảng viên

- **Soạn khóa:** tạo chương, bài; **kéo-thả** để sắp xếp (có cả thao tác bằng bàn phím cho người khiếm thị); tải video, lời giảng; soạn bài tập code (đề, test mẫu, test ẩn, giới hạn thời gian); soạn quiz.
- **Gửi duyệt:** khóa dừng ở trạng thái "chờ duyệt" tới khi admin duyệt.
- **Thống kê:** doanh thu, học viên mới, tỉ lệ hoàn thành theo 7 / 30 / 90 ngày / 12 tháng, so với kỳ trước, có "xem dạng bảng". Doanh thu chia đúng phần giảm giá cho từng khóa trong cùng một đơn.

### 4.13. Khu quản trị (admin)

Tổng quan toàn sàn (doanh thu, người dùng hoạt động trong ngày, khóa hot); **duyệt / từ chối / gỡ khóa học** (bắt buộc ghi lý do, giảng viên nhận thông báo); xử lý **báo cáo vi phạm** (gỡ nội dung ngay trong một giao dịch); khóa tài khoản (thu hồi mọi phiên); quản lý danh mục, mã giảm giá, banner trang chủ.

### 4.14. Hạ tầng, bảo mật, triển khai

- **Docker Compose:** cả hệ thống (13 dịch vụ ở bản production) dựng bằng một lệnh, giống hệt nhau ở máy em, máy CI và máy chủ.
- **Đưa lên mạng 0 đồng:** tên miền `.me` miễn phí (GitHub Student Pack) + **Cloudflare Tunnel**. Máy chủ không cần mở cổng ra Internet: một tiến trình `cloudflared` từ bên trong **gọi ra** Cloudflare, và Cloudflare đưa khách vào theo đường đó. Chứng chỉ HTTPS là của Cloudflare.
- **nginx:** cổng vào duy nhất, TLS, header bảo mật. **Content-Security-Policy** (bật enforce 18/10) chỉ cho trang chạy script của chính nó. Nhờ vậy nó chặn luôn cả script phân tích mà Cloudflare tự chèn vào trang.
- **IP thật của người dùng** sau tunnel: nginx chỉ tin header `CF-Connecting-IP` khi request đến từ đúng địa chỉ của cloudflared. Nhờ vậy giới hạn đăng nhập tính đúng theo từng người.
- **Sao lưu CSDL mỗi đêm** lên kho riêng (giữ 14 bản), đã **diễn tập khôi phục thật**: 41/41 bảng giống hệt từng dòng. Trên máy demo hiện **tạm tắt** vì chưa có nơi lưu ngoài máy (Backblaze B2); bật khi lên máy chủ thật.
- **Giám sát:** script chạy trên máy chủ mỗi phút (container sống, trang trả lời, chứng chỉ còn hạn, đĩa còn chỗ), báo qua điện thoại (ntfy). Đã diễn tập 10 kịch bản; cài thật khi có máy chủ Linux.
- **CI (GitHub Actions)** 6 job mỗi lần đẩy code: test backend trên Postgres + Redis thật, build ảnh sandbox và chạy bộ tấn công, kiểm migration lên-xuống-lên, kiểm cấu hình nginx/compose, build frontend, chạy E2E toàn hệ thống.

### 4.15. Kiểm thử và chất lượng

| Loại | Số lượng / kết quả | Bằng chứng |
|---|---|---|
| Test backend (pytest, CSDL thật) | 1.873 ca, 0 bỏ qua (CI 13/10); coverage **94,5 %** | `phase-6/test-summary.md` |
| Test chấm bài + tấn công sandbox | 283 ca + 59 ca chạy lại qua proxy; 7/7 kiểu tấn công bị chặn | như trên |
| E2E (Playwright) | 1 kịch bản đi trọn: đăng ký → mua → học → nộp code → chứng chỉ, chạy cả trên tên miền thật | `phase-6/e2e-golden-flow.txt`, `gvhd-milestone.txt` |
| Tổng ca tự động trên CI | **2.256** (13/10) | `phase-6/test-summary.md` |
| Tải | API danh sách 7 ms trung vị ở 100 người dùng ảo; trang tới 148,6 request/giây | `phase-6/load-test.md` |
| Rà soát bảo mật | Ma trận phân quyền mọi route (0 lỗ); `/security-review` toàn bộ code, sửa 3 lỗ thật | `phase-6/security-review*.txt` |

Quy tắc: **logic quan trọng (chấm bài, thanh toán, gợi ý) viết test trước** (TDD). Mỗi lỗi tìm ra đều có test "đỏ trước khi sửa, xanh sau khi sửa".

## 5. Giới hạn và việc còn lại — nói chủ động trước khi bị hỏi

- Chưa lên **máy chủ thật**: site đang chạy trên máy của em qua tunnel, nên máy phải bật và không được ngủ. Máy chủ Azure for Students là bước cuối của Phase 6. Lúc đó giữ nguyên tên miền, chỉ đổi DNS.
- Chấm code mới hỗ trợ **Python**. Kiến trúc mỗi ngôn ngữ một ảnh Docker để mở rộng sau (Java, C++…).
- VNPay chưa chạy giao dịch thật (lý do ở mục 4.8). Không làm MoMo.
- Đăng nhập Google đang ở chế độ **Testing** của Google: chỉ các email được khai báo mới đăng nhập được, cho tới khi bấm "Publish app".
- Qua tunnel Cloudflare gói miễn phí, **tải lên tệp > 100 MB bị chặn** (413).
- Dữ liệu tương tác để đo hệ gợi ý là **dữ liệu mô phỏng** (48 học viên giả, có quy luật cụm sở thích); đã gỡ khỏi bản demo. Số đo hợp lệ cho so sánh các thuật toán, chưa phải hành vi người dùng thật.
- Giao diện hiện là shadcn/ui gần mặc định; Phase 7 sẽ làm bộ nhận diện riêng.

---

# PHẦN B — CÂU HỎI GIÁO VIÊN CÓ THỂ HỎI

> Gợi ý trả lời là **ý chính** để nắm, không phải để đọc thuộc. Nếu gặp câu chưa chắc: nói "chỗ này em mở code xem lại" rồi mở đúng tệp. Biết đường tìm câu trả lời trong chính dự án của mình cũng là một cách chứng minh hiểu.

## B1. Tổng quan và lựa chọn công nghệ

**1. Dự án của em khác Udemy hay các trang học khác ở điểm nào?**
Ba điểm nhấn: chấm code tự động trong sandbox với kết quả realtime, trợ giảng AI chỉ trả lời từ tài liệu khóa có trích nguồn, và gợi ý lai giải được khóa mới (cold-start). Udemy không chấm code trực tiếp và không có trợ giảng theo tài liệu từng khóa.

**2. Vì sao chọn FastAPI chứ không phải Django hay Node.js?**
FastAPI chạy bất đồng bộ (async), hợp với việc nhiều kết nối chờ lâu như WebSocket chấm bài và stream AI. Tự sinh tài liệu API từ Pydantic. Kiểm dữ liệu vào bằng kiểu. Hệ sinh thái Python có sẵn cho AI. Em cũng đã có kinh nghiệm với FastAPI (ghi trong đề cương). Django mạnh ở trang quản trị dựng sẵn, nhưng dự án này chủ yếu là API cho một frontend riêng.

**3. Vì sao Next.js mà không phải React thuần?**
Cần **render ở server** (SSR) để trang khóa học có sẵn nội dung trong HTML đầu tiên, tốt cho SEO và chia sẻ link (Open Graph). React thuần chỉ render ở trình duyệt.

**4. Redis dùng vào những việc gì? Tắt Redis thì sao?**
Hàng đợi Celery, kênh pub/sub kết quả chấm, bảng xếp hạng, cache gợi ý, đếm rate limit. Tắt Redis thì chấm bài và các việc nền dừng; bảng xếp hạng dựng lại được từ sổ cái XP trong PostgreSQL. Endpoint `/health/ready` báo "not ready" để giám sát phát hiện.

**5. Vì sao cần hàng đợi (Celery)? Chấm luôn trong request không được à?**
Chấm một bài có thể mất vài giây đến vài chục giây. Giữ request lâu thì máy chủ nhanh cạn kết nối, và người dùng đóng tab là mất kết quả. Hàng đợi tách "nhận bài" khỏi "chấm bài", kiểm soát được số bài chấm cùng lúc, và lỗi tạm thời thì thử lại được.

**6. Kiến trúc backend chia lớp thế nào? Vì sao?**
Router → service → model. Router chỉ lo HTTP; luật nghiệp vụ ở service; model là bảng. Một luật dùng chung nhiều nơi (ví dụ "ghi danh" dùng ở đăng ký miễn phí, IPN thanh toán, đơn 0đ) và test được không cần HTTP.

## B2. Chấm code ⭐ (câu hỏi sâu nhất, chắc chắn bị hỏi)

**7. Nếu học viên nộp code `import os; os.system("rm -rf /")` thì chuyện gì xảy ra?**
Code chạy trong container dùng một lần, filesystem chỉ đọc, user không phải root, không có quyền đặc biệt (cap-drop ALL). Lệnh xóa thất bại hoặc chỉ ảnh hưởng container sắp bị hủy. Thư mục chứa code mount chỉ đọc. Máy chủ không bị gì.

**8. Còn fork bomb, vòng lặp vô hạn, ăn hết RAM?**
- Fork bomb: `--pids-limit 64`.
- Vòng lặp vô hạn: giới hạn CPU (ulimit) bên trong + đồng hồ ngoài: **timeout hai lớp**, phòng trường hợp chương trình bắt được tín hiệu.
- Ăn RAM: `--memory 256m` và `--memory-swap` bằng nhau (không cho dùng swap), vượt thì bị kill và báo MLE.

Mỗi trường hợp đều có test tự động; riêng 7 kiểu tấn công (đọc tệp ngoài, gọi mạng, fork bomb, ghi rootfs, làm đầy `/tmp`, leo thang quyền, tự tắt container) chạy trong CI ở mọi lần đẩy code.

**9. Làm sao phân biệt MLE với TLE khi container bị kill?**
Docker có cờ `OOMKilled`, nhưng cờ này có lúc sai trên CI. Nên hệ thống xét thêm **thời gian sống** của container: bị kill (exit 137) sớm, trước điểm giữa giới hạn CPU mềm và cứng, thì là MLE. Lỗi này tìm ra nhờ CI đỏ ngẫu nhiên, đã ghi lại.

**10. Học viên có xem trộm được test ẩn không?**
Không. API không bao giờ trả input/output của test ẩn, chỉ trả đúng/sai. Container không có mạng nên không gửi dữ liệu ra ngoài được. Code cũng không đọc được tệp đáp án, vì đáp án không nằm trong container: worker so kết quả **bên ngoài**.

**11. Docker socket là gì, vì sao phải có proxy?**
Socket Docker là cổng điều khiển Docker. Ai cầm nó tạo được container mount cả ổ đĩa máy chủ, coi như có quyền root. Nên worker chấm bài không cầm socket; nó gọi qua một proxy tự viết, chỉ cho phép tạo **đúng một kiểu** container sandbox với đúng các cờ bảo mật. Request khác bị từ chối 403.

**12. Kết quả từng test hiện ra realtime bằng cách nào?**
Worker chấm xong test nào thì publish lên kênh Redis của bài đó; backend giữ một WebSocket với trình duyệt và chuyển tiếp. Nếu WebSocket bị chặn (proxy công ty chẳng hạn), trang tự chuyển sang hỏi lại định kỳ (polling) để vẫn có kết quả cuối.

**13. 100 người cùng nộp thì sao?**
Bài vào hàng đợi, mỗi lần chấm 2 bài (đo benchmark trên máy 8 CPU). Thời gian chờ tăng tuyến tính theo hàng. Đo lớp 20 người: người cuối chờ 35–50 giây. Mở rộng bằng cách thêm worker hoặc máy chấm. Vì có hàng đợi nên không mất bài.

## B3. AI (trợ giảng, sinh quiz, gợi ý)

**14. RAG là gì? Vì sao không hỏi thẳng Gemini?**
RAG là "tìm tài liệu liên quan rồi mới trả lời từ tài liệu đó". Hỏi thẳng thì Gemini trả lời theo hiểu biết chung, có thể sai hoặc lệch với bài giảng, và không chỉ ra nguồn. RAG buộc câu trả lời bám tài liệu khóa, có trích nguồn kiểm chứng được, và từ chối khi tài liệu không có.

**15. Embedding / vector là gì? Giải thích cho người không học AI.**
Biến một đoạn văn thành một dãy 768 con số sao cho hai đoạn cùng ý nghĩa thì hai dãy số "gần nhau". Như đặt mỗi đoạn văn lên một bản đồ ý nghĩa; tìm tài liệu liên quan là tìm các điểm gần câu hỏi nhất.

**16. Sao biết trợ giảng không bịa (hallucination)?**
Prompt bắt chỉ dùng các đoạn được cung cấp và ghi nguồn [n]; không có thì phải từ chối bằng câu mở đầu cố định. Đánh giá bằng bộ 20 câu × 3 lần: 58/60, từ chối đúng 18/18. Vẫn có rủi ro, nên giao diện ghi "AI có thể nhầm — bấm vào nguồn để đối chiếu".

**17. Học viên khóa A có hỏi ra tài liệu khóa B được không?**
Không. Điều kiện "đúng khóa, khóa đã xuất bản, người hỏi đã ghi danh" nằm ngay trong câu SQL tìm vector, không phải lọc sau. Đã thử hạ khóa về nháp: truy vấn trả 0 đoạn.

**18. Hệ gợi ý của em đánh giá bằng gì? Recall@5 = 0,884 nghĩa là gì?**
Giấu bớt một phần khóa mà mỗi học viên đã học, cho hệ thống gợi ý 5 khóa, đếm xem tìm lại được bao nhiêu phần trăm khóa bị giấu. 0,884 nghĩa là trung bình tìm lại được khoảng 88 %. Có so với gợi ý ngẫu nhiên (0,239) và gợi ý theo độ phổ biến (0,178).

**19. Dữ liệu để đo gợi ý lấy đâu ra?**
Dữ liệu **mô phỏng**: 48 học viên giả, 20 khóa giả chia 4 cụm sở thích, sinh có hạt giống cố định nên tái tạo được. Phải nói rõ đây là giới hạn: số đo dùng để so thuật toán với nhau, chưa phản ánh người dùng thật. Hướng phát triển: thu dữ liệu thật, thử mô hình chuỗi (SASRec).

**20. Cold-start là gì, em giải quyết thế nào?**
Khóa mới chưa ai học thì lọc cộng tác không biết gợi ý cho ai; người mới chưa học gì thì không biết họ thích gì. Khóa mới: phần content-based vẫn so được nội dung. Người mới: gợi ý phổ biến theo danh mục.

**21. Vì sao gộp bằng RRF mà không cộng điểm?**
Hai phương pháp chấm theo thang khác nhau. Điểm content-based của mọi khóa đều cao (≥ 0,747) vì chúng cùng là khóa lập trình; cộng vào thì nó lấn át tín hiệu thật. RRF chỉ dùng **thứ hạng**, nên không cần chuẩn hóa thang điểm.

**22. Gemini hết quota hoặc sập thì sao?**
Có lớp adapter: tự thử lại khi chưa có chữ nào; đã ra chữ rồi mới lỗi thì báo lỗi rõ và **không lưu** câu trả lời dở. Gợi ý tính sẵn hằng đêm nên Gemini sập không ảnh hưởng. Quiz AI đã sinh thì lưu trong CSDL. Đổi nhà cung cấp AI chỉ sửa adapter.

## B4. Bảo mật, thanh toán, dữ liệu

**23. JWT là gì? Vì sao access token chỉ sống 15 phút?**
JWT là thẻ có chữ ký, server kiểm chữ ký là biết ai mà không cần tra CSDL. Sống ngắn để lỡ bị lộ thì chỉ dùng được ít phút; còn phiên lâu dài dựa vào refresh token nằm trong cookie HttpOnly và có xoay vòng.

**24. Nếu kẻ gian lấy được refresh token thì sao?**
Mỗi refresh token chỉ dùng được một lần. Kẻ gian và chủ tài khoản, ai dùng sau thì đưa ra một token đã bị thay. Server nhận ra "token đã dùng bị dùng lại" và thu hồi mọi phiên của tài khoản đó. Có 30 giây ân hạn cho trường hợp hai tab của chính chủ cùng làm mới.

**25. Làm sao chắc người dùng không tự sửa số tiền thanh toán?**
Link thanh toán có chữ ký HMAC-SHA512 bằng khóa bí mật chỉ server và VNPay biết. Sửa số tiền thì chữ ký sai. Khi VNPay báo về (IPN), server kiểm lại chữ ký **và** so số tiền với đơn trong CSDL.

**26. VNPay gọi IPN 2 lần thì người dùng có bị ghi danh 2 lần, coupon bị trừ 2 lần không?**
Không. Khóa dòng đơn (`SELECT … FOR UPDATE`) và chỉ xử lý khi đơn còn ở trạng thái "chờ". Lần sau trả mã 02 ("đã xử lý") và không thay đổi gì. Có ràng buộc duy nhất trên mã giao dịch.

**27. Em demo thanh toán bằng IPN giả lập — vậy có chắc chạy được với VNPay thật?**
Phần còn thiếu chỉ là VNPay khai địa chỉ IPN. Trang sandbox thật của VNPay **đã nhận** link do server ký (đúng mã merchant, đúng chữ ký). IPN giả lập ký bằng đúng khóa bí mật và đi qua đúng endpoint, cùng các bước kiểm như IPN thật. Thuật toán ký có test ghim chuỗi được viết tay từ đặc tả của VNPay.

**28. Thiết kế CSDL: bảng nào quan trọng nhất? Vì sao dùng PostgreSQL?**
Quan trọng nhất: `users`, `courses` → `course_sections` → `lessons`, `enrollments`, `submissions` + `submission_results`, `orders` + `order_items`, `xp_events`, `doc_chunks` (vector RAG). Chọn PostgreSQL vì có giao dịch ACID cho thanh toán, full-text search, và **pgvector**: lưu vector AI ngay trong cùng CSDL, không cần dựng thêm một vector database riêng.

**29. Thay đổi cấu trúc bảng thế nào để không mất dữ liệu?**
Mọi thay đổi đi qua **Alembic migration** (29 tệp), có cả chiều nâng và chiều hạ. CI chạy lên → xuống → lên trên CSDL trắng, và `alembic check` bảo đảm model khớp migration.

**30. Website chống XSS, SQL injection thế nào?**
SQL dùng ORM/tham số hóa, không ghép chuỗi. Giao diện React tự escape; nội dung Markdown không render HTML thô. Content-Security-Policy chặn script từ nơi khác. Cookie HttpOnly nên script không đọc được phiên. Tệp người dùng tải lên được phục vụ với CSP `sandbox` để không chạy được như trang web.

## B5. Triển khai và vận hành

**31. Site đang chạy ở đâu? Tunnel là gì?**
Chạy trên máy em bằng chính cấu hình production. Cloudflare Tunnel là một tiến trình trong máy **chủ động nối ra** Cloudflare, nên không phải mở cổng hay có IP tĩnh. Người xem vào `devpath-01.me` → Cloudflare → đường hầm → nginx trong máy. Hạn chế: máy phải bật; tải lên tối đa 100 MB. Máy chủ thật (Azure) là bước kế tiếp, dùng cùng tệp cấu hình.

**32. Máy chủ chết hoặc mất dữ liệu thì sao?**
Mọi dịch vụ tự khởi động lại. Sao lưu CSDL mỗi đêm (giữ 14 bản) và giám sát mỗi phút báo về điện thoại đều đã làm và diễn tập (khôi phục thật thành công). Trên máy demo hiện tại hai thứ này **chưa bật**: sao lưu cần nơi lưu ngoài máy, giám sát chạy bằng systemd của máy chủ Linux. Cả hai bật khi lên máy chủ thật. Nói thẳng điểm này nếu được hỏi.

**33. Docker để làm gì? Không có Docker có chạy được không?**
Hệ thống cần PostgreSQL + pgvector, Redis, ffmpeg, kho S3, và sandbox chấm bài vốn **phải** là container. Docker gói tất cả để máy em, máy CI và máy chủ chạy cùng một image, nên không còn chuyện "máy em chạy được". Không có Docker thì phần chấm code không tồn tại được.

## B6. Kiểm thử và quy trình làm việc

**34. Em kiểm thử thế nào? Coverage bao nhiêu?**
Backend 1.873 ca trên PostgreSQL và Redis thật (không giả lập CSDL), coverage 94,5 %. Có test tấn công sandbox, ma trận phân quyền mọi route, E2E Playwright đi trọn luồng người dùng. CI chạy toàn bộ mỗi lần đẩy code. Test nào cần dịch vụ ngoài mà không chạy được thì trên CI tính là **đỏ**, không phải "bỏ qua", để không có chuyện CI xanh mà test không chạy.

**35. Kể một lỗi khó nhất em gặp và cách tìm ra.**
Chọn một chuyện thật và kể theo mạch "triệu chứng → đo → nguyên nhân → sửa → test chốt". Vài lỗi có ghi lại:
- Hệ gợi ý luôn đẩy khóa mới xuống cuối (tìm ra khi đánh giá cold-start).
- Byte NUL trong output làm PostgreSQL không lưu được kết quả, và bài sai bị báo là lỗi hệ thống.
- Hai tab cùng làm mới phiên làm người dùng bị đăng xuất khỏi mọi thiết bị.
- Sau tunnel, mọi người dùng mang cùng một IP.

**36. Em có dùng AI (ChatGPT, Claude…) để viết code không?**
**Trả lời trung thực.** Nếu có dùng trợ lý AI lập trình thì nói rõ đã dùng vào việc gì, và em kiểm soát thế nào: em là người đặt yêu cầu và quyết định thiết kế; mọi thay đổi có test và bằng chứng chạy thật; em đọc hiểu và giải thích được từng phần (chính tài liệu này là phần chuẩn bị đó). Giáo viên đánh giá mức hiểu, nên điều quan trọng là trả lời được các câu ở trên bằng lời của mình và mở đúng chỗ trong code khi được hỏi.

**37. Nếu có thêm 3 tháng, em sẽ làm gì?**
Đưa lên máy chủ thật với người dùng thật để có dữ liệu thật cho hệ gợi ý; mở rộng chấm code sang Java/C++; thanh toán thật; ứng dụng di động dùng chung API; lớp học trực tiếp (WebRTC). Hướng phát triển trong đề cương mục 6.

## B7. Câu "bẫy" để kiểm tra có hiểu thật không

**38. Mở trang học, F5 liên tục — server có bị ghi tiến độ quá nhiều không?**
Tiến độ ghi theo nhịp 10 giây và khi dừng/chuyển tab; tải lại trang thì đọc vị trí đã lưu chứ không ghi mới. Mỗi bài một dòng tiến độ, cập nhật đè chứ không thêm dòng.

**39. Hai học viên cùng dùng lượt cuối cùng của một mã giảm giá cùng lúc?**
Trừ lượt bằng một câu `UPDATE … SET used_count = used_count + 1 WHERE used_count < max_uses`: CSDL bảo đảm chỉ một người thành công. Kiểu "đọc 99 rồi ghi 100" ở code ứng dụng thì cả hai cùng đọc 99, cùng ghi 100. Thêm một ràng buộc CHECK làm lớp chặn cuối.

**40. Tại sao chứng chỉ vẫn cấp khi học viên tự bấm "hoàn thành" bài quiz mà không làm?**
Đây là **quyết định có chủ đích** (giống Udemy), đã chốt: chứng chỉ ghi nhận hoàn thành khóa, không phải điểm thi. Nếu muốn chặt hơn thì đổi điều kiện cấp, ví dụ bắt quiz đạt hoặc bài code AC.

**41. Đổi `localhost` sang `127.0.0.1` thì đăng nhập mất — vì sao?**
Trình duyệt coi hai địa chỉ là hai site khác nhau. Cookie phiên đặt cho site này không gửi sang site kia (`SameSite`). Kiến thức cookie và same-site.

**42. Vì sao không lưu vector AI trong một vector database riêng (Pinecone, Qdrant)?**
Dữ liệu nhỏ (vài chục đến vài nghìn đoạn mỗi khóa), mà pgvector với chỉ mục HNSW đủ nhanh. Quan trọng hơn: điều kiện phân quyền (đã ghi danh, khóa đã xuất bản) nằm **chung một câu SQL** với tìm vector. Tách sang DB khác thì phải đồng bộ hai nơi và lọc quyền ở ứng dụng, dễ sai hơn.

---

## Phụ lục — Mở nhanh khi cần

| Muốn chỉ cho thầy | Mở ở đâu |
|---|---|
| Cờ bảo mật của sandbox | `grader/runner/sandbox.py` (hàm dựng lệnh `docker create`) |
| Luật của proxy Docker | `grader/proxy/policy.py` |
| Trợ giảng AI (tìm tài liệu + prompt) | `backend/app/services/chat.py`, `services/chunking.py` |
| Hệ gợi ý | `backend/app/services/collaborative.py`, `services/hybrid.py` |
| Ký và kiểm VNPay | `backend/app/services/vnpay.py`, `services/orders.py` |
| Đăng nhập, xoay vòng token | `backend/app/services/auth.py` |
| Header bảo mật, CSP | `infra/nginx/snippets/security-headers.conf` |
| Kịch bản demo + câu hỏi kỹ thuật thêm | `docs/huong-dan-demo-truoc-giao-vien.md` |
| Mọi số đo, ảnh, log | `docs/report/assets/phase-1` … `phase-6` |
