# Bằng chứng Phase 7 — Nâng cấp UI/UX

Chỉ mục **gate → tệp** của Phase 7 ([plan](../../../plan/phase-7-ui-ux-upgrade.md), [thiết kế](../../../ui-ux/thiet-ke-nang-cap-ui-ux.md)). Phase đang mở; bảng gate điền dần theo từng task.

## Gate cuối phase

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Design system khớp `globals.css`; nhân vật đủ mọi `mood`, có tư thế tĩnh | — | chưa |
| CI xanh: E2E "1 passed", hồi quy hình ảnh, axe; 0 tràn ngang 360/375/1440 px | — | chưa |
| Ảnh trước/sau từng nhóm màn; 42 ảnh `capture.cjs` mới cho chương 4; model sheet + biểu cảm; GIF phản ứng; **bảng số đo Lighthouse/axe/JS trước/sau** | cột "trước": [`before.md`](before.md) + [`before/`](before/) | cột "trước" **có 20/10** |
| Deploy bản mới lên URL demo, chạy lại luồng vàng ở đó | — | chưa |
| Tag `phase-7-done` | — | chưa |

## Tệp

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `skills-audit/` | JSON audit skills.sh của từng skill cộng đồng trước khi cài (18/10); danh sách đã cài ở [`docs/ui-ux/README.md`](../../../ui-ux/README.md) | 4 — Công cụ |
| [`before.md`](before.md) + `before/` | **Mốc "trước"** (20/10): bảng số đo (First Load JS, JS trang chủ, Lighthouse mobile 3 trang × 3 lượt, axe 12 trang), 42 ảnh `capture.cjs` + 12 ảnh màn Phase 6.5, cách chạy lại | 5 — Đánh giá (cột "trước"), 4 — ảnh giao diện cũ |
| `measure.cjs` | Script đo JS/axe/Lighthouse, chạy lại với `LABEL=after` cho cột "sau" | 5 |
| `stack.cjs` | Đường nội bộ tới stack demo (tên miền thật trỏ vào nginx 127.0.0.1) dùng chung cho các script đo/chụp | — |
