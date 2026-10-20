# Dialog

Hộp thoại chặn trang để xác nhận một việc không hoàn tác được, hoặc để điền một biểu mẫu ngắn.

**Code:** `frontend/components/ui/dialog.tsx` (viết tay; **đừng chạy `shadcn add dialog`**, lệnh đó ghi đè `button.tsx`). Bên dùng truyền `open`/`onOpenChange`, tiêu đề, mô tả và các nút.

## Luật

- Lớp phủ `overlay`; hộp `popover`, bo `radius-xl`, bóng `shadow-lg`, padding `space-6`, rộng tối đa 440px (biểu mẫu tới 560px).
- Tiêu đề `h3` là câu hỏi cụ thể ("Xóa bài "Vòng lặp for"?"), mô tả nói hậu quả bằng số khi có ("12 ghi chú").
- Nút: hành động bên phải, "Hủy" (`outline`) bên trái nó. Nút hành động mang đúng động từ của tiêu đề ("Xóa bài học"), không "OK"/"Đồng ý".
- Vào: mờ dần + phóng 0,96 → 1 trong `duration-slow`, `ease-enter`. Ra: `ease-exit` trong ~220ms. Khi `prefers-reduced-motion` chỉ mờ dần.
- Focus nhảy vào nút an toàn ("Hủy") khi mở, trả về nút đã mở dialog khi đóng; `Esc` đóng.
