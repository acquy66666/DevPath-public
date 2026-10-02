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
proxy/             Proxy Docker API giữa worker và daemon: policy.py (luật), server.py (HTTP), Dockerfile
tests/fixtures/    Code mẫu tái hiện từng verdict + 7 ca tấn công (`attack_*.py`), body `create` thật của CLI
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
- **Worker không cầm socket Docker** (từ 02/10/2026): nó đi qua `proxy/`, container duy nhất cầm socket, và proxy chỉ cho `create` một container đúng các bất biến trên, cùng start/attach/wait/kill/inspect/rm container mang nhãn `devpath.grading=1`. **Đổi cờ nào trong `runner/sandbox.py` (`_container_flags`) thì phải đổi `proxy/policy.py` cùng lúc** — proxy là danh sách cho phép viết từ chính các cờ đó, cờ mới mà proxy chưa biết sẽ làm mọi bài nộp ra lỗi hệ thống (403). Ghi lại body mới vào `tests/fixtures/docker_create_body.json` và chạy `tests/test_docker_proxy_*.py`

## Chạy qua proxy

Ở máy dev, toàn bộ bộ verdict + tấn công sandbox + tấn công proxy chạy được xuyên qua proxy, ngay trong container worker (proxy không cho build image, nên image phải build sẵn):

```bash
docker compose -f infra/docker-compose.yml exec -e DEVPATH_THROUGH_PROXY=1 -w /grader grading-worker python -m pytest -q -p no:cacheprovider tests/test_verdict_end_to_end.py tests/test_sandbox_attacks.py tests/test_runner_core.py tests/test_docker_proxy_live.py
```

CI làm đúng việc đó trên runner (bước "Pytest through the Docker proxy"), thêm `DEVPATH_REAL_DOCKER_HOST` để hai ca cần dựng "nạn nhân" bằng daemon thật cũng chạy.

## Verdicts

`AC` · `WA` · `TLE` · `MLE` · `RE` · `CE` · `SE`

`SE` là lỗi phía hệ thống — phải log và cảnh báo, không đổ cho học viên.

## Cách làm việc

TDD bắt buộc: mỗi verdict và mỗi ca tấn công (đọc file ngoài mount, gọi network, ghi rootfs, fork bomb) phải có fixture tái hiện được trong `tests/fixtures/` trước khi viết runner. Bắt đầu ở [Phase 3](../docs/plan/phase-3-code-grading.md).

Bằng chứng đã thu: [docs/report/assets/phase-3/](../docs/report/assets/phase-3/).
