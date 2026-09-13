# Bằng chứng Phase 3 — Code Grading ⭐

## Gate cuối phase yêu cầu gì, và nó nằm ở tệp nào

Bảng này để Phase 7 không phải đi tìm, và để soát gate bằng mắt thay vì bằng trí nhớ.

| Gate đòi | Tệp | Con số đáng trích |
|---|---|---|
| Bảng benchmark | `benchmark.md` (script `backend/scripts/bench_grading.py`) | 10 bài nộp đồng thời, 4 cấu hình slot; mặc định 2 slot: 9,55 s nộp → verdict, trong đó 6,40 s là chờ hàng đợi |
| Output test tấn công sandbox | `attack-tests.txt` | 7 ca tấn công, 43 lần bị chặn, **0 ca thoát** — trên cả máy dev lẫn runner CI |
| Log demo đủ 7 verdict | `verdicts.txt` | 10 bài nộp thật, 10/10 khớp verdict mong đợi, đủ AC/WA/TLE/MLE/RE/CE/SE |
| Screenshot trang nộp bài lúc chấm realtime | `per-test-realtime-dang-cham.png`, `per-test-realtime-test-sai.png`, `demo-gate-2-dang-cham.png`, `demo-gate-3-wa-realtime.png`, `submission-page-grading.png` | khung "Đang chấm test 3/8" và khung ba test ẩn đã đỏ trong khi test 8 còn chạy |
| *(ngoài gate, thu thêm)* Demo đủ đường WA → AC | `demo-gate-wa-to-ac.txt` + 6 ảnh `demo-gate-*` | test ẩn đỏ ở 2 294 ms, verdict tổng ở 4 406 ms |
| *(ngoài gate, thu thêm)* CI xanh trên máy khác | `ci-xanh.txt` | 5 job xanh; 2 lỗi chỉ CI mới bắt được |

Sơ đồ kiến trúc grading **không** vẽ ở đây — theo kế hoạch, mọi hình vẽ dồn về Phase 7.

## Image sandbox Python (08/09/2026)

Image mà mã nguồn của người lạ sẽ chạy trong đó: `grader/images/python/Dockerfile`, tag `devpath-sandbox-python:v1`.

| Tệp | Nội dung | Dùng cho chương |
|---|---|---|
| `sandbox-image.txt` | Cấu hình image đã build; **bảng đối chứng image thường ↔ image sandbox** trên 9 phép thử; kết quả ruff + 12 test | 4 — Xây dựng hệ thống, và 6 — Bảo mật |
| `runner-core.txt` | Giới hạn đọc từ **bên trong** container; hai lớp timeout đo bằng số thật; **phát hiện PID 1 nuốt tín hiệu**; OOM / crash / cắt output / SE; kiểm tra rò container; chi phí một lần chấm | 4 — Xây dựng hệ thống, và 6 — Bảo mật |
| `attack-tests.txt` | **7 ca tấn công thật, 43 lần bị chặn, 0 ca thoát**; báo cáo do chính chương trình tấn công in ra từ bên trong container; 4 lớp phòng thủ độc lập | 6 — Bảo mật (chương chính) |
| `verdicts.txt` | **Log demo đủ 7 verdict** sinh từ 10 bài nộp thật; thứ tự ưu tiên; thông báo lỗi cú pháp và lỗi hệ thống nguyên văn; kết quả ruff + 30 test | 4 — Xây dựng hệ thống |
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

## Bộ verdict (10/09/2026)

`grader/runner/verdict.py` — nơi hai nửa gặp nhau: `sandbox` nói tiến trình kết thúc thế nào và từ chối phán xét, `compare` nói output có đúng không và không biết gì về tiến trình.

`verdicts.txt` là **log demo đủ 7 verdict** mà gate cuối phase yêu cầu: 10 bài nộp thật, 10/10 khớp verdict mong đợi, không letter nào còn thiếu.

### Thứ tự ưu tiên — chỗ dễ sai nhất

Ba luật, xếp theo đúng thứ tự này, mỗi luật bảo vệ học viên khỏi một câu trả lời sai về chính chương trình họ viết:

1. **Lỗi phía mình không bao giờ tính vào học viên.** SE đè mọi letter khác, cả trong một case lẫn trên cả bài nộp — kể cả khi output tình cờ khớp.
2. **Bài bị giới hạn giết không phải là WA.** Nó chưa chạy xong, nên thứ nó in ra chưa từng là câu trả lời. So output trước sẽ báo "sai đáp án" cho một bài đang in đúng thì bị cắt ngang, và chỉ học viên sai chỗ: lỗi ở độ phức tạp chứ không ở logic.
3. **Bài chết giữa chừng không đậu, dù đã in đúng.** Fixture `right_answer_then_crash.py` in y hệt đáp án rồi mới chết — so sánh output đơn thuần sẽ chấm AC.

Verdict của cả bài lấy theo **case hỏng đầu tiên**, không phải case "nặng nhất": test case do giảng viên xếp thứ tự, dễ trước, nên "case 3 quá giờ" là câu học viên hành động được.

### Đã chứng minh được

- **Cả 7 letter đều đã tận mắt thấy hệ thống sinh ra**, mỗi cái từ một fixture riêng trong `grader/tests/fixtures/`. Hai letter có hai đường sinh khác nhau: TLE từ giới hạn CPU *bên trong* (`burn_cpu.py`, 2.23s) và từ đồng hồ tường *bên ngoài* (`sleep_forever.py`, 6.11s).
- **CE chặn ở pha compile, không case nào chạy**: nộp bài sai cú pháp kèm 5 test case → 0 container chạy bài, tổng 0.64s. Python không có bước biên dịch riêng, nên pha này là một lần `compile()` trong đúng sandbox đó; thiếu nó thì lỗi cú pháp sẽ về dưới dạng RE trên *từng* test case, mỗi case tốn một container.
- **Thông báo lỗi nói về tệp của học viên, không nói về hạ tầng của mình**: `File "main.py", line 3` chứ không phải `/sandbox/main.py`, ở cả CE lẫn traceback lúc chạy.
- **Mỗi test case một container riêng**, nên tiến trình sót, tệp ghi vào `/tmp` hay interpreter đã "nóng máy" không thể chạy từ case này sang case kia — nếu không, verdict sẽ phụ thuộc vào thứ tự case.
- Chạy **hết mọi case**, không dừng ở case hỏng đầu tiên: học viên cần biết "đúng 2/3" chứ không phải "trượt", và điểm thành phần cần con số đó.

