# Verdict

Kết quả chấm một bài code: mã verdict, nhãn tiếng Việt, icon và màu riêng cho từng loại trong 7 loại.

**Code hôm nay:** `frontend/lib/grading/verdicts.ts` (`VERDICT_LABELS`, `VERDICT_HINTS`, `verdictTone`) cùng `components/exercise/live-cases.tsx`, `run-result.tsx`. Code chỉ có 3 tông (`pass`/`fail`/`system`) viết bằng class `emerald`/`rose`/`amber`. Design system tách thành 7 tông. Phần này làm ở nhóm màn 3 (Nộp bài code).

Bên dùng truyền mã verdict (`AC`…`SE` hoặc `null` = chưa chấm). Component tự lấy nhãn và gợi ý từ `verdicts.ts`.

| Mã | Nhãn | Chữ/icon | Nền | Chấm, đoạn tiến độ | `mood` nhân vật |
|---|---|---|---|---|---|
| AC | Đúng | `verdict-ac` | `verdict-ac-soft` | `verdict-ac-solid` | `celebrate` (100/100), `partial` (một phần) |
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
- Thanh tiến độ chấm: một đoạn mỗi test, tô `verdict-*-solid` khi khung WebSocket báo test đó xong, đoạn chưa chấm để `muted`. Có `role="progressbar"` với `aria-valuenow` = số test đã chấm.
- Verdict tới qua WebSocket thì phản ứng một lần (`ease-overshoot` chỉ cho AC 100/100). Mở lại lịch sử thì hiện tĩnh.
