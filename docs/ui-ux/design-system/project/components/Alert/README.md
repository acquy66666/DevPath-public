# Alert

Một thông báo nằm trong luồng trang, nói một chuyện và việc cần làm tiếp.

**Code:** `frontend/components/ui/alert.tsx` (`Alert`, `AlertTitle`, `AlertDescription`, `AlertAction`). Đủ năm biến thể trong code từ task "Nền" (22/10/2026). Bên dùng truyền `variant`, icon, tiêu đề và mô tả.

| Biến thể | Nền | Chữ | Icon | `role` |
|---|---|---|---|---|
| `info` *(thêm)* | `info-soft` | `info-text` | `info` | `status` |
| `success` *(thêm)* | `success-soft` | `success-text` | `success` | `status` |
| `warning` *(thêm)* | `warning-soft` | `warning-text` | `warning` | `status` |
| `destructive` | `destructive-soft` | `destructive-text` | `destructive` | `alert` |
| `default` | `card` + viền `border` | `card-foreground` | `muted-foreground` | `status` |

## Luật

- Bo `radius-md`, padding `space-3` × `space-4`, chữ 14px. Tiêu đề đậm 600, mô tả cùng màu chữ.
- Không viền màu bên trái. Sắc thái nằm ở nền nhạt và icon.
- `role="alert"` chỉ cho lỗi vừa xảy ra do thao tác của người dùng; còn lại `role="status"`. Trong code, `destructive` mặc định là `alert`, bốn biến thể kia là `status`; truyền `role` để nói khác.
- Câu lỗi: chuyện gì xảy ra + dữ liệu của bạn đang ở đâu + cách thử lại. Không xin lỗi chung chung.
