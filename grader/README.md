# Grader — chấm mã nguồn trong sandbox

Điểm nhấn kỹ thuật số 1 của khóa luận, đồng thời là bề mặt tấn công lớn nhất: hệ thống **thực thi code tùy ý của người lạ**.

> ⚠️ Mọi thay đổi trong thư mục này phải đi qua checklist bảo mật trong skill `sandbox-grading`. Không có ngoại lệ.

## Cấu trúc

```
runner/            Điều phối container, so sánh output, tổng hợp verdict
runner/images.py   Tên tag của các image sandbox — nguồn duy nhất, và lệnh build
runner/sandbox.py  Chạy 1 file + 1 stdin trong 1 container dùng một lần, đủ giới hạn
runner/compare.py  Chuẩn hóa và so sánh output — chính sách "thế nào là đúng", không cần Docker
runner/verdict.py  Compile 1 lần, chạy từng test case, đặt tên verdict cho cả bài nộp
images/python/     Dockerfile sandbox cho Python (v1 chỉ hỗ trợ Python)
tests/fixtures/    Code mẫu tái hiện từng verdict + 7 ca tấn công (`attack_*.py`)
```

## Chạy

```bash
cd grader
python -m runner.images     # build mọi image sandbox
python -m pytest -q         # test cũng tự build trước khi chạy
```

Toàn bộ test ở đây cần Docker thật: thứ được kiểm là một image và mức cô lập
nhân dành cho nó, không mock được. Thiếu Docker thì test **skip** trên máy dev
và **fail** trong CI (biến `CI`) — một bộ test sandbox bị skip im lặng còn tệ
hơn một bộ test đỏ.

## Một biến môi trường: `DEVPATH_GRADING_WORKSPACE`

Không đặt thì runner dùng thư mục tạm của hệ thống — đúng ở máy dev và trong CI.

Chỉ cần khi **runner chạy bên trong một container** (worker chấm bài). Đường dẫn
trong `--mount source=` do Docker daemon phân giải, tức là phân giải trên host:
một runner nằm trong container sẽ xin mount thư mục chỉ tồn tại bên trong chính
nó, và Docker đáp "bind source path does not exist" trên **mọi** bài nộp. Worker
vì thế bind-mount một thư mục của host vào đúng đường dẫn ấy bên trong nó rồi
trỏ biến này vào đó — cùng một cái tên ở cả hai phía.

## Bất biến bảo mật (tóm tắt — bản đầy đủ ở skill)

- `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`
- Chạy dưới user không đặc quyền `sandbox` (uid 10001) — `USER` nằm sẵn trong image, `--user` của runner là lớp thứ hai
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

Bằng chứng đã thu: [docs/report/assets/phase-3/](../docs/report/assets/phase-3/).
