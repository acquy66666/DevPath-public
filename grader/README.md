# Grader — chấm mã nguồn trong sandbox

Điểm nhấn kỹ thuật số 1 của khóa luận, đồng thời là bề mặt tấn công lớn nhất: hệ thống **thực thi code tùy ý của người lạ**.

> ⚠️ Mọi thay đổi trong thư mục này phải đi qua checklist bảo mật trong skill `sandbox-grading`. Không có ngoại lệ.

## Cấu trúc

```
runner/            Điều phối container, so sánh output, tổng hợp verdict
images/python/     Dockerfile sandbox cho Python (v1 chỉ hỗ trợ Python)
tests/fixtures/    Code mẫu tái hiện từng verdict + các ca tấn công
```

## Bất biến bảo mật (tóm tắt — bản đầy đủ ở skill)

- `--network none`, `--read-only`, `--user nobody`, `--cap-drop ALL`, `--security-opt no-new-privileges`
- Giới hạn `--memory`, `--memory-swap` bằng memory, `--cpus`, `--pids-limit` (chặn fork bomb)
- Timeout hai lớp: wall-clock ở worker **và** CPU time trong container
- Cắt stdout/stderr trước khi so sánh (chống flood)
- Code người dùng là dữ liệu độc hại: truyền qua mount + argv, **không bao giờ** nội suy vào shell command
- Expected output của test case ẩn không bao giờ rời server

## Verdicts

`AC` · `WA` · `TLE` · `MLE` · `RE` · `CE` · `SE`

`SE` là lỗi phía hệ thống — phải log và cảnh báo, không đổ cho học viên.

## Cách làm việc

TDD bắt buộc: mỗi verdict và mỗi ca tấn công (đọc file ngoài mount, gọi network, ghi rootfs, fork bomb) phải có fixture tái hiện được trong `tests/fixtures/` trước khi viết runner. Bắt đầu ở [Phase 3](../docs/plan/phase-3-code-grading.md).
