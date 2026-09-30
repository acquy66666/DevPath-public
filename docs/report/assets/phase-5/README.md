# Bằng chứng Phase 5 — Commerce, Gamification & Admin

Phase **chưa đóng**. Bảng dưới là gate cuối phase, chép từ [kế hoạch](../../../plan/phase-5-commerce-admin.md), kèm tệp chứa bằng chứng. Soát ngày 01/10/2026.

Ảnh chụp từ 01/10 được chụp bằng Chrome headless trên máy dev: khung 1440 px, hồ sơ tạm, điều khiển qua DevTools Protocol, đăng nhập bằng form thật. Nút dev-mode của Next được ẩn khỏi ảnh.

## Gate

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Demo end-to-end: giỏ hàng → coupon → VNPay sandbox → thanh toán → vào học ngay | `payment-ipn.txt` (24/09) | **tạm hoãn theo quyết định của user (01/10)**. <br>• **Đã có:** phần sau khi tiền chuyển (chữ ký, chống trùng, đơn `paid`, ghi danh, coupon trừ lượt, giỏ rỗng), chạy bằng IPN giả lập ký bằng đúng secret; giỏ + mã `PYTHON30` chạy trên UI thật 01/10 (898.000 − 149.700 = 748.300 ₫, ghi ở file kế hoạch). <br>• **Còn thiếu:** bước trên trang VNPay (user tự điền thẻ test) và cú bắt tay IPN thật. VNPay chưa khai IPN URL, xin qua mail ngày 24/09 |
| Học viên hoàn thành khóa → nhận chứng chỉ PDF, quét QR verify được | `certificate-demo.txt`, `certificate-sample.pdf` / `.png`, `certificate-1…5-*.png` | **có** — 01/10, khóa seed 18 bài. <br>• Bài code được sandbox chấm AC; bài cuối tick trên UI; chứng chỉ cấp cùng transaction; PDF vẽ sau ~2 s. <br>• QR giải bằng `zbarimg` ra đúng `/cert/{code}`; mã sai trả 404. <br>• Tìm và sửa lỗi ngày: trang ghi 30/09, PDF ghi 01/10 |
| Admin duyệt khóa học mới trước khi hiện công khai | `course-review-gate.txt`, `review-1…8-*.png` | **có** — 01/10. <br>• Khi chờ duyệt: 14 bề mặt công khai đều 404 hoặc không liệt kê; kho chatbot/recommender = 0. <br>• Duyệt trên UI: tất cả mở cùng lúc; ingest + embedding xong trong ~1,7 s; trợ giảng AI trích bài của khóa mới. <br>• Tìm và sửa soft-404: trang khóa chưa công khai từng trả 200 vì `loading.tsx` |
| Thu bằng chứng: screenshot luồng thanh toán VNPay end-to-end | — | **thiếu**, chờ mục demo VNPay |
| Thu bằng chứng: log IPN (đã che dữ liệu nhạy cảm) | `payment-ipn.txt` §3–§5 | **một phần**. Log là của IPN giả lập, với TmnCode giả `LOCALDEMO`, và đã bỏ `vnp_SecureHash`. IPN thật chưa từng tới. Khi tới, phải che TmnCode (`IFW2…`) và chữ ký trước khi đưa vào đây |
| Thu bằng chứng: chứng chỉ PDF mẫu + trang verify | `certificate-sample.pdf`, `certificate-sample.png`, `certificate-3-verify-page.png`, `certificate-5-verify-phone.png`, `certificate-4-wrong-code.png` | **có** |
| Thu bằng chứng: dashboard instructor và admin | `dashboards.txt`, `instructor-dashboard-{30d,12m}.png`, `admin-dashboard-{30d,12m}.png` (+ `admin-categories/coupons/banners.png`, `home-banners.png`) | **có** — 01/10, tài khoản seed trên dữ liệu bán hàng 12 tháng. Số trên ảnh đối chiếu với SQL gốc (`dashboards.txt` §2) |

## Ngoài gate, đã thu

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `payment-ipn.txt` | Luồng đơn hàng + IPN VNPay chạy thật (24/09): ai được quyền nói là đã trả tiền, IPN hợp lệ / trùng / sai chữ ký, log append-only ghi trước khi phán xét, 26 + 20 test | 4 — Xây dựng hệ thống, 5 — Kiểm thử |
| `admin-moderation.txt` | Vòng duyệt khóa học (gửi → từ chối có lý do → gửi lại → duyệt), báo cáo vi phạm → gỡ khóa học, khóa/mở tài khoản, 375 px. **Duyệt là lúc nạp khóa học vào chatbot và recommender**, sau khi bỏ cờ auto-approve | 4 — Xây dựng hệ thống |
| `admin-dashboard.txt` | Định nghĩa DAU không cần bảng mới (dấu vết ở 11 bảng sẵn có), danh mục 2 cấp, mã giảm giá toàn sàn, banner (tải ảnh thẳng lên bucket) | 4 — Xây dựng hệ thống |

Các task còn lại của phase (giỏ hàng, coupon, dashboard giảng viên, XP + chuỗi ngày, bảng xếp hạng, Q&A, thông báo) ghi bằng chứng chạy thật **ngay trong ghi chú của từng task** ở [file kế hoạch](../../../plan/phase-5-commerce-admin.md), không có tệp riêng.
