# Bằng chứng Phase 7 — Nâng cấp UI/UX

Chỉ mục **gate → tệp** của Phase 7 ([plan](../../../plan/phase-7-ui-ux-upgrade.md), [thiết kế](../../../ui-ux/thiet-ke-nang-cap-ui-ux.md)). Phase đang mở; bảng gate điền dần theo từng task.

## Gate cuối phase

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Design system khớp `globals.css`; nhân vật đủ mọi `mood`, có tư thế tĩnh | artifact + [`docs/ui-ux/design-system/`](../../../ui-ux/design-system/README.md), ảnh `design-system/` | artifact **có 21/10**; chưa vào `globals.css`; nhân vật: ba hướng phác 21/10 (`mascot-directions/`), user chọn A — tắc kè Naomi; **model sheet + 30 hình biểu cảm có 21/10** (`naomi/`), tư thế tĩnh = chính các hình đó; hoạt ảnh chưa |
| CI xanh: E2E "1 passed", hồi quy hình ảnh, axe; 0 tràn ngang 360/375/1440 px | — | chưa |
| Ảnh trước/sau từng nhóm màn; 42 ảnh `capture.cjs` mới cho chương 4; model sheet + biểu cảm; GIF phản ứng; **bảng số đo Lighthouse/axe/JS trước/sau** | cột "trước": [`before.md`](before.md) + [`before/`](before/); model sheet + biểu cảm: [`naomi/`](naomi/) | cột "trước" **có 20/10**; model sheet + biểu cảm **có 21/10**; GIF chưa |
| Deploy bản mới lên URL demo, chạy lại luồng vàng ở đó | — | chưa |
| Tag `phase-7-done` | — | chưa |

## Tệp

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `skills-audit/` | JSON audit skills.sh của từng skill cộng đồng trước khi cài (18/10); danh sách đã cài ở [`docs/ui-ux/README.md`](../../../ui-ux/README.md) | 4 — Công cụ |
| [`before.md`](before.md) + `before/` | **Mốc "trước"** (20/10): bảng số đo (First Load JS, JS trang chủ, Lighthouse mobile 3 trang × 3 lượt, axe 12 trang), 42 ảnh `capture.cjs` + 12 ảnh màn Phase 6.5, cách chạy lại | 5 — Đánh giá (cột "trước"), 4 — ảnh giao diện cũ |
| `measure.cjs` | Script đo JS/axe/Lighthouse, chạy lại với `LABEL=after` cho cột "sau" | 5 |
| `design-system/` | Design system DevPath (21/10): ảnh 11 preview của artifact ở 960px (bìa, Button, Badge, Verdict, QuizResult, Card, FormField, Tabs, Alert, Dialog, Motion), Verdict ở 400px, Motion lúc đang chạy. Bảng 130 cặp tương phản ở [`docs/ui-ux/design-system/contrast.txt`](../../../ui-ux/design-system/contrast.txt) | 4 — Thiết kế giao diện; 5 — truy cập (tương phản) |
| `font/` | Chọn font chữ chính (21/10): 7 ứng viên phóng to với chữ khó + "₫" (`closeup.png`), cỡ 12/14px ở DPR 1 (`small-3x.png`), Be Vietnam Pro bị `truncate` cắt dấu và cách thêm lề (`zoom-bvp-14-20*.png`, `clipfix2.png`), header khách 360px (`header-360.png`), specimen 4 font, app thật với Lexend (`app-*.png`). Bảng số đo: [`docs/ui-ux/design-system/fonts.md`](../../../ui-ux/design-system/fonts.md) | 4 — Thiết kế giao diện (tiếng Việt); 5 — truy cập |
| `mascot-directions/` | Ba hướng linh vật (21/10): 5 artboard của canvas dựng lại trên máy (`Main.png` tổng quan, `Gecko.png`, `Lac.png`, `Robot.png`, `Duo.png` kiểm với Duo), bảng 12 hình ở 200/64/32 px + hình bóng (`sheet-12-drawings@2x.png`), khoảng cách màu tới Duo (`duo-distance.txt`). Nguồn và cách chạy lại: [`docs/ui-ux/mascot/`](../../../ui-ux/mascot/README.md) | 4 — Thiết kế giao diện (nhân vật) |
| `naomi/` | Model sheet + bộ biểu cảm của Naomi (21/10): `turnaround@2x.png` (ba góc trên đường gióng), `sheet-views@2x.png` + `sheet-moods@2x.png` (33 hình ở 200/64/32 px + hình bóng), `boards/` (artboard model sheet, bộ biểu cảm và tổng quan dựng lại trên máy), `check.txt` (6 luật: token, lớp, nghệ không tô thân, cách Duo, tràn khung, % đuôi + đốm còn lộ). Nguồn: [`docs/ui-ux/mascot/`](../../../ui-ux/mascot/README.md) | 4 — Thiết kế giao diện (nhân vật) |
| `stack.cjs` | Đường nội bộ tới stack demo (tên miền thật trỏ vào nginx 127.0.0.1) dùng chung cho các script đo/chụp | — |
