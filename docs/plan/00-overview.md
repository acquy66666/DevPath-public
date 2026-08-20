# Kế hoạch tổng thể (14 tuần)

> Trạng thái dự án = checkbox trong các file phase. Sau khi hoàn thành task nào, tick ngay task đó. Mốc ngày tính theo khởi động **24/08/2026**; nếu lệch thì giữ nguyên thứ tự, dồn/cắt theo mục "Phương án cắt giảm".

| Phase | Nội dung | Tuần | Dự kiến | Điều kiện hoàn thành (gate) |
|---|---|---|---|---|
| [1 — Foundation](phase-1-foundation.md) | Khảo sát, thiết kế CSDL, khung dự án | 1–2 | 24/08 → 06/09 | Schema CSDL chốt; `docker compose up` chạy đủ stack; CI xanh |
| [2 — Core Platform](phase-2-core-platform.md) | Auth, quản lý khóa học, video streaming | 3–5 | 07/09 → 27/09 | Demo: đăng ký → tạo khóa học → enroll → xem video, tiến độ được lưu |
| [3 — Code Grading](phase-3-code-grading.md) ⭐ | Docker sandbox + hàng đợi chấm bài | 6–8 | 28/09 → 18/10 | Nộp bài → verdict realtime; test tấn công sandbox đều bị chặn |
| [4 — AI Features](phase-4-ai-features.md) ⭐ | Recommender, chatbot RAG, sinh quiz | 9–10 | 19/10 → 01/11 | Chatbot trả lời có trích nguồn; precision@k đo được; quiz sinh được từ bài giảng |
| [5 — Commerce & Admin](phase-5-commerce-admin.md) | Thanh toán, gamification, admin | 11–12 | 02/11 → 15/11 | Mua khóa học end-to-end qua VNPay sandbox; admin duyệt khóa học |
| [6 — Hardening & Deploy](phase-6-hardening-deploy.md) | Kiểm thử, bảo mật, triển khai VPS | 13 | 16/11 → 22/11 | **Sản phẩm đóng băng tính năng:** URL demo công khai chạy ổn định, E2E test xanh |
| [7 — Báo cáo & bảo vệ](phase-7-report.md) | Vẽ sơ đồ, viết báo cáo, slide, demo | 14 | 23/11 → 29/11 | Báo cáo hoàn chỉnh; slide + kịch bản demo đã tổng duyệt |

## Nguyên tắc xuyên suốt

1. **Vertical slice:** mỗi tính năng làm xuyên suốt DB → API → UI rồi mới sang tính năng kế; không xây "toàn bộ backend" trước.
2. **Demo được mỗi cuối phase** — gate ở bảng trên là bắt buộc, chưa qua gate chưa sang phase mới.
3. **Báo cáo viết sau khi sản phẩm xong** — toàn bộ việc vẽ sơ đồ (use case, ERD, kiến trúc) và viết chương dồn vào Phase 7, khi hệ thống đã hoàn chỉnh và không còn đổi thiết kế. Đổi lại, **bằng chứng phải thu ngay trong lúc làm**: mỗi gate phase lưu screenshot / số đo / log vào `docs/report/assets/phase-N/`. Không viết chữ nào trước Phase 7, nhưng cũng không để mất số liệu (skill `thesis-report` có bảng bằng chứng cần thu).
4. **Deploy sớm:** VPS chạy từ cuối Phase 2, không đợi Phase 6.
5. **Seed data sớm:** khóa học lập trình thật (Python cơ bản...) có từ Phase 2 để mọi tính năng sau demo trên dữ liệu thật.

## Rủi ro chính & đối sách

| Rủi ro | Đối sách |
|---|---|
| Sandbox phức tạp hơn dự kiến (tuần 6–8 tràn) | Phạm vi v1 chỉ Python; kiến trúc image per-language để mở rộng sau. Bắt đầu từ MVP: chấm sync 1 test → thêm queue → thêm realtime |
| Gemini API đổi/giới hạn quota | Adapter layer cho LLM call; cache câu trả lời; quiz sinh sẵn lưu DB |
| VNPay/MoMo sandbox trục trặc | Làm VNPay trước (tài liệu tốt hơn); MoMo là nice-to-have; luồng "mua khóa học 0đ" làm trước để không chặn các tính năng sau thanh toán |
| Ôm đồm tính năng phụ | Danh sách cắt giảm bên dưới |
| **Tuần 14 quá tải vì toàn bộ báo cáo dồn vào đây** | Bằng chứng đã thu đủ theo từng phase nên tuần 14 chỉ còn vẽ hình + viết; dàn ý 6 chương cố định sẵn trong skill `thesis-report`; nếu Phase 5 trễ thì cắt tính năng phụ theo danh sách bên dưới để giữ nguyên tuần 14, **không lấn sang tuần báo cáo** |

## Phương án cắt giảm (nếu trễ tiến độ, cắt theo thứ tự)

1. MoMo (giữ VNPay) → 2. Phụ đề video → 3. Wishlist → 4. Banner quản trị → 5. Leaderboard (giữ XP + streak) → 6. Upvote Q&A (giữ Q&A cơ bản)

**Không bao giờ cắt:** 3 điểm nhấn ⭐ (sandbox grading, recommender, RAG chatbot) — đây là giá trị khoa học của khóa luận.
