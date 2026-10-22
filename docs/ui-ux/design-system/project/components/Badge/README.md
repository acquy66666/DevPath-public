# Badge

Một hai chữ trạng thái đặt cạnh tên một thứ: khóa học, đơn hàng, câu hỏi.

**Code:** `frontend/components/ui/badge.tsx`. Bên dùng truyền `variant` và chữ; `asChild` khi badge là link.

| Biến thể | Token | Ví dụ |
|---|---|---|
| `default` | `primary` / `primary-foreground` | "Mới" |
| `secondary` | `secondary` / `secondary-foreground` | Tên danh mục: "Python" |
| `outline` | viền `border-strong`, chữ `foreground` | "Bản nháp" |
| `muted` *(thêm)* | `muted` / `muted-foreground` | "Đã lưu trữ" |
| `success` / `warning` / `info` / `destructive` *(thêm)* | `*-soft` / `*-text` | "Đã xuất bản", "Chờ duyệt", "Miễn phí", "Bị từ chối" |
| `reward` *(thêm)* | `reward` / `reward-foreground` | "+30 XP" |
| `streak` *(thêm)* | nền `reward-soft`, chữ `streak-text`, lửa `streak` | "7 ngày" |

Biến thể *(thêm)* có trong code từ task "Nền" (22/10/2026). Các màn còn class `bg-emerald-*`/`bg-amber-*` viết tay chuyển sang chúng khi nhóm màn của mình được thiết kế lại.

## Luật

- Cao 22px, bo `radius-full`, chữ 12px đậm 600, không xuống dòng.
- Badge không phải nút: không hover, trừ khi nó là link.
- Verdict chấm bài **không** dùng Badge mà dùng `Verdict` (có mã + icon).
- Số trong badge dùng `tabular-nums`.
