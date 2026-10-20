# Card

Khung chứa một thứ có thể tách riêng: một khóa học, một con số, một nhóm cài đặt.

**Code:** `frontend/components/ui/card.tsx` (`Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardAction`, `CardContent`, `CardFooter`; `size="sm"` cho bản gọn). Card khóa học là `components/courses/*`, ô thống kê là `components/instructor/stats/stat-tile.tsx`.

## Luật

- Nền `card`, viền 1px `border`, bo `radius-lg`, padding `space-4` (bản gọn `space-3`). **Lúc yên không có bóng**: card nằm trên `background` đã đủ tách bằng viền.
- Card bấm được (cả card là một link): hover thêm `shadow-md` và viền `border-strong` trong `duration-fast`; focus ring bao cả card.
- Không lồng card trong card. Một card có nhiều phần thì chia bằng đường `border`.
- Không viền màu bên trái để "nhấn". Muốn báo trạng thái thì dùng `Badge`, `Alert` hoặc nền `*-soft` cho cả khối.
- Ảnh bìa khóa học dự phòng (`components/courses/course-cover.tsx`): gradient `<họ>-50` → `<họ>-200` và icon `<họ>-600`, họ màu chọn theo id khóa trong `jade`, `blue`, `violet`, `rose`, `amber`, `green`, `orange`, `turmeric`. Tỉ lệ 16:9.
- Giá tiền: `title` + `tabular-nums`, dấu chấm hàng nghìn, ký hiệu "₫" sau số.
- Ô thống kê: nhãn `body-sm muted-foreground`, số `numeral`, dòng so sánh `body-sm` màu `success-text` / `destructive-text`, và luôn có chữ ("+120 trong tuần này"), không chỉ mũi tên màu.
- Empty state trong card: một câu nói chưa có gì + cách tạo cái đầu tiên. Nhân vật (khi có) đứng bên trái câu đó.
