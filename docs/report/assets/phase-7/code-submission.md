# Phase 7 — Nhóm màn 3: Nộp bài code (23–24/10/2026)

Nhóm màn thứ hai của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md), điểm nhấn ⭐ số 1 của khóa luận: Monaco, kết quả từng test qua WebSocket, Naomi theo 7 verdict và `grading` theo "test k/n". Nhánh `feature/phase7-code-submission`. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 3: Nộp bài code"**: <https://claude.ai/artifact/BKT1qVijkW67ekwt8LLY36>. Bản trong repo: [`docs/ui-ux/code-submission/canvas/`](../../../ui-ux/code-submission/canvas/project/canvas.json).

- **5 artboard:**
  - Trang học · bài code · đang chấm (1440);
  - Bài code · Đúng (375);
  - Toàn màn hình · Sai kết quả (1440);
  - Khối kết quả · 12 trạng thái;
  - Thành phần "khối kết quả": một artboard có Tweaks chọn trạng thái, các artboard khác nhúng lại nó.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 8 hình chép từ canvas linh vật (`grading` + 7 mood verdict).
- **Dữ liệu thật:** bài "đếm số chẵn" của khóa Python cơ bản trên CSDL demo: 2 test mẫu, 4 test ẩn, trọng số 1·1·1·1·2·2, 2 giây/128 MB. Lần nộp WA 50/100 (quên số 0 và số âm) và AC 100/100 ngày 18/10 dùng đúng thời gian từng test. Câu báo lỗi cú pháp theo đúng định dạng grader in ra (`File "main.py", line …`). Trạng thái không có trên CSDL ghi rõ "[trạng thái mẫu]".
- **User duyệt 24/10**, kèm chế độ toàn màn hình (đề xuất ngoài plan).
- **Khớp với code:** sau khi code, canvas sửa theo code ở bản 8 (code thắng). Monaco tô hàm dựng sẵn (`int`, `print`) cùng màu từ khóa, vì bộ tách token Python của Monaco xếp chúng vào `keyword`.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Đề bài** | Khối viền mỏng, chữ `text-sm`, một dòng "Giới hạn: 2000 ms · 128 MB · 2 test mẫu · 4 test ẩn" | Thẻ `card`: tiêu đề "Đề bài" + 4 chip (Python 3, "2 giây mỗi test", 128 MB, "2 test mẫu · 4 test ẩn"). Đề vẽ bằng `<Markdown>` cỡ chữ thường. Test mẫu thành thẻ "Test #n" hai cột Đầu vào / Kết quả mong đợi |
| **Khung code** | Monaco viền mỏng, theme `light` của Monaco, font Consolas; nút "Khôi phục" ở tiêu đề mục; hai nút + một dòng ghi chú bên dưới | Một thẻ: thanh tab `main.py` + "Bản nháp tự lưu trên trình duyệt này" + "Khôi phục code mẫu" + nút **Toàn màn hình** (từ 1024 px). Monaco theo theme `devpath-light`: màu đọc từ biến `--color-*` của `globals.css`, font Geist Mono. Chân thẻ: ghi chú chạy thử + "Chạy thử"/"Nộp bài" (điện thoại: hai nút 44 px chia đôi) |
| **Đang chấm** | Hộp xám, spinner, "Đang chấm test k/n", thanh tiến độ một màu, lưới test hai cột với badge | Dải `muted`: **Naomi `grading`** (laptop sáng theo k/n, gõ phím mỗi khi một test xong), nhãn "Nộp bài · đang chấm", "Đang chấm test k/n", câu nói sandbox (không mạng, giới hạn giờ/bộ nhớ của bài), **thanh tiến độ mỗi test một đoạn** tô màu verdict khi test đó xong. Danh sách test một cột: chấm màu, `#n`, "Mẫu"/"Ẩn", trạng thái, thời gian |
| **Kết quả** | Một badge tông `emerald`/`rose`/`amber` + "Điểm: 50/100" + "Chậm nhất 418 ms"; mọi test liệt kê kèm bảng ba ô input/mong đợi/in ra cho mẫu | **Dải kết quả màu verdict** (7 tông): Naomi theo verdict (`celebrate`, `partial`, `sleepy`, `stuffed`, `dizzy`, `tangled`, `sorry`), chip `WA Sai kết quả`, "50/100 · Sai kết quả", gợi ý, **dòng chỉ test sai đầu tiên** ("Sai đầu tiên ở test #5 — test ẩn, chỉ biết đúng hay sai."), thanh tiến độ ở lại làm hình tóm tắt, "4/6 test đúng · chậm nhất 0,42 s". Test sai đầu tiên được tô nền; nếu là test mẫu thì ô so đầu ra **tự mở**, ô sai viền màu verdict. Dòng test mẫu sai ghi luôn "in ra 2, mong đợi 3" khi vừa một dòng. CE: khối "Thông báo của Python" viền lam |
| **Chạy thử** | Như kết quả, thêm nhãn "Chạy thử — không tính vào lịch sử" | Dải gọn **không có Naomi**: "Chạy thử · 2/2 test mẫu đúng", "Bấm “Nộp bài” để chấm với cả 4 test ẩn." |
| **Lịch sử** | Badge chữ + điểm + giờ máy (`toLocaleString`) + "Xem lại" | Chip verdict (mã + nhãn + icon), điểm, giờ Việt Nam "21:21 · 18/10/2026", "Xem lại"; dòng đang xem ghi "Đang xem". Mở lại thì đầu khối kết quả ghi "Xem lại bài nộp lúc …" + "Đưa code này vào editor" |
| **Toàn màn hình** (mới) | — | Thanh trên: "Thoát toàn màn hình", tên bài + khóa, hai nút. Đề bài 480 px bên trái, editor + khối kết quả (cuộn riêng) bên phải. Esc thoát. Là **cùng một cây React** với lớp khác (`display: contents` ở chế độ thường), nên Monaco không dựng lại: giữ con trỏ và lịch sử hoàn tác |
| **Nút hoàn thành** | "Đánh dấu hoàn thành" là nút chính, cạnh "Nộp bài" cũng là nút chính | Với bài code: nút viền + "Bài code tự hoàn thành khi bạn nộp đúng mọi test." (mỗi màn một nút chính; vẫn tự đánh dấu được, chứng chỉ giữ kiểu Udemy) |

