# Khóa học mẫu có sẵn quiz — "Nhập môn SQL với PostgreSQL"

Bản mẫu để chép vào trình soạn khóa học (`/giang-day` → **Tạo khóa học**). Mỗi mục ghi đúng tên ô trên giao diện. Có 4 chương, 4 bài đọc, 4 bài trắc nghiệm, tổng **25 câu hỏi**.

Cách điền một câu hỏi: gõ **Câu hỏi**, gõ bốn **Phương án** theo thứ tự A–D, tích vào phương án có dấu ✅, chép **Giải thích**, bấm **Thêm câu hỏi**. Đáp án đúng được đặt ở nhiều vị trí khác nhau, có chủ đích.

**Chép bài đọc:** chỉ chép phần **giữa** hai dòng `~~~markdown` và `~~~`. Dán kèm hai dòng đó thì cả bài hiện thành một khối code. Bảng hiện đúng từ bản có ô soạn mới (23/10); dùng tab **Xem trước** để kiểm trước khi lưu.

Các bài đọc đủ dài để thử nút **Sinh câu hỏi bằng AI**: ở ô **Soạn từ bài học**, chọn bài đọc của chương đó.

---

## 1. Thông tin khóa học

| Ô | Nội dung |
|---|---|
| Tên khóa học | Nhập môn SQL với PostgreSQL |
| Danh mục | Lập trình web › Backend |
| Mô tả ngắn | Viết được câu truy vấn SQL đầu tiên: lọc, sắp xếp, gộp nhóm và nối bảng trên PostgreSQL. |
| Trình độ | Cơ bản (người mới bắt đầu) |
| Giá (VND) | 0 |

**Mô tả chi tiết** (Markdown):

~~~markdown
Khóa học dành cho người chưa từng viết SQL. Mọi ví dụ dùng chung hai bảng nhỏ — `students` và `scores` — nên bạn luôn biết câu truy vấn đang chạy trên dữ liệu nào.

**Bạn sẽ làm được:**

- Hiểu bảng, dòng, cột, khóa chính và khóa ngoại
- Lấy dữ liệu bằng `SELECT`, lọc bằng `WHERE`, sắp xếp bằng `ORDER BY`
- Tính tổng, trung bình, đếm theo nhóm bằng `GROUP BY`
- Nối hai bảng bằng `JOIN`

Mỗi chương kết thúc bằng một bài trắc nghiệm ngắn, cuối khóa có bài tổng kết.
~~~

---

## 2. Cấu trúc

| Chương | Bài | Loại | Thời gian | Điểm đạt |
|---|---|---|---|---|
| 1. Làm quen cơ sở dữ liệu quan hệ | 1.1 Bảng, dòng, cột và khóa | Bài đọc | | |
| | 1.2 Kiểm tra chương 1 | Trắc nghiệm (5 câu) | 10 phút | 60 % |
| 2. Truy vấn dữ liệu với SELECT | 2.1 SELECT, WHERE, ORDER BY, LIMIT | Bài đọc | | |
| | 2.2 Kiểm tra chương 2 | Trắc nghiệm (6 câu) | 10 phút | 70 % |
| 3. Gộp nhóm và nối bảng | 3.1 GROUP BY và JOIN | Bài đọc | | |
| | 3.2 Kiểm tra chương 3 | Trắc nghiệm (6 câu) | 15 phút | 70 % |
| 4. Tổng kết | 4.1 Thay đổi dữ liệu an toàn | Bài đọc | | |
| | 4.2 Bài kiểm tra cuối khóa | Trắc nghiệm (8 câu) | bỏ trống (không tính giờ) | 80 % |

---

## Chương 1. Làm quen cơ sở dữ liệu quan hệ

### Bài 1.1 — Bảng, dòng, cột và khóa (Bài đọc)

~~~markdown
## Dữ liệu nằm trong bảng

Cơ sở dữ liệu quan hệ lưu dữ liệu thành **bảng**. Mỗi **cột** là một thuộc tính có kiểu dữ liệu cố định, mỗi **dòng** là một bản ghi.

| id | name      | email             |
|----|-----------|-------------------|
| 1  | An Nguyễn | an@example.com    |
| 2  | Bình Trần | NULL              |
| 3  | Chi Lê    | chi@example.com   |

Bảng trên tên là `students`. Ô email của Bình là `NULL` — nghĩa là *chưa biết*, không phải chuỗi rỗng.

## Khóa chính

Cột `id` là **khóa chính** (`PRIMARY KEY`): giá trị của nó *không được trùng* và *không được NULL*. Nhờ vậy mỗi dòng luôn chỉ ra được đúng một sinh viên.

