---
name: thesis-report
description: Use when writing, updating, or planning the thesis report (báo cáo khóa luận) — chapter structure, Vietnamese academic style, and the evidence/figures/metrics to capture during development so nothing is missing at write-up time.
---

# Báo cáo khóa luận

## Nguyên tắc quan trọng nhất

**Viết báo cáo ở Phase 7, sau khi sản phẩm hoàn chỉnh và đóng băng tính năng.** Trong Phase 1–6 không viết chương nào, không vẽ sơ đồ nào — nhưng **bắt buộc thu bằng chứng** ở gate mỗi phase, lưu vào `docs/report/assets/phase-N/`.

Ranh giới rõ ràng:

| Làm ngay trong lúc code (Phase 1–6) | Để đến Phase 7 |
|---|---|
| Screenshot màn hình lúc tính năng vừa chạy | Viết chương, đặt caption, trích dẫn |
| Chạy script đo và lưu output (benchmark, precision@k, load test) | Vẽ use case, ERD, sơ đồ kiến trúc, sơ đồ luồng |
| Lưu log demo, output test tấn công sandbox | Bản vẽ thiết kế giao diện |
| Ghi 1–2 dòng cho mỗi quyết định kỹ thuật vào `docs/report/assets/decisions.md` | Slide, kịch bản demo |

Lý do chia thế này: câu chữ và hình vẽ làm cuối thì khớp sản phẩm thật và không phải sửa lại; còn số đo/ảnh chụp mà không lấy ngay thì tuần 14 phải dựng lại môi trường để đo lại — đắt và dễ thiếu.

## Cấu trúc chương đề xuất

1. **Mở đầu** — lý do chọn đề tài, mục tiêu, phạm vi (lấy từ đề cương, viết lại thành văn)
2. **Cơ sở lý thuyết & công nghệ** — e-learning, sandbox/container isolation, collaborative + content-based filtering, RAG, kiến trúc hàng đợi
3. **Phân tích & thiết kế hệ thống** — use case, ERD, kiến trúc tổng thể, thiết kế sandbox, thiết kế recommender & RAG pipeline
4. **Xây dựng hệ thống** — chi tiết cài đặt từng phân hệ, các quyết định kỹ thuật và trade-off
5. **Kiểm thử & đánh giá** — test coverage, benchmark grading, đánh giá recommender (precision@k, recall@k), đánh giá chatbot, kết quả triển khai VPS
6. **Kết luận & hướng phát triển**

## Bằng chứng phải thu thập theo phase (đừng để mất)

| Phase | Thu thập |
|---|---|
| 1 | Bảng khảo sát nền tảng tham chiếu; ảnh `docker compose ps` đủ service; ảnh CI xanh; dump schema sau migration đầu |
| 2 | Screenshot luồng đăng ký→học video; ghi chú quyết định về JWT/OAuth, HLS, R2 (chưa vẽ sơ đồ) |
| 3 | Bảng đo thời gian chấm (per giới hạn tài nguyên); log demo đủ 7 verdict; output test tấn công sandbox (fork bomb, network, đọc file → đều bị chặn); screenshot chấm realtime |
| 4 | Precision@k / recall@k trên tập dữ liệu seed; ví dụ hội thoại chatbot có trích nguồn + 1 ca từ chối ngoài phạm vi; ví dụ quiz sinh tự động kèm đánh giá chất lượng |
| 5 | Screenshot luồng thanh toán sandbox end-to-end; log IPN đã che dữ liệu nhạy cảm; chứng chỉ PDF mẫu; dashboard instructor + admin |
| 6 | Kết quả load test nhẹ (k6/locust); URL demo chạy trên VPS; bảng tổng hợp test; **rà soát lần cuối toàn bộ kho bằng chứng trước khi đóng băng** |
| 7 | Không thu nữa — đây là phase tiêu thụ bằng chứng: vẽ sơ đồ, viết 6 chương, làm slide |

## Văn phong

- Tiếng Việt học thuật, khách quan ("hệ thống được thiết kế..." thay vì "em làm..."). Thuật ngữ kỹ thuật giữ tiếng Anh kèm giải thích lần đầu xuất hiện.
- Mọi hình vẽ có đánh số + caption + được tham chiếu trong văn bản. Sơ đồ vẽ bằng mermaid/draw.io xuất PNG, lưu source trong `docs/report/diagrams/`.
- Số liệu phải tái tạo được: script đo benchmark/metrics lưu trong repo (`backend/scripts/eval_*.py`), báo cáo ghi rõ cách chạy.
