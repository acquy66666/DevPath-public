# Bằng chứng Phase 3 — Code Grading ⭐

## Image sandbox Python (08/09/2026)

Image mà mã nguồn của người lạ sẽ chạy trong đó: `grader/images/python/Dockerfile`, tag `devpath-sandbox-python:v1`.

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `sandbox-image.txt` | Cấu hình image đã build; **bảng đối chứng image thường ↔ image sandbox** trên 9 phép thử; kết quả ruff + 12 test | 4 — Xây dựng hệ thống, và 6 — Bảo mật |
| `runner-core.txt` | Giới hạn đọc từ **bên trong** container; hai lớp timeout đo bằng số thật; **phát hiện PID 1 nuốt tín hiệu**; OOM / crash / cắt output / SE; kiểm tra rò container; chi phí một lần chấm | 4 — Xây dựng hệ thống, và 6 — Bảo mật |
| `output-comparison.txt` | **Bảng đối chứng so sánh thô ↔ so sánh có chuẩn hóa** trên 14 ca; lý do không dùng `splitlines()`; luật output bị cắt không bao giờ AC; kết quả ruff + 18 test | 4 — Xây dựng hệ thống |

### Đã chứng minh được

Cột "base" trong bảng đối chứng là thứ sẽ xảy ra nếu chấm bài bằng `python:3.12-slim` nguyên bản — nó không phải giả định, mà là kết quả chạy thật cùng bộ cờ container:

| | `python:3.12-slim` | image sandbox |
|---|---|---|
| uid khi runner **quên** truyền `--user` | `0 0` (root) | `10001 10001` |
| Ghi vào `/usr/local/lib` khi **thiếu** cờ `--read-only` | ghi được | `EACCES` |
| Binary còn bit setuid | 11 (`su`, `mount`, `passwd`...) | 0 |
| `pip` / `ensurepip` | có | không |
| Gói bên thứ ba cài sẵn | `['pip']` | `[]` |
| `hash('devpath')` hai lần chạy | hai giá trị khác nhau | như nhau |
| Output đã in trước khi tiến trình chết không flush | **mất sạch** | còn nguyên |

Hai dòng cuối là lỗi chấm bài chứ không phải lỗi bảo mật, và đó là lý do chúng nằm trong cùng một bảng:

- Hash ngẫu nhiên theo tiến trình khiến một bài in ra `set` được AC hay WA tùy vào worker nào nhận — cùng một đoạn code, hai kết quả.
- Bài bị giết vì quá thời gian chết đúng kiểu `os._exit`: nếu stdout còn đệm, học viên sẽ thấy một lần chạy trắng trơn thay vì thấy chương trình mình đã in tới đâu.

### Còn nợ ở task sau

Các ca tấn công thật — gọi network, fork bomb, đọc file ngoài mount, ghi rootfs — thuộc task *"Bộ test bảo mật"* của tuần 6 và sẽ nằm ở `attack-tests.txt`. Ở đây mới chỉ chứng minh **tính chất của image**: nó không chứa gì, chạy dưới danh nghĩa ai, và cái gì còn đứng vững khi runner thiếu một cờ.

## Runner core (09/09/2026)

`grader/runner/sandbox.py` — chạy một file với một stdin trong một container dùng một lần, rồi dọn sạch.

### Đã chứng minh được

- **Mọi giới hạn đều có thật, đo từ bên trong**: uid 10001, `rlimit_cpu` mềm/cứng, `memory.max` đúng byte, `memory.swap.max = 0` (cấm swap), `pids.max`, `cpu.max`, chỉ có `lo`, `CapEff` toàn 0, `NoNewPrivs=1`, rootfs read-only, `/tmp` ghi được, và thư mục mount chỉ có đúng `main.py`.
- **Hai lớp timeout bắt hai loại bài khác nhau** — vòng lặp vô hạn bị giới hạn CPU trong container dừng ở 2.31s (exit 152 = SIGXCPU); bài `sleep(3600)` không tốn CPU nên giới hạn CPU vĩnh viễn không bắn, đồng hồ tường ngoài container dừng nó ở 6.14s. Một lớp là không đủ, và đây là số đo chứ không phải lập luận.
- **Output đã in trước khi bị giết vẫn về tới nơi** (`'dang cho\n'`).
- Không rò container nào, kể cả những cái phải giết.

