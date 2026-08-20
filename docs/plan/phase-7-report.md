# Phase 7 — Báo cáo & bảo vệ (tuần 14, 23/11 → 29/11)

**Mục tiêu:** sản phẩm đã đóng băng ở Phase 6, tuần này chỉ làm ba việc: vẽ sơ đồ, viết báo cáo, chuẩn bị bảo vệ.

> Nguyên tắc: **không code tính năng mới.** Chỉ sửa lỗi chặn demo. Mọi sơ đồ vẽ theo hệ thống *đã có thật*, không vẽ theo dự định.

## Vẽ sơ đồ & thiết kế (chương 3)

- [ ] Use case diagram cho 3 nhóm người dùng (student / instructor / admin) — dựng từ tính năng thực tế đã làm, đối chiếu [đề cương mục 5](../../de-cuong-khoa-luan-elearning.md) xem có lệch gì cần giải trình
- [ ] ERD final — sinh từ schema thật (`pg_dump -s` hoặc SQLAlchemy metadata) rồi vẽ lại bằng mermaid/draw.io, không vẽ tay theo trí nhớ
- [ ] Sơ đồ kiến trúc tổng thể (Next.js ↔ FastAPI ↔ Postgres/Redis ↔ Celery ↔ sandbox ↔ R2 ↔ Gemini)
- [ ] Sơ đồ luồng: auth JWT/OAuth, luồng chấm bài trong sandbox, pipeline RAG, luồng thanh toán VNPay
- [ ] Bản vẽ thiết kế giao diện các màn chính — dựng lại từ sản phẩm thật (screenshot có chú thích, hoặc wireframe vẽ lại cho gọn)
- [ ] Toàn bộ source sơ đồ lưu `docs/report/diagrams/`, ảnh xuất PNG lưu `docs/report/assets/`

## Viết báo cáo

- [ ] Chương 1 — Mở đầu: lý do, mục tiêu, phạm vi (nguồn: đề cương + [bảng khảo sát nền tảng](../report/assets/khao-sat-nen-tang-tham-chieu.md))
- [ ] Chương 2 — Cơ sở lý thuyết: e-learning, container isolation, content-based + collaborative filtering, RAG, kiến trúc hàng đợi
- [ ] Chương 3 — Phân tích & thiết kế: use case, ERD, kiến trúc, thiết kế sandbox, thiết kế recommender & RAG
- [ ] Chương 4 — Xây dựng hệ thống: cài đặt từng phân hệ + quyết định kỹ thuật (nguồn: `decisions.md` và screenshot thu theo từng phase)
- [ ] Chương 5 — Kiểm thử & đánh giá: coverage, benchmark grading, bảng test tấn công sandbox, precision@k/recall@k, đánh giá chatbot, load test
- [ ] Chương 6 — Kết luận & hướng phát triển: nêu thẳng hạn chế (tính năng đã cắt, phạm vi v1 chỉ Python...)
- [ ] Rà toàn bộ hình: đánh số, caption, được tham chiếu trong văn bản; rà bảng số liệu khớp với file trong `assets/`; rà trích dẫn tài liệu tham khảo

## Bảo vệ

- [ ] Slide 15–20 trang, tập trung 3 điểm nhấn ⭐ (sandbox grading, recommender, RAG chatbot)
- [ ] Kịch bản demo 7–10 phút: dữ liệu, tài khoản, đường đi bấm chuẩn bị sẵn
- [ ] **Quay video demo dự phòng** — phòng khi mạng/VPS trục trặc hôm bảo vệ
- [ ] Chuẩn bị trả lời câu hỏi hội đồng về 3 điểm nhấn: đọc lại code, nhờ Claude giảng lại đoạn nào chưa chắc
- [ ] Tổng duyệt: nhờ 1–2 bạn dùng thử theo kịch bản, sửa vấp váp cuối

## Gate cuối phase (= sẵn sàng bảo vệ)

- [ ] Báo cáo in được, đủ 6 chương, mọi số liệu tái tạo được bằng script trong repo
- [ ] URL demo công khai vẫn chạy ổn định
- [ ] Video demo dự phòng đã quay
- [ ] Slide + kịch bản demo đã tổng duyệt
