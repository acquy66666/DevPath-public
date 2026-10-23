# Bài đọc: ô soạn có xem trước và chèn ảnh (23/10/2026)

Task ngoài kế hoạch Phase 7. User yêu cầu ngày 23/10 sau khi tự soạn thử một khóa có quiz và gặp hai vấn đề:
- dán Markdown vào bài đọc thì hiển thị xấu;
- giảng viên không có cách nào chèn ảnh.

Nhánh `feature/article-editor-images`. Đây là **ngoại lệ có chủ đích** với luật "backend đứng yên" của Phase 7: muốn chèn ảnh thì cần một endpoint cấp URL tải lên. Lý do chọn hướng này nằm ở [`decisions.md`](../decisions.md), mục "Bài đọc: Markdown có xem trước, ảnh chỉ từ kho nhà".

## 1. Vì sao bài dán vào trông xấu

| Nguyên nhân | Sửa |
|---|---|
| Ô soạn là một `<textarea>` 8 dòng, không có xem trước. Giảng viên phải lưu rồi mở trang học mới thấy kết quả | Ô soạn mới: tab **Soạn / Xem trước**. Ô soạn tự cao theo nội dung tới 70 % màn hình. Nút **Toàn màn hình** đặt soạn và xem trước cạnh nhau ở màn ≥ 1024 px |
| Trình hiển thị không có `remark-gfm`, nên bảng `\| a \| b \|` hiện nguyên dấu `\|`. Ảnh, `---`, ~~gạch ngang~~ và danh sách việc không có kiểu | Thêm `remark-gfm@4.0.1`. Có kiểu cho bảng (cuộn ngang trong khung trên điện thoại), ảnh (chú thích bên dưới), đường kẻ, chữ gạch ngang, hộp đánh dấu |
| Tệp mẫu `docs/mau-khoa-hoc-quiz.md` bọc mỗi bài đọc trong `~~~markdown`. Dán kèm hai dòng đó thì cả bài thành một khối code | Ghi chú ở đầu tệp mẫu: chỉ chép phần giữa hai dòng `~~~` |

## 2. Đổi gì

**Ô soạn** (`frontend/components/curriculum/article-editor.tsx`):
- **Thanh công cụ:** tiêu đề, đậm, nghiêng, danh sách, danh sách số, trích dẫn, code trong dòng, khối code, bảng, liên kết, **Chèn ảnh**.
- **Cách áp định dạng:** mỗi nút chỉ viết cú pháp Markdown, qua `document.execCommand("insertText")`, nên **Ctrl+Z hoàn tác được** như khi gõ. Phím tắt: Ctrl+B, Ctrl+I, Ctrl+K.
- **Logic thuần:** các thao tác văn bản nằm ở `lib/markdown/editing.ts` và có test.

**Chèn ảnh** bằng dán (Ctrl+V ảnh chụp màn hình), kéo thả hoặc nút. Mỗi ảnh đi qua bốn bước:
1. Một dòng giữ chỗ `![Đang tải ảnh lên](#dang-tai-anh-…)` hiện ngay tại con trỏ.
2. Trình duyệt xin vé `POST /api/v1/lessons/{id}/images`.
3. Trình duyệt PUT ảnh thẳng lên bucket.
4. Dòng giữ chỗ được thay bằng `![<tên tệp>](<địa chỉ công khai>)`.

Trong lúc ảnh đang tải, giảng viên vẫn gõ tiếp được, còn nút **Lưu bài học** bị khóa (lưu lúc này sẽ lưu luôn dòng giữ chỗ). Mô tả ảnh lấy từ tên tệp. Ảnh dán từ clipboard luôn tên `image.png`, nên mô tả khởi đầu là "Ảnh".

**Backend:**
- `services/lesson_images.py` + `api/v1/lesson_images.py`, cùng khuôn với avatar/banner.
- Chỉ giảng viên chủ khóa hoặc admin; chỉ bài `article` (khác → 409 `LESSON_NOT_ARTICLE`).
- Chỉ PNG/JPEG/WebP/GIF, không nhận SVG vì SVG chứa được script; tối đa 5 MB, kích thước được ký vào URL.
- Tối đa 200 vé mỗi ngày mỗi tài khoản (429 `UPLOAD_RATE_LIMITED`).
- Key: `lesson-images/<id khóa>/<32 hex>.<đuôi theo kiểu>`.
- **Không có bảng và không có bước "xác nhận":** bài đọc nhắc tới địa chỉ ảnh chính là bằng chứng sở hữu.
- **Job dọn object mồ côi** (`services/orphans.py`) quản thêm prefix thứ năm `lesson-images/`. Một ảnh được coi là còn dùng khi có ít nhất một `lessons.article_content` chứa đúng key đó, đọc theo đường dẫn nên đổi host bucket vẫn nhận ra. Ảnh dán rồi xóa, hoặc đóng tab trước khi lưu, được đánh dấu rồi xóa sau 14 ngày như mọi object mồ côi khác.
- **Trợ giảng AI:** ingest (`services/ingest.py::article_words`) chỉ giữ phần mô tả của ảnh. Địa chỉ dài 80 ký tự không bị nhúng như chữ. Bài không có ảnh thì chunk không đổi, nên không tốn quota nhúng lại.