### Lỗi bắt được trong lúc làm

Traceback lúc chạy ghi `File "/sandbox/main.py"` — đường dẫn nội bộ của hệ thống dán vào thông báo lỗi của học viên, trong khi pha compile đã ghi đúng `main.py`. Đặt `--workdir` vào chỗ mount **không đủ**: từ Python 3.11 đường dẫn script luôn được tuyệt đối hóa. Phải cắt tiền tố ở tầng trình bày — và **chỉ trên stderr**: stdout là thứ đem đi chấm, sửa nó thì verdict thôi không còn nói về việc chương trình đã làm gì.

## Bộ test tấn công sandbox (10/09/2026)

`grader/tests/test_sandbox_attacks.py` + 7 fixture `attack_*.py`. Mỗi ca tấn công **tự kết luận từ bên trong container**: `docker inspect` chỉ nói mình đã *yêu cầu* gì, còn các file này nói kernel thực sự *cho phép* gì.

### Kết quả

| Ca tấn công | Chặn bằng | Thoát được? | Số lần bị chặn |
|---|---|---|---|
| Gọi ra ngoài mạng (4 đích TCP, DNS, raw socket) | `--network none`, `--cap-drop ALL` | không | 6 |
| Đọc file ngoài chỗ mount (17 đường dẫn) | không bind mount gì khác + uid 10001 + Docker che `/proc` | không | 17 |
| Ghi vào rootfs (7 đích) | `--read-only`, mount code read-only | không | 7 |
| Fork bomb | `--pids-limit 64` | không | 2 |
| Leo thang đặc quyền (9 lối) | `--cap-drop ALL`, `no-new-privileges`, `USER 10001` | không | 9 |
| Làm đầy ổ đĩa máy chấm | `--tmpfs /tmp size=64m` | không | 2 |
| Tự giết container của chính mình | PID namespace riêng | không (chỉ hại chính nó) | — |

**Tổng: 43 lần một bức tường nói không, 0 ca thoát.**

### Vài con số đáng trích vào chương 6

- Mạng trả về **`ENETUNREACH`** chứ không phải timeout — kernel *không có tuyến* để đi, đúng nghĩa `--network none`. Timeout sẽ ám chỉ có một tường lửa ở đâu đó, mà tường lửa thì cấu hình sai được. Interface duy nhất nhìn thấy: `['lo']`.
- **`/var/run/docker.sock` không tồn tại.** Đây là ca quan trọng nhất cả bộ: đọc được socket của daemon thì không cần thoát sandbox nữa, chỉ cần xin daemon một container không giới hạn.
- Fork bomb dừng ở **62 tiến trình con** (giới hạn 64, trừ init và tiến trình cha), lỗi `EAGAIN`. Máy chạy test không hề hấn gì.
- Ghi `/tmp` dừng đúng ở **64 MB**, `ENOSPC`.
- `/etc/shadow` có tồn tại nhưng **đọc bị từ chối** — bằng chứng trực tiếp rằng bài nộp không chạy bằng root.
- Kernel tự trả lời: `Uid: 10001`, `CapEff/CapPrm/CapBnd: 0000000000000000`, `NoNewPrivs: 1`.

### Lớp phòng thủ thứ ba và thứ tư (không do mình cấu hình)

Bộ test lộ ra hai lớp không nằm trong Dockerfile lẫn cờ của runner:

- **Docker che `/proc`**: `/proc/kcore` mở được nhưng rỗng — nó bị bind mount đè bằng `/dev/null`, chứng minh bằng `st_rdev` trùng khít `1,3` của `/dev/null`. **Nhưng lớp này phụ thuộc máy chủ, và chỉ CI mới cho thấy điều đó** (13/09): trên runner của GitHub, `/proc/kcore` *không* bị che — file vẫn nằm đó và quyền `0400` gặp user không đặc quyền nên trả `PermissionError`. Cùng một bài tấn công, hai lớp khác nhau chặn, không lớp nào do mình cấu hình. Kết luận đáng viết vào báo cáo không phải "Docker che `/proc`" mà là: **đọc bộ nhớ kernel bị từ chối ở mọi máy đã thử, và có ít nhất hai cơ chế độc lập cùng làm việc đó** — cái thứ nhất chặn được cả root, cái thứ hai chặn được vì mình đã bỏ root. Test vì vậy khẳng định sự từ chối chứ không khẳng định cơ chế (`grader/tests/test_sandbox_attacks.py`).
- **Seccomp bật sẵn**: `/proc/self/status` báo `Seccomp: 2` (chế độ lọc), tức profile mặc định của Docker đang chặn hàng chục syscall trước khi capability kịp có ý kiến.

### Hai lần fixture báo động giả — và vì sao vẫn giữ lại chuyện đó

Lần chạy đầu, hai ca báo `ESCAPED`. Cả hai đều là **fixture kết luận sai**, không phải tường thủng, và cách phân biệt mới là điều đáng ghi vào báo cáo:

1. `/proc/kcore` mở được → tưởng đọc được bộ nhớ kernel. Thực tế đọc ra 0 byte vì đã bị che bằng `/dev/null`. Bài học: *mở được* không đồng nghĩa với *đọc được*; phải kiểm tra nội dung, và ở đây là kiểm tra cả số hiệu thiết bị.
2. `os.kill(1, 9)` **trả về thành công** → tưởng giết được init. Thực tế PID 1 (`docker-init`) vẫn sống, trạng thái `S`: kernel bảo vệ init của một PID namespace khỏi tín hiệu do chính con cháu nó gửi. Bài học: *syscall được phép gọi* không đồng nghĩa với *syscall có tác dụng*; phải đo hậu quả chứ không đọc mã trả về.

