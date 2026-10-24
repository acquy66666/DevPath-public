# Phase 7 — Nhóm màn 4: Trang học (25/10/2026)

Nhóm màn 4 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): video, bài đọc, mục lục, ghi chú, Hỏi đáp và **trợ giảng AI** ⭐ (`thinking` khi đang trả lời, `answer` khi có nguồn). Nhánh `feature/phase7-learn-page`. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 4: Trang học"**: <https://claude.ai/artifact/Ah6qN7TNcWZQzEuYYcoUS4>. Bản trong repo: [`docs/ui-ux/learn-page/canvas/`](../../../ui-ux/learn-page/canvas/project/canvas.json).

- **6 artboard:**
  - Bài video + ghi chú (1440);
  - Bài đọc + Hỏi đáp + trợ giảng đã trả lời (1440);
  - Bài video (375);
  - Trợ giảng AI, 4 trạng thái: chưa hỏi, đang trả lời, ngoài phạm vi rồi đã dừng, lịch sử;
  - Hỏi đáp: đang đặt câu hỏi, và một câu hỏi có câu trả lời của giảng viên;
  - Trạng thái: vừa hoàn thành khóa, chưa đăng nhập / chưa đăng ký, đang tải.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 8 hình chép từ canvas linh vật: `rest`, `thinking`, `answer`, `graduate`, `wave`, `empty`, `empty-notes`, `empty-courses`.