## Khóa ngoại

Bảng `scores` lưu điểm, và cột `student_id` của nó là **khóa ngoại** trỏ về `students.id`. PostgreSQL từ chối một điểm thuộc về sinh viên không tồn tại — đó là *toàn vẹn tham chiếu*.

```sql
CREATE TABLE students (
  id    integer PRIMARY KEY,
  name  text NOT NULL,
  email text
);

CREATE TABLE scores (
  id         integer PRIMARY KEY,
  student_id integer NOT NULL REFERENCES students(id),
  course     text NOT NULL,
  score      numeric(4, 1) NOT NULL
);
```

## Chọn kiểu dữ liệu

- `integer`, `bigint`: số nguyên
- `numeric`: số thập phân **chính xác**, dùng cho tiền và điểm
- `real`, `double precision`: số thực dấu phẩy động, có sai số làm tròn
- `text`: chuỗi, `boolean`: đúng/sai, `timestamptz`: thời điểm có múi giờ
~~~

### Bài 1.2 — Kiểm tra chương 1 (Trắc nghiệm · 10 phút · đạt 60 %)

**Câu 1.** Trong cơ sở dữ liệu quan hệ, dữ liệu được tổ chức thành gì?
- A. Cây thư mục lồng nhau
- B. ✅ Các bảng gồm dòng và cột
- C. Các tệp JSON rời rạc
- D. Một danh sách khóa–giá trị duy nhất

Giải thích: Mô hình quan hệ lưu dữ liệu thành bảng. Mỗi cột là một thuộc tính, mỗi dòng là một bản ghi.

**Câu 2.** Cột khóa chính (`PRIMARY KEY`) phải thỏa điều kiện nào?
- A. Chỉ cần không trùng, được phép NULL
- B. Bắt buộc là số nguyên tự tăng
- C. ✅ Không trùng và không được NULL
- D. Được trùng nếu khác bảng

Giải thích: Khóa chính dùng để chỉ ra đúng một dòng, nên phải duy nhất và luôn có giá trị. Kiểu dữ liệu không bắt buộc là số.

**Câu 3.** Khóa ngoại `scores.student_id REFERENCES students(id)` có tác dụng gì?
- A. ✅ Không cho lưu điểm của một sinh viên không tồn tại
- B. Tự động tạo sinh viên mới khi thêm điểm
- C. Làm truy vấn trên bảng `scores` nhanh hơn
- D. Bắt mỗi sinh viên chỉ có một điểm

Giải thích: Khóa ngoại giữ toàn vẹn tham chiếu: giá trị phải có sẵn ở cột được tham chiếu. Nó không tự tạo dòng, cũng không giới hạn số điểm của mỗi sinh viên.

**Câu 4.** Nên dùng kiểu nào để lưu số tiền cần chính xác tới từng đồng?
- A. `real`
- B. `double precision`
- C. `text`
- D. ✅ `numeric`

Giải thích: `real` và `double precision` là số dấu phẩy động, có sai số làm tròn. `numeric` lưu chính xác. `text` thì không tính toán được.

**Câu 5.** Ô email của Bình là `NULL`. Điều đó nghĩa là gì?
- A. Email là chuỗi rỗng `''`
- B. ✅ Giá trị chưa biết hoặc không có
- C. Email bằng số 0
- D. Dòng đó đã bị xóa

Giải thích: `NULL` biểu thị "không có giá trị". Nó khác chuỗi rỗng và khác số 0.

---

## Chương 2. Truy vấn dữ liệu với SELECT

### Bài 2.1 — SELECT, WHERE, ORDER BY, LIMIT (Bài đọc)

~~~markdown
## Lấy dữ liệu

```sql
SELECT * FROM students;            -- mọi cột
SELECT name, email FROM students;  -- chỉ hai cột
```

## Lọc dòng bằng WHERE

```sql
SELECT name FROM scores
JOIN students ON students.id = scores.student_id
WHERE score >= 8;
```

Một số toán tử hay dùng trong `WHERE`:

- So sánh: `=`, `<>`, `<`, `>=`…
- Kết hợp: `AND`, `OR`, `NOT`
- Khớp mẫu: `name LIKE 'An%'` — `%` thay cho một chuỗi bất kỳ, `_` thay cho đúng một ký tự
- Kiểm tra NULL: `email IS NULL`, `email IS NOT NULL`. **Không dùng `= NULL`**: phép so sánh với NULL luôn cho kết quả *không xác định*, nên không dòng nào được chọn.

## Sắp xếp và giới hạn