**Naomi** (bản đồ phản ứng, thiết kế mục 5):
- Chỉ phản ứng với **lần nộp trang vừa gửi** (`reactTo` = id bài nộp đang theo dõi): `grading` một lần khi bắt đầu, rồi mood của verdict một lần.
- Mở lại từ lịch sử, đổi chế độ toàn màn hình hay trang vẽ lại thì đứng yên.
- Chạy thử không có Naomi, để phản ứng của nhân vật gắn với lần nộp thật.
- Khi đang chấm, 7 hình verdict được tải trước, nên đổi mood không phải chờ.
- Lỗi hệ thống (`status = error` hay SE) dùng `sorry`, màu xám, câu "không phải lỗi của bạn".

## 3. Lỗi tìm ra khi làm

- **Theme Monaco âm thầm rơi về mặc định.** CSS đã rút gọn đổi `#ffffff` thành `#fff`, nên phép kiểm "6 chữ số hex" thấy một màu không hợp lệ và dùng theme dự phòng. Ảnh chụp lộ ra lỗi: từ khóa vẫn xanh dương. Sửa bằng `longHex()` mở rộng hex 3 chữ số.
- **Vùng đọc màn hình chứa câu gợi ý sẽ làm E2E nhập nhằng.** Spec tìm "Chương trình in ra đúng kết quả mong đợi ở mọi test case." theo chuỗi con. Vì vậy vùng `aria-live` chỉ đọc tiêu đề ("100/100 · Đúng") và nằm sau nội dung. Vùng này là một phần tử cố định suốt lượt chấm. Một vùng mới gắn vào đã có chữ thì trình đọc màn hình không đọc, mà dải "đang chấm" bị thay khi có kết quả.
- **Dòng lịch sử ở 375 px rớt nút "Xem lại" xuống hàng riêng.** Chip + cột điểm 64 px + nút vượt 321 px. Cột điểm giờ chỉ cố định từ `sm`, khoảng cách 8 px trên điện thoại.
- **Luật cũ chặn `animate-pulse` ngoài skeleton** (`site-states.test.ts`). Đoạn "đang chấm" trên thanh tiến độ bỏ nhấp nháy; dòng test đã có icon quay.
- Hai lỗi của chính script chụp, ghi lại cho lần chạy sau:
  - Monaco tự thụt lề sau `for …:`, nên code mẫu chèn bằng `insertText` phải không có dòng thụt lề.
  - Tên nút "Xem lại" khớp cả "Đánh dấu để xem lại", nên phải tìm với `exact: true`.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **69/69** (13 test mới: `lib/grading/verdicts.test.ts` — đủ nhãn/gợi ý/mood/4 class cho 7 mã và class trỏ đúng token trong `globals.css`, bản đồ mood, mã lạ = SE, spec E2E còn chứa đúng câu gợi ý AC; `lib/grading/result-view.test.ts` — dòng theo thứ tự chạy, test ẩn không bao giờ mang output kể cả khi lọt tới client, tóm tắt lần WA thật, câu chỉ test sai, "in ra 2, mong đợi 3", hàng đợi, "0,37 s"/"1,5 giây", giờ Việt Nam) |