- **Dữ liệu thật:** khóa "Python cơ bản cho người mới bắt đầu" trên CSDL dev (4 chương, 18 bài), học viên đã xong 4 bài; ba ghi chú, câu hỏi `int("3.5")` và câu trả lời của giảng viên Trần Minh Khoa giống bộ ảnh Phase 6; hai câu hỏi trợ giảng của buổi demo 22/09 (một câu có nguồn, một câu bị từ chối). Trạng thái không có trên dữ liệu ghi rõ "[trạng thái mẫu]".
- **User duyệt 25/10.**
- **Khớp với code:** sau khi code, canvas sửa theo code ở bản 8 (code thắng). Nhãn loại bài là "Bài tập code" (nhãn có sẵn của trang khóa học), trạng thái trợ giảng khi đang soạn là "Đang soạn câu trả lời từ 6 bài…", khi vừa dừng là "Đã dừng câu trả lời".

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Đầu trang** | "← tên khóa", thanh tiến độ 192 px, "4/18 bài · 22%" | Thanh khóa học: ảnh bìa nhỏ của khóa (cùng ảnh với thẻ khóa học), "Về trang khóa học" + tên khóa, thanh tiến độ 200 px, "4/18 bài · 22%". Điện thoại: mũi tên + tên khóa một dòng, thanh tiến độ trải hết bề ngang. "x/y bài" chỉ viết ở đây |
| **Đầu bài** | Tên bài `text-xl` | Dòng vị trí "Chương 3 · Rẽ nhánh và vòng lặp · Bài 2/6", tên bài là h1 của trang, các chip: "Video · 08:18" hoặc "Bài đọc · 1 phút đọc", "Tiếp tục từ 02:20", "Đã hoàn thành" |
| **Video** | Khung đen, ô "Tốc độ phát" bên dưới bên phải | Một thẻ: video, rồi chân thẻ "Ghi chú tại 02:20" (đếm theo giây, bấm là sang tab ghi chú và đặt con trỏ vào ô) + tốc độ phát |
| **Bài đọc** | Chữ thường trên nền trang | Thẻ trắng, chữ `body-lg` (18/30), tối đa 68 ký tự mỗi dòng |
| **Nút dưới bài** | "Đánh dấu hoàn thành" + "Đánh dấu để xem lại" | "Đánh dấu hoàn thành", nút đánh dấu xem lại thu thành biểu tượng (`aria-pressed`), **"Bài trước" / "Bài tiếp theo"** (mới, tính từ mục lục). Xong bài thì "Bài tiếp theo" thành nút chính. Bài code và quiz: đánh dấu tay là nút viền, kèm câu "… tự hoàn thành khi …". Điện thoại: nút chính 44 px trải ngang, hàng dưới là biểu tượng + hai nút chia đôi |
| **Mục lục** | Mọi chương mở, dấu tích thay biểu tượng loại bài | Thẻ "Nội dung khóa học · 4 chương · 18 bài"; mỗi chương một nút gập có "Chương N", tên và "x/y" (đủ thì tích xanh); chỉ mở chương đang học. Mỗi bài hai dòng: tên + "Video · Đã xong" / "Video · Đang học" (trạng thái bằng chữ, không chỉ bằng màu); bài đang học nền ngọc nhạt, vòng tròn ngọc. Trên laptop, danh sách cuộn bên trong cột dính |
| **Ghi chú** | Tiêu đề "Ghi chú của tôi", ô nhập, nút, mỗi ghi chú một khung | Tab kiểu gạch chân. Ô nhập trong thẻ có chân thẻ ("Ghi chú giữ mốc thời gian của video lúc bạn lưu" + "Thêm ghi chú"); "3 ghi chú · theo thứ tự trong video"; danh sách một thẻ, mỗi dòng: mốc thời gian dạng viên ngọc có biểu tượng phát, nội dung, sửa/xóa |
| **Hỏi đáp** | Dòng câu hỏi viền mỏng, số bình chọn nhỏ ở góc | "N câu hỏi" + sắp xếp + "Đặt câu hỏi"; mỗi câu hỏi là thẻ có cột số người cũng hỏi bên trái, tên, đoạn đầu, avatar + người hỏi, nhãn "Giảng viên đã trả lời" (xanh lá), số trả lời. Ô đặt câu hỏi ghi rõ "Câu hỏi mới về bài “…”" |
| **Một câu hỏi** | Tiêu đề, byline, nội dung, hàng nút, các câu trả lời viền mỏng | Câu hỏi trong thẻ (tiêu đề h3, byline + nhãn, nội dung, hàng nút cách bằng đường kẻ); câu trả lời của giảng viên nền ngọc nhạt + nhãn "Giảng viên"; ô trả lời trong thẻ có chân thẻ |
| **Trợ giảng AI** | Đầu khung là tên cuộc trò chuyện; Naomi chỉ ở phần trống; câu trả lời có avatar lấp lánh; lúc đang trả lời là spinner + "Đang đọc 6 bài: …" | **Naomi ở đầu khung** đổi dáng theo trạng thái + dòng trạng thái ("Đang tra cứu tài liệu khóa học…", "Đang soạn câu trả lời từ 6 bài…", "Đã trả lời · 1 nguồn trong khóa học"). Lúc đang trả lời: **3 bước** tra cứu → đọc 6 bài (3 tên + "+3 bài") → soạn. Câu trả lời không avatar; số nguồn là viên ngọc; "Nguồn trong khóa học" là các thẻ "Mở bài" / "Đang xem". Câu từ chối có nhãn "Ngoài phạm vi khóa học" |
| **Xong khóa** | "· đã hoàn thành khóa học 🎉" sau số bài + link "Xem chứng chỉ" | Banner màu phần thưởng: **Naomi `graduate`**, "Bạn đã hoàn thành khóa học", "Xem chứng chỉ" + "Học tiếp theo" (chỉ khi có khóa gợi ý) |
| **Không vào được** | Khung viền đứt, biểu tượng ổ khóa / đăng nhập | Thẻ có Naomi tĩnh (`wave` khi chưa đăng nhập, `empty-courses` khi chưa đăng ký), tên là h1 |
| **Đang tải** | Một khối xám 384 px | Khung thật của trang: thanh khóa học, tên bài, video 16:9, hai nút, thẻ mục lục |

**Naomi** (bản đồ phản ứng, thiết kế mục 5):
- Trợ giảng: `thinking` mỗi lần hỏi, `answer` khi câu trả lời trích được nguồn, `rest` khi chưa hỏi, bị từ chối, bị dừng hoặc lỗi. Mỗi câu hỏi và mỗi câu trả lời là một sự kiện, phản ứng một lần. Mở lại từ lịch sử thì đứng yên.
- Xong khóa: `graduate` phản ứng một lần, chỉ khi trang đã thấy khóa chưa xong trước đó. Mở lại khóa đã xong thì đứng yên.
- Ghi chú trống giữ `empty-notes` (task trạng thái toàn site); Hỏi đáp trống giữ `empty`.

## 3. Lỗi tìm ra khi làm