### Hạn chế đã biết, nói thẳng

Bài nộp **giết được container của chính nó** bằng `SIGTERM` gửi tới PID 1 (`docker-init` có handler cho tín hiệu này). Không chặn được, và cũng không cần chặn: tín hiệu không đi ra khỏi PID namespace nên không bài nộp nào khác bị ảnh hưởng, container thoát mã 143 ≠ 0 nên verdict là RE. Học viên chỉ có thể vứt bỏ chính bài của mình. Có fixture và test riêng cho việc này thay vì giấu đi.

## Trình soạn bài tập code (11/09/2026)

`instructor-code-exercise.png` — ảnh chụp thật, không dựng: khóa học tạo mới qua UI, bài học `code_exercise`, đề bài, code mở đầu, hai giới hạn tài nguyên và hai test case (một mẫu, một ẩn) đều đi qua API thật vào Postgres thật.

### Đường đi đã đi hết bằng chuột

| Bước | Kết quả quan sát được |
|---|---|
| Chọn loại bài học “Bài tập code” | Bài học tạo được — trước hôm nay loại này backend nhận nhưng frontend không cho chọn |
| Mở bài học chưa có bài tập | `GET /lessons/{id}/code-exercise` trả 404, UI hiện trạng thái rỗng thay vì báo lỗi |
| Nhập giới hạn thời gian 99999 ms | Chặn tại chỗ: “Giới hạn thời gian phải trong khoảng 100–10000 ms”, không phát request |
| Tạo bài tập | 201, form đổi sang chế độ sửa, phần test case hiện ra |
| Chưa có test case nào | Cảnh báo đỏ: hệ thống sẽ từ chối nhận bài nộp |
| Thêm 1 case mẫu | Cảnh báo đổi giọng: mọi case đều hiển thị thì chỉ cần in đáp án là qua |
| Thêm 1 case ẩn, trọng số 2 | Hết cảnh báo. Dòng tóm tắt: “2 test case · 1 mẫu, 1 ẩn · tổng trọng số 3” |
| Đưa case 2 lên trên | Postgres đổi `position` đúng (0 ↔ 1) — ràng buộc `uq_test_cases_position` DEFERRABLE chịu được |
| Sửa trọng số thành 0 | Chặn tại chỗ: “Trọng số là số nguyên từ 1 trở lên” |
| Sửa trọng số thành 3 | Lưu, tổng trọng số trên UI thành 4, DB khớp |

### Điều đáng nói trong báo cáo

- **Ba cảnh báo trên đều là bài tập hợp lệ với API.** Không có test case, toàn ẩn, toàn hiện — cả ba đều tạo được qua API và đều sai về mặt sư phạm. Đây là chỗ giao diện làm được việc mà ràng buộc CSDL không làm: nó khuyên, chứ không cấm.
- **Ô “Ẩn với học viên” tự về mặc định ẩn sau mỗi lần thêm**, không giữ lựa chọn trước đó. Quên ô này một lần là đáp án nằm trên trang, nên giá trị an toàn phải là giá trị phải chủ động bỏ chọn mỗi lần.
- **Chính sách so sánh output được nói ngay dưới ô nhập đáp án**: bỏ khoảng trắng cuối dòng và dòng trống cuối, giữ khoảng trắng giữa dòng. Giảng viên biết luật trước khi viết đáp án thì không mất buổi tối đi truy một WA không có thật.
- Trang học của học viên tạm thời nói thẳng “trang nộp bài đang được xây dựng”. Nếu không sửa, bài tập code rơi vào nhánh bài đọc và hiện “Bài học này chưa có nội dung” — một câu sai, vì bài học có nội dung, chỉ là chưa có chỗ nộp (tuần 8).

## Hàng đợi chấm bài (12/09/2026)

`grading-queue.txt` — nộp bài thật qua API, worker Celery thật, sandbox Docker thật. Sáu chương trình, sáu verdict, không mock chỗ nào.

| Chương trình nộp | Verdict | Điểm | run_time_ms |
|---|---|---|---|
| Đọc hai số, in tổng | AC | 100 | 420 |
| `print(0)` | WA | 0 | 424 |
| `while True: pass` | TLE | 0 | 4288 |
| `raise ValueError` | RE | 0 | 419 |
| `def broken(:` | CE | 0 | (chưa từng chạy) |
| `[0] * 100_000_000` | MLE | 0 | 920 |

### Ba điều số liệu này nói

- **Test case ẩn có verdict, không có output.** Bài AC và bài WA đều được chấm đủ hai case; `stdout_trunc` của case mẫu có nội dung, của case ẩn là `None`. Đây là luật "test case ẩn không rời server" ở tầng ghi dữ liệu — API đã từ chối trả nó, còn đây là lớp trước đó: cột không bao giờ được điền.
- **Điểm tính theo trọng số**, không theo số case đúng.
- **CE không có `run_time_ms`** vì chương trình chưa bao giờ chạy, và thông điệp trả về là `File "main.py", line 1` — nói về file của học viên chứ không về mount của hệ thống.

### Bằng chứng có giá trị nhất trong file này là một sự cố thật

Lần chạy đầu tiên **cả 6 bài đều hỏng**. Runner tạo thư mục tạm bên trong container worker rồi bảo daemon bind-mount nó; daemon phân giải đường dẫn trên host, nơi thư mục đó không tồn tại. Lỗi chỉ lộ ra khi chạy thật — không một test đơn vị nào bắt được, vì trên máy dev runner chạy ngoài container và đường dẫn luôn đúng.

Đường xử lý thất bại chạy đúng như thiết kế, và đó là phần đáng viết vào báo cáo:

- ba lần thử, giãn 15s rồi 30s;
- **không bài nào bị gán verdict**, không dòng `submission_results` nào được ghi;
- hết lượt thì hàng nộp bài "đỗ" lại ở `status = error`, `verdict = NULL`, `message` là câu tiếng Việt cho học viên;
- câu lỗi kỹ thuật (`bind source path does not exist`) chỉ nằm trong log worker.

