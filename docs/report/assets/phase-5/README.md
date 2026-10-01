# Bằng chứng Phase 5 — Commerce, Gamification & Admin

Gate cuối phase **qua ngày 01/10/2026**; tag `phase-5-done` gắn sau khi PR gate được merge vào `main`. Bảng dưới là gate cuối phase, chép từ [kế hoạch](../../../plan/phase-5-commerce-admin.md), kèm tệp chứa bằng chứng. Soát ngày 01/10/2026: mọi dòng đều có tệp. MoMo (mục cắt giảm số 1) bị cắt khỏi phase.

Ảnh chụp từ 01/10 được chụp bằng Chrome headless trên máy dev: khung 1440 px, hồ sơ tạm, điều khiển qua DevTools Protocol, đăng nhập bằng form thật. Nút dev-mode của Next được ẩn khỏi ảnh.

## Gate

| Gate đòi | Tệp | Trạng thái |
|---|---|---|
| Demo end-to-end: giỏ hàng → coupon → VNPay sandbox → thanh toán → vào học ngay | `vnpay-e2e.txt` + `pay-1…7-*.png`; trước đó `payment-ipn.txt` (24/09) | **có, IPN giả lập** — 01/10, UI thật. <br>• Giỏ + `PYTHON30` (748.300 ₫) → **trang VNPay sandbox nhận URL đã ký** → quay về với `vnp_ResponseCode=00` trong URL mà trang vẫn chờ → IPN → trang tự chuyển sang thành công sau 2,9 s → vào học; IPN lần hai trả `02`. <br>• **IPN giả lập** vì VNPay chưa khai IPN URL (yếu tố bên ngoài, mail 24/09); ký bằng đúng secret, đúng route. <br>• Bước điền thẻ test trên trang VNPay không làm lần này; đã chạy ngày 24/09. <br>• Tìm và sửa: chuông giỏ giữ số cũ sau thanh toán |
| Học viên hoàn thành khóa → nhận chứng chỉ PDF, quét QR verify được | `certificate-demo.txt`, `certificate-sample.pdf` / `.png`, `certificate-1…5-*.png` | **có** — 01/10, khóa seed 18 bài. <br>• Bài code được sandbox chấm AC; bài cuối tick trên UI; chứng chỉ cấp cùng transaction; PDF vẽ sau ~2 s. <br>• QR giải bằng `zbarimg` ra đúng `/cert/{code}`; mã sai trả 404. <br>• Tìm và sửa lỗi ngày: trang ghi 30/09, PDF ghi 01/10 |
| Admin duyệt khóa học mới trước khi hiện công khai | `course-review-gate.txt`, `review-1…8-*.png` | **có** — 01/10. <br>• Khi chờ duyệt: 14 bề mặt công khai đều 404 hoặc không liệt kê; kho chatbot/recommender = 0. <br>• Duyệt trên UI: tất cả mở cùng lúc; ingest + embedding xong trong ~1,7 s; trợ giảng AI trích bài của khóa mới. <br>• Tìm và sửa soft-404: trang khóa chưa công khai từng trả 200 vì `loading.tsx` |
| Thu bằng chứng: screenshot luồng thanh toán VNPay end-to-end | `pay-1-course-in-cart.png` … `pay-7-learning.png` | **có** — giỏ, mã giảm giá, trang VNPay sandbox, kết quả chờ → thành công, khóa học của tôi, trang học |
| Thu bằng chứng: log IPN (đã che dữ liệu nhạy cảm) | `vnpay-e2e.txt` §6; trước đó `payment-ipn.txt` §5 | **có, của IPN giả lập** — 2 dòng `payment_events` (lần nhận + lần trùng), payload đã che TmnCode thật (`IFW2****`) và bỏ `vnp_SecureHash`. IPN thật chưa từng tới; khi tới thì bổ sung một bản đã che |
| Thu bằng chứng: chứng chỉ PDF mẫu + trang verify | `certificate-sample.pdf`, `certificate-sample.png`, `certificate-3-verify-page.png`, `certificate-5-verify-phone.png`, `certificate-4-wrong-code.png` | **có** |
| Thu bằng chứng: dashboard instructor và admin | `dashboards.txt`, `instructor-dashboard-{30d,12m}.png`, `admin-dashboard-{30d,12m}.png` (+ `admin-categories/coupons/banners.png`, `home-banners.png`) | **có** — 01/10, tài khoản seed trên dữ liệu bán hàng 12 tháng. Số trên ảnh đối chiếu với SQL gốc (`dashboards.txt` §2) |

## Ngoài gate, đã thu

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `payment-ipn.txt` | Luồng đơn hàng + IPN VNPay chạy thật (24/09): ai được quyền nói là đã trả tiền, IPN hợp lệ / trùng / sai chữ ký, log append-only ghi trước khi phán xét, 26 + 20 test | 4 — Xây dựng hệ thống, 5 — Kiểm thử |
| `admin-moderation.txt` | Vòng duyệt khóa học (gửi → từ chối có lý do → gửi lại → duyệt), báo cáo vi phạm → gỡ khóa học, khóa/mở tài khoản, 375 px. **Duyệt là lúc nạp khóa học vào chatbot và recommender**, sau khi bỏ cờ auto-approve | 4 — Xây dựng hệ thống |
| `admin-dashboard.txt` | Định nghĩa DAU không cần bảng mới (dấu vết ở 11 bảng sẵn có), danh mục 2 cấp, mã giảm giá toàn sàn, banner (tải ảnh thẳng lên bucket) | 4 — Xây dựng hệ thống |

Các task còn lại của phase (giỏ hàng, coupon, dashboard giảng viên, XP + chuỗi ngày, bảng xếp hạng, Q&A, thông báo) ghi bằng chứng chạy thật **ngay trong ghi chú của từng task** ở [file kế hoạch](../../../plan/phase-5-commerce-admin.md), không có tệp riêng.