- **Chữ ẩn cho trình đọc màn hình làm "x/y bài" xuất hiện 5 lần.** Số của từng chương ban đầu kèm chữ ẩn " bài đã xong", tức là "3/3 bài đã xong". Playwright đọc cả chữ ẩn, nên E2E tìm "1/2 bài" sẽ gặp hai chỗ khớp và đỏ vì "strict mode". `check.cjs` bắt được (5 chỗ). Giờ chữ ẩn đứng trước số: "Đã xong 3/3".
- **Quiz có hai nút chính.** Nút "Đánh dấu hoàn thành" màu chính đứng cạnh nút nộp của quiz. Giờ quiz đi chung luật với bài code: tự hoàn thành khi làm đạt, nên nút đánh dấu tay là nút viền.
- Lỗi của chính script kiểm, ghi lại cho lần chạy sau: chữ "Bạn đã hoàn thành khóa học" có ở cả banner lẫn mô tả của khối "Học tiếp theo", nên phải tìm theo heading. Một Naomi có hai phần tử mang `data-mood`, nên đếm Naomi theo khung `[data-mascot]`.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **82/82** (13 test mới: `lib/learn/position.test.ts` — vị trí "Chương · Bài", bài trước/sau qua ranh giới chương, tiến độ từng chương, chương mở sẵn, thời gian đọc, "Tiếp tục từ"; `lib/chat/assistant-state.test.ts` — cụm từ chối khớp `chat.py` của backend, luật câu đầu, Naomi theo từng trạng thái, chip bài đang đọc) |
| `tsc --noEmit`, `eslint app components lib` | sạch |
| Hành vi trên Chrome thật ([`learn-page/check.cjs`](learn-page/check.cjs), stack dev, 1 lượt Gemini) | **19/19** ([`results.json`](learn-page/results.json)) |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai, có trang học video/bài đọc/bài code/quiz) | **0/132** ([`learn-page/overflow.json`](learn-page/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (21 s), không sửa spec: "0/2 bài", "Đánh dấu hoàn thành", "2/2 bài" và link "Xem chứng chỉ" vẫn mỗi thứ một chỗ |
| `next build` không mạng (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) | xanh |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải thêm gì mới (không thư viện, không font; hình Naomi `thinking`/`answer`/`graduate`/`wave` là chunk cùng origin đã đo ở task component). Phép đo ở gate phủ cả trang này |

## 5. Ảnh — `learn-page/before/` và `learn-page/after/`

[`learn-page/capture.cjs`](learn-page/capture.cjs) dựng một học viên dùng một lần, ghi danh khóa Python miễn phí, tick 4 bài, viết 3 ghi chú, đánh dấu một bài, đặt một câu hỏi để giảng viên seed trả lời, rồi hỏi trợ giảng 3 câu (2 qua API, 1 trên màn hình lúc đang trả lời). Cuối cùng script xóa thông báo `qa_question` của giảng viên và chạy `purge_e2e`. `PHASE=before` chạy trên `main` @ `72378a0`, `PHASE=after` trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-video-ghi-chu-{1440,375}` | Bài video đang học dở (02:20), 3 ghi chú |
| `2-bai-doc-{1440,375}` | Bài đọc "Đọc hiểu thông báo lỗi" |
| `3-hoi-dap-1440` | Danh sách Hỏi đáp của bài "Ép kiểu…" |
| `4-hoi-dap-cau-hoi-{1440,375}` | Câu hỏi có câu trả lời của giảng viên |
| `5-tro-giang-trong-1440` | Trợ giảng chưa hỏi gì |
| `6-tro-giang-tra-loi-{1440,375}` | Một câu trả lời có nguồn + một câu bị từ chối |
| `7-tro-giang-dang-tra-loi-1440` | Đang trả lời (sau khi có nguồn) |
| `8-chua-dang-ky-1440` | Khóa chưa đăng ký |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh.

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/learn-page/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/learn-page/check.cjs
```

## 6. Để lại

- **Thứ tự trên điện thoại giữ như cũ:** ghi chú ngay dưới video, mục lục và trợ giảng ở cuối. Nút "Bài trước" / "Bài tiếp theo" giảm nhu cầu kéo xuống mục lục. Gộp cả bốn thành một hàng tab trên điện thoại phải dựng hai cây component (trợ giảng phải giữ nguyên khi đổi tab), nên để sau nếu cần.
- **Trình phát video vẫn là điều khiển gốc của trình duyệt** (`controls`): đã truy cập được bằng bàn phím và trình đọc màn hình. Tự vẽ điều khiển là việc lớn, không đổi được gì cho hội đồng.
- **Có lúc hai Naomi cùng trên màn:** banner xong khóa (hoặc Naomi của bài code) cùng lúc với ghi chú trống. Mỗi Naomi gắn với một khối riêng và đều đứng yên trừ đúng sự kiện của nó.
- **Khung quiz** giữ nguyên, là việc của nhóm 5. Theme tối chờ quyết định chung.