Bất biến "lỗi của mình không đổ lên đầu học viên" vì thế được kiểm chứng bằng một sự cố có thật chứ không bằng một test giả lập.

### Đánh đổi kiến trúc đã ghi rõ

`grading-worker` là container duy nhất cầm `/var/run/docker.sock`, vì chấm bài **chính là** khởi động container. Socket không phải hệ thống phân quyền: container cầm nó khởi động được container tùy ý trên host. Thu hẹp thiệt hại bằng cách nó không phục vụ HTTP, không publish cổng, chạy uid 10001 trên production, và **không bao giờ tự chạy code người nộp** — mọi dòng đó chạy trong container dùng một lần có `--network none`, `--read-only`, `--cap-drop ALL`. Hướng làm chặt hơn (chưa làm): proxy socket chỉ cho `create`/`start`/`wait`/`rm`.

## Rate limit nộp bài (12/09/2026)

`rate-limit.txt` — bấm "Nộp" 10 lần trong 0.1 giây trên stack thật.

```
10 lần bấm trong 0.1s -> nhận 1, từ chối 9
Số bài nộp thật sự được tạo trong CSDL: 1
```

Chín lần bị chặn **trước khi** ghi dòng nào và **trước khi** đẩy job nào. Chặn sau thì cái giá đã trả rồi và mã 429 chỉ còn là lời nói.

### Hai cửa, hai kiểu lạm dụng

| Cửa | Khóa Redis | Lệnh | Chặn được gì |
|---|---|---|---|
| Cooldown 10s mỗi (học viên, bài tập) | `rl:submit:cooldown:<user>:<bài>` | `SET NX EX` | Nút bấm hai lần, script quay vòng một bài |
| 40 bài/giờ mỗi học viên | `rl:submit:hour:<user>` | `INCR` + `EXPIRE` | Script kiên nhẫn ngồi đợi hết cooldown |

Cả hai là **lệnh đơn của Redis**, không phải đọc-rồi-ghi: API chạy nhiều tiến trình, hai request của cùng một cú double-click rơi vào hai worker, cả hai cùng đọc "chưa có gì" rồi cùng đi tiếp.

### Bốn quyết định đáng bảo vệ trước hội đồng

- **Lần bị từ chối không đẩy lùi hạn chờ.** Bấm thêm 9 lần vẫn hết hạn sau đúng 10 giây kể từ lần nộp thành công — cooldown để giãn nhịp, không để phạt người bấm nhầm.
- **`Retry-After` ở cả header lẫn thân phản hồi.** Header là thứ trình duyệt và proxy đọc sẵn; trường `retry_after` là để trang web vẽ đồng hồ đếm ngược. Một 429 không nói khi nào quay lại thì chỉ có thể trả lời bằng một request nữa.
- **Khóa theo user id, không theo IP.** Cả phòng máy của trường ngồi sau một IP NAT; chặn theo IP là chặn nhầm cả lớp vì một người. Đổi lại nó không chống được kẻ tạo hàng loạt tài khoản — việc đó thuộc về giới hạn đăng ký.
- **Redis chết thì cho qua.** Redis cũng là broker của Celery: lúc nó chết, bài nộp vừa được cho qua cũng không vào được hàng đợi và API trả 503 ngay sau đó. Từ chối ở đây là đổi "hàng đợi hở một lúc" lấy "không ai nộp được bài", để bảo vệ một hàng đợi vốn đang không chạy.

### Một lỗi chỉ có test mới thấy

Nếu tiến trình chết đúng giữa `INCR` và `EXPIRE`, khóa đếm nằm lại **không có TTL** — người đó bị chặn vĩnh viễn, và triệu chứng chỉ xuất hiện vài ngày sau, trông y như tài khoản hỏng. Bộ đếm vì thế tự vá: thấy TTL âm thì đặt lại hạn. Có test riêng cho tình huống này.

## API kết quả: test case ẩn (12/09/2026)

`hidden-tests.txt` — không đọc code rồi khẳng định. Một bài nộp **cố tình tấn công** đi qua đúng đường một bài nộp thật đi:

```python
import sys
print(sys.stdin.read())
```

Chương trình in lại đúng stdin của nó, nên trên test case ẩn **output của nó chính là input bí mật**. Nếu hệ thống lưu hoặc trả output của case ẩn ở bất kỳ đâu, bí mật lộ nguyên văn.

```
case 0 (mẫu) -> WA   stdout_trunc='1 2\n\n'     ← nhóm đối chứng
case 1 (ẩn ) -> WA   stdout_trunc=None          ← bí mật không tồn tại để mà rò
```

Sau đó **9 bề mặt API** được gọi lại và thân phản hồi thô bị tìm chuỗi bí mật: 7 lần với tư cách học viên (4 lần đọc → 200, 3 route soạn đề → 403), 2 lần với tư cách giảng viên. **Không lần nào của học viên có bí mật.**

### Dòng đáng giá nhất của bảng là dòng đối chứng

`stdout_trunc='1 2\n\n'` ở case mẫu. Không có nó, cả bảng vẫn "không rò rỉ" kể cả khi endpoint hỏng và không trả gì cả. Case mẫu chứng minh API thật sự có trả output — cái bị giữ lại là output của case **ẩn**, không phải mọi output.

Dòng cuối cùng **có** bí mật, và phải như vậy: giảng viên sở hữu bài tập đọc danh sách test case thì nhận đủ đáp án. Nếu dòng ấy ghi "không" thì phép thử đang đo nhầm thứ gì đó.

### Bốn lớp, không lớp nào là lớp duy nhất đúng

| Lớp | Cơ chế |
|---|---|
| Worker | Không ghi `stdout_trunc` cho case ẩn — cột không bao giờ được điền |
| Schema | `TestCaseSample` **không có trường** `expected_output` để dữ liệu chui qua |
| API | `result_out()` vẫn xóa lần nữa dù worker đã không ghi |
| Quyền | 4 route trả `TestCaseOut` đầy đủ không chọn model theo người gọi — chúng từ chối người gọi (403) |

