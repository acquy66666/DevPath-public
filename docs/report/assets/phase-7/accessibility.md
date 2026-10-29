# Rà truy cập — bằng chứng (29/10/2026)

Nhánh `feature/phase7-accessibility`. Task Phase 7 "Rà truy cập": axe-core trên các trang chính → 0 lỗi `critical`/`serious`; đi hết luồng vàng bằng bàn phím; rà skill `web-design-guidelines`.

Trước đây axe chỉ nằm trong các script rời của từng nhóm màn (`*/check.cjs`). Giờ cả hai phần là test Playwright trong `frontend/e2e/`, nằm trong `npm run test:e2e`, nên CI chạy chúng ở job E2E sau mỗi lần đẩy code.

## 1. Quét axe — `e2e/a11y/pages.a11y.spec.ts`

- **4 vai × 2 khổ (1440, 375 px)**, mỗi lượt quét hết các màn của vai đó rồi mới kết luận (một lượt liệt kê mọi lỗi, không dừng ở trang đầu):
  - khách: trang chủ, danh sách khóa, chi tiết khóa, đăng nhập, đăng ký, bảng xếp hạng, chính sách bảo mật, 404, cộng menu điều hướng mobile **đang mở**;
  - học viên: chào mừng, khóa học của tôi, giỏ hàng, yêu thích, hồ sơ, thông báo, trở thành giảng viên, trang học với bài video + bài đọc + bài code, cộng **menu tài khoản và chuông thông báo đang mở**;
  - giảng viên: 5 trang `/giang-day/*` + trang soạn khóa (tab nội dung và tab thông tin);
  - quản trị: 12 mục thanh bên + trang duyệt một khóa, cộng thanh bên gập (dưới `lg`) **đang mở**.
- Tổng cộng 82 lượt quét mỗi lần chạy: 42 ở 375 px, 40 ở 1440 px (ở đó nút menu mobile và nút gập thanh bên admin không hiện nên bỏ qua). Tiêu chí: không có vi phạm `critical`/`serious`. Hàm `axe()` ở `e2e/support/axe.ts` dùng chung cho cả spec bàn phím.
- Chờ trước khi quét: heading hiện, không còn skeleton, `networkidle`, mọi hoạt ảnh có hồi kết đã chạy xong (menu đang mờ dần sẽ cho số tương phản sai), `<title>` đã có (Next 16 stream metadata vào sau body).
- Tài khoản cố định như bộ hồi quy hình ảnh (`e2e/support/accounts.ts`), nên quét được trên CSDL dev lẫn stack CI chỉ có seed.

### Lượt đầu tìm ra (trên CSDL dev, trước khi sửa)

| Lỗi axe | Mức | Ở đâu | Nguyên nhân → cách sửa |
|---|---|---|---|
| `button-name` | critical | `/quan-tri/{khoa-hoc,nguoi-dung,ma-giam-gia,danh-muc}` @375 | Chữ "Tìm" (ô tìm admin dùng chung) và "Thêm" (danh mục) bị `hidden sm:inline` → dưới `sm` nút không có tên. Đổi thành `max-sm:sr-only`. |
| `scrollable-region-focusable` | serious | `/quan-tri/doanh-thu`, `/quan-tri/thanh-toan` @375 | Bảng cuộn ngang không có gì nhận focus bên trong → bàn phím không cuộn được. Thêm `tabIndex={0} role="region" aria-label` (đúng cách `profit-page` đã làm) cho **7** khung bảng số liệu: doanh thu theo giảng viên/khóa, số dư giảng viên, các bảng kê, dòng bảng kê, khóa hot ở tổng quan, thống kê từng khóa của giảng viên. |
| `aria-valid-attr-value` | critical | `/thong-bao` @1440 + @375 | Tab "Tất cả/Chưa đọc" trỏ `aria-controls` vào panel không tồn tại (danh sách vẽ ngoài `Tabs`). Danh sách giờ nằm trong `TabsContent`. |
| `aria-hidden-focus` | serious | menu điều hướng mobile, menu tài khoản (mở) | Radix DropdownMenu ở chế độ modal gắn `aria-hidden` lên header/main/footer mà không làm chúng `inert`. Wrapper `components/ui/dropdown-menu.tsx` giờ mặc định `modal={false}`: menu theo mẫu WAI-ARIA không phải hộp thoại; Esc, bấm ra ngoài và Tab vẫn đóng. |
| `color-contrast` | serious | menu tài khoản @1440 | **Không phải lỗi màu**: axe đo lúc menu còn mờ dần (opacity < 1). Token `slate-600` trên `slate-0` đã qua kiểm 130 cặp của `palette.py`. Spec giờ chờ hoạt ảnh xong; lỗi không còn. |

