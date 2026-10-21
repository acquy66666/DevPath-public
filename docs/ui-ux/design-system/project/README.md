DevPath là nền tảng học lập trình bằng tiếng Việt. Học viên xem bài, nộp code được chấm trong sandbox, làm quiz và hỏi trợ giảng AI. Giao diện phải đọc như một công cụ làm việc nghiêm túc, nhưng ấm với người mới học: phần lớn màn hình là giấy trắng và chữ mực, **ngọc** (`jade`) là màu của DevPath, **nghệ** (`turmeric`) chỉ xuất hiện khi người học được thưởng.

## Giọng văn

- Viết tiếng Việt, gọi người học là **bạn**. Hệ thống không tự xưng.
- Câu ngắn, nói việc làm được tiếp theo. Ví dụ thật trong app: "Chưa đạt — cần 80%. Làm lại được ngay.", "Chương trình chạy xong nhưng in ra khác kết quả mong đợi."
- Nút là động từ đứng đầu, viết hoa kiểu câu: "Nộp bài", "Chạy thử", "Thêm test case", "Khôi phục code mẫu". Đang xử lý thì dùng dấu "…": "Đang lưu…".
- Lỗi nói chuyện gì xảy ra và cách sửa. Lỗi của hệ thống thì nói thẳng là không phải lỗi của bạn: "Lỗi phía hệ thống chấm bài, không phải lỗi bài của bạn. Bài này chưa được chấm."
- Empty state: "Chưa có … nào" cộng một cách tạo cái đầu tiên.
- Không emoji, không dấu chấm than, không "Oops".
- Mã verdict giữ chữ Anh (AC, WA, TLE, MLE, RE, CE, SE) và luôn đi kèm nhãn tiếng Việt.
- Số theo kiểu Việt: dấu chấm hàng nghìn, dấu phẩy thập phân, đơn vị sau số, cách một dấu cách (trừ %): "1.250 XP", "0,42 s", "499.000 ₫", "80%". Ngày `dd/mm/yyyy`, giờ Việt Nam.

## Màu

Component chỉ đọc **lớp ngữ nghĩa** (`background`, `primary`, `verdict-ac`…). Dải màu gốc (`jade-50`…`jade-900`, `turmeric-*`, `slate-*` và các họ trạng thái) dành cho minh họa, nhân vật và lớp ngữ nghĩa trỏ tới. Không có mã màu rời trong component. Ngoại lệ duy nhất là logo Google trên nút đăng nhập, theo luật thương hiệu của Google.

- Trang nằm trên `background`; card, bảng, ô nhập nằm trên `card`; đầu bảng và khối code nằm trên `muted`.
- Chữ chính là `foreground`. Chữ phụ, placeholder và thời gian là `muted-foreground` (đạt 4.5:1 trên cả `background`, `card`, `muted`, `accent`).
- **Một nút `primary` mỗi màn** cho việc chính của màn đó. Hành động phụ cùng nhóm dùng `secondary` (ngọc nhạt), hành động trung tính dùng outline (viền `input`), xóa/gỡ dùng `destructive`.
- Link trong đoạn văn là `link` (`jade-700`), có gạch chân.
- Đường kẻ trang trí là `border`. Viền của thứ bấm hay gõ được (ô nhập, checkbox, nút outline) là `input`, đậm hơn có chủ đích để đạt 3:1.
- Trạng thái chung: `success`, `warning`, `info`, `destructive`, mỗi cái có `*-soft` (nền) và `*-text` (chữ). `warning` (hổ phách) chỉ làm icon; nếu tô nền thì chữ tối.
- **Nghệ là phần thưởng, không phải cảnh báo.** `reward`, `reward-soft`, `reward-foreground`, `reward-mark` chỉ dùng cho XP, sao đánh giá, quiz 100%, huy chương. Không dùng `turmeric-400`/`turmeric-500` làm chữ hay icon trên nền trắng: dưới 3:1.
- Chuỗi ngày: lửa `streak`, số ngày `streak-text`. Huy chương: `medal-gold`, `medal-silver`, `medal-bronze`.
- Biểu đồ: `chart-1` tới `chart-5` theo thứ tự chuỗi. `chart-5` dành cho kỳ trước hoặc "khác". Biểu đồ luôn có bảng dữ liệu đi kèm ("Xem dạng bảng").

### Bảy verdict

| Mã | Nhãn | Token |
|---|---|---|
| AC | Đúng | `verdict-ac` · `verdict-ac-soft` · `verdict-ac-solid` (xanh lá) |
| WA | Sai kết quả | `verdict-wa` … (đỏ) |
| TLE | Quá thời gian | `verdict-tle` … (hổ phách) |
| MLE | Quá bộ nhớ | `verdict-mle` … (hồng) |
| RE | Lỗi khi chạy | `verdict-re` … (tím) |
| CE | Lỗi cú pháp | `verdict-ce` … (lam) |
| SE | Lỗi hệ thống | `verdict-se` … (xám: lỗi của hệ thống, không phải của học viên) |