Bộ test mới đi hết từng route đó với tư cách một học viên **đã ghi danh** — người duy nhất mà chỉ còn mỗi lớp kiểm tra quyền đứng chắn giữa họ và đáp án.

### Hạn chế đã biết: verdict là một oracle

Trả verdict cho từng case ẩn cho học viên một oracle nhị phân — nộp chương trình kiểu "nếu input bắt đầu bằng 'A' thì in đáp án đúng" rồi đọc AC/WA để dò dần. Đúng với mọi hệ thống chấm báo kết quả theo test case, kể cả Codeforces. Không tuyên bố đã chặn: chặn nó là bỏ luôn kết quả theo từng case, tức bỏ thứ làm việc chấm bài có ích.

Cái làm nó không đáng bỏ công là **rate limit vừa làm ở task trước**: 10 giây/lần cùng một bài và 40 bài/giờ, nên dò một input 20 ký tự cần hàng chục giờ — và mỗi bước đều để lại một dòng mang tên tài khoản trong bảng `submissions`.

### Một lỗ thật tìm thấy khi rà

`submissions.message` (lời trình biên dịch cho CE) **không bị cắt**: trần của nó là 1 MB của runner, và cột này được đọc lại trong **mọi trang** lịch sử nộp bài. Đã cắt về cùng hạn mức với output từng case, kèm test.


## Tiến độ chấm realtime: Redis pub/sub → WebSocket (12/09/2026)

`grading-progress.txt` — một bài nộp thật, và socket được mở ở **bốn thời điểm khác nhau** để lấy bốn câu trả lời khác nhau.

### Trong lúc chấm: tiến độ đến từng test case

```
   109 ms  snapshot  running   0/4  -                    verdict=None
  2828 ms  progress  running   1/4  case 0 (mẫu) -> AC   verdict=None
  3922 ms  progress  running   2/4  case 1 (mẫu) -> AC   verdict=None
  5078 ms  progress  running   3/4  case 2 (ẩn ) -> RE   verdict=None
  6906 ms  progress  running   4/4  case 3 (ẩn ) -> AC   verdict=None
  7031 ms  progress  done      4/4  -                    verdict=RE
```

Bốn mốc thời gian là bốn container khác nhau chạy xong — mỗi test case một container. Cột `type` là chỗ đáng nhìn: frame đầu đọc từ Postgres, năm frame sau do worker publish. Hai nguồn, một hình dạng dữ liệu.

### Sau khi chấm xong: tình huống pub/sub bó tay

Redis pub/sub **không có bộ nhớ** — gửi cho ai đang nghe tại đúng khoảnh khắc đó, không phát lại. Socket mở muộn đã lỡ mọi sự kiện sẽ từng tồn tại. Đó là lý do mỗi socket mở đầu bằng một snapshot đọc từ CSDL, và tại sao client vào muộn vẫn có đáp án sau **47 ms** thay vì đợi mãi mãi.

Cùng cơ chế ấy xử lý luôn ba hỏng hóc khác bằng một câu trả lời: thông điệp mất khi subscription chưa kịp thiết lập, kết nối Redis đứt giữa chừng, và worker chết để lại dòng `running`. Cứ im lặng 10 giây là đọc CSDL một lần.

### Redis tắt hẳn: tính năng còn hay mất

```
a) Socket vẫn mở được, trả lời đúng sau 1578 ms bằng snapshot
b) Polling REST: 200 — kết quả nằm ở Postgres, không nằm ở Redis
c) Nộp bài mới: 503 GRADING_UNAVAILABLE — từ chối thẳng, không nhận rồi bỏ đó
```

Không có kênh thì socket tự hạ cấp thành vòng đọc CSDL — tức là polling, chỉ khác là chạy trên WebSocket.

### Token đi trong handshake, không đi trong URL

Trình duyệt không cho đặt header `Authorization` cho WebSocket. Cách phổ biến nhất — nhét token vào query string — ghi một chứng danh còn sống vào log nginx. Ở đây client chào `["bearer", "<token>"]` qua `Sec-WebSocket-Protocol` và server nhận với `bearer`. Quyền xem socket là **đúng hàm** mà `GET /submissions/{id}` dùng: học viên khác nhận 4404, chưa đăng nhập nhận 4401.

### Một lỗi chỉ chạy thật mới tìm ra

Lần chạy đầu không có frame `progress` nào — `done` đến ở đúng mốc 10 giây, tức nhịp heartbeat. `_shared_publisher()` trả về client Redis trần thay vì bọc trong `RedisEventPublisher`, nên sáu lần publish đều ném `TypeError` và đều bị nuốt.

Toàn bộ unit test vẫn xanh: chúng kiểm adapter trực tiếp, còn fixture thì thay luôn `get_publisher` — không test nào chạm đoạn dây nối giữa hai thứ đó. Đã thêm test đúng vào chỗ ấy. Đáng chú ý là **học viên vẫn nhận kết quả đúng, chỉ chậm 10 giây** — thiết kế tự chứng minh, nhưng cũng cho thấy kênh hỏng im lặng rất khó thấy, nên mỗi lần publish thất bại đều ghi log WARNING, và chính dòng log ấy chỉ ra lỗi.

### Bí mật của case ẩn không đi qua kênh realtime

8 frame nhận được, quét tìm input và đáp án của case ẩn: **0**. `GradingEvent` không có trường nào chứa output, input hay message — con số 0 là tính chất của kiểu dữ liệu, không phải kết quả của một câu lệnh lọc.


## Trang nộp bài: Monaco, chạy thử, nộp chính thức, lịch sử (12/09/2026)

`submission-page.txt` · `submission-page-grading.png` · `submission-page-accepted.png`

### Hai nút, hai nghĩa khác nhau

