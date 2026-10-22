# Pager

"Trang 2 / 5" giữa hai nút, dưới một danh sách phân trang của API (`{items, total, page, page_size}`).

**Code:** `frontend/components/ui/pager.tsx`. Bên dùng truyền `page`, `pageSize`, `total` và `onPage`. Danh sách vừa một trang thì Pager không vẽ gì.

## Luật

- Hai nút `ghost` cỡ `sm` (32px) ở hai đầu, chữ "Trang trước" / "Trang sau" kèm chevron 16px; giữa là "Trang k / n" bằng `muted-foreground`, `tabular-nums` để số không làm hàng nhảy.
- Ở trang đầu/cuối, nút tương ứng `disabled` (mờ 50%), không biến mất, để hai nút không đổi chỗ.
- Bọc trong `<nav aria-label="Phân trang">`. Icon `aria-hidden`; tên của nút là chữ.
- Không có ô nhập số trang: danh sách của DevPath ngắn (tối đa vài chục trang).
