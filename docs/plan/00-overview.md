# Kế hoạch tổng thể (14 tuần)

> Trạng thái dự án = checkbox trong các file phase. Sau khi hoàn thành task nào, tick ngay task đó. Mốc ngày tính theo khởi động **24/08/2026**; nếu lệch thì giữ nguyên thứ tự, dồn/cắt theo mục "Phương án cắt giảm".

| Phase | Nội dung | Tuần | Dự kiến | Điều kiện hoàn thành (gate) |
|---|---|---|---|---|
| [1 — Foundation](phase-1-foundation.md) | Khảo sát, thiết kế CSDL, wireframe, khung dự án | 1–2 | 24/08 → 06/09 | ERD duyệt xong; `docker compose up` chạy đủ stack; CI xanh |
| [2 — Core Platform](phase-2-core-platform.md) | Auth, quản lý khóa học, video streaming | 3–5 | 07/09 → 27/09 | Demo: đăng ký → tạo khóa học → enroll → xem video, tiến độ được lưu |
| [3 — Code Grading](phase-3-code-grading.md) ⭐ | Docker sandbox + hàng đợi chấm bài | 6–8 | 28/09 → 18/10 | Nộp bài → verdict realtime; test tấn công sandbox đều bị chặn |
| [4 — AI Features](phase-4-ai-features.md) ⭐ | Recommender, chatbot RAG, sinh quiz | 9–10 | 19/10 → 01/11 | Chatbot trả lời có trích nguồn; precision@k đo được; quiz sinh được từ bài giảng |
| [5 — Commerce & Admin](phase-5-commerce-admin.md) | Thanh toán, gamification, admin | 11–12 | 02/11 → 15/11 | Mua khóa học end-to-end qua VNPay sandbox; admin duyệt khóa học |
| [6 — Hardening & Report](phase-6-hardening-report.md) | Kiểm thử, triển khai VPS, báo cáo | 13–14 | 16/11 → 29/11 | URL demo công khai; báo cáo hoàn chỉnh |

## Nguyên tắc xuyên suốt

1. **Vertical slice:** mỗi tính năng làm xuyên suốt DB → API → UI rồi mới sang tính năng kế; không xây "toàn bộ backend" trước.
2. **Demo được mỗi cuối phase** — gate ở bảng trên là bắt buộc, chưa qua gate chưa sang phase mới.
3. **Báo cáo viết song song** — cuối mỗi phase cập nhật chương tương ứng (skill `thesis-report` có bảng bằng chứng cần thu).
4. **Deploy sớm:** VPS chạy từ cuối Phase 2, không đợi Phase 6.
5. **Seed data sớm:** khóa học lập trình thật (Python cơ bản...) có từ Phase 2 để mọi tính năng sau demo trên dữ liệu thật.

## Rủi ro chính & đối sách

| Rủi ro | Đối sách |
|---|---|
| Sandbox phức tạp hơn dự kiến (tuần 6–8 tràn) | Phạm vi v1 chỉ Python; kiến trúc image per-language để mở rộng sau. Bắt đầu từ MVP: chấm sync 1 test → thêm queue → thêm realtime |
| Gemini API đổi/giới hạn quota | Adapter layer cho LLM call; cache câu trả lời; quiz sinh sẵn lưu DB |
| VNPay/MoMo sandbox trục trặc | Làm VNPay trước (tài liệu tốt hơn); MoMo là nice-to-have; luồng "mua khóa học 0đ" làm trước để không chặn các tính năng sau thanh toán |
| Ôm đồm tính năng phụ | Danh sách cắt giảm bên dưới |

## Phương án cắt giảm (nếu trễ tiến độ, cắt theo thứ tự)

1. MoMo (giữ VNPay) → 2. Phụ đề video → 3. Wishlist → 4. Banner quản trị → 5. Leaderboard (giữ XP + streak) → 6. Upvote Q&A (giữ Q&A cơ bản)

**Không bao giờ cắt:** 3 điểm nhấn ⭐ (sandbox grading, recommender, RAG chatbot) — đây là giá trị khoa học của khóa luận.