Màu verdict không bao giờ đứng một mình: luôn có mã, nhãn và icon (xem component **Verdict**).

### Bốn mức quiz

`quiz-party` (100%, nghệ), `quiz-proud` (≥ 80%, xanh lá), `quiz-cheer` (50–79%, lam), `quiz-comfort` (< 50%, tím dịu: an ủi, không phải lỗi). Mỗi mức có `-soft` và `-solid`. Hết giờ dùng `verdict-tle`. Xem component **QuizResult**.

### Tương phản

Mọi cặp chữ/nền nêu trong ghi chú của token đạt **4.5:1**. Viền control, vòng focus, icon và cột biểu đồ đạt **3:1**. Bảng màu được sinh và kiểm bằng script, 130 cặp, không cặp nào dưới sàn. Theme tối chưa làm: tên token giữ nguyên để thêm theme `dark` sau mà không đổi component.

## Chữ

- Họ chữ: `sans` = **Lexend** cho mọi thứ; `mono` = Geist Mono cho code, mã verdict và số đo; `serif` = Noto Serif chỉ cho trang chứng chỉ. Cả ba tự host qua `app/fonts.css`, có subset `vietnamese`. Lexend là font variable 400–700, chỉ dùng bốn độ đậm 400 (chữ), 500 (caption, nút trong code cũ), 600 (tiêu đề nhỏ, nút, nhãn), 700 (display, h1).
- Vì sao Lexend: dấu chồng ở cỡ 12–14px vẫn tách được "ẩ" với "ẫ"; ký hiệu "₫" cao bằng chữ số (Geist vẽ nó chỉ bằng 0,73); mọi dấu của chữ thường nằm trong dòng ở mọi cỡ của thang. Lexend rộng hơn Geist ~6%: chỗ chật (header ở 360px, thanh tab, bảng) phải đo lại khi đổi chữ.
- Thang: `display` (hero, một lần mỗi trang) → `h1` (tiêu đề trang) → `h2` → `h3` → `title` (tiêu đề card) → `body-lg` (bài đọc) → `body` (mặc định 16px) → `body-sm` (bảng, gợi ý) → `caption` → `eyebrow` (nhãn viết hoa). Code: `code`, `code-sm`. Số lớn: `numeral`.
- **Tiếng Việt có dấu hai tầng** ("Luồng", "Người", "ưở"): line-height của thang đã đo để dấu của chữ thường không trồi khỏi dòng (display 40/52, h1 30/40, caption 12/18). Không hạ line-height dưới thang, không dùng `leading-none` cho chữ có dấu. Chữ nằm trong khung cắt (`truncate`, `line-clamp`, `overflow: hidden`) chỉ dùng kiểu từ `h3` trở xuống: ở đó cả dấu của chữ hoa cũng nằm trong dòng.
- Bài đọc dùng `body-lg`, tối đa ~70 ký tự mỗi dòng.
- Mọi cột số, đồng hồ quiz, XP và tiền dùng `font-variant-numeric: tabular-nums`.
- Tiêu đề dùng `text-wrap: balance`.
- Chữ thương hiệu: "Dev" màu `foreground`, "Path" màu `primary`, đậm 600–700. DevPath chưa có logo dạng hình.

## Khoảng cách, bo góc, đổ bóng

- Lưới 4px: `space-1` (4) … `space-24` (96), trùng thang của Tailwind. Padding card `space-4`, khoảng giữa card `space-5`, giữa các mục `space-8` trên điện thoại và `space-12` từ md. Lề trang `space-4` trên điện thoại.
- Bo góc theo kích thước vật: `radius-xs` (code trong dòng, chấm test) · `radius-sm` (checkbox) · `radius-md` (nút, ô nhập, tab, alert; là gốc `--radius`) · `radius-lg` (card, khung code) · `radius-xl` (dialog, bong bóng lời nhân vật) · `radius-full` (badge, verdict, avatar, thanh tiến độ).
- Chỉ lớp nổi mới có bóng: `shadow-xs` cho ô nhập và nút outline, `shadow-sm` cho tab đang chọn, `shadow-md` cho dropdown/popover/toast và card khi hover, `shadow-lg` cho dialog. Card lúc yên chỉ có viền `border`.
- Bố cục: lưới và flex dùng `gap`, không dùng margin lẻ. Mọi con của flex/grid chứa chữ có `min-width: 0`. Không tràn ngang ở 360, 375 và 1440px.

## Chuyển động

