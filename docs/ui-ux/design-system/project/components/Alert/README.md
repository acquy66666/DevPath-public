# Alert

Một thông báo nằm trong luồng trang, nói một chuyện và việc cần làm tiếp.

**Code:** `frontend/components/ui/alert.tsx` (`Alert`, `AlertTitle`, `AlertDescription`, `AlertAction`). Code có `default` và `destructive`; design system thêm `info`, `success`, `warning`. Bên dùng truyền `variant`, icon, tiêu đề và mô tả.

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
- `role="alert"` chỉ cho lỗi vừa xảy ra do thao tác của người dùng; còn lại `role="status"`. Code hôm nay đặt `role="alert"` cho mọi Alert, cần sửa ở task "Nền".
- Câu lỗi: chuyện gì xảy ra + dữ liệu của bạn đang ở đâu + cách thử lại. Không xin lỗi chung chung.
