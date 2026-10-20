# Button

Nút cho mọi hành động; mặc định là nút trầm, `primary` chỉ dành cho việc chính của màn đó.

**Code:** `frontend/components/ui/button.tsx` (`Button`, `buttonVariants`). Bên dùng truyền `variant`, `size`, nội dung và `onClick`; `asChild` để bọc một `Link`.

## Biến thể

| `variant` | Token | Khi nào |
|---|---|---|
| `default` (primary) | `primary` → `primary-hover`, chữ `primary-foreground` | Một lần mỗi màn: "Nộp bài", "Thanh toán", "Ghi danh" |
| `secondary` | `secondary` → `secondary-hover`, chữ `secondary-foreground` | Hành động phụ cùng nhóm: "Chạy thử" cạnh "Nộp bài" |
| `outline` | nền `card`, viền `input`, `shadow-xs`; hover `accent` | Hành động trung tính: "Xem lại", "Xuất Excel" |
| `ghost` | hover `accent` | Hủy, đóng, hành động trong thanh công cụ |
| `destructive` | `destructive`, chữ `destructive-foreground` | Xóa, gỡ, hạ khóa. Luôn có dialog xác nhận |
| `link` | `link`, gạch chân | Hành động nằm trong một câu |

## Kích thước

`sm` 32px · mặc định 36px · `lg` 44px · `icon` 36×36. **Đề xuất đổi so với code hiện tại** (32/28/36px): mặc định lên 36px, và nút chính trên điện thoại dùng `lg` để vùng chạm đủ 44px. Bo góc `radius-md`, chữ 14px đậm 600.

## Luật

- Nhãn là động từ đứng đầu, viết hoa kiểu câu: "Nộp bài", "Thêm test case". Không dấu chấm than.
- Đang xử lý: giữ nhãn dạng tiến trình kèm dấu "…" ("Đang lưu…") và `disabled`. Không đổi chiều rộng nút.
- Nút chỉ có icon phải có `aria-label`.
- Focus: `outline 2px var(--ring)`, `outline-offset 2px`. Không bỏ focus ring.
- Nhấn: lún 1px trong `duration-instant`; đổi màu trong `duration-fast` với `ease-standard`. Khi `prefers-reduced-motion` chỉ còn đổi màu.
- Không dùng `primary` cho hai nút cạnh nhau; nút thứ hai là `secondary` hoặc `outline`.