### Sau khi sửa

`8 passed` (8 lượt vai × khổ, 2,0 phút), 0 vi phạm critical/serious. Chạy liên tục 3 lần trên CSDL dev.

## 2. Luồng vàng chỉ bằng bàn phím — `e2e/keyboard-flow.spec.ts`

Đăng ký → thêm giỏ → giỏ hàng → thanh toán VNPay (trang ngân hàng giả lập như luồng vàng) → trang kết quả → bài đọc → bài code → chứng chỉ, **không một cú bấm chuột**. Gõ URL được cho phép, vì đó cũng là thao tác bàn phím.

- Mỗi control được với tới bằng Tab, từng lần một, từ chỗ focus đang đứng; quá 120 lần là đỏ. Tới nơi thì kiểm **focus nhìn thấy được**: `:focus-visible` + outline hoặc ring; riêng Monaco thì kiểm lớp `focused` (Monaco tự vẽ con trỏ + viền).
- Monaco: Tab trong editor là thụt lề. **Ctrl+M** là lối ra của chính Monaco (Tab chuyển focus cho tới khi bấm lại). Spec đọc lại dòng code trên editor ngay trước khi nộp.
- axe chạy ở 4 trạng thái mà lượt quét không tới được: giỏ có hàng, đơn vừa trả tiền, bài code đã chấm Đúng, trang chứng chỉ.
- Số lần Tab tới từng control (sau khi có liên kết bỏ qua, xem §3):

  | Control | Tab |
  |---|---|
  | Họ và tên (đăng ký, tự focus) | 0 |
  | Thêm vào giỏ hàng | 2 (trước liên kết bỏ qua: 9) |
  | Thanh toán … qua VNPay | 7 |
  | Bắt đầu học (trang kết quả) | 10 |
  | Đánh dấu hoàn thành | 9 |
  | Trình soạn code | 11 |
  | Nộp bài (từ editor, sau Ctrl+M) | 2 |
  | Xem chứng chỉ | 26 |

- **Thử đỏ:** tạm cho nút "Nộp bài" `tabIndex={-1}` → `Nộp bài: not reached in 120 presses of Tab`; trả lại.
- **Một lượt WA chưa giải thích được:** lượt chạy thứ hai của spec ra WA 50/100 (test ẩn `-7` sai) khi code lẽ ra đúng. Dữ liệu đã bị `purge_e2e` xóa trước khi kịp đọc code, log worker chỉ ghi `'WA'`. 12 lượt sau đều AC với đúng `n = int(input())⏎print(2 * n)⏎` (đọc từ CSDL với `E2E_KEEP_DATA=1`). Từ đó spec kiểm nội dung editor trước khi nộp: nếu lặp lại mà code trên màn hình đúng, lỗi nằm ở khâu chấm bài.

## 3. Rà theo `web-design-guidelines`

Bộ luật đã ghim ở `.claude/skills/web-design-guidelines/references/command.md` (commit `434b7f9`). Rà bằng tìm kiếm trên toàn bộ `app/` + `components/`; phần axe đã phủ (tên nút, nhãn, tương phản, ARIA) không rà lại.

