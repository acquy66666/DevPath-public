# Load test (k6)

Đo **stack production** (`docker-compose.prod.yml`) bằng [k6](https://k6.io), chạy trong container trên chính mạng compose của stack, gọi vào nginx. Kết quả và cách đọc: [`docs/report/assets/phase-6/load-test.md`](../../docs/report/assets/phase-6/load-test.md).

| Tệp | Đo gì |
|---|---|
| `catalogue.js` | `VUS` người duyệt danh sách khóa học: trang `/khoa-hoc`, tìm kiếm, trang 2 (Next render phía server) + API `/api/v1/courses` qua nginx, nghỉ `THINK` giây giữa hai trang |
| `submissions.js` | Một lớp nộp **cùng lúc** một bài tập code, mỗi người chờ verdict trên **đúng WebSocket** trang nộp bài mở; `BROWSE_VUS > 0` thêm người duyệt danh sách trong lúc chấm |
| `run.sh` | Chạy cả hai: dựng lớp → k6 → dọn, kể cả khi lỗi giữa chừng |

## Chạy

Stack production phải đang chạy và đã seed (`scripts/deploy.sh --seed`), image sandbox đã build.

```bash
cd infra
./loadtest/run.sh catalogue      # 10, 25, 50, 100 người duyệt, mỗi mức 60 s
./loadtest/run.sh class          # lớp 20 người, rồi lớp 20 người + 25 người duyệt
```

Biến môi trường (mặc định là của VPS): `COMPOSE_PROJECT_NAME` (`devpath`), `ENV_FILE` (`.env.prod`), `OUT` (thư mục kết quả, mặc định `docs/report/assets/phase-6/load-test`), `LEVELS`, `CLASS`, `BROWSE_VUS`. Mỗi lượt k6 ghi một tệp JSON tóm tắt vào `OUT`; trong đó chỉ có số, không có token hay email.

## Dữ liệu của lớp học

`python -m scripts.stage_load_test --students 21` (trong container backend) dựng một khóa miễn phí đã xuất bản với một bài đọc + một bài tập 5 test case, rồi in JSON gồm **access token** của từng học viên. Ghi thẳng bảng chứ không qua API, vì 21 lần đăng ký từ một địa chỉ vượt giới hạn đăng ký (50/giờ/IP) từ lượt chạy thứ ba, mà đăng nhập không phải thứ đang đo. Token ký bằng đúng khóa của API, sống 2 giờ; tệp JSON nằm trong thư mục tạm của `run.sh` và bị xóa khi script thoát.

Mọi tài khoản dùng tên miền của bộ E2E (`@e2e.devpath.example`), nên `python -m scripts.purge_e2e` dọn sạch cả lớp — `run.sh` gọi nó sau mỗi lượt. Bài đọc đứng trước bài tập có chủ đích: khóa chỉ có một bài thì mỗi bài AC sẽ hoàn thành khóa và xếp hàng vẽ 20 PDF chứng chỉ, không phải việc của một lớp đang làm bài tập.

## Trước khi tin con số: hiệu chuẩn

Trên Docker Desktop, daemon có những quãng chậm hẳn đi — ngay sau khi build image, và vài phút sau mỗi đợt tạo/xóa vài trăm container. Lượt đo đầu tiên của Phase 6 rơi vào một quãng như thế và cho số **chậm gấp năm** lần thật. Đo một mốc trước và sau mỗi lượt:

```bash
docker run --rm devpath-sandbox-python:v1 python -c "print(1)"   # lặp 5 lần, bấm giờ
```

Máy yên: 0,33–0,40 s. Trên 0,6 s là máy đang bận — chờ rồi đo lại. Cũng đừng chạy `docker stats` liên tục trong lúc đo: nó giữ daemon bận đúng ở thứ đang được đo (dựng container chấm bài).

## Trên Windows

`run.sh` chạy được trong Git Bash: nó tắt việc Git Bash tự đổi đường dẫn (`MSYS_NO_PATHCONV=1`) và đưa Docker Desktop đường dẫn dạng Windows (`pwd -W`). Stack production thử trên máy dev chạy dưới tên project khác để không đụng volume của stack dev — cách dựng ở `docs/report/assets/phase-6/load-test.md`, mục "Tái tạo".
