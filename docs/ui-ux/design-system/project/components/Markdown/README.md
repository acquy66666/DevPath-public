# Markdown

Chữ một người viết cho người khác đọc: bài đọc, đề bài code, câu hỏi và trả lời trong Hỏi đáp.

**Code:** `frontend/components/ui/markdown.tsx` (`react-markdown`, không render HTML thô: `<script>` trong bài hiện ra đúng các ký tự đã gõ). Bên dùng truyền chuỗi Markdown và, nếu cần, cỡ chữ của khối (`className="text-sm"` cho đề bài gọn).

## Luật

- Tiêu đề lùi một bậc: `#` của tác giả thành `h2` vì `h1` của trang là tên bài. Tiêu đề đậm 600, cách đoạn trên 8px.
- Đoạn văn giữ xuống dòng của tác giả. Bài đọc dùng `body-lg`, tối đa ~70 ký tự mỗi dòng (giới hạn đặt ở màn trang học).
- Code trong dòng: nền `muted`, bo `radius-xs`, Geist Mono 0,85em. Khối code: nền `muted`, bo `radius-md`, padding 12px, cuộn ngang trong chính nó.
- Link: `link`, gạch chân, mở tab mới (`noreferrer noopener`) vì nó dẫn ra ngoài bài.
- Trích dẫn: vạch trái 2px `border-strong`, chữ `muted-foreground`. Đây là kiểu chữ của Markdown, không phải "card viền màu bên trái".
- Danh sách: dấu đầu dòng `muted-foreground`, thụt 20px.
