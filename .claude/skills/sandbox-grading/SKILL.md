---
name: sandbox-grading
description: MANDATORY when touching anything that executes user-submitted code — the grader worker, Docker sandbox images, submission queue, or test-case runner. Security checklist and grading flow that must never be violated.
---

# Hệ thống chấm mã nguồn — quy tắc an toàn

Đây là điểm nhấn kỹ thuật số 1 của khóa luận và cũng là bề mặt tấn công lớn nhất: **hệ thống thực thi code tùy ý của người lạ.** Mọi thay đổi phải giữ nguyên các bất biến dưới đây.

## Bất biến bảo mật (không có ngoại lệ)

1. **Network tắt hoàn toàn:** container chạy `--network none`.
2. **Giới hạn tài nguyên:** `--memory` (mặc định 256MB) + `--memory-swap` bằng memory (cấm swap), `--cpus` (mặc định 0.5), `--pids-limit` (mặc định 64, chặn fork bomb).
3. **Timeout hai lớp:** wall-clock timeout ở worker (kill container) VÀ CPU time limit trong container. Mặc định 5s/test case, giảng viên cấu hình được trong giới hạn trần.
4. **Không chạy root:** user không đặc quyền trong container (`--user nobody` hoặc user riêng trong image).
5. **Filesystem:** rootfs read-only (`--read-only`), code + input mount read-only, chỉ `/tmp` là tmpfs có giới hạn size để ghi.
6. **Chặn escalation:** `--security-opt no-new-privileges`, drop mọi capability (`--cap-drop ALL`).
7. **Giới hạn output:** cắt stdout/stderr (mặc định 1MB) trước khi so sánh — chống flood.
8. **Code người dùng là dữ liệu độc hại:** không bao giờ nội suy code/filename người dùng vào shell command; truyền qua mount + argv. Không log nguyên văn code vào log chung.
9. **Test case ẩn không bao giờ rời server:** API không trả expected output của hidden test case, kể cả khi sai — chỉ trả verdict + input của sample test.

## Luồng chấm bài

```
Học viên nộp → API tạo submission (status=pending) → đẩy job vào Celery queue
→ Worker nhận job → spin container theo ngôn ngữ → compile (nếu cần)
→ chạy tuần tự từng test case (feed stdin, so stdout đã trim trailing whitespace)
→ verdict per test → tổng hợp → update DB → publish tiến độ realtime (Redis pub/sub → WebSocket/polling)
```

## Verdicts chuẩn

`AC` (accepted) · `WA` (wrong answer) · `TLE` (time limit) · `MLE` (memory limit) · `RE` (runtime error) · `CE` (compile error) · `SE` (system error — lỗi phía mình, phải log và alert, không đổ cho học viên)

## Khi thay đổi grader

- Viết test trước (TDD): mỗi verdict phải có submission mẫu tái hiện được trong test suite (`grader/tests/fixtures/` — code mẫu AC, vòng lặp vô hạn cho TLE, cấp phát quá đà cho MLE, fork bomb cho pids-limit...).
- Test bảo mật là test hạng nhất: thử đọc file ngoài mount, thử gọi network, thử ghi rootfs — tất cả phải fail.
- Ngôn ngữ hỗ trợ ban đầu: Python. Java/C++/Go là hướng phát triển — thiết kế image per-language để mở rộng được, nhưng KHÔNG build sớm.
