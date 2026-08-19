---
name: thesis-report
description: Use when writing, updating, or planning the thesis report (báo cáo khóa luận) — chapter structure, Vietnamese academic style, and the evidence/figures/metrics to capture during development so nothing is missing at write-up time.
---

# Báo cáo khóa luận

## Nguyên tắc quan trọng nhất

**Báo cáo viết song song với code, không dồn về tuần 13–14.** Cuối mỗi phase, cập nhật chương tương ứng và chụp/lưu bằng chứng ngay khi tính năng còn chạy tốt. Bằng chứng lưu tại `docs/report/assets/`.

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
| 1 | ERD final, wireframe, bảng use case |
| 2 | Screenshot luồng đăng ký→học video; sơ đồ luồng auth JWT/OAuth |
| 3 | Sơ đồ kiến trúc grading; bảng đo thời gian chấm (per ngôn ngữ, per giới hạn); log demo các verdict; bảng thử nghiệm tấn công sandbox (fork bomb, network, đọc file → đều bị chặn) |
| 4 | Precision@k / recall@k trên tập dữ liệu seed; ví dụ hội thoại chatbot có trích nguồn; ví dụ quiz sinh tự động kèm đánh giá chất lượng |
| 5 | Screenshot luồng thanh toán sandbox end-to-end; dashboard admin |
| 6 | Kết quả load test nhẹ (k6/locust); URL demo chạy trên VPS; bảng tổng hợp test |

## Văn phong

- Tiếng Việt học thuật, khách quan ("hệ thống được thiết kế..." thay vì "em làm..."). Thuật ngữ kỹ thuật giữ tiếng Anh kèm giải thích lần đầu xuất hiện.
- Mọi hình vẽ có đánh số + caption + được tham chiếu trong văn bản. Sơ đồ vẽ bằng mermaid/draw.io xuất PNG, lưu source trong `docs/report/diagrams/`.
- Số liệu phải tái tạo được: script đo benchmark/metrics lưu trong repo (`backend/scripts/eval_*.py`), báo cáo ghi rõ cách chạy.
