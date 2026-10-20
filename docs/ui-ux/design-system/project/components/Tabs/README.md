# Tabs

Chuyển giữa các phần ngang hàng của cùng một chỗ mà không rời trang.

**Code:** `frontend/components/ui/tabs.tsx` (Radix: `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`). Bên dùng truyền `value` / `onValueChange` và **một `TabsContent` cho mỗi `TabsTrigger`**. Thiếu `TabsContent` là lỗi axe critical đã đo ở bảng xếp hạng (`docs/report/assets/phase-7/before.md`).

## Hai kiểu

- **Khay** (mặc định): khay `muted` bo `radius-md`, tab đang chọn nền `card` + `shadow-sm`, chữ `foreground`; tab khác chữ `muted-foreground`. Dùng cho 2–4 phần ngắn: "Ghi chú | Hỏi đáp | Trợ giảng AI".
- **Gạch chân** *(thêm)*: đường `border` dưới cả hàng, tab đang chọn có vạch 2px `primary`. Dùng khi tab là bộ lọc của cả trang: kỳ bảng xếp hạng, thanh tab admin. Hàng tab dài hơn khung thì cuộn ngang trong chính nó, không làm tràn trang (thanh tab admin 10 mục đang tràn ở 1440px).

## Luật

- Tab cao 32px (khay) / 40px (gạch chân), chữ 14px đậm 600.
- Đổi tab: nền và bóng chuyển trong `duration-base` với `ease-standard`; nội dung đổi ngay, không trượt.
- Phím mũi tên đi giữa các tab (Radix đã lo); focus ring `ring`.
- Mở thẳng một tab bằng URL thì dùng query string như code đang làm (`?hoi-dap=<id>`).
