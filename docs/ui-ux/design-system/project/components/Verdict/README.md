# Verdict

Kết quả chấm một bài code: mã verdict, nhãn tiếng Việt, icon và màu riêng cho từng loại trong 7 loại.

**Code (nhóm màn 3, 24/10/2026):** `frontend/lib/grading/verdicts.ts` giữ nhãn, gợi ý, `mood` (`VERDICT_MOOD`) và class màu (`VERDICT_CLASSES`: `text`/`soft`/`solid`/`border`) của từng mã. Chip là `components/exercise/verdict-chip.tsx`; chấm, thanh tiến độ và danh sách test là `case-list.tsx`; dải kết quả là `run-result.tsx`. `lib/grading/verdicts.test.ts` đỏ khi một mã thiếu nhãn, `mood` hay token.

Bên dùng truyền mã verdict (`AC`…`SE` hoặc `null` = chưa chấm). Component tự lấy nhãn và gợi ý từ `verdicts.ts`. Mã lạ (grader thêm mã mới trước frontend) được vẽ như `SE`.

| Mã | Nhãn | Chữ/icon | Nền | Chấm, đoạn tiến độ | `mood` nhân vật |
|---|---|---|---|---|---|
| AC | Đúng | `verdict-ac` | `verdict-ac-soft` | `verdict-ac-solid` | `celebrate` (AC = mọi test đúng, 100/100) |
| WA | Sai kết quả | `verdict-wa` | `verdict-wa-soft` | `verdict-wa-solid` | `partial` |
| TLE | Quá thời gian | `verdict-tle` | `verdict-tle-soft` | `verdict-tle-solid` | `sleepy` |
| MLE | Quá bộ nhớ | `verdict-mle` | `verdict-mle-soft` | `verdict-mle-solid` | `stuffed` |
| RE | Lỗi khi chạy | `verdict-re` | `verdict-re-soft` | `verdict-re-solid` | `dizzy` |
| CE | Lỗi cú pháp | `verdict-ce` | `verdict-ce-soft` | `verdict-ce-solid` | `tangled` |
| SE | Lỗi hệ thống | `verdict-se` | `verdict-se-soft` | `verdict-se-solid` | `sorry` |

## Luật

- **Màu không bao giờ đứng một mình.** Luôn có mã (chữ mono) + nhãn + icon. Người mù màu đọc được bằng chữ, trình đọc màn hình đọc nhãn.
- SE dùng màu trung tính (`slate`), không đỏ: lỗi của hệ thống, không phải của học viên. Câu chữ nói rõ điều đó (`VERDICT_HINTS.SE`).
- Ba hình thái: **chip** (cao 28px, `radius-full`) trong lịch sử nộp bài; **dải kết quả** (`radius-lg`, chữ `h3` + gợi ý `body-sm`) trên đầu khối kết quả; **chấm** 10px `radius-xs` ở từng dòng test.
- Thanh tiến độ chấm: một đoạn mỗi test, tô `verdict-*-solid` khi khung WebSocket báo test đó xong, đoạn đang chấm `primary` nhạt, đoạn chưa chấm `border-strong`. Lúc chấm có `role="progressbar"` với `aria-valuenow` = số test đã chấm; chấm xong thanh ở lại trong dải kết quả làm hình tóm tắt (`role="img"`, "4/6 test đúng").
- Test sai đầu tiên được tô nền `verdict-*-soft`, có một dòng chỉ tới nó; nếu là test mẫu thì ô so "Đầu vào / Mong đợi / Chương trình in ra" tự mở, ô sai viền `verdict-*-solid`. Test ẩn chỉ có mã và thời gian.
- Verdict tới qua WebSocket thì phản ứng một lần (`ease-overshoot` chỉ cho AC 100/100). Mở lại lịch sử thì hiện tĩnh. **Chạy thử không có nhân vật**: chỉ lần nộp thật được phản ứng.