Token: `duration-instant` 90ms · `duration-fast` 150ms · `duration-base` 220ms · `duration-slow` 320ms · `duration-progress` 600ms · `duration-mascot` 2400ms (trần một lần phản ứng). Đường cong: `ease-standard`, `ease-enter`, `ease-exit`, `ease-overshoot` (chỉ cho ăn mừng). Bảng ghép cặp và luật nằm ở component **Motion**. Tóm tắt:

- Chỉ động `transform` và `opacity`. Không hoạt ảnh nào chặn thao tác.
- Ăn mừng (AC 100/100, quiz 100%, lên hạng) một lần mỗi sự kiện vừa xảy ra trong phiên.
- `prefers-reduced-motion`: chỉ còn đổi màu ≤ `duration-fast`; nhân vật đứng yên.

## Trạng thái và tương tác

- Focus: `outline: 2px solid var(--ring)`, `outline-offset: 2px`. Khoảng hở 2px có màu nền nên vòng vẫn thấy được quanh nút `primary`. Không bao giờ bỏ focus.
- Hover: `primary` → `primary-hover`; `secondary` → `secondary-hover`; nút và dòng trung tính → `accent`.
- Nhấn: lún 1px trong `duration-instant`.
- Vô hiệu: mờ 50% và con trỏ "not-allowed", kèm lý do ở gần nếu người dùng không tự đoán được.
- Đang tải: skeleton nền `muted` đúng kích thước nội dung thật, để trang không nhảy khi dữ liệu tới.
- Vùng chạm tối thiểu 24×24px (WCAG 2.2 AA); nút chính trên điện thoại cao 44px.

## Biểu tượng

- Một bộ duy nhất: **lucide-react**, nét 2, cỡ 16px cạnh chữ 14–16px, 20px trong ô thống kê và alert lớn.
- Icon trang trí có `aria-hidden`. Nút chỉ có icon phải có `aria-label`.
- Icon mang nghĩa (verdict, trạng thái) luôn đi cùng chữ.
- Không dùng emoji làm icon.

## Nhân vật linh vật

Nhân vật là **Naomi**, tắc kè "bắt bug" (hướng A trong ba hướng đã phác; user chọn ngày 21/10/2026 và đặt tên). Tắc kè ăn côn trùng, tức là bắt bug: bài AC là bắt được con bọ, bài WA là để nó bay mất. Model sheet ba góc và bộ biểu cảm nằm trên canvas [Linh vật DevPath](https://claude.ai/artifact/LgYj69gDYUuze9geb8J7W8).

- **Bảng màu của Naomi:** thân, đầu, tay, chân, đuôi `jade-500`; bụng `jade-100`; đốm `jade-700`; nét viền, con ngươi, miệng `jade-900`; mống mắt `turmeric-300`; lòng trắng mắt `slate-0`; lưỡi `rose-500`; má hồng `rose-200`; bóng dưới chân `slate-100`.
- **Màu nghệ không tô miệng, tay, chân, bàn chân, đuôi hay thân.** `turmeric-300` cách màu mỏ của Duo (Duolingo) chỉ ΔE 0,028, gần như trùng. Trên người Naomi, nghệ chỉ có ở mống mắt. Ngoài người, nghệ vẫn theo luật phần thưởng: sao lấp lánh khi AC, mũ tiệc khi quiz 100%, tua mũ tốt nghiệp.
- **Góc nào cũng có đốm và đuôi xoắn.** Nhìn thẳng mà thiếu hai thứ đó thì tắc kè thành con ếch.
- Đạo cụ mang màu của sự kiện: TLE hổ phách, MLE hồng, RE tím, CE lam, SE xám, quiz theo bốn mức, lửa chuỗi ngày `streak`.
- Naomi xuất hiện ở trang học viên theo bản đồ phản ứng: verdict, quiz, chuỗi ngày, chứng chỉ, 404, empty state, trợ giảng AI, thanh toán. Ở khu giảng viên và admin chỉ ở empty state và lời chào. Mỗi sự kiện phản ứng một lần, tối đa `duration-mascot`, rồi về tư thế nghỉ `rest`. Với `prefers-reduced-motion` chỉ hiện hình tĩnh.
- Mỗi hình là SVG có cùng bộ lớp đặt tên (`tail`, `body`, `arm-left`, `head`, `eyes`, `eyelids`, `mouth`, `props`, `fx`…), chỉ dùng thuộc tính trình bày, không `<style>`, không chữ.

## Không làm

- Gradient tím–lam, nền kem + đất nung, nền đen + một màu neon, glassmorphism.
- Kiểu "đất nặn" (claymorphism), font tròn kiểu thiếu nhi: người dùng là sinh viên và người đi làm.
- Card viền màu bên trái, emoji làm tiêu đề mục, mọi thứ căn giữa, cùng một bo góc lớn cho mọi khối.
- Màu là tín hiệu duy nhất của một trạng thái.
