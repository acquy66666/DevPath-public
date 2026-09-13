# Benchmark hệ thống chấm bài

Ngày đo: 13/09/2026 · script: [`backend/scripts/bench_grading.py`](../../../../backend/scripts/bench_grading.py)

```
docker compose exec backend python -m scripts.bench_grading --submissions 10 --cases 5
```

## Đo cái gì, và đo bằng cách nào

Con số học viên cảm nhận được không phải thời gian sandbox chạy code, mà là
khoảng cách từ lúc bấm "Nộp bài" tới lúc thấy verdict. Trên hàng đợi đông, phần
lớn khoảng đó là **chờ tới lượt**. Nên script tách làm hai nửa, vì hai nửa này
sửa bằng hai cách khác nhau:

| Nửa | Từ → đến | Sửa bằng |
|---|---|---|
| Chờ hàng đợi | API trả 201 → worker bắt đầu chấm | thêm slot / thêm worker |
| Chấm | worker bắt đầu → verdict ghi xong | sandbox nhanh hơn, ít case hơn |

Mốc thời gian lấy từ **chính kênh tiến độ realtime** (Redis pub/sub), không phải
từ đồng hồ riêng cắm thêm vào worker: worker đã publish `running` trước case đầu
tiên và một sự kiện sau mỗi case, nên chỉ cần `psubscribe` là có đủ mốc. Không
thêm cột nào vào CSDL, và cũng có nghĩa là **thứ được đo chính là thứ trang web
đang hiển thị**.

Mỗi bài nộp đi từ một tài khoản học viên khác nhau. Mười bài từ một tài khoản
không phải phép đo tải, đó là phép đo rate limit — `submission_cooldown_seconds`
sẽ chặn chín bài. Mười học viên nộp cùng lúc cũng đúng là tình huống cần đo: một
lớp thực hành cùng làm một bài.

**Cấu hình máy đo:** Docker Desktop trên Windows 11, máy ảo Linux 8 CPU / 7,8 GB.
Sandbox mỗi container: `--cpus 0.5`, 128 MB, `--network none`, rootfs read-only.
Bài tập: 5 test case, chương trình `a + b` — cố tình tầm thường, vì thứ đang đo
là bộ máy quanh chương trình chứ không phải chương trình.

## Kết quả: 10 bài nộp cùng lúc, 5 test case mỗi bài

| Slot worker | Cả đợt xong trong | Throughput | Nộp → verdict (TB) | p90 | Chờ hàng đợi (TB) | Chấm (TB) | ms/test case |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 26,9 s | 22,3 bài/phút | 14,90 s | 24,35 s | 12,25 s | 2,65 s | 530 |
| **2** *(mặc định)* | **16,1 s** | **37,2 bài/phút** | **9,55 s** | **15,87 s** | **6,40 s** | **3,15 s** | **630** |
| 4 | 12,4 s | 48,4 bài/phút | 7,22 s | 12,06 s | 3,18 s | 4,04 s | 808 |
| 8 | 9,7 s | 62,2 bài/phút | 7,21 s | 9,42 s | 1,35 s | 5,86 s | 1172 |

Một học viên nộp một mình, hàng đợi rỗng: **2,6 – 2,8 giây** cho cả 5 test case,
ở mọi cấu hình. Đây là con số cho trải nghiệm thường ngày; bảng trên là con số
cho giờ thực hành.

## Bốn điều đọc được

**1. Hàng đợi, không phải sandbox, là thứ học viên phải chờ.** Ở cấu hình mặc
định, trong 9,55 giây trung bình thì 6,40 giây là nằm chờ và chỉ 3,15 giây là
được chấm. Người xui nhất trong đợt chờ 12,8 giây trước khi container đầu tiên
của mình được dựng. Đây chính là lý do thanh tiến độ và danh sách per-test tồn
tại: phần lớn thời gian chờ xảy ra *trước* khi có gì để hiện, nên trang phải nói
"đang chờ tới lượt chấm" một cách thành thật.

**2. Thêm slot thì throughput tăng, nhưng tăng chậm dần.** 1→2 slot: +67%.
2→4: +30%. 4→8: +29%. Trên máy 8 CPU với mỗi container 0,5 CPU, tám container
song song mới dùng hết 4 CPU — vẫn còn chỗ, nhưng cái đội lên không phải CPU mà
là chi phí dựng/xóa container và tranh chấp I/O của Docker daemon.