### Phát hiện đáng viết vào báo cáo: PID 1 nuốt tín hiệu

Nhân Linux không áp dụng hành vi mặc định của tín hiệu cho PID 1 — tín hiệu không có handler thì bị **bỏ qua**. Bài nộp chạy làm PID 1 nên SIGXCPU biến mất, giới hạn CPU mềm trở thành trang trí, và mọi bài quá giờ đều chết muộn một giây bởi SIGKILL của giới hạn cứng, với mã thoát không phân biệt được với bài crash.

| Cùng vòng lặp vô hạn, cùng `--ulimit cpu=1:2` | PID của bài nộp | Kết thúc |
|---|---|---|
| không `--init` | 1 | exit 137 sau 2.72s (giới hạn **cứng**) |
| có `--init` | 7 | exit 152 sau 1.88s (giới hạn **mềm**, đúng hạn) |

`--init` vì thế là điều kiện để lớp timeout bên trong tồn tại, không phải tiện ích. Có test riêng chặn hồi quy.

### Lỗi bắt được trong lúc làm

`Path.write_text` trên Windows đổi mọi `\n` thành `\r\n`, nên **input của test case bị thêm carriage return vào cuối mỗi dòng** trước khi tới bài nộp — một bài đúng sẽ bị chấm sai vì một ký tự không ai nhìn thấy. Ghi bằng `write_bytes` mới là đúng: thứ được nộp là thứ được chạy.

## So sánh output (10/09/2026)

`grader/runner/compare.py` — chính sách "thế nào là đúng", tách hẳn khỏi container: hàm thuần, không Docker, 18 test chạy trong 0.02 giây.

### Chính sách một dòng

Tha thứ cho thứ trình soạn thảo làm, chấm thứ chương trình quyết định.

| Bỏ qua (lỗi của trình soạn thảo / `print`) | Vẫn tính là sai (quyết định của chương trình) |
|---|---|
| CRLF của Windows, ở cả hai phía | Thụt đầu dòng |
| Space/tab cuối dòng | Khoảng trắng giữa dòng |
| Dòng trống ở cuối output (kể cả không có newline cuối) | Dòng trống ở giữa, thứ tự dòng, hoa/thường |

### Đã chứng minh được

- **8/14 ca đối chứng là bài làm đúng bị so sánh byte chấm sai** — và không có chiều ngược lại: không ca nào bài sai được chuẩn hóa thành đúng. Đây là con số cho chương 4, thay cho lập luận suông rằng "cần trim whitespace".
- **`str.splitlines()` là bẫy**: nó cắt dòng trên 11 ký tự chứ không phải 1, nên `ab` và `a
b` sẽ bằng nhau — một bài in ra ký tự điều khiển được chấm như đã xuống dòng. Chuẩn hóa vì thế chỉ tách trên LF sau khi quy CRLF/CR về LF. Có test tham số hóa chặn hồi quy trên 4 ký tự.
- **Output bị cắt không bao giờ là AC**: quá trần 1 MB thì thứ giữ được chỉ là đoạn đầu, và một đoạn đầu trùng đáp án không nói gì về phần còn lại. Thiếu luật này thì chính cái trần bảo vệ bộ nhớ worker lại thành lỗ hổng chấm điểm — in đúng đáp án rồi in thêm 500 MB rác vẫn AC.
- Chuẩn hóa **idempotent**, nên tầng verdict phía trên được phép lưu output đã chuẩn hóa và so lại về sau mà đáp án không trôi.

### Việc phụ đã làm cùng

Fixture Docker trong `grader/tests/conftest.py` từ `autouse` chuyển thành **xin mới có** (`pytestmark = pytest.mark.usefixtures("sandbox_images")` ở hai module chạy container). Trước đó mọi test đều phải chờ build image, và trên máy không bật Docker thì cả bộ test chính sách chấm điểm — thứ không cần Docker chút nào — bị skip im lặng.