| Luật | Kết quả |
|---|---|
| Liên kết bỏ qua tới nội dung chính | **Thiếu → thêm.** "Bỏ qua tới nội dung chính" là điểm Tab đầu tiên của mọi trang (`app/layout.tsx`, `sr-only` cho tới khi có focus); đích là `<main id="noi-dung">` của 4 layout + `error.tsx` + `not-found.tsx`. Spec bàn phím kiểm Tab đầu trúng nó, và Tab sau Enter nằm trong `<main>`. |
| Ô email tắt kiểm chính tả | **Thiếu → thêm** ở `FormField` (`spellCheck={false}` khi `type="email"`), áp cho đăng nhập + đăng ký. |
| `autocomplete` ô đăng nhập/đăng ký | Đủ (`email`, `name`, `current-password`, `new-password`). |
| `<div onClick>` thay cho nút/liên kết | 0. |
| `outline-none` không có focus thay thế | 2 chỗ, đều là đích `tabIndex={-1}` mà script chuyển focus tới (kết quả quiz, câu quiz), không phải control. Giữ nguyên. |
| `transition: all` | 0 (`motion.test.ts` đã chặn). |
| Header dính che phần tử đang focus | Header không dính, không áp dụng. |
| Chặn dán | `onPaste` duy nhất (ô soạn bài đọc) chỉ chặn khi dán **ảnh**, chữ vẫn dán bình thường. |
| Chữ "Đang …" phải kết thúc bằng `…` | Các chuỗi tìm thấy là nhãn trạng thái ("Đang bán", "Đang chạy"), không phải chữ báo đang tải. |
| Title Case cho tiêu đề/nút | Không áp dụng cho tiếng Việt. |
| `<img>` có `width`/`height` | Thuộc task hiệu năng kế tiếp (CLS). |

## Kiểm

- `npm run test:e2e` trên CSDL dev (stack dev): **10 passed** (8 axe + luồng vàng + bàn phím, 3,0 phút).
- Bộ hồi quy hình ảnh trên stack sạch `devpath-visual`: xem §4.
- ESLint sạch toàn `frontend/`; `npm test` 156/156. `tsc` còn 1 lỗi có từ trước, ở `app/(marketing)/chao-mung/page.tsx` (kiểu route sinh sẵn đã cũ), không thuộc nhánh này.
- **Chưa có lượt CI thật:** GitHub Actions bị chặn tới 01/11/2026.
- Giới hạn đăng nhập 10 lần/15 phút/email: một lượt CI đăng nhập admin 6 lần (ảnh 2, axe 2, luồng vàng 1, bàn phím 1). Chạy lặp trên máy thì `redis-cli DEL auth:login:email:admin@devpath.example`.

## 4. Hồi quy hình ảnh sau các thay đổi

Chạy bộ ảnh trên stack sạch để xác nhận các thay đổi DOM ở trên (liên kết bỏ qua `sr-only`, thuộc tính vùng cuộn) không làm lệch điểm ảnh nào. Lượt này **đỏ 7/24**, và nguyên nhân nằm ở bộ ảnh của task trước, không phải ở các sửa đổi truy cập. Ảnh bìa dự phòng chọn màu theo **id khóa học** (`lib/courses/cover.ts`), mà mỗi lần seed CSDL mới lại sinh UUID ngẫu nhiên. Baseline 29/10 từng xanh "ba lượt liền" chỉ vì cả ba lượt chạy trên đúng stack đã sinh ra nó. Trên CI (CSDL mới mỗi lần) nó sẽ luôn đỏ.

Cách sửa: `backend/scripts/seed_courses.py` gán id khóa học bằng `uuid5(SEED_COURSE_NAMESPACE, slug)`. Sản phẩm không đổi gì; mọi CSDL seed mới có cùng id; CSDL dev đang có giữ nguyên id cũ (seed khớp theo slug, không ghi lại khóa đã có). Baseline được sinh lại. Phép thử đúng giờ là **hai stack**: sinh trên stack A, xóa (`down -v`), dựng stack B sạch rồi so.

| Bước | Kết quả |
|---|---|
| Stack A: id 4 khóa | `cau-truc… e520ab20…`, `javascript… ee59ce09…`, `python-co-ban… 4cdbd5fe…`, `xay-dung… 53f7cf2f…` |
| Stack A: sinh baseline, so | 24 passed, 24 passed |
| Stack B (dựng lại từ đầu): id 4 khóa | giống hệt stack A |
| Stack B: so với baseline của A, hai lượt | 24 passed (1,0 phút), 24 passed (48,1 s) |
| Stack B: `npm run test:e2e` | **10 passed** (3,7 phút); "Xem chứng chỉ" cách 23 lần Tab (CSDL dev: 26, vì lượng dữ liệu ở trang khác nhau) |
