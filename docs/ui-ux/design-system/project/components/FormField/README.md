# FormField

Một trường biểu mẫu đủ bốn phần: nhãn, ô nhập, gợi ý và lời báo lỗi.

**Code:** `frontend/components/ui/form-field.tsx` ghép `label.tsx` với `input.tsx`, `textarea.tsx` hoặc `native-select.tsx`. Bên dùng truyền `label`, `id`, gợi ý, lỗi (chuỗi hoặc rỗng) và ô nhập làm con.

## Luật

- Nhãn luôn hiện, đặt trên ô (14px đậm 600). Placeholder chỉ là ví dụ, không thay nhãn.
- Ô nhập cao 40px, chữ 16px (để iOS không tự phóng to), nền `card`, viền `input` (≥ 3:1), bo `radius-md`, bóng `shadow-xs`. Đã vào code ở task "Nền" (22/10/2026; trước đó 32px, chữ 14px từ md).
- Focus: `outline 2px var(--ring)`, `outline-offset 2px`.
- Lỗi: viền `destructive`, `aria-invalid="true"`, lời báo ngay dưới ô bằng `destructive-text` kèm icon, nối với ô qua `aria-describedby`. Câu lỗi nói điều cần sửa ("Mật khẩu cần ít nhất 8 ký tự."), không chỉ "Không hợp lệ".
- Vô hiệu: nền `muted`, chữ `muted-foreground`, viền `border-strong`, kèm một dòng gợi ý vì sao. (Bản đầu ghi `slate-300`; code chỉ đọc lớp ngữ nghĩa nên dùng `border-strong`, và code thắng.)
- Khoảng giữa các trường `space-4`; giữa nhãn, ô và gợi ý 6px.
- Form đăng nhập/đăng ký: giữ điều kiện "chỉ gửi sau khi hydrate" mà E2E và `capture.cjs` dựa vào. Đổi giao diện không được đổi cơ chế đó.