```sql
SELECT name, score FROM scores
JOIN students ON students.id = scores.student_id
ORDER BY score DESC   -- giảm dần; ASC (mặc định) là tăng dần
LIMIT 3               -- lấy 3 dòng
OFFSET 3;             -- bỏ qua 3 dòng đầu → dòng thứ 4 tới 6
```

Không có `ORDER BY` thì thứ tự dòng **không được đảm bảo**, nên `LIMIT`/`OFFSET` luôn nên đi kèm `ORDER BY`.
~~~

### Bài 2.2 — Kiểm tra chương 2 (Trắc nghiệm · 10 phút · đạt 70 %)

**Câu 1.** Câu lệnh nào lấy mọi cột của bảng `students`?
- A. `GET * FROM students;`
- B. `SELECT ALL students;`
- C. ✅ `SELECT * FROM students;`
- D. `SELECT students.*;`

Giải thích: `*` sau `SELECT` nghĩa là mọi cột, và `FROM` chỉ bảng nguồn.

**Câu 2.** Mệnh đề nào dùng để lọc **dòng** trước khi trả kết quả?
- A. ✅ `WHERE`
- B. `ORDER BY`
- C. `LIMIT`
- D. `HAVING`

Giải thích: `WHERE` lọc từng dòng. `HAVING` lọc các nhóm sau `GROUP BY` (chương 3).

**Câu 3.** `ORDER BY score DESC` sắp xếp kết quả thế nào?
- A. Tăng dần theo điểm
- B. ✅ Giảm dần theo điểm
- C. Ngẫu nhiên
- D. Theo thứ tự thêm vào bảng

Giải thích: `DESC` là giảm dần. Bỏ trống hoặc ghi `ASC` là tăng dần.

**Câu 4.** Cách nào tìm đúng các sinh viên **chưa có** email?
- A. `WHERE email = NULL`
- B. `WHERE email = ''`
- C. `WHERE email <> NULL`
- D. ✅ `WHERE email IS NULL`

Giải thích: So sánh với NULL bằng `=` hay `<>` luôn cho kết quả không xác định, nên không chọn được dòng nào. Phải dùng `IS NULL`.

**Câu 5.** `... ORDER BY score DESC LIMIT 3 OFFSET 3` trả về gì?
- A. 3 dòng đầu tiên
- B. 6 dòng đầu tiên
- C. ✅ Dòng thứ 4, 5, 6 theo điểm giảm dần
- D. Mọi dòng trừ 3 dòng đầu

Giải thích: `OFFSET 3` bỏ qua 3 dòng đầu, `LIMIT 3` lấy 3 dòng tiếp theo.

**Câu 6.** `WHERE name LIKE 'An%'` khớp với tên nào?
- A. ✅ Tên bắt đầu bằng "An", ví dụ "An Nguyễn"
- B. Tên kết thúc bằng "An"
- C. Tên chứa đúng hai ký tự
- D. Chỉ tên đúng bằng "An%"

Giải thích: `%` thay cho một chuỗi bất kỳ, kể cả chuỗi rỗng, nên `'An%'` nghĩa là "bắt đầu bằng An". Lưu ý `LIKE` phân biệt hoa thường; `ILIKE` thì không.

---

## Chương 3. Gộp nhóm và nối bảng

### Bài 3.1 — GROUP BY và JOIN (Bài đọc)

~~~markdown
## Hàm gộp

`COUNT`, `SUM`, `AVG`, `MIN`, `MAX` gộp nhiều dòng thành một giá trị.

- `COUNT(*)` đếm **mọi dòng**
- `COUNT(email)` chỉ đếm dòng có email **khác NULL**

## Gộp theo nhóm

```sql
SELECT course, AVG(score) AS diem_tb, COUNT(*) AS so_bai
FROM scores
GROUP BY course
HAVING AVG(score) >= 7;
```

Mỗi giá trị `course` thành một dòng kết quả. Khi có `GROUP BY`, cột nào được `SELECT` mà không nằm trong hàm gộp thì phải có mặt trong `GROUP BY`. `HAVING` lọc **nhóm**, còn `WHERE` lọc **dòng** trước khi gộp.

## Nối bảng

```sql
-- INNER JOIN: chỉ sinh viên đã có điểm
SELECT s.name, sc.score
FROM students s
JOIN scores sc ON sc.student_id = s.id;

-- LEFT JOIN: mọi sinh viên, ai chưa có điểm thì score là NULL
SELECT s.name, sc.score
FROM students s
LEFT JOIN scores sc ON sc.student_id = s.id;
```

`JOIN` không ghi gì thêm nghĩa là `INNER JOIN`. Quên điều kiện `ON` là ghép **mọi dòng với mọi dòng** (tích Descartes).
~~~