| | Chấm với | Vào lịch sử | Route |
|---|---|---|---|
| **Chạy thử** | chỉ test mẫu | không | `POST /code-exercises/{id}/trial-runs` |
| **Nộp bài** | mọi test | có | `POST /code-exercises/{id}/submissions` |

Cùng hàng đợi, cùng worker, cùng sandbox, cùng kênh tiến độ realtime. Một lần chạy thử là một hàng `submissions` với `is_trial = true` — bảng riêng sẽ phải nhân đôi hàng đợi, worker, kênh tiến độ và mọi luật về ai được đọc bài nộp nào.

### Bài học sư phạm nằm gọn trong một lần chạy

Cùng một đoạn code, chạy trên stack thật:

```
chạy thử  -> AC  100/100   chấm 2/2 case (mẫu)
nộp bài   -> RE   75/100   chấm 4/4 case  ← case ẩn số 2 làm int() ném lỗi
```

Qua hết test mẫu **không** có nghĩa là qua bài. Đó chính là lý do test ẩn tồn tại, và trang nộp bài nói điều đó bằng cách cho học viên tự thấy.

### Vì sao chạy thử không thể rò rỉ

Worker nạp test case bằng `_cases_of(..., samples_only=submission.is_trial)`. Case ẩn **không được nạp**, nên không chạy, không đo giờ, không ghi. Mạnh hơn "chạy hết rồi lọc kết quả": không tồn tại thời điểm nào mà một lần chạy thử cầm đáp án ẩn. Bằng chứng ngắn nhất là cột `so_case` trong CSDL — hàng `is_trial=t` có đúng 2 kết quả, hàng `is_trial=f` có 4.

### Monaco tự phục vụ, không qua CDN

`@monaco-editor/react` mặc định tải editor từ jsdelivr — tức trang quan trọng nhất của đồ án phụ thuộc mạng của căn phòng, đúng hôm bảo vệ. `scripts/copy-monaco.mjs` chép bản AMD vào `public/monaco`. Kiểm bằng danh sách request thật: **19 file, tất cả từ cùng origin, không một request nào ra ngoài**.

### Hai lỗi gặp khi chạy thật

1. **Lần chạy thử đầu chấm 4 case thay vì 2** — Celery không tự nạp lại code dù thư mục nguồn được mount. Triệu chứng đáng chú ý: thanh tiến độ hiện "0/2" (API mới) trong khi worker chạy 4 case (worker cũ). Hai nửa bất đồng thì tính chất "mẫu số mô tả chính lần chạy này" vỡ trước tiên.
2. **Playwright gõ vào Monaco mất ký tự** — ban đầu tưởng lỗi sản phẩm, kiểm lại bằng cách bấm từng phím riêng thì đủ cả. Giới hạn của công cụ kiểm thử với Monaco 0.56 (EditContext API), không phải lỗi trang; chú thích trong code đã được sửa lại cho đúng.


## Kết quả per-test realtime (12/09/2026)

`per-test-realtime.txt` · `per-test-realtime-dang-cham.png` · `per-test-realtime-test-sai.png`

Trước: một thanh tiến độ và dòng chữ "Đang chấm — 3/8 test case". Sau: tám dòng, mỗi test một dòng, đổi trạng thái ngay khi sự kiện của worker tới.

### Con số biện hộ cho việc này

Bảng khung hình chụp DOM 100 ms/lần trên một bài nộp sai đúng một test ẩn:

| Mốc | Điều học viên thấy |
|---:|---|
| 2 562 ms | `Test 4 Ẩn 266 ms Sai kết quả` — trong khi test 5 còn đang chạy |
| 4 572 ms | verdict tổng: `Sai kết quả · 88/100` |

**Học viên biết mình sai ở giây 2,5 chứ không phải 4,6.** Khoảng cách hai giây đó co giãn theo số test case, nên với bài 30 case nó là hàng chục giây.

### Ba chi tiết đáng viết vào chương 4

- **Tiêu đề phải bị kẹp.** Có khung mà cả 8 case đã xong nhưng worker còn đang ghi bảng điểm: `completed_cases = 8` trong khi `status` vẫn `running`. Không kẹp thì tiêu đề hiện "đang chấm test 9/8".
- **Test ẩn đi qua kênh realtime mà không mang theo gì.** Sự kiện chỉ có `position`, `is_hidden`, `verdict`, `run_time_ms` — đề bài và đáp án của case ẩn không tồn tại trong kiểu dữ liệu, nên không có gì để rò.
- **Trang không bịa.** Case nào máy chủ chưa nói gì thì nằm im ở "Chờ", không đoán màu. Có hẳn trạng thái "Đã chấm" (xong nhưng không rõ verdict) cho tình huống ảnh chụp báo nhiều case hơn số sự kiện nhận được.

Logic tách khỏi JSX, nằm trong `frontend/lib/grading/run-progress.ts`: `mergeCaseReport` xếp mỗi sự kiện vào đúng ô theo `completed_cases - 1` (nhận trùng một sự kiện không sinh dòng thừa; job bị retry thì những dòng phía sau bị bỏ thay vì giữ verdict của lần chạy đã chết), còn `caseSlots` quyết định trạng thái từng dòng bằng bộ đếm.

### Hạn chế đã biết, và vì sao chấp nhận

Chặn hẳn WebSocket rồi nộp lại: danh sách **không nhích** suốt 18 giây, tới lúc xong mới hiện đủ. Giới hạn này nằm ở backend chứ không ở giao diện — worker ghi toàn bộ `submission_results` trong **một** commit lúc chấm xong, nên khi polling thì CSDL thật sự không biết case nào đã chạy.

Đã cân nhắc và không làm: commit sau mỗi case. Cái giá là 8 lần ghi + 8 lần commit mỗi bài nộp thay vì 1, đổi lấy trải nghiệm của nhánh dự phòng — nhánh chỉ chạy khi Redis hoặc WebSocket hỏng. Ghi lại ở đây để Phase 6 quyết định lại nếu tunnel/proxy chặn WebSocket thường xuyên hơn dự kiến.

