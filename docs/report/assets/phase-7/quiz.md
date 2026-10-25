# Phase 7 — Nhóm màn 5: Quiz (25/10/2026)

Nhóm màn 5 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): làm bài có đồng hồ, kết quả theo 4 mức (`party` / `proud` / `cheer` / `comfort`) và `startled` khi hết giờ. Nhánh `feature/phase7-quiz`, chồng lên `feature/phase7-learn-page` (PR #124 chưa merge). Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 5: Quiz"**: <https://claude.ai/artifact/UDrWjt17EWn5E3ohFCiNmo>. Bản trong repo: [`docs/ui-ux/quiz/canvas/`](../../../ui-ux/quiz/canvas/project/canvas.json).

- **6 artboard:**
  - Đang làm bài, có giờ (1440);
  - Kết quả vừa nộp, 80%, đạt, xem lại cả 5 câu (1440);
  - Đang làm bài (375) và kết quả (375);
  - Năm kiểu kết quả: 100%, ≥ 80%, 50–79%, dưới 50%, hết giờ; cộng một lượt cũ mở lại từ lịch sử;
  - Trạng thái: chưa làm lượt nào, đã làm chưa đạt, đang làm dở, không tính giờ + bài đã xong, thanh làm bài (bình thường / dưới 1 phút / không tính giờ / đang nộp), chưa mở, đang tải.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 5 hình chép từ canvas linh vật: `party`, `proud`, `cheer`, `comfort`, `startled`.
- **Dữ liệu thật:** quiz "Kiểm tra: vòng lặp for" của khóa Python trên CSDL dev. Đây là 5 câu AI soạn từ transcript, giảng viên duyệt ở gate Phase 4 ([`phase-4/quiz-demo.txt`](../phase-4/quiz-demo.txt)), giữ nguyên đáp án và lời giải thích. Quiz này không tính giờ, nên giới hạn 10 phút ở artboard "Đang làm bài" là trạng thái mẫu (ghi ở tên artboard).
- **User duyệt 25/10.**
- **Khớp với code:** canvas bản 8 đã được sửa theo code (code thắng). Lịch sử là một thẻ riêng dưới màn đầu. Dòng thời gian có ngày ("nộp lúc 16:26 · 25/10/2026"). Lượt cũ mở lại giữ câu chữ của mức điểm. Trên điện thoại, nhãn "Bạn chọn · đáp án đúng" nằm dòng riêng, và hàng nút dưới bài giữ bố cục của `LessonActions`.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Trước khi làm** | Một khung viền: "Bài trắc nghiệm", 3 badge, một câu về đồng hồ, nút | Thẻ có biểu tượng, câu mô tả. Lượt đầu có 3 ô thông tin (Số câu / Thời gian / Điểm đạt). Có lịch sử thì gọn thành một dòng "5 câu · 10 phút · đạt từ 70%", kèm "Điểm cao nhất của bạn" hoặc "Bạn đã đạt bài này: cao nhất 80% sau 2 lượt". Lượt đang làm dở có hộp thông tin "bắt đầu lúc …, đồng hồ vẫn chạy". Đầu bài ghi "Quiz · 5 câu" |
| **Thanh làm bài** | "Đã trả lời 3/5 câu" + đồng hồ `9:56`, đỏ khi ≤ 30 s; `aria-live` trên đồng hồ đọc từng giây | Thanh dính: số câu đã trả lời, **một nút cho mỗi câu** (đã trả lời thì tô ngọc, bấm thì tới câu đó và đặt focus), đồng hồ `06:42` "còn lại trong 10 phút". Dưới 1 phút thì đồng hồ chuyển màu hổ phách (`verdict-tle`) và ghi "Còn dưới 1 phút". Đồng hồ là `role="timer"` im lặng; vùng đọc chỉ báo lúc còn 5 phút, 1 phút, 10 giây. Điện thoại: đồng hồ nằm chung dòng với số câu |
| **Câu hỏi** | "Câu 1. …" trên một dòng, radio của trình duyệt | "CÂU 1 / 5" + "Đã trả lời", câu hỏi cỡ `body-lg`; mỗi phương án là thẻ cao 52 px có chữ cái A–D, chọn thì viền và nền ngọc. Radio thật nằm trong nhãn: phím mũi tên đi giữa các phương án |
| **Code trong câu hỏi** | In nguyên dấu backtick: "là \`range(5)\`" (ghi nhận từ gate Phase 4) | `range(5)` vẽ thành code ở câu hỏi, phương án và lời giải thích (`lib/quiz/inline-code.ts`) |
| **Nộp bài** | Nút "Nộp bài" trơn ở cuối | Thẻ cuối: "Còn 2 câu chưa trả lời: câu 4 và câu 5" + "Câu bỏ trống tính là sai…", nút chính 44 px |
| **Tải lại giữa chừng** | Mất mọi câu đã chọn (máy chủ chỉ lưu đáp án khi nộp), đồng hồ vẫn chạy | Câu đã chọn được giữ trong trình duyệt này đến khi nộp (`localStorage`, theo id lượt làm) |
| **Kết quả** | Khung xanh hoặc vàng: "80%" + một câu | Dải màu theo mức. Có Naomi, chip (Điểm tuyệt đối / Đạt / Chưa đạt / Hết giờ), "Lượt 2", "80% · 4/5 câu đúng", câu gợi ý theo mức. Có dòng **"↓ Câu sai: câu 3"** (bấm thì tới câu đó), thanh một đoạn mỗi câu (đúng / sai / bỏ trống) và "Làm trong 0:45 · nộp lúc …". Sau khi nộp, trang cuộn tới dải kết quả và đặt focus vào đó |
| **Nút ở kết quả** | "Làm lại" (về màn đầu) | "Làm lại" bắt đầu ngay lượt mới. Dưới 50% và bài chưa xong: "Ôn lại chương 3" (về bài đầu chương) là nút chính, "Làm lại" là nút viền |
| **Xem lại từng câu** | Mỗi câu một khung; "đáp án đúng" / "bạn chọn" chữ nhỏ cạnh phương án | Thẻ có "Câu 3 · Sai" (dấu, chữ và màu); đáp án đúng viền xanh có dấu tích, câu chọn sai viền đỏ có dấu X, nhãn "Bạn chọn · đáp án đúng" / "Đáp án đúng" / "Bạn chọn"; lời giải thích trong hộp "GIẢI THÍCH". Bộ lọc **"Tất cả · 5 / Câu sai · 1"** |
| **Hết giờ** | "Hết giờ trước khi bài được nộp nên lượt này tính 0 điểm." và 5 câu "Bạn chưa trả lời câu này" | Dải hổ phách, Naomi `startled`, "0% · Bài chưa kịp nộp", câu nói rõ vì sao 0 điểm; mỗi câu ghi "Chưa nộp" thay vì "Bỏ trống" (máy chủ không nhận được câu nào, không ai biết học viên đã chọn gì) |
| **Lịch sử** | "Lượt đã làm": giờ + điểm, không mở lại được | Thẻ "Lượt đã làm · 4 lượt · cao nhất 80%": "Lượt k", điểm trong màu của mức, Đạt/Chưa đạt, giờ · ngày, **"Xem lại"** mở lại bài đã chấm (endpoint `GET /quiz-attempts/{id}` có sẵn, trước đây không dùng). Lượt đang xem ghi "Đang xem" |
| **Chưa mở / đang tải** | Alert "chưa được mở"; khối xám 160 px | Thẻ ổ khóa "Bài trắc nghiệm này chưa được mở…"; skeleton đúng khung màn đầu |

**Naomi** (bản đồ phản ứng, thiết kế mục 5): `party` 100%, `proud` ≥ 80%, `cheer` 50–79%, `comfort` dưới 50%, `startled` khi máy chủ chấm hết giờ. Ngưỡng 80/50 của design system được giữ; đạt hay không vẫn theo điểm đạt của từng quiz. Naomi chỉ phản ứng với lượt vừa nộp trên trang. Lượt mở lại từ lịch sử thì đứng yên. Năm hình được tải trước trong lúc làm bài, để kết quả không phải chờ tải hình.

**Một nút chính mỗi màn:** khi đang làm bài, "Nộp bài" là nút chính và "Bài tiếp theo" giữ màu phụ, kể cả khi bài đã xong từ trước. Ở màn đầu và màn kết quả, bài chưa xong thì nút bắt đầu / làm lại là nút chính. Bài đã xong thì "Bài tiếp theo" là nút chính, còn "Làm lại" là nút viền.

## 3. Lỗi tìm ra khi làm

- **Tải lại giữa một quiz có giờ là mất hết câu đã chọn**, trong khi đồng hồ ở máy chủ vẫn chạy. Ảnh `before/8-sap-het-gio-1440` cho thấy "Đã trả lời 0/5 câu" sau khi tiếp tục. Giờ câu đã chọn được giữ trong trình duyệt đến lúc nộp.
- **Đồng hồ cũ có `aria-live="polite"`**, nên trình đọc màn hình đọc nó mỗi giây.
- **Dấu backtick in nguyên văn** ở câu hỏi AI soạn (ghi từ gate Phase 4, chưa sửa ở task UX Phase 6).
- **Lượt hết giờ ghi "Bạn chưa trả lời câu này" ở cả 5 câu.** Máy chủ không lưu đáp án của lượt quá giờ, nên câu đó nói sai về học viên.
- Lỗi của chính script, ghi lại cho lần sau:
  - Lùi giờ lượt đang làm 10 phút thì lượt đó thành cũ hơn các lượt vừa làm, làm số lượt trong lịch sử sai. Giờ trước mỗi lần lùi, script đẩy các lượt đã nộp lùi thêm 30 phút.
  - Ảnh chụp cả trang khi đang cuộn vẽ thanh dính ở giữa ảnh. Giờ script cuộn về đầu trước khi chụp.
  - "Bài chưa kịp nộp" có ở cả tiêu đề lẫn vùng đọc ẩn, nên phải tìm theo heading.
  - `getByText` không phân biệt hoa thường, nên "· Bỏ trống" cũng khớp "bỏ trống" trong dòng trỏ câu sai; phải dùng `exact`.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **100/100** (18 test mới: `lib/quiz/result-view.test.ts` 13 — mức điểm, Naomi và màu theo mức, trạng thái từng câu, câu chữ của dải kết quả, đạt theo điểm đạt của quiz chứ không theo màu, dòng trỏ câu sai, dòng câu bỏ trống, thời gian làm, lời báo đồng hồ, đánh số lượt; `lib/quiz/inline-code.test.ts` 4; `lib/learn/position.test.ts` +1 — bài đầu chương) |
| `tsc --noEmit`, `eslint components/quiz components/learn lib/quiz lib/learn` | sạch |
| Hành vi trên Chrome thật ([`quiz/check.cjs`](quiz/check.cjs), stack dev, cho phép chuyển động) | **26/26** ([`results.json`](quiz/results.json)): nút chính đúng ở từng màn; focus khi mở bài / nộp / đóng lượt cũ; Tab + Space + mũi tên; nút số câu không bị thanh dính che; đồng hồ im lặng; tải lại vẫn còn câu đã chọn; dưới 1 phút đổi màu; vùng đọc "80%. Đạt. 4/5 câu đúng."; Naomi `proud` phản ứng (`data-phase` playing), lượt cũ đứng yên; bộ lọc; "Ôn lại chương 3" trỏ về bài đầu chương; hết giờ "Chưa nộp" ×5; quiz không tính giờ không có `timer`; 3 lần đo 375 px không tràn |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai, có trang học quiz) | **0/132** ([`quiz/overflow.json`](quiz/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (19,6 s), không sửa spec (luồng vàng không đi qua quiz) |
| `next build` không mạng (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) | xanh |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải thêm gì mới. Hình Naomi `party`/`proud`/`cheer`/`comfort`/`startled` là chunk cùng origin đã đo ở task component |

## 5. Ảnh — `quiz/before/` và `quiz/after/`

[`quiz/capture.cjs`](quiz/capture.cjs) dựng một học viên dùng một lần, ghi danh khóa Python miễn phí, tick mọi bài trước quiz. Script đặt quiz 10 phút cho lượt chạy (ghi thẳng `quizzes.time_limit_s`, trả lại cuối cùng), rồi làm 5 lượt: 20%, 60%, hết giờ, 80% (lượt đạt), 100%. "Sắp hết giờ" và "hết giờ" có được bằng cách lùi `started_at` của lượt đang làm, vì máy chủ tính giờ theo cột đó. Cuối cùng `purge_e2e` xóa học viên. `PHASE=before` chạy trên `feature/phase7-learn-page` @ `1355be9` (file script nằm ngoài cây git lúc đó), `PHASE=after` chạy trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-truoc-khi-lam-{1440,375}` | Chưa làm lượt nào, quiz 10 phút |
| `2-muc-20-1440` | Lượt 1: 20% (`comfort`), một câu bỏ trống |
| `3-muc-60-1440` | Lượt 2: 60% (`cheer`), chưa tới điểm đạt 70% |
| `4-het-gio-1440` | Lượt 3: nộp sau hạn + 10 s ân hạn, máy chủ chấm 0 |
| `5-co-lich-su-1440` | Quay lại bài: màn đầu + lịch sử 3 lượt |
| `6-dang-lam-{1440,375}` | Đang làm, đã trả lời 3/5 |
| `7-lam-do-1440` | Rời trang rồi quay lại: lượt đang làm dở |
| `8-sap-het-gio-1440` | Tiếp tục với dưới 1 phút (trước: 0/5 câu còn lại; sau: 3/5, đồng hồ hổ phách) |
| `9-ket-qua-80-{1440,375}` | Lượt 4: 80% (`proud`), đạt, bài tự hoàn thành |
| `10-muc-100-1440` | Lượt 5: 100% (`party`) |
| `11-xem-lai-luot-cu-1440` | Chỉ có ở "sau": mở lại lượt 1 từ lịch sử |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh. Thời gian "Làm trong 0:01" là tốc độ của script.

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/quiz/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/quiz/check.cjs
```

## 6. Để lại

- **Lượt cũ mở lại giữ câu gợi ý của mức điểm** ("Ôn lại chương này rồi thử lần nữa"), kể cả khi một lượt sau đã đạt. Muốn câu khác thì `resultCopy` cần biết lượt này có phải lượt mới nhất không.
- **Lịch sử không phân biệt được lượt hết giờ với lượt 0% thật**: `AttemptOut` không có cờ `expired` (backend đứng yên), nên dòng lịch sử ghi "0% · Chưa đạt". Mở lượt đó ra thì thấy đúng là hết giờ.
- **XP không hiện ở kết quả.** Lượt đạt đầu tiên được cộng XP (`quiz_passed` +20), nhưng API kết quả không trả về số XP đã cộng. Đoán từ lịch sử thì dễ sai, nên không ghi.
- **Quiz vẫn là danh sách mọi câu trên một trang**, chưa làm kiểu từng câu một. Với 5–20 câu, nút số câu trên thanh dính đủ để đi lại, và một trang thì xem lại được mọi câu trước khi nộp.