**3. Cái giá của song song nằm ở chỗ không ai nghĩ tới: số đo của chính học
viên.** `run_time_ms` là thời gian sandbox đo được từ bên trong container. Cùng
một chương trình `a + b`:

| Slot | Chương trình chạy trong sandbox | Chi phí dựng container | Tổng mỗi case |
|---:|---:|---:|---:|
| 1 | 248 ms | 282 ms | 530 ms |
| 2 | 301 ms | 329 ms | 630 ms |
| 4 | 373 ms | 435 ms | 808 ms |
| 8 | 516 ms | 656 ms | 1172 ms |

Chạy 8 bài song song làm **chính chương trình của học viên chậm gấp đôi** (248 →
516 ms). Với hệ thống chấm thì đây không phải chuyện hiệu năng, mà là chuyện
công bằng: giới hạn thời gian là 2000 ms, nên một bài nộp đúng nhưng sát biên có
thể ăn TLE chỉ vì nó xui, nộp đúng lúc chín người khác cũng nộp. **Đây là lý do
không chọn cấu hình throughput cao nhất.**

**4. Dựng container tốn ngang chạy chương trình.** 282 ms dựng cho 248 ms chạy,
ở cấu hình rảnh nhất. Một bài tập 10 case tốn ~2,8 giây riêng cho việc tạo và
xóa container. Đổi lại là cô lập thật: mỗi test case một container dùng một lần,
không có trạng thái nào sống sót giữa hai case. Ở quy mô khóa luận, đổi như vậy
là đáng — nhưng nếu về sau cần nhanh hơn, đây là chỗ để tối ưu (một container
cho cả bài, reset giữa các case), chứ không phải chỗ nào khác.

## Kết luận cho cấu hình triển khai

Giữ **`GRADING_CONCURRENCY=2`** trên VPS 2 vCPU, và giữ vì ba lý do, theo thứ tự
quan trọng:

1. Hai container × 0,5 CPU = 1 CPU cho sandbox, chừa 1 CPU cho API, Postgres,
   Redis và worker thường. Bốn slot trên 2 vCPU sẽ lấy CPU của chính cái API
   đang phải trả lời WebSocket tiến độ.
2. Số đo `run_time_ms` còn đáng tin ở mức song song này (chậm hơn bản rảnh 21%,
   trong khi ở 8 slot là 108%).
3. Một lớp 30 người nộp cùng lúc mất khoảng **50 giây** để chấm hết (37,2
   bài/phút) — người cuối cùng chờ lâu, nhưng có thanh tiến độ nói rõ đang đứng
   thứ mấy, và không ai bị chấm sai vì máy bận.

Nếu cần nhanh hơn thì **tăng vCPU rồi mới tăng slot**, theo tỉ lệ 1 slot cho mỗi
1 vCPU dôi ra. Tăng slot trên máy cũ là đổi độ chính xác của việc chấm lấy tốc
độ, và đó là cái không được phép đổi.

## Giới hạn của phép đo này, nói thẳng

- **Máy dev, không phải VPS.** 8 CPU ở đây so với 2 vCPU thuê được bằng credit
  Student Pack là hai thế giới. Bảng trên dùng để chọn *hình dạng* cấu hình
  (bao nhiêu slot cho mỗi vCPU), không phải để hứa con số tuyệt đối. Đo lại trên
  máy chủ thật ở Phase 6.
- **Chương trình được chấm là `a + b`.** Bài nào tính toán nặng thì cán cân
  nghiêng về phía sandbox và chi phí dựng container bớt quan trọng đi.
- **Mỗi cấu hình chạy một lượt 10 bài**, có một bài khởi động trước để làm nóng
  image và kết nối. Không phải trung bình của nhiều lượt, nên chênh vài phần
  trăm giữa các lần chạy là bình thường; các kết luận ở trên đều dựa trên khoảng
  cách gấp rưỡi tới gấp đôi, không dựa trên vài phần trăm.
- **Một worker duy nhất.** Chưa đo cấu hình nhiều worker trên nhiều máy; kiến
  trúc cho phép (hàng đợi `grading` riêng), nhưng không nằm trong phạm vi khóa
  luận.