### Bài 3.2 — Kiểm tra chương 3 (Trắc nghiệm · 15 phút · đạt 70 %)

**Câu 1.** Bảng `students` có 10 dòng, trong đó 3 dòng có email là NULL. `SELECT COUNT(email) FROM students;` trả về bao nhiêu?
- A. 10
- B. ✅ 7
- C. 3
- D. NULL

Giải thích: `COUNT(cột)` bỏ qua giá trị NULL. `COUNT(*)` mới đếm cả 10 dòng.

**Câu 2.** Muốn chỉ giữ những khóa có điểm trung bình từ 7 trở lên **sau khi** đã `GROUP BY course`, dùng mệnh đề nào?
- A. `WHERE AVG(score) >= 7`
- B. `ORDER BY AVG(score) >= 7`
- C. ✅ `HAVING AVG(score) >= 7`
- D. `LIMIT 7`

Giải thích: `WHERE` chạy trước khi gộp nên chưa có `AVG` để so. `HAVING` lọc trên kết quả đã gộp.

**Câu 3.** `INNER JOIN` giữa `students` và `scores` trả về những dòng nào?
- A. Mọi sinh viên, kể cả người chưa có điểm
- B. ✅ Chỉ những cặp sinh viên–điểm khớp điều kiện `ON`
- C. Mọi điểm, kể cả điểm không thuộc sinh viên nào
- D. Mọi tổ hợp có thể của hai bảng

Giải thích: `INNER JOIN` chỉ giữ dòng có cặp khớp ở cả hai bên. Đáp án D là kết quả khi quên `ON` (tích Descartes).

**Câu 4.** Với `students LEFT JOIN scores`, một sinh viên chưa có điểm nào sẽ thế nào?
- A. Bị loại khỏi kết quả
- B. Gây lỗi truy vấn
- C. Xuất hiện với điểm bằng 0
- D. ✅ Vẫn xuất hiện, các cột của `scores` là NULL

Giải thích: `LEFT JOIN` giữ mọi dòng của bảng bên trái. Chỗ không có cặp được điền NULL, không phải 0.

**Câu 5.** `SELECT course, AVG(score) FROM scores GROUP BY course;` cho kết quả gì?
- A. ✅ Điểm trung bình của từng khóa
- B. Điểm trung bình của toàn bộ bảng, lặp lại ở mỗi dòng
- C. Điểm cao nhất của từng khóa
- D. Số bài của từng khóa

Giải thích: `GROUP BY course` chia dòng theo khóa, và `AVG` tính trên từng nhóm.

**Câu 6.** Trong câu có `GROUP BY course`, cột nào được đứng một mình trong `SELECT` (không bọc hàm gộp)?
- A. `score`
- B. `student_id`
- C. ✅ `course`
- D. `id`

Giải thích: Mỗi nhóm có một giá trị `course` duy nhất, còn `score`, `student_id`, `id` có nhiều giá trị trong cùng nhóm nên phải bọc trong hàm gộp.

---

## Chương 4. Tổng kết

### Bài 4.1 — Thay đổi dữ liệu an toàn (Bài đọc)

~~~markdown
## Thêm, sửa, xóa

```sql
INSERT INTO students (id, name, email) VALUES (4, 'Dũng Phạm', NULL);
UPDATE students SET email = 'binh@example.com' WHERE id = 2;
DELETE FROM students WHERE id = 4;
```

`UPDATE` và `DELETE` **không có `WHERE`** sẽ tác động lên *mọi dòng* của bảng. Trước khi chạy, hãy thử `SELECT` với đúng điều kiện đó để xem sẽ chạm vào bao nhiêu dòng.

## Giao dịch (transaction)

```sql
BEGIN;
UPDATE scores SET score = score + 1 WHERE course = 'SQL';
-- kiểm tra lại, thấy sai:
ROLLBACK;   -- hủy mọi thay đổi từ BEGIN; dùng COMMIT để giữ lại
```

## Thứ tự xử lý của một câu SELECT

Về mặt logic, PostgreSQL xử lý theo thứ tự: `FROM`/`JOIN` → `WHERE` → `GROUP BY` → `HAVING` → `SELECT` → `DISTINCT` → `ORDER BY` → `LIMIT`. Vì `WHERE` chạy trước `SELECT`, bí danh đặt ở `SELECT` (`AS diem_tb`) không dùng được trong `WHERE`, nhưng dùng được trong `ORDER BY`.

## Chỉ mục (index)