## Benchmark: thời gian chấm và throughput (13/09/2026)

`benchmark.md` · script `backend/scripts/bench_grading.py` (chạy lại được: `docker compose exec backend python -m scripts.bench_grading --submissions 10 --cases 5`)

Mười học viên **khác nhau** nộp cùng lúc — mười bài từ một tài khoản không phải phép đo tải mà là phép đo rate limit. Mốc thời gian lấy từ chính kênh Redis pub/sub mà trang web đang nghe, nên **thứ được đo đúng là thứ học viên đang nhìn**, không phải một đồng hồ riêng cắm thêm vào worker.

| Slot | Cả đợt | Throughput | Nộp → verdict (TB) | Chờ hàng đợi | Chấm | ms/case |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 26,9 s | 22,3 bài/phút | 14,90 s | 12,25 s | 2,65 s | 530 |
| **2** *(mặc định)* | **16,1 s** | **37,2 bài/phút** | **9,55 s** | **6,40 s** | **3,15 s** | **630** |
| 4 | 12,4 s | 48,4 bài/phút | 7,22 s | 3,18 s | 4,04 s | 808 |
| 8 | 9,7 s | 62,2 bài/phút | 7,21 s | 1,35 s | 5,86 s | 1172 |

Một học viên nộp một mình, hàng đợi rỗng: **2,6 – 2,8 giây** cho cả 5 case, ở mọi cấu hình.

### Kết quả đáng giá nhất không phải throughput mà là công bằng

`run_time_ms` — con số sandbox đo từ bên trong container — **tăng gấp đôi khi chạy 8 bài song song** (248 ms → 516 ms cho cùng chương trình `a + b`). Giới hạn thời gian là 2000 ms, nên một bài đúng nhưng sát biên có thể ăn TLE chỉ vì nó xui, nộp trúng lúc chín người khác cũng nộp.

Đó là lý do chọn `GRADING_CONCURRENCY=2` chứ không chọn cấu hình nhanh nhất: ở 2 slot số đo chỉ lệch 21% so với máy rảnh, ở 8 slot là 108%. **Tăng slot trên máy cũ là đổi độ chính xác của việc chấm lấy tốc độ** — thứ một hệ thống chấm điểm không được phép đổi. Muốn nhanh hơn thì tăng vCPU trước, theo tỉ lệ 1 slot cho mỗi vCPU dôi ra.

### Hai điều nữa cho chương 5

- **Hàng đợi, không phải sandbox, là thứ học viên chờ.** Ở cấu hình mặc định, 6,40 trong 9,55 giây là nằm chờ tới lượt. Đây chính là lý do trang phải nói thành thật "đang chờ tới lượt chấm" thay vì hiện thanh tiến độ giả.
- **Dựng container tốn ngang chạy chương trình** (282 ms dựng / 248 ms chạy). Đổi lại là cô lập thật: mỗi case một container dùng một lần, không trạng thái nào sống sót giữa hai case. Nếu sau này cần nhanh hơn thì đây là chỗ tối ưu, không phải chỗ nào khác.

Phép đo chạy trên máy dev 8 CPU, không phải VPS 2 vCPU — bảng này dùng để chọn *hình dạng* cấu hình (bao nhiêu slot cho mỗi vCPU), không phải để hứa con số tuyệt đối. Đo lại ở Phase 6.

## Buffer UX: hai lỗ được vá trước khi đóng phase (13/09/2026)

`buffer-ux.txt` · `buffer-ux-ac-hoan-thanh.png` · `buffer-ux-404.png`

Task này không nói vá cái gì, nên việc đầu tiên là đi soát: mục "CÒN THIẾU" trong các file bằng chứng đã có, quy ước trong skill `nextjs-feature`, và đường đi của bài demo cuối phase. Ra hai lỗ thật.

### 1. Giải đúng bài tập mà bài học vẫn chưa xong

Học viên ăn AC 100/100 rồi vẫn phải tự bấm "Đánh dấu hoàn thành" — tức bắt người ta khai báo với hệ thống đúng cái điều hệ thống vừa tự tay chấm. Trên đường demo của phase, lỗ này lộ ngay: chấm xong AC mà tiêu đề vẫn "0/1 bài · 0%".

Worker giờ ghi `lesson_progress.completed_at` **trong cùng transaction** với verdict. Cùng transaction là có chủ ý: một dấu hoàn thành ghi tách ra có thể sống sót qua một rollback của chính cái verdict biện minh cho nó, và một bài học được tick mà không có hàng AC nào đứng sau là loại lỗi không ai tìm ra.

Bốn ranh giới được test khẳng định, mỗi cái là một câu trả lời cho "tick khi nào":

| Tình huống | Kết quả |
|---|---|
| AC, bài nộp thật, có ghi danh | tick |
| WA | không tick |
| Chạy thử AC (chỉ test mẫu) | **không tick** — qua test mẫu không phải là giải được bài |
| Không có ghi danh (giảng viên thử bài của chính mình) | chấm bình thường, không sinh tiến độ nào |
| Nộp AC lần thứ hai | giữ nguyên mốc hoàn thành lần đầu |

### 2. Bốn trang lỗi/chờ còn thiếu, trong đó có trang quan trọng nhất

Quy ước dự án đòi mỗi route segment có `loading.tsx` và `error.tsx`; phòng học `(learn)` thiếu **cả hai**, và `app/` gốc không có lưới cuối nào — nghĩa là một render ném lỗi sẽ rơi vào trang lỗi mặc định của Next: tiếng Anh, trên đó không có gì ngoài chữ "error".

Thêm bốn file, chọn theo chỗ thật sự có ích chứ không rải cho đủ bộ: `app/error.tsx`, `app/not-found.tsx`, `(learn)/error.tsx` (nói rõ tiến độ và bài nộp vẫn nằm trên máy chủ), và `loading.tsx` cho hai trang khóa học là Server Component có await thật. **Không** thêm cho `ho-so` và `khoa-hoc-cua-toi`: hai trang đó là Client Component, vẽ ra tức thì và đã tự có skeleton — thêm file chỉ là thêm nhiễu.

