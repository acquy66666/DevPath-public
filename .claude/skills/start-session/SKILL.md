---
name: start-session
description: Use when beginning a work session on this project — the user opens with "bắt đầu", "tiếp tục", "làm tiếp", "hôm nay làm gì", "start Phase N", or asks to work without naming a specific task.
---

# Mở đầu phiên làm việc

## Nguyên tắc

Không viết dòng code nào trước khi biết **đang ở đâu trong kế hoạch** và **phiên này làm đúng một task nào**. Trạng thái dự án nằm ở checkbox trong `docs/plan/phase-*.md`, không nằm trong trí nhớ của phiên trước.

## Quy trình — làm đủ 4 bước, đúng thứ tự

### 1. Thu thập trạng thái

- Đọc `docs/plan/00-overview.md` → phase hiện tại là phase đầu tiên còn task chưa tick
- Đọc file phase đó → lấy **task chưa tick đầu tiên**
- Chạy `git status --short`, `git log --oneline -3`, và xem branch hiện tại

Đọc file kế hoạch bằng **tool Read hoặc Grep**, không dùng PowerShell `Get-Content` — PowerShell 5.1 đọc mặc định ANSI nên tiếng Việt bị vỡ thành mojibake. Nếu buộc dùng, thêm `-Encoding utf8`.

### 2. Đối chiếu checkbox với thực tế

Checkbox hay lệch với code thật. Kiểm tra nhanh hai chiều:
- Task đã tick nhưng file/endpoint tương ứng không tồn tại → báo, đề xuất bỏ tick
- Code đã có nhưng task chưa tick → báo, đề xuất tick

Không tự ý sửa checkbox khi chưa được chốt.

### 3. In báo cáo mở phiên

Xuất đúng khối dưới đây, không thêm đoạn dẫn nhập dài dòng:

```
📍 Phase <N> — <tên phase> (tuần <x>, gate: <điều kiện gate rút gọn>)
✅ Tiến độ phase: <đã tick>/<tổng> task
🔀 Git: <branch> — <"sạch" | "N file chưa commit">
⚠️ Lệch trạng thái: <mô tả — bỏ hẳn dòng này nếu không có>
▶️ Đề xuất phiên này: <1 task, chép nguyên văn từ file phase>
🧰 Skill sẽ dùng: <fastapi-endpoint | db-migration | nextjs-feature | sandbox-grading | thesis-report>
```

In xong thì **dừng lại chờ chốt**, chưa động vào code.

### 4. Vào việc sau khi được chốt

- Còn thay đổi chưa commit từ phiên trước → xử lý trước (commit hoặc stash), không chồng việc mới lên việc dở
- Task ước lượng ≥ 1 ngày → bẻ nhỏ rồi mới code
- Task > 1 giờ → tạo branch `feature/<tên-task>`
- Logic trọng điểm (grading, payment, recommender) → TDD, viết test trước

## Quy tắc chọn task

Lấy **task chưa tick đầu tiên** của phase, không nhảy cóc. Ngoại lệ duy nhất: task bị chặn bởi yếu tố bên ngoài (chưa có API key Gemini, chưa đăng ký VNPay sandbox, chưa có VPS) → lấy task kế tiếp và nói rõ lý do bỏ qua.

Một phiên = **một task**. Xong sớm thì mở phiên mới, không gộp nhiều task vào một phiên.

## Trước khi kết thúc phiên

Phiên sau chỉ mở tốt nếu phiên này đóng sạch:

- [ ] Tick checkbox task vừa xong trong `docs/plan/phase-*.md`
- [ ] Test liên quan chạy pass — dán kết quả thật, không tuyên bố suông
- [ ] Commit (Conventional Commits) + push
- [ ] Vừa qua gate cuối phase → thu bằng chứng báo cáo (skill `thesis-report`) và tag `phase-N-done`

## Red flags — dừng lại nếu đang

- Viết code trước khi in báo cáo mở phiên
- Chọn task không có trong file phase
- Làm 2–3 task cùng lúc "cho tiện vì đang mở sẵn file"
- Bỏ qua `git status` vì "chắc là sạch"
- Kết thúc phiên mà không tick checkbox
