# Kế hoạch tổng thể (14 tuần + phase nâng cấp UI/UX)

> Trạng thái dự án = checkbox trong các file phase. Sau khi hoàn thành task nào, tick ngay task đó. Mốc ngày tính theo khởi động **24/08/2026**; nếu lệch thì giữ nguyên thứ tự, dồn/cắt theo mục "Phương án cắt giảm". Ngày 16/10/2026 dự án đi trước lịch khoảng một tháng, và user thêm Phase 7 (UI/UX). Lịch của Phase 7–8 tính lại khi biết ngày bảo vệ.

| Phase | Nội dung | Tuần | Dự kiến | Điều kiện hoàn thành (gate) |
|---|---|---|---|---|
| [1 — Foundation](phase-1-foundation.md) | Khảo sát, thiết kế CSDL, khung dự án | 1–2 | 24/08 → 06/09 | Schema CSDL chốt; `docker compose up` chạy đủ stack; CI xanh |
| [2 — Core Platform](phase-2-core-platform.md) | Auth, quản lý khóa học, video streaming | 3–5 | 07/09 → 27/09 | Demo: đăng ký → tạo khóa học → enroll → xem video, tiến độ được lưu |
| [3 — Code Grading](phase-3-code-grading.md) ⭐ | Docker sandbox + hàng đợi chấm bài | 6–8 | 28/09 → 18/10 | Nộp bài → verdict realtime; test tấn công sandbox đều bị chặn |
| [4 — AI Features](phase-4-ai-features.md) ⭐ | Recommender, chatbot RAG, sinh quiz | 9–10 | 19/10 → 01/11 | Chatbot trả lời có trích nguồn; precision@k đo được; quiz sinh được từ bài giảng |
| [5 — Commerce & Admin](phase-5-commerce-admin.md) | Thanh toán, gamification, admin | 11–12 | 02/11 → 15/11 | Mua khóa học end-to-end qua VNPay sandbox; admin duyệt khóa học |
| [6 — Hardening & Deploy](phase-6-hardening-deploy.md) | Kiểm thử, bảo mật, triển khai 0đ | 13 | 01/10 → … | **Đóng băng nghiệp vụ:** URL demo công khai chạy ổn định **trên tên miền thật**, E2E test xanh. Mốc giữa: **trình bày GVHD** trên tên miền thật qua tunnel 0đ |
| [6.5 — Cấp bậc giảng viên & tài chính](phase-6-5-tiers-finance.md) | Giảng viên không thấy tiền; 5 cấp + hoa hồng; doanh thu, xếp hạng, bảng kê, lãi lỗ cho admin; xuất Excel mọi trang | chèn 20/10 | 20/10 → … | Test backend xanh; giảng viên không thấy số tiền nào (test + ảnh); CI xanh trên PR |
| [7 — Nâng cấp UI/UX](phase-7-ui-ux-upgrade.md) | Design system (Claude Design), nhân vật linh vật + hoạt ảnh, thiết kế lại mọi màn | ~3 tuần sau mốc GVHD | tính lại | **Đóng băng giao diện:** design system khớp code; nhân vật đủ bản đồ phản ứng; CI xanh (E2E + hồi quy hình ảnh + axe); ảnh chương 4 chụp lại; tag `phase-7-done` |
| [8 — Báo cáo & bảo vệ](phase-8-report.md) | Vẽ sơ đồ, viết báo cáo, slide, demo | 14 | 23/11 → 29/11 | Báo cáo hoàn chỉnh; slide + kịch bản demo đã tổng duyệt |

## Ưu tiên hiện tại (user chốt 16/10/2026)