**Ảnh chỉ từ kho nhà** (`lib/markdown/images.ts`, dùng cho mọi chỗ render Markdown: bài đọc, đề bài code, mô tả khóa, Hỏi đáp):
- Ảnh chỉ được vẽ khi địa chỉ thuộc kho media của DevPath. Production là chính origin của site (`NEXT_PUBLIC_SITE_URL`); dev thêm `http://minio.localhost:9000`.
- Ảnh từ nơi khác hiện thành liên kết "Ảnh ngoài: <mô tả>". Nhờ vậy giảng viên không thể giấu ảnh theo dõi vào bài để biết học viên nào đọc lúc nào, và học viên cũng không làm được điều đó với giảng viên qua câu hỏi Hỏi đáp.
- Địa chỉ không phải http(s) (`javascript:`, `data:`) hiện thành chữ, không thành link.

## 3. Kiểm

| Kiểm | Kết quả |
|---|---|
| Backend: `tests/api/test_lesson_images.py` (vé đúng, kiểu + cỡ được ký, mỗi ảnh một tên, admin được, 401, 403 giảng viên khác / học viên, 404, 409 ba loại bài, 422 SVG/HTML/quá 5 MB/0 byte/thiếu cỡ, 429 rồi mở lại sau 24 giờ), `test_orphans.py` (+3: nhận đúng tệp, đọc mọi bài đọc kể cả URL có tiêu đề và host cũ, ảnh không ai nhắc bị đánh dấu), `test_ingest.py` (+1), ma trận phân quyền (+1 luật) | 297 passed trong nhóm liên quan; ruff sạch |
| Frontend: `lib/markdown/editing.test.ts` (13) + `images.test.ts` (8) | `npm test` 56/56; `tsc` + ESLint sạch |
| Chạy thật trên stack dev, Chrome, tài khoản dùng một lần (`article-editor/run.cjs`) | **18/18**: định dạng + Ctrl+Z + Ctrl+B, danh sách số, bảng; dán PNG → PUT 200 → ảnh đọc lại được (`image/png`); xem trước vẽ ảnh (720 px), bảng thật, ảnh `tracker.example` thành liên kết và **0 request** tới đó; toàn màn hình hai cột ở 1440 px, Esc thoát; lưu xong máy chủ có đúng địa chỉ; 375 px không tràn (trang và trong khung bài học) |
| E2E luồng vàng | 1 passed |

Lượt chạy đầu tìm ra một lỗi: ở 375 px, dòng địa chỉ ảnh dài làm cột lưới của ô soạn rộng theo dòng dài nhất (cột ngầm định là `auto`), và ô soạn tràn khỏi khung bài học. Trang vẫn rộng đúng 375 px vì phần tràn nằm trong một khung cuộn con, nên phép đo `scrollWidth` của trang không bắt được. Đã sửa bằng `grid-cols-1` (`minmax(0, 1fr)`) + `min-w-0`. Script giờ đo thêm mép phải của ô soạn và thanh công cụ so với khung bài học.

## 4. Ảnh

| Tệp | Nội dung |
|---|---|
| `article-editor/1-soan-1440.png` | Bảng sửa bài học: tab Soạn, thanh công cụ, Markdown đã định dạng, ảnh vừa dán |
| `article-editor/2-xem-truoc-1440.png` | Tab Xem trước: tiêu đề, chữ đậm, danh sách số, code, bảng, ảnh kèm chú thích, ảnh ngoài thành liên kết |
| `article-editor/3-toan-man-hinh-1440.png` | Toàn màn hình: soạn và xem trước cạnh nhau |
| `article-editor/4-soan-375.png`, `5-xem-truoc-375.png` | Điện thoại: thanh công cụ xuống dòng, bảng cuộn trong khung |

Chạy lại: `NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/article-editor/run.cjs` (cần stack dev có storage; script tự `purge_e2e` ở cuối, ảnh đã tải để job dọn mồ côi lo). Container frontend dev cần `npm install` sau khi kéo nhánh này (`node_modules` nằm trong volume riêng): `docker compose exec frontend npm install && docker compose restart frontend`.

## 5. Còn lại

- **Chưa kiểm trên trang học của học viên.** Script kiểm ở khung xem trước của giảng viên. Khung đó dùng đúng component `<Markdown>` của trang học, nhưng chưa đi qua luồng ghi danh rồi mở `/hoc/…`.
- **Nếu chuyển media sang R2 với tên miền riêng:** phải thêm origin đó vào `mediaOrigins()`, không thì mọi ảnh thành liên kết.
- **Stack demo `devpath-01.me` chưa có bản này:** cần deploy lại (`deploy.sh` build lại image frontend có `remark-gfm`).