`CREATE INDEX ON scores (student_id);` giúp tìm theo `student_id` nhanh hơn. Đổi lại, index tốn chỗ lưu và làm thao tác ghi chậm đi một chút.
~~~

### Bài 4.2 — Bài kiểm tra cuối khóa (Trắc nghiệm · không tính giờ · đạt 80 %)

**Câu 1.** Về mặt logic, mệnh đề nào được xử lý **đầu tiên** trong một câu `SELECT`?
- A. `SELECT`
- B. `WHERE`
- C. ✅ `FROM`
- D. `ORDER BY`

Giải thích: Phải biết dữ liệu lấy từ bảng nào (`FROM`/`JOIN`) trước, rồi mới lọc, gộp và chọn cột.

**Câu 2.** Vì sao `SELECT score * 10 AS diem FROM scores WHERE diem > 50;` báo lỗi?
- A. Không được nhân trong `SELECT`
- B. ✅ `WHERE` được xử lý trước `SELECT`, nên chưa có bí danh `diem`
- C. Bí danh phải viết hoa
- D. Thiếu `GROUP BY`

Giải thích: Bí danh sinh ra ở bước `SELECT`, sau `WHERE`. Viết `WHERE score * 10 > 50` thì chạy được.

**Câu 3.** Chạy `UPDATE students SET email = NULL;` (không có `WHERE`) thì điều gì xảy ra?
- A. Báo lỗi vì thiếu `WHERE`
- B. Chỉ dòng đầu tiên bị đổi
- C. Không dòng nào bị đổi
- D. ✅ Email của **mọi** sinh viên thành NULL

Giải thích: Không có `WHERE` nghĩa là áp cho mọi dòng. SQL không tự hỏi lại.

**Câu 4.** Lệnh nào xóa đúng sinh viên có `id` bằng 5?
- A. ✅ `DELETE FROM students WHERE id = 5;`
- B. `DROP students WHERE id = 5;`
- C. `DELETE students.id = 5;`
- D. `REMOVE FROM students id 5;`

Giải thích: `DELETE FROM <bảng> WHERE <điều kiện>` xóa dòng. `DROP` xóa cả bảng.

**Câu 5.** `SELECT DISTINCT course FROM scores;` dùng để làm gì?
- A. Sắp xếp các khóa theo bảng chữ cái
- B. ✅ Liệt kê mỗi khóa đúng một lần, bỏ dòng trùng
- C. Đếm số khóa
- D. Lấy khóa có điểm cao nhất

Giải thích: `DISTINCT` loại các dòng kết quả trùng nhau. Muốn đếm thì dùng `COUNT(DISTINCT course)`.

**Câu 6.** Sau `BEGIN; UPDATE ...; ROLLBACK;` dữ liệu ở trạng thái nào?
- A. Đã lưu thay đổi của `UPDATE`
- B. Lưu một nửa thay đổi
- C. ✅ Trở lại như trước `BEGIN`
- D. Bảng bị khóa vĩnh viễn

Giải thích: `ROLLBACK` hủy mọi thay đổi trong giao dịch, còn `COMMIT` giữ chúng lại.

**Câu 7.** Thêm index trên `scores(student_id)` mang lại gì?
- A. Bắt `student_id` không được trùng
- B. Làm mọi thao tác ghi nhanh hơn
- C. Tự xóa các điểm trùng lặp
- D. ✅ Tìm theo `student_id` nhanh hơn, đổi lại tốn chỗ và ghi chậm hơn một chút

Giải thích: Index thường không ràng buộc dữ liệu (đó là việc của `UNIQUE`). Nó tăng tốc đọc, đổi lại phải cập nhật thêm mỗi lần ghi.

**Câu 8.** Câu nào liệt kê **mọi** sinh viên kèm số bài đã có điểm, kể cả người chưa có bài nào (ra 0)?
- A. `SELECT s.name, COUNT(*) FROM students s JOIN scores sc ON sc.student_id = s.id GROUP BY s.name;`
- B. ✅ `SELECT s.name, COUNT(sc.id) FROM students s LEFT JOIN scores sc ON sc.student_id = s.id GROUP BY s.id, s.name;`
- C. `SELECT s.name, COUNT(*) FROM students s LEFT JOIN scores sc ON sc.student_id = s.id;`
- D. `SELECT name, COUNT(score) FROM students GROUP BY name;`

Giải thích: Cần `LEFT JOIN` để giữ sinh viên chưa có điểm, và `COUNT(sc.id)` để dòng NULL đếm ra 0 (`COUNT(*)` sẽ ra 1). A bỏ mất người chưa có điểm, C thiếu `GROUP BY`, D đọc cột `score` vốn không có trong `students`.