1. **Hoàn thiện các tính năng chính của đề cương.** 18/20 tính năng đã chạy; MoMo và phụ đề đã cắt; đăng nhập Google có code, chỉ chờ tên miền thật. Phase 6 còn 3 task gia cố không cần máy chủ: byte NUL → SE, ffmpeg, đơn 0đ.
2. **Không làm bước thanh toán thật qua cổng VNPay** (quét mã QR hoặc nhập thẻ test trên trang VNPay, rồi chờ IPN thật). Luồng mua vẫn chạy trên UI tới URL thanh toán đã ký; tiền được ghi nhận bằng IPN giả lập `scripts.simulate_vnpay_ipn`, đúng như gate Phase 5 và E2E. Báo cáo ghi rõ điều này.
3. **Deploy 0đ để kịp trình bày với GVHD**: tên miền `.me` của Student Pack + Cloudflare named tunnel vào stack production chạy trên máy dev. Được URL cố định trên tên miền thật, nên bật được đăng nhập Google và CSP. Máy chủ thật (Azure for Students, dự phòng Oracle) vẫn là gate Phase 6.
4. **Sau mốc trình bày GVHD: Phase 7 nâng cấp UI/UX** ([thiết kế](../ui-ux/thiet-ke-nang-cap-ui-ux.md)).
5. **Chèn 20/10/2026 — Phase 6.5 cấp bậc giảng viên & tài chính** ([thiết kế](../thiet-ke-cap-bac-va-tai-chinh.md)). User tạm dừng các task theo tiến độ để làm phần này, nên Phase 7 bắt đầu sau khi nó xong.

**Thứ tự phase không còn tuyệt đối.** Task Phase 6 chờ máy chủ thật không chặn Phase 7. Khi mở phiên: nếu task chưa tick đầu tiên của Phase 6 bị chặn bởi VPS **và** mục "Mốc trình bày GVHD" của Phase 6 đã tick, thì lấy task chưa tick đầu tiên của Phase 7.

## Nguyên tắc xuyên suốt

1. **Vertical slice:** mỗi tính năng làm xuyên suốt DB → API → UI rồi mới sang tính năng kế; không xây "toàn bộ backend" trước.
2. **Demo được mỗi cuối phase** — gate ở bảng trên là bắt buộc, chưa qua gate chưa sang phase mới. Ngoại lệ duy nhất: Phase 6 → 7, xem mục "Ưu tiên hiện tại".
3. **Báo cáo viết sau khi sản phẩm xong** — toàn bộ việc vẽ sơ đồ (use case, ERD, kiến trúc) và viết chương dồn vào Phase 8, khi hệ thống đã hoàn chỉnh và không còn đổi thiết kế. Đổi lại, **bằng chứng phải thu ngay trong lúc làm**: mỗi gate phase lưu screenshot / số đo / log vào `docs/report/assets/phase-N/`. Không viết chữ nào trước Phase 7, nhưng cũng không để mất số liệu (skill `thesis-report` có bảng bằng chứng cần thu).
4. **Deploy sớm, nhưng tốn tiền muộn:** từ cuối Phase 2 đã phải có **URL công khai** để gửi cho GVHD và kiểm luồng thật từ máy khác — nhưng bằng phương án 0đ (Cloudflare Quick Tunnel trỏ vào stack chạy trên máy dev), không phải bằng VPS thuê. Máy chủ thật dựng ở Phase 6, bằng credit của GitHub Student Developer Pack, cũng 0đ. Điều kiện để làm được như vậy: **cấu hình production phải được tổng duyệt sớm** — đã làm ở tuần 5, chạy chính `docker-compose.prod.yml` trên máy dev, nên phần việc kỹ thuật của deploy đã xong trước khi có máy chủ.
5. **Seed data sớm:** khóa học lập trình thật (Python cơ bản...) có từ Phase 2 để mọi tính năng sau demo trên dữ liệu thật.

## Rủi ro chính & đối sách