## Demo gate: tạo bài tập → nộp sai → WA realtime → sửa → AC (13/09/2026)

`demo-gate-wa-to-ac.txt` · `demo-gate-1-tao-bai-tap.png` (trình soạn bài tập, 8 test case) · `demo-gate-2-dang-cham.png` (đang chấm test 3/8) · `demo-gate-3-wa-realtime.png` (ba test ẩn đã đỏ, test 8 còn chạy) · `demo-gate-4-wa-ket-qua.png` (WA 62/100) · `demo-gate-5-ac.png` (AC 100/100) · `demo-gate-6-lich-su.png` (lịch sử sai → đúng)

Mục đầu tiên của gate cuối Phase 3, đi trọn một lượt trên giao diện thật: giảng viên tạo khóa → chương → bài học kiểu bài tập code → đề bài + 8 test case (2 mẫu, 6 ẩn); học viên đăng ký tài khoản mới → ghi danh → nộp bài sai → sửa → AC.

### Bài tập chọn theo một lỗi có thật của người mới

Đề "số lớn nhất trong dãy", lời giải sai khởi tạo `best = 0`. Cái bẫy nằm ở chỗ nó **qua sạch cả hai test mẫu** rồi mới gãy ở ba test ẩn toàn số âm — tức là bấm "Chạy thử" thấy xanh hết vẫn có thể trượt. Test ẩn sinh ra đúng để bắt tình huống đó, và demo cho học viên tự thấy điều ấy thay vì giải thích bằng lời.

### Con số biện hộ cho việc làm realtime per-test

| Mốc | Bài nộp sai |
|---|---|
| API nhận bài → worker chạy test đầu | 202 ms |
| Test ẩn số 3 chuyển đỏ | 2 294 ms |
| Verdict tổng (WA 62/100) | 4 406 ms |

**Học viên biết mình sai sớm hơn verdict tổng 2,1 giây.** Với bài 8 case chạy 4 giây thì đó là một nửa thời gian chờ; với bài 30 case thì là hàng chục giây.

### Ba thứ được kiểm ngoài giao diện

1. **Test ẩn không rò qua API.** Gọi thẳng `GET /submissions/{id}` bằng token học viên trên chính bài nộp sai: case ẩn chỉ mang vị trí, cờ ẩn, verdict, thời gian chạy — không stdin, không đáp án, không cả stdout đã in ra, kể cả ở case sai.
2. **Chạy thử không vào lịch sử.** Bản chạy thử nằm ở `submissions.is_trial = true`, danh sách lịch sử lọc nó ra.
3. **AC tự đóng bài học.** Không bấm "Đánh dấu hoàn thành" lần nào; `lesson_progress.completed_at` được ghi 4 giây sau verdict AC, tiến độ khóa nhảy 0/1 → 1/1.

### Hai điều nói thẳng trong file bằng chứng

- Ba bài nộp chậm trong lịch sử là **cùng lời giải sai cộng vòng lặp 6 triệu bước**, dựng riêng để chụp được ảnh lúc đang chấm — ở tốc độ thật cả lần chấm chỉ 4,4 giây, ngắn hơn một lượt chụp màn hình. Số trên hai ảnh đó là của bản cố tình chậm, không phải tốc độ hệ thống.
- Khóa demo là khóa mới tạo, không phải khóa seed: bốn khóa seed đang thuộc hai tài khoản `@devpath.local` không đăng nhập được nữa (email-validator từ chối domain `.local`). Lệch dữ liệu của máy dev, cần dọn trước buổi bảo vệ.


## CI xanh: test verdict + test bảo mật chạy trên máy không phải máy mình (13/09/2026)

`ci-xanh.txt` · [PR #25](https://github.com/acquy66666/DevPath/pull/25) · [lần chạy xanh](https://github.com/acquy66666/DevPath/actions/runs/34753790965)

Mục thứ hai của gate. Năm job xanh: backend `610 passed, 2 skipped`, grader `89 passed`, frontend lint + build, migrations trên CSDL trống, và cấu hình deploy. 89 test của grader gồm 18 test luật verdict, 15 test end-to-end đủ bảy chữ, và 7 test tấn công sandbox.

### Giá trị của mục gate này nằm ở hai lỗi nó bắt được

Trước khi mở PR, cả ba bộ đều xanh trên máy dev. CI vẫn đỏ ngay lần đầu, ở hai chỗ mà **không lần chạy local nào có thể phát hiện**:

| Lỗi | Vì sao máy dev không thấy |
|---|---|
| Test seed hỏng vì thiếu danh mục | `seed_courses()` tra cứu danh mục chứ không tạo; máy đã seed một lần thì hàng đó có sẵn. CSDL của CI trống |
| Test bảo mật đỏ ở `/proc/kcore` | Máy dev được Docker che bằng `/dev/null`; runner GitHub không che, quyền `0400` từ chối thay |

Lỗi thứ nhất sửa ở gốc: test tự dựng tiền đề bằng `seed_categories()` như `main()` vẫn làm. Tái hiện trước khi sửa bằng một CSDL rỗng dựng ngay tại máy, để không phải đoán.

Lỗi thứ hai **không phải lỗ hổng**: `assert "ESCAPED" not in report` qua ở cả hai máy ngay từ lần đỏ đầu tiên. Thứ sai là kỳ vọng của test — nó khẳng định *cơ chế* thay vì *tính chất*. Xem mục "Lớp phòng thủ thứ ba và thứ tư" ở trên, đã được sửa lại theo phát hiện này.

### Câu đáng mang ra hội đồng

Một bộ test xanh trên máy của mình chỉ chứng minh được điều nó tự dựng lấy tiền đề, trên đúng cấu hình máy đó. Phần đi mượn — hàng dữ liệu đã có sẵn, lớp phòng thủ mà máy chủ tình cờ cung cấp — là phần chưa được kiểm, và nó chỉ lộ ra khi có một máy thứ hai chạy lại.
