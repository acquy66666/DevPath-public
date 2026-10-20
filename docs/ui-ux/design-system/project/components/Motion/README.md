# Motion

Cách mọi thứ trên DevPath chuyển động: thời lượng, đường cong, và lúc nào thì không động.

Không phải component; đây là luật dùng token `duration-*` và `ease-*`. Chuyển động trong code đi bằng CSS transition (Tailwind + `tw-animate-css`) và, cho nhân vật, thư viện Motion (`motion/react`).

## Ghép cặp

| Việc | Thời lượng | Đường cong |
|---|---|---|
| Nhấn nút (lún 1px), tick checkbox | `duration-instant` | `ease-standard` |
| Hover, focus, đổi màu | `duration-fast` | `ease-standard` |
| Tab, accordion, menu mở | `duration-base` | `ease-standard` / `ease-enter` |
| Dialog, toast, dòng mới đi vào | `duration-slow` | `ease-enter` |
| Đi ra | ~70% lúc vào | `ease-exit` |
| Thanh tiến độ, điểm và XP đếm lên | `duration-progress` | `ease-standard` |
| Ăn mừng: AC 100/100, quiz 100%, lên hạng | `duration-slow` | `ease-overshoot` |
| Một lần phản ứng của nhân vật | ≤ `duration-mascot` | theo từng `mood` |

Lò xo cho Motion (không phải token vì không viết được bằng giá trị CSS): giao diện `{ type: "spring", stiffness: 400, damping: 32 }` (không nảy); nhân vật `{ type: "spring", stiffness: 260, damping: 14 }` (nảy nhẹ).

## Luật

- Chỉ động `transform` và `opacity`. Không động `width`, `height`, `top`, `left`.
- Không hoạt ảnh nào chặn thao tác: nút bấm được ngay cả khi thứ bên cạnh còn đang chạy.
- Nhân vật phản ứng **một lần mỗi sự kiện vừa xảy ra trong phiên** (verdict qua WebSocket, quiz vừa nộp, chứng chỉ vừa cấp), rồi về tư thế nghỉ. Không lặp khi render lại, không chạy khi xem lại lịch sử.
- `prefers-reduced-motion: reduce`: bỏ mọi `transform` và trượt; chỉ còn đổi màu và mờ dần ≤ `duration-fast`; nhân vật đứng tư thế tĩnh của `mood` đó; thanh tiến độ nhảy thẳng tới giá trị. Kiểm bằng `page.emulateMedia({ reducedMotion: "reduce" })`.
- Ở khu giảng viên và admin, chuyển động chỉ để phản hồi thao tác. Không ăn mừng trên bảng số liệu.
