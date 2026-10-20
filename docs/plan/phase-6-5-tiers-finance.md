# Phase 6.5 — Cấp bậc giảng viên & tài chính sàn (chèn 20/10/2026)

**Mục tiêu:**

- Giảng viên chỉ thấy số liệu về khóa học và học viên, không thấy số tiền.
- Giảng viên được xếp 5 cấp, cấp càng cao thì tỉ lệ chia (hoa hồng) càng lớn; admin là người xét lên cấp.
- Doanh thu, xếp hạng, hoa hồng, bảng kê chi trả và lợi nhuận chỉ nằm ở trang admin.
- Mọi trang thống kê đều xuất được Excel.

Thiết kế đầy đủ — nghiên cứu ba subagent, ngưỡng, công thức, giả định và hướng phát triển: [`docs/thiet-ke-cap-bac-va-tai-chinh.md`](../thiet-ke-cap-bac-va-tai-chinh.md).

> **User chốt 20/10/2026:**
>
> - Tạm dừng các task đang theo tiến độ (Phase 6 chờ VPS, Phase 7 UI/UX) để làm phần này.
> - Phase 7 bắt đầu sau khi phase này xong. Luật "backend đứng yên" của Phase 7 tính từ đó.

## Backend

- [x] Migration `ad80b1df78a1`:
  - bảng `instructor_tiers` (seed 5 cấp 50 → 70%), `instructor_tier_changes`, `payout_statements` + `payout_statement_lines`, `platform_expenses`;
  - cột `users.instructor_tier_id`, `order_items.instructor_share_rate` (gán 0,5 cho dòng đã bán);
  - thêm loại thông báo `instructor_tier_changed`.
- [x] Chốt tỉ lệ chia vào từng dòng bán lúc thanh toán (`orders._deliver`, chung cho IPN và đơn 0đ).
- [x] Thống kê giảng viên **không có tiền**:
  - `GET /instructor/stats/overview|insights|courses|courses/{id}/lessons` và hai `export.xlsx`;
  - test duyệt mọi trường của mọi phản hồi và cả tệp Excel.
- [x] Xét cấp (`services/instructor_tiers.py`):
  - chỉ số khó gian lận, đề xuất cấp cao nhất đạt đủ tiêu chí, ngưỡng duy trì;
  - admin đổi cấp kèm lý do và ảnh chụp số liệu, giảng viên nhận thông báo;
  - giảng viên chỉ thấy đạt/chưa đạt với tiêu chí tiền (`GET /instructor/tier`).
- [x] Tài chính admin (`services/finance.py`, `rankings.py`):
  - doanh thu theo giờ/ngày/tuần/tháng/quý/năm, toàn sàn hoặc một giảng viên, so với kỳ trước, kèm bảng theo giảng viên/khóa;
  - 17 bảng xếp hạng và độ tập trung doanh thu.
- [x] Bảng kê chi trả (`services/payouts.py`):
  - lập theo tháng đã qua, dồn kỳ, mỗi dòng bán chỉ vào một bảng kê;
  - ngưỡng chi 200.000đ (tháng 12 trả hết), thuế TNCN ước tính;
  - vòng đời nháp → đã chốt → đã chi / hủy.
- [x] Lãi lỗ + chi phí (`services/profit.py`):
  - GMV → học viên trả → doanh thu sàn → phí cổng ước tính → chi phí vận hành → lợi nhuận giữ lại;
  - CRUD chi phí.
- [x] Xuất Excel dùng chung (`services/excel.py`, `exports.py`):
  - tiền là số có định dạng ₫;
  - ô chữ không bao giờ thành công thức.
- [x] Ma trận phân quyền thêm luật cho 5 route giảng viên mới. Route `/admin/*` tự được kiểm.

## Frontend

- [x] `/giang-day/thong-ke` viết lại:
  - 8 ô so với kỳ trước, biểu đồ chọn chỉ số;
  - 6 thẻ: học tập, quiz, code, đánh giá, Hỏi đáp, quan tâm;
  - bảng từng khóa, phễu theo bài (dialog), xuất Excel.
- [x] `/giang-day/cap-bac`: cấp hiện tại, bậc thang, tiến độ tới cấp sau, lịch sử. Lối vào ở menu người dùng và trang `/giang-day`.
- [x] Admin có 5 tab mới:
  - `/quan-tri/doanh-thu`, `/quan-tri/xep-hang`, `/quan-tri/cap-giang-vien`, `/quan-tri/thanh-toan` (+ `/[id]` bảng kê in được), `/quan-tri/loi-nhuan`;
  - nút "Xuất Excel" ở mọi trang, kể cả Tổng quan.
- [x] Chuông thông báo hiểu loại `instructor_tier_changed`.

## Kiểm

- [x] Test backend:
  - 5 tệp mới/viết lại (`test_instructor_stats`, `test_instructor_tiers`, `test_finance`, `test_payouts`, `test_profit`): 93 ca;
  - toàn bộ trong container: 2.448 qua, 3 đỏ cố định của container (2 storage-503 + `deploy.sh` không mount).
- [x] Ảnh 12 màn + kiểm không lỗi console, và giảng viên không thấy số tiền: `docs/report/assets/phase-6/tiers-finance/capture.cjs`.
- [x] CI xanh trên PR #108 (6/6 check; backend 2.453 passed; E2E 1 passed ngay lượt đầu), merge 20/10/2026.
