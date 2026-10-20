# QuizResult

Card kết quả ngay sau khi nộp quiz; màu và giọng đổi theo 4 mức điểm.

**Code hôm nay:** khối kết quả trong `frontend/components/quiz/quiz-workspace.tsx` chỉ có 2 tông (đạt: `emerald`, chưa đạt: `amber`). Design system tách 4 mức; làm ở nhóm màn 5 (Quiz).

Bên dùng truyền `score` (0–100), `pass_score`, số câu đúng/tổng, và cờ `just_submitted`. Chỉ khi `just_submitted` thì nhân vật phản ứng và vòng điểm chạy từ 0 (`duration-progress`, `ease-standard`).

| Mức | Điểm | Chữ | Nền | Vòng điểm | `mood` |
|---|---|---|---|---|---|
| party | 100% | `quiz-party` | `quiz-party-soft` | `quiz-party-solid` | `party` |
| proud | ≥ 80% | `quiz-proud` | `quiz-proud-soft` | `quiz-proud-solid` | `proud` |
| cheer | 50–79% | `quiz-cheer` | `quiz-cheer-soft` | `quiz-cheer-solid` | `cheer` |
| comfort | < 50% | `quiz-comfort` | `quiz-comfort-soft` | `quiz-comfort-solid` | `comfort` |
| hết giờ | 0 (backend chấm) | `verdict-tle` | `verdict-tle-soft` | — | `startled` |

Ngưỡng 80/50 là giả định của tài liệu thiết kế. "Đạt" vẫn theo `pass_score` của từng quiz: một quiz đặt ngưỡng 60% thì 65% là đạt, dù màu vẫn là `cheer`.

## Luật

- Mức thấp nhất là **an ủi**, không phải lỗi: tím dịu, không đỏ. Câu chữ chỉ việc làm tiếp ("Ôn lại bài 4 rồi thử lần nữa"), không trách.
- Điểm bằng `numeral` với `tabular-nums`; câu tiêu đề bằng `title`; dòng phụ bằng `body-sm`.
- Mức `party` được dùng `ease-overshoot` một lần. Các mức khác không nảy.
- Vòng điểm chỉ trang trí (`aria-hidden`); con số mới là nội dung.