| `tsc --noEmit`, `eslint app components lib` | sạch |
| Hành vi trên Chrome thật ([`code-submission/check.cjs`](code-submission/check.cjs), stack dev, 4 lần chấm thật) | **15/15** ([`results.json`](code-submission/results.json)): chạy thử không có Naomi; nộp WA → `grading:playing → grading:still → partial:playing → partial:still`; AC → `celebrate` đúng một lần; không phản ứng lại khi vẽ lại; mở lại từ lịch sử đứng yên; kết quả được cuộn vào màn hình; toàn màn hình giữ đúng một Monaco, khóa cuộn trang, editor cao 432 px, đề bài 480 px bên trái; Esc thoát, bàn phím về nút "Toàn màn hình"; 375 px không tràn; giảm chuyển động: hiện `celebrate`, không phản ứng |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai, có trang bài code) | **0/132** ([`code-submission/overflow.json`](code-submission/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (23,4 s), không sửa spec: "Nộp bài", câu gợi ý AC và "100/100" giữ nguyên |
| `next build` không mạng (`frontend/scripts/build-offline.sh`, `--network none`, stack dev tắt) | xanh. Image `devpath-frontend:dev` cũ hơn PR #122 nên `node_modules` của nó thiếu `remark-gfm`; build chạy với volume `node_modules` của container dev (đã `npm install`) |

## 5. Ảnh — `code-submission/before/` và `code-submission/after/`

[`code-submission/capture.cjs`](code-submission/capture.cjs) dựng một học viên dùng một lần, ghi danh khóa Python miễn phí, rồi nộp code thật vào sandbox: 1 lần chạy thử và 8 lần nộp, cách nhau 11 s vì mỗi học viên phải chờ 10 s giữa hai lần nộp. Cuối cùng script chạy `purge_e2e`. `PHASE=before` chạy trên code của `main` @ `1e2f2eb`, `PHASE=after` trên nhánh này; cả hai đều trên stack dev với dữ liệu thật của lượt chạy đó.

| Ảnh | Trạng thái |
|---|---|
| `1-de-bai-{1440,375}` | Vừa mở bài, chưa nộp lần nào |
| `2-sai-ket-qua-{1440,375}` | WA 50/100, sai đầu tiên ở test ẩn #5 |
| `3-chay-thu-1440` | Chạy thử đúng 2/2 test mẫu |
| `4-sai-test-mau-1440` | WA 0/100, sai ngay test mẫu #1 (ô so tự mở) |
| `5-loi-cu-phap-1440` … `8-qua-bo-nho-1440` | CE, RE, TLE, MLE |
| `9-dang-cham-1440` | Đang chấm test k/6 (chỉ màn hình đầu) |
| `10-dung-{1440,375}` | AC 100/100 |
| `11-xem-lai-1440` | Mở lại lần WA đầu tiên từ lịch sử |
| `12-toan-man-hinh-1440` | Chỉ có ở "sau" |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh của mood.

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/code-submission/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/code-submission/check.cjs
```

## 6. Để lại

- **SE không chụp được:** không có cách làm sandbox lỗi theo ý muốn trên stack thật. Giao diện của nó có trên canvas (trạng thái 10), và logic có test.
- **CSP:** không chạy lại `csp-probe.cjs`. Nhóm này không tải thêm gì mới: Monaco và Geist Mono vốn cùng origin, hình Naomi là chunk đã đo ở task component. Phép đo ở gate sẽ phủ cả trang này.
- **Khung trang học** (header tiến độ, mục lục, tab Ghi chú/Hỏi đáp) giữ nguyên. Phần đó là việc của nhóm 4.
- **Theme tối cho Monaco:** vẫn là `vs-dark`, chờ quyết định theme tối của cả site.