| Rủi ro | Đối sách |
|---|---|
| Sandbox phức tạp hơn dự kiến (tuần 6–8 tràn) | Phạm vi v1 chỉ Python; kiến trúc image per-language để mở rộng sau. Bắt đầu từ MVP: chấm sync 1 test → thêm queue → thêm realtime |
| Gemini API đổi/giới hạn quota | Adapter layer cho LLM call; cache câu trả lời; quiz sinh sẵn lưu DB |
| VNPay/MoMo sandbox trục trặc | Làm VNPay trước (tài liệu tốt hơn); MoMo là nice-to-have; luồng "mua khóa học 0đ" làm trước để không chặn các tính năng sau thanh toán |
| Ôm đồm tính năng phụ | Danh sách cắt giảm bên dưới |
| Trả tiền hạ tầng suốt hai tháng chỉ để có URL công khai | Giai đoạn Phase 2–5 chỉ cần *demo được*, chưa cần *trình bày*: dùng Cloudflare Quick Tunnel (0đ, HTTPS thật, không cần tên miền). Máy chủ thật để tới Phase 6 và trả bằng credit Student Pack. Rủi ro còn lại là tunnel chỉ sống khi máy dev bật và URL đổi sau mỗi lần khởi động — chấp nhận được với một link gửi GVHD xem, không chấp nhận được với buổi bảo vệ, nên Phase 6 vẫn bắt buộc có tên miền thật |
| Phase 7 (UI/UX) tràn thời gian, lấn tuần báo cáo | Ngày bắt đầu Phase 8 là hạn cứng của Phase 7. Thiếu thời gian thì cắt nhóm màn từ nhóm 10 ngược lên ([phase-7](phase-7-ui-ux-upgrade.md)); không cắt phần nền, nhân vật và các kiểm chất lượng. Backend đứng yên suốt Phase 7, nên phần đã đo của chương 5 không phải đo lại |
| Đổi giao diện làm đỏ E2E hoặc làm cũ ảnh báo cáo | E2E chạy sau **mỗi** nhóm màn, spec sửa cùng commit; gate Phase 7 chạy lại `capture.cjs` để có bộ ảnh chương 4 mới |
| Đường tunnel cho buổi GVHD phụ thuộc máy dev | Tắt chế độ ngủ (Docker chết khi máy ngủ), cắm sạc, mạng dự phòng 4G — như `docs/huong-dan-demo-truoc-giao-vien.md`. Cloudflare Free chặn request > 100 MB, nên đừng demo tải video lớn qua tunnel |
| **Tuần 14 quá tải vì toàn bộ báo cáo dồn vào đây** | Bằng chứng đã thu đủ theo từng phase nên tuần 14 chỉ còn vẽ hình + viết; dàn ý 6 chương cố định sẵn trong skill `thesis-report`; nếu Phase 5 trễ thì cắt tính năng phụ theo danh sách bên dưới để giữ nguyên tuần 14, **không lấn sang tuần báo cáo** |

## Phương án cắt giảm (nếu trễ tiến độ, cắt theo thứ tự)

1. MoMo (giữ VNPay) → 2. Phụ đề video → 3. Wishlist → 4. Banner quản trị → 5. Leaderboard (giữ XP + streak) → 6. Upvote Q&A (giữ Q&A cơ bản)

**Đã cắt:**

- Mục 1 — MoMo, cắt 01/10/2026 (ghi ở [phase-5](phase-5-commerce-admin.md)).
- Mục 2 — phụ đề video, user chốt cắt ngày 05/10/2026. Tệp `.srt` giảng viên tải lên vẫn được giữ và dùng cho trợ giảng AI; player chỉ không hiển thị nó thành phụ đề.
- Ngoài danh sách — bước thanh toán thật qua cổng VNPay (QR/thẻ test + IPN thật), user chốt không làm ngày 16/10/2026. Đây không phải cắt tính năng: giỏ hàng, đơn, mã giảm giá, URL thanh toán đã ký và xử lý IPN đều đã có và có test; chỉ không chạy một giao dịch thật với VNPay.

Mục 3–6 đều đã làm.

**Không bao giờ cắt:** 3 điểm nhấn ⭐ (sandbox grading, recommender, RAG chatbot) — đây là giá trị khoa học của khóa luận.
