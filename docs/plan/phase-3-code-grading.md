# Phase 3 — Code Grading ⭐ (tuần 6–8, 28/09 → 18/10)

**Mục tiêu:** điểm nhấn kỹ thuật số 1. Học viên nộp code Python, hệ thống chấm trong Docker sandbox cô lập, trả kết quả từng test case realtime.

> **BẮT BUỘC:** đọc skill `sandbox-grading` trước mọi task trong phase này. Làm theo TDD — mỗi verdict có fixture tái hiện.

## Tuần 6 — Sandbox MVP

- [ ] Image sandbox Python: user không đặc quyền, tối giản (python:slim + user nobody)
- [ ] Runner core: chạy 1 file code + 1 stdin trong container với đủ giới hạn (network none, memory, cpus, pids, read-only, no-new-privileges, cap-drop ALL, tmpfs /tmp, timeout 2 lớp)
- [ ] So sánh output (trim trailing whitespace từng dòng), cắt output 1MB
- [ ] Bộ test verdict: AC / WA / TLE / MLE / RE / CE / SE — fixture cho từng loại trong `grader/tests/fixtures/`
- [ ] **Bộ test bảo mật:** thử network, đọc file ngoài mount, ghi rootfs, fork bomb → tất cả bị chặn (kết quả vào báo cáo chương 5)

## Tuần 7 — Tích hợp queue & API

- [ ] Bảng + API: `code_exercises`, `test_cases`, `submissions`, `submission_results`
- [ ] Instructor UI: tạo bài tập code (đề markdown, starter code, test case, giới hạn tài nguyên, sample/hidden)
- [ ] Celery queue riêng cho grading; worker gọi runner; retry + dead letter; concurrency giới hạn theo tài nguyên VPS
- [ ] Rate limit nộp bài (Redis) — chống spam queue
- [ ] API kết quả: hidden test chỉ trả verdict, không trả input/expected output

## Tuần 8 — Realtime & UX

- [ ] Redis pub/sub tiến độ chấm → WebSocket endpoint; fallback polling
- [ ] Trang nộp bài: Monaco editor, starter code, chạy thử với sample test, nộp chính thức, lịch sử submission
- [ ] Kết quả hiển thị per-test realtime (đang chấm test 3/10...)
- [ ] Benchmark: thời gian chấm trung bình, throughput khi 10 bài nộp cùng lúc — số liệu vào báo cáo
- [ ] Buffer trễ / hoàn thiện UX còn dở của phase trước

## Gate cuối phase

- [ ] Demo: tạo bài tập → nộp bài sai → thấy WA realtime → sửa → AC
- [ ] Toàn bộ test verdict + test bảo mật xanh trong CI
- [ ] Bằng chứng chương 4+5: sơ đồ kiến trúc grading, bảng benchmark, bảng thử nghiệm tấn công
