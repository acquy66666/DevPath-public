# Design system DevPath

Bản trong repo của artifact Claude Design **DevPath** (loại *Design System*): <https://claude.ai/artifact/EYuvEMN1fJ2pJpZiNp3S3Q> (riêng tư, chỉ chủ tài khoản mở được). Tạo 21/10/2026, task đầu của mục "Định danh thương hiệu" trong [Phase 7](../../plan/phase-7-ui-ux-upgrade.md).

## Trong thư mục

| Tệp | Là gì |
|---|---|
| `project/` | Đúng các tệp đã publish lên artifact: `tokens.json`, `README.md` (brand book), `components/<Tên>/{README.md,preview.html}`, `components/bundle.css`, bìa `components/Cover/preview.html`, chỉ mục `design-system.json` |
| `palette.py` | **Nguồn của mọi token.** Chọn màu bằng OKLCH, đổi sang hex, viết `project/tokens.json`, kiểm 130 cặp tương phản; một cặp dưới sàn là thoát 1 |
| `contrast.txt` | Kết quả lần chạy gần nhất: từng cặp chữ/nền với tỉ lệ, và bảng OKLCH → hex của mọi bậc màu |
| `check/` | Dựng lại `tokens.css` như trang artifact làm, rồi chụp từng preview ở 960 và 400px (tràn ngang, lỗi console, font) và thử nút "Phát" của Motion có và không có `prefers-reduced-motion` |

Ảnh các preview: [`docs/report/assets/phase-7/design-system/`](../../report/assets/phase-7/design-system/).

## Đổi một token

1. Sửa `palette.py` (bậc màu, bí danh ngữ nghĩa, thang chữ, khoảng cách, chuyển động).
2. `python docs/ui-ux/design-system/palette.py` → phải in `0 below floor`.
3. Kiểm preview: `python docs/ui-ux/design-system/check/build.py`, rồi `NODE_PATH=frontend/node_modules node docs/ui-ux/design-system/check/shoot.cjs`.
4. Publish lại các tệp đã đổi lên artifact (tool Artifact, `root` = thư mục này). Index `project/design-system.json` gửi cuối cùng, sau khi đọc lại bản trên artifact, và chỉ đổi `lastChange`.

Khi token đã vào `frontend/app/globals.css` (task "Nền"), **code thắng**: lệch thì sửa `palette.py` cho khớp code rồi publish lại.

## Đã chốt, và lý do

- **Ngọc + nghệ.** `jade` (hue OKLCH 178) là màu thương hiệu, cũng là màu dành cho thân nhân vật. Ngọc ngả lam rõ, khác hẳn xanh lá Duolingo (hue ~135). `turmeric` (hue 84) chỉ cho phần thưởng. Nền giấy và chữ mực (`slate`, hue 235) ngả xanh mực, hợp chủ đề code.
- **Bác bỏ gợi ý của `ui-ux-pro-max`.** Gợi ý là chàm `#4F46E5` + cam, kiểu claymorphism, font Baloo 2 / Comic Neue. Người dùng là sinh viên chứ không phải trẻ em, và chàm–tím là kiểu "giao diện AI chung chung" mà tài liệu thiết kế tránh.
- **Hai lớp token.** Component chỉ đọc lớp ngữ nghĩa, giữ đúng tên của shadcn (`background`, `primary`, `muted`, `accent`, `border`, `input`, `ring`…) để task "Nền" thay giá trị mà không phải đổi class trong `components/ui/*`. Lớp mới: `primary-hover`, `secondary-hover`, `link`, `border-strong`, `overlay`, `*-soft`/`*-text` cho 4 trạng thái, `reward*`, `streak*`, `medal-*`, `verdict-*` (7 × 3), `quiz-*` (4 × 3), `chart-1…5`.
- **7 màu verdict.** AC xanh lá, WA đỏ, TLE hổ phách, MLE hồng, RE tím, CE lam. SE màu xám vì đó là lỗi hệ thống, không phải lỗi bài làm. Màu luôn đi cùng mã + nhãn + icon.
- **4 mức quiz.** Nghệ (100%), xanh lá (≥ 80%), lam (50–79%), tím dịu (< 50%). Mức thấp nhất là "an ủi", không dùng đỏ.
- **Viền ô nhập `slate-500` đạt 3:1** (WCAG 1.4.11), đậm hơn viền mặc định của shadcn. Đường kẻ trang trí vẫn nhạt (`border`).
- **Sao, cúp, huy chương vàng dùng `turmeric-600`, không dùng vàng sáng.** Vàng sáng trên nền trắng chỉ 2,3:1; lần chạy đầu của `palette.py` bắt đúng 6 cặp này.
- **Chuyển động:** 6 thời lượng (90–600ms, cộng trần 2.400ms cho một lần phản ứng của nhân vật) và 4 đường cong; `ease-overshoot` chỉ dành cho ăn mừng.
- **Số theo kiểu đang dùng trong code:** "80%" viết liền, "0,42 s", "499.000 ₫".

## Đã duyệt / còn là giả định

- **User duyệt bảng màu ngọc + nghệ ngày 21/10/2026.** Đổi màu sau này vẫn đi qua `palette.py`, tương phản được kiểm lại tự động.
- **Font chữ chính: Lexend** (21/10, task chọn font): so 7 ứng viên, lý do và số đo ở [`fonts.md`](fonts.md). Geist Mono và Noto Serif giữ nguyên. Thang chữ đổi ba line-height theo số đo của Lexend (display 52, h1 40, caption 18).
- Giả định, áp dụng ở task "Nền": nút mặc định 32 → 36px, ô nhập 32 → 40px với chữ 16px, bo góc gốc 10px.
- Chỉ có theme sáng (tài liệu thiết kế, mục 10). Tên token giữ nguyên để thêm theme `dark` sau.

## Chưa có trong artifact

- Preview của `DropdownMenu`, `ExportButton`, `Markdown`, `Pager` (có trong `components/ui/*`), làm ở task "Nền". `Label`, `Textarea`, `NativeSelect` đã nằm trong preview `FormField`.
- Preview là **bản tĩnh** (HTML + `bundle.css`), không phải component React thật: chưa build bundle của frontend vào artifact.
- Logo dạng hình: DevPath chưa có, thương hiệu là chữ "Dev" + "Path".
- Nhân vật linh vật: task sau. Màu đã dành sẵn trong brand book.
