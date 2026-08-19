# Workflow phát triển tối ưu với Claude Code

Quy trình làm việc đề xuất cho một người làm khóa luận 14 tuần, dùng Claude Code làm cộng sự chính.

## Vòng lặp chuẩn cho MỖI tính năng

```
1. Chọn task từ docs/plan/phase-N.md (theo đúng thứ tự trong file)
2. Brainstorm nhanh (nếu task mơ hồ) → Claude dùng skill brainstorming, chốt thiết kế nhỏ
3. Plan mode (Shift+Tab) với task phức tạp → duyệt kế hoạch trước khi Claude viết code
4. Implement theo TDD với logic quan trọng (grading, payment, recommender):
   test đỏ → code → test xanh → refactor
5. Tự chạy demo bằng mắt (không tin "đã xong" khi chưa thấy chạy)
6. /code-review trước khi commit các thay đổi lớn
7. Commit (Conventional Commits) + tick checkbox trong file phase
```

**Kích thước task lý tưởng:** 0.5–1 ngày. Task nào ước lượng >2 ngày → bảo Claude bẻ nhỏ trước khi làm.

## Nhịp làm việc theo tuần

| Thời điểm | Việc |
|---|---|
| Đầu tuần | Đọc lại file phase hiện tại, chọn các task tuần này, điều chỉnh nếu tuần trước trễ |
| Trong tuần | Vòng lặp tính năng ở trên; mỗi ngày kết thúc bằng commit sạch (không để code dở qua đêm không commit) |
| Cuối tuần | Demo tự thân những gì làm được; cập nhật bằng chứng báo cáo (skill `thesis-report`); ghi lại quyết định kỹ thuật đáng nhớ vào docs |
| Cuối phase | Chạy gate checklist cuối file phase; chưa qua gate → chưa sang phase mới; tag git `phase-N-done` |

## Phân vai với Claude Code

**Claude làm tốt — giao hẳn:**
- Viết code theo spec đã chốt, viết test, viết migration, seed data
- Scaffold trang UI theo skill `nextjs-feature`
- Debug có hệ thống (skill systematic-debugging), viết tài liệu, vẽ sơ đồ mermaid
- Review code (`/code-review`), rà bảo mật (`/security-review`)

**Bạn phải tự làm/tự quyết:**
- Quyết định phạm vi: làm gì, cắt gì (tham chiếu "Phương án cắt giảm" trong 00-overview.md)
- Nhìn demo bằng mắt trước khi coi một tính năng là xong
- Hiểu code các phần trọng điểm (sandbox, payment, recommender) đủ sâu để **trả lời hội đồng** — bảo Claude giảng lại bất kỳ đoạn nào bạn chưa chắc; đây là khóa luận của bạn
- Tài khoản/secret: API key Gemini, VNPay, R2, VPS — không bao giờ dán secret vào chat/repo, dùng `.env` (đã gitignore)

## Kỹ thuật dùng Claude Code hiệu quả cho dự án này

1. **Mỗi phiên bắt đầu bằng `/start-session`:** skill này tự đọc plan, xác định phase + task kế tiếp, kiểm tra git và đề xuất mục tiêu phiên — bạn chỉ cần chốt. Không cần giải thích lại ngữ cảnh mỗi lần.
2. **Skill tự kích hoạt:** khi đụng endpoint → `fastapi-endpoint`; schema → `db-migration`; UI → `nextjs-feature`; grader → `sandbox-grading` (bắt buộc); báo cáo → `thesis-report`. Nếu Claude quên, nhắc tên skill.
3. **Một việc một phiên:** xong tính năng, commit, mở phiên mới (hoặc `/clear`) cho tính năng kế — context sạch cho kết quả tốt hơn.
4. **Việc song song độc lập** (ví dụ: seed data + viết docs trong khi bạn xử lý VNPay đăng ký tài khoản) → dùng subagent/worktree.
5. **Trước khi hỏi "tại sao lỗi":** đưa Claude log/traceback đầy đủ thay vì mô tả lại bằng lời.
6. **Cuối mỗi phase:** yêu cầu Claude "chạy gate checklist phase N" — nó sẽ tự kiểm tra từng mục và báo mục nào chưa đạt.

## Git

- `main` luôn chạy được; feature branch `feature/<tên>` cho mọi thay đổi ≥1 giờ
- Commit nhỏ, message Conventional Commits; tag `phase-N-done` tại mỗi gate
- Push lên GitHub hằng ngày — GitHub là backup khóa luận của bạn
- File `.env`, `*.pem`, dữ liệu video KHÔNG commit

## Ba cạm bẫy lớn nhất của đề tài này (đã gặp là trễ deadline)

1. **Xây ngang thay vì xây dọc** — làm "toàn bộ backend" 5 tuần đầu rồi mới đụng UI. Luôn làm vertical slice từng tính năng chạy được end-to-end.
2. **Để dành 3 điểm nhấn ⭐ đến cuối** — sandbox ở tuần 6–8 và AI ở tuần 9–10 là *chính giữa* kế hoạch, đúng chỗ của nó. Tính năng phụ (wishlist, banner...) mới là thứ được phép trễ.
3. **Dồn báo cáo về tuần 14** — mỗi phase kết thúc phải cập nhật chương báo cáo tương ứng ngay (skill `thesis-report` liệt kê bằng chứng cần thu từng phase).
