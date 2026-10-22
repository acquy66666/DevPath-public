# DropdownMenu

Danh sách lệnh hoặc đường dẫn mở ra từ một nút: menu tài khoản, menu điều hướng trên điện thoại, chuông thông báo.

**Code:** `frontend/components/ui/dropdown-menu.tsx` (Radix: `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuLabel`, `DropdownMenuSeparator`…). Bên dùng truyền nút mở (`asChild` quanh một `Button`) và các mục; mục là link thì `asChild` quanh `Link`.

## Luật

- Hộp `popover`, viền `border`, bo `radius-md`, bóng `shadow-md`, padding 4px. Rộng theo nội dung, tối thiểu 128px; menu tài khoản 224px.
- Mục cao tối thiểu 32px (40px trong menu điều hướng trên điện thoại), chữ 14px, icon 16px cách chữ 8px, bo `radius-sm`.
- Mục được trỏ hoặc chọn bằng bàn phím: nền `accent`. Mục là trang đang mở: nền `secondary`, chữ `secondary-foreground`, đậm 600, `aria-current="page"`.
- Mục `destructive` ("Xóa"): chữ `destructive-text`, khi trỏ nền `destructive-soft`.
- Nhãn đầu menu (tên, email, vai trò) không bấm được: tên đậm 600, phần còn lại `muted-foreground` 12px.
- Mở: mờ dần + phóng 0,96 → 1 trong `duration-base`, `ease-enter`; đóng trong `duration-fast`, `ease-exit`. Khi `prefers-reduced-motion` chỉ còn mờ dần.
- Nút mở chỉ có icon thì phải có `aria-label` ("Mở menu điều hướng"). Nút mở menu tài khoản đọc là "Tài khoản: <tên>".
- Phím mũi tên đi giữa các mục, `Esc` đóng và trả focus về nút mở (Radix đã lo).
