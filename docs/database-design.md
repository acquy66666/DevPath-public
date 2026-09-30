# Thiết kế CSDL

> File này phải luôn khớp với schema thật (xem skill `db-migration`). ERD hình vẽ làm ở [Phase 7](plan/phase-7-report.md); tài liệu này là đặc tả chữ, đủ chi tiết để viết model SQLAlchemy và migration mà không phải đoán thêm.

## Quy ước chung

| Hạng mục | Quy ước |
|---|---|
| Khóa chính | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Thời gian | `created_at`, `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at` do ORM cập nhật (`onupdate`) |
| Enum nghiệp vụ | `VARCHAR(n) NOT NULL` + `CHECK` liệt kê giá trị — **không dùng Postgres ENUM** (khó migrate) |
| Tiền | `NUMERIC(12,2)`, đơn vị VND, không bao giờ dùng float |
| Khóa ngoại | Tên `<bảng_số_ít>_id`; mặc định `ON DELETE RESTRICT`, chỉ dùng `CASCADE` cho quan hệ sở hữu chặt |
| Đặt tên | index `ix_<bảng>_<cột>`, unique `uq_<bảng>_<cột…>`, check `ck_<bảng>_<mô tả>` |
| Chuỗi dài | `TEXT` khi không có giới hạn nghiệp vụ thật; `VARCHAR(n)` khi có |
| Soft delete | **Chỉ `courses`** có `deleted_at` |

### Năm quyết định thiết kế đã chốt

| Quyết định | Chọn | Lý do |
|---|---|---|
| Refresh token | Bảng `refresh_tokens` trong Postgres | Thu hồi được từng phiên, liệt kê thiết bị đăng nhập, có vết để điều tra |
| Soft delete | Chỉ `courses` | Đúng một nhu cầu nghiệp vụ: khóa học bị gỡ nhưng học viên đã mua vẫn học được. Càng ít bảng soft delete càng ít chỗ quên lọc |
| Số liệu khóa học | Lưu sẵn trong `courses` (`rating_avg`, `rating_count`, `students_count`, `duration_total_s`) | Trang danh sách sắp xếp theo rating dùng được index; bù rủi ro lệch bằng script rebuild |
| Giỏ hàng | Mỗi user một giỏ duy nhất — `uq_carts_user_id` | Đủ cho nghiệp vụ, không có kịch bản nhiều giỏ song song |
| Lesson ↔ nội dung | `lessons.type` + bảng con trỏ ngược, `lesson_id` unique | Giữ được FK thật; ràng buộc `type` khớp bảng con kiểm ở service |

---

## 1. Người dùng & phân quyền

### `users`

| Cột | Kiểu | Null | Default | Ghi chú |
|---|---|---|---|---|
| `id` | UUID | ✗ | `gen_random_uuid()` | PK |
| `email` | VARCHAR(255) | ✗ | | Chuẩn hóa lowercase + trim **ở service trước khi ghi** |
| `password_hash` | VARCHAR(255) | ✓ | | NULL khi tài khoản chỉ đăng nhập bằng OAuth (bcrypt) |
| `full_name` | VARCHAR(150) | ✗ | | |
| `avatar_url` | TEXT | ✓ | | Key R2 dạng URL đầy đủ |
| `role` | VARCHAR(20) | ✗ | `'student'` | `student` / `instructor` / `admin` |
| `oauth_provider` | VARCHAR(20) | ✓ | | `google` (v1 chỉ Google) |
| `oauth_sub` | VARCHAR(255) | ✓ | | `sub` từ Google, dùng để merge account theo email |
| `email_verified_at` | TIMESTAMPTZ | ✓ | | Đăng nhập Google coi như đã xác thực |
| `locked_at` | TIMESTAMPTZ | ✓ | | Admin khóa tài khoản (Phase 5); khác NULL ⇒ chặn đăng nhập |
| `last_login_at` | TIMESTAMPTZ | ✓ | | |
| `created_at` / `updated_at` | TIMESTAMPTZ | ✗ | `now()` | |

Ràng buộc & index:

- `uq_users_email` UNIQUE (`email`)
- `uq_users_oauth` UNIQUE (`oauth_provider`, `oauth_sub`) — partial `WHERE oauth_sub IS NOT NULL`
- `ck_users_role` CHECK `role IN ('student','instructor','admin')`
- `ck_users_credential` CHECK `password_hash IS NOT NULL OR oauth_sub IS NOT NULL` — không cho tồn tại tài khoản không đăng nhập được bằng cách nào
- `ix_users_role` — phục vụ màn quản lý user của admin (Phase 5)

### `refresh_tokens`

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| `id` | UUID | ✗ | PK |
| `user_id` | UUID | ✗ | FK → `users` **ON DELETE CASCADE** |
| `token_hash` | VARCHAR(64) | ✗ | SHA-256 hex của token. **Không lưu token thô** — lộ DB cũng không dùng lại được |
| `expires_at` | TIMESTAMPTZ | ✗ | |
| `revoked_at` | TIMESTAMPTZ | ✓ | Khác NULL ⇒ token đã bị thu hồi |
| `user_agent` | VARCHAR(255) | ✓ | Hiển thị "thiết bị đang đăng nhập" |
| `ip_address` | INET | ✓ | |
| `created_at` | TIMESTAMPTZ | ✗ | |

- `uq_refresh_tokens_token_hash` UNIQUE (`token_hash`)
- `ix_refresh_tokens_user_id`
- **Rotation:** mỗi lần refresh thành công thì `revoked_at` token cũ và cấp token mới. Dùng lại token đã revoke ⇒ nghi ngờ bị đánh cắp, thu hồi toàn bộ phiên của user đó.
- Job dọn dẹp xóa hẳn bản ghi hết hạn > 30 ngày.

---

## 2. Danh mục khóa học

### `categories`

| Cột | Kiểu | Null | Default | Ghi chú |
|---|---|---|---|---|
| `id` | UUID | ✗ | `gen_random_uuid()` | |
| `name` | VARCHAR(100) | ✗ | | |
| `slug` | VARCHAR(120) | ✗ | | |
| `parent_id` | UUID | ✓ | | FK → `categories`, ON DELETE RESTRICT |
| `position` | INT | ✗ | `0` | Thứ tự hiển thị |
| `created_at` / `updated_at` | TIMESTAMPTZ | ✗ | `now()` | |

- `uq_categories_slug` UNIQUE (`slug`), `ix_categories_parent_id`
- `ck_categories_not_self_parent` CHECK `parent_id IS DISTINCT FROM id`
- Giới hạn **2 cấp** (danh mục cha có `parent_id IS NULL`) kiểm ở service — Postgres không ép rẻ được.

### `courses`

| Cột | Kiểu | Null | Default | Ghi chú |
|---|---|---|---|---|
| `id` | UUID | ✗ | `gen_random_uuid()` | |
| `instructor_id` | UUID | ✗ | | FK → `users`, ON DELETE RESTRICT |
| `category_id` | UUID | ✗ | | FK → `categories`, ON DELETE RESTRICT |
| `title` | VARCHAR(200) | ✗ | | |
| `slug` | VARCHAR(220) | ✗ | | Sinh từ title + hậu tố ngắn chống trùng |
| `subtitle` | VARCHAR(300) | ✓ | | Mô tả 1 dòng cho card |
| `description` | TEXT | ✓ | | Markdown |
| `thumbnail_url` | TEXT | ✓ | | |
| `price` | NUMERIC(12,2) | ✗ | `0` | `0` = miễn phí |
| `level` | VARCHAR(20) | ✗ | `'beginner'` | `beginner` / `intermediate` / `advanced` |
| `language` | VARCHAR(10) | ✗ | `'vi'` | |
| `status` | VARCHAR(20) | ✗ | `'draft'` | Xem mục 8 |
| `rejection_reason` | TEXT | ✓ | | Bắt buộc khi `status='rejected'`. Admin ghi lúc từ chối, giảng viên đọc ở trang quản lý khóa học; gửi duyệt lại và duyệt đều xóa nó (lý do cũ trả lời phiên bản cũ) |
| `published_at` | TIMESTAMPTZ | ✓ | | Bắt buộc khi `status='published'`. Là lần **đầu tiên** lên sàn: duyệt lại một khóa từng bị gỡ giữ nguyên mốc cũ |
| `rating_avg` | NUMERIC(3,2) | ✗ | `0` | Denormalize từ `reviews` |
| `rating_count` | INT | ✗ | `0` | |
| `students_count` | INT | ✗ | `0` | Denormalize từ `enrollments` |
| `duration_total_s` | INT | ✗ | `0` | Tổng thời lượng video, cập nhật khi asset `ready` |
| `search_vector` | TSVECTOR | ✓ | | `title` (A) + `subtitle` (B) + `description` (C), cấu hình `simple` trên văn bản đã `unaccent`; trigger tự ghi |
| `deleted_at` | TIMESTAMPTZ | ✓ | | Soft delete |
| `created_at` / `updated_at` | TIMESTAMPTZ | ✗ | `now()` | |

Ràng buộc:

- `uq_courses_slug` UNIQUE (`slug`)
- `ck_courses_status`, `ck_courses_level` — CHECK danh sách giá trị
- `ck_courses_price_non_negative` CHECK `price >= 0`
- `ck_courses_rating_range` CHECK `rating_avg BETWEEN 0 AND 5` và `rating_count >= 0`
- `ck_courses_published_at` CHECK `status <> 'published' OR published_at IS NOT NULL`
- `ck_courses_rejection_reason` CHECK `status <> 'rejected' OR rejection_reason IS NOT NULL`

### Các bảng còn lại của nhóm

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `course_sections` | `course_id`, `title`, `position` | `uq_course_sections_position` (`course_id`,`position`) — **DEFERRABLE INITIALLY DEFERRED** | course → CASCADE | Sắp xếp lại ghi nhiều dòng trong một transaction, giữa chừng có hai dòng cùng vị trí |
| `lessons` | `section_id`, `title`, `type`, `position`, `is_preview`, `video_asset_id`, `article_content` | `uq_lessons_position` (`section_id`,`position`) — **DEFERRABLE INITIALLY DEFERRED**; `ck_lessons_type`; `ck_lessons_video_asset_type` | section → CASCADE, video_asset → SET NULL | `type`: `video`/`article`/`quiz`/`code_exercise`; `video_asset_id` chỉ khác NULL khi `type='video'`; `is_preview` cho xem thử không cần enroll |
| `video_assets` | `storage_key`, `duration_s`, `hls_manifest_key`, `status`, `error_message`, `transcript_key` | `uq_video_assets_storage_key` | — | `error_message` và `transcript_key` là cột **mới**. `transcript_key` trỏ file `.srt`/`.txt` trên R2 — nguồn để pipeline RAG chunk ở Phase 4, bản cũ không có chỗ nào lưu |
| `reviews` | `course_id`, `user_id`, `rating`, `comment` | `uq_reviews_course_user` (`course_id`,`user_id`); `ck_reviews_rating` CHECK 1–5 | course → CASCADE, user → CASCADE | Ghi/sửa review phải cập nhật `courses.rating_avg` trong cùng transaction |

---

## 3. Học tập

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `enrollments` | `user_id`, `course_id`, `source`, `completed_at` | `uq_enrollments_user_course` (`user_id`,`course_id`); `ck_enrollments_source` (`purchase`/`free`) | user → CASCADE, course → RESTRICT | Course bị gỡ chỉ soft delete nên enrollment không mất |
| `lesson_progress` | `enrollment_id`, `lesson_id`, `last_position_s`, `completed_at` | **`uq_lesson_progress_enrollment_lesson`** (`enrollment_id`,`lesson_id`) — thiếu trong bản cũ; `ck_lesson_progress_position_non_negative` | enrollment → CASCADE, lesson → CASCADE | `last_position_s INT NOT NULL DEFAULT 0`. Cột bị ghi dày nhất schema (heartbeat vài giây/lần) nên cố tình rẻ: một số nguyên, không lịch sử |
| `notes` | `user_id`, `lesson_id`, `timestamp_s`, `content` | `ix_notes_user_lesson` (`user_id`,`lesson_id`); `ck_notes_timestamp_non_negative`; `ck_notes_content_not_empty` | user → CASCADE, lesson → CASCADE | 1 user nhiều note/lesson (không unique). `timestamp_s` = 0 với bài không có timeline (article), nghĩa là "cả bài này". Nội dung tối đa 2000 ký tự |
| `bookmarks` | `user_id`, `lesson_id` | **`uq_bookmarks_user_lesson`** — thiếu trong bản cũ | user → CASCADE, lesson → CASCADE | |
| `certificates` | `enrollment_id`, `code` (varchar 16), **`recipient_name`**, **`course_title`**, **`instructor_name`**, `issued_at`, `pdf_key` (null được) | **`uq_certificates_code`**, `uq_certificates_enrollment`; **`ck_certificates_code_format`** (`code ~ '^[A-HJ-NP-Z2-9]{16}$'`) | enrollment → RESTRICT | `code` là mã công khai trên QR và là khóa duy nhất trang xác thực nhận. Mã gồm 16 ký tự lấy từ 32 ký tự không gây nhầm (bỏ I/O/0/1), tức 80 bit ngẫu nhiên, **không đoán được**. **Cấp trong cùng transaction** với lúc khóa học chuyển sang hoàn thành (`progress._refresh_course_completion`, chỗ duy nhất khóa học trở thành hoàn thành dù bài cuối là video, quiz hay bài code). Mỗi lượt ghi danh chỉ một chứng chỉ: bỏ tick rồi hoàn thành lại vẫn là chứng chỉ cũ; bỏ tick **không** thu hồi chứng chỉ. Ba cột **đóng băng** lúc cấp (thêm so với đặc tả ban đầu): một chứng chỉ đổi chữ theo hồ sơ hay tựa khóa sửa về sau thì không còn là bản ghi của điều gì cả, cùng lý do với `order_items.unit_price`. `issued_at` = `enrollments.completed_at`. `pdf_key` để trống cho tới khi worker vẽ xong PDF (sau commit). RESTRICT là cố ý: chứng chỉ không được biến mất như tác dụng phụ của việc xóa lượt ghi danh; các script `--purge` xóa chứng chỉ trước qua `certificates.delete_for_enrollments` |


> **`notes` và `bookmarks` gắn vào `user_id`, không phải `enrollment_id`** — khác `lesson_progress` một cách có chủ ý. Tiến độ mô tả *một lượt học* và đáng bị xóa nếu người ta học lại từ đầu; còn ghi chú là thứ người ta **viết ra**, mất nó vì enrolment bị dựng lại là mất công sức của họ. Quyền viết ghi chú/bookmark cũng chính là quyền *đọc* bài học (chủ khóa học, bài học thử, hoặc đã ghi danh) — không có luật riêng.

---

## 4. Bài tập code & chấm bài ⭐

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `code_exercises` | `lesson_id`, `statement_md`, `language`, `starter_code`, `time_limit_ms`, `memory_limit_mb` | `uq_code_exercises_lesson` (`lesson_id`); `ck_code_exercises_language`; CHECK `time_limit_ms BETWEEN 100 AND 10000`, `memory_limit_mb BETWEEN 16 AND 512` | lesson → CASCADE | Giới hạn có trần cứng để instructor không đặt số làm sập VPS — con số trên form này được nhân với **mọi** học viên nộp bài. Trần chặn hai lớp: Pydantic trả 422, CHECK constraint là lớp cuối |
| `test_cases` | `exercise_id`, `input`, `expected_output`, `is_hidden`, `position`, `score_weight` | `uq_test_cases_position` (`exercise_id`,`position`) — **DEFERRABLE INITIALLY DEFERRED**; CHECK `score_weight > 0` | exercise → CASCADE | `expected_output` của test hidden **không bao giờ** ra khỏi backend — cưỡng chế bằng schema riêng (`TestCaseSample` không có trường nào để chứa nó) chứ không bằng lời hứa của service. `is_hidden` mặc định `true` |
| `submissions` | `user_id`, `exercise_id`, `code`, `language`, **`is_trial`**, `status`, `verdict`, `score`, `run_time_ms`, `peak_memory_mb`, **`message`** | `ck_submissions_verdict_requires_done` CHECK `status='done' OR verdict IS NULL`; `ck_submissions_status`; `ck_submissions_verdict`; `ck_submissions_score` CHECK `score BETWEEN 0 AND 100` | user → CASCADE, exercise → CASCADE | Ngăn worker ghi verdict khi bài chưa chấm xong. **`message`** là cột thêm so với bản thiết kế đầu: CE không có kết quả theo từng test case, thiếu chỗ chứa lời của trình biên dịch thì học viên nhận đúng hai chữ "CE" và không hành động được gì. SE cũng dùng cột này để ghi lỗi phía hệ thống. **`is_trial`** phân biệt lần bấm "chạy thử" với bài nộp thật: cùng hàng, cùng hàng đợi, cùng sandbox — khác ở chỗ worker chỉ nạp test case mẫu, và lịch sử nộp bài lọc nó ra. Bảng riêng sẽ phải nhân đôi hàng đợi, worker, kênh tiến độ và mọi luật về ai được đọc |
| `submission_results` | `submission_id`, `test_case_id`, `verdict`, `run_time_ms`, `stdout_trunc` | `uq_submission_results` (`submission_id`,`test_case_id`); `ck_submission_results_verdict` | submission → CASCADE, test_case → CASCADE | `stdout_trunc` chỉ điền cho test sample — in lại thứ chương trình xuất ra trên input bí mật cũng chính là lộ input, chỉ chậm hơn một nhịp |

---

## 5. Quiz

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `quizzes` | `lesson_id`, `time_limit_s` (NULL = không tính giờ), `pass_score`, `ai_generated`, `is_published` | `uq_quizzes_lesson` (`lesson_id`); `ck_quizzes_pass_score` (`0..100`); `ck_quizzes_time_limit` (NULL hoặc 30..7200 giây) | lesson → CASCADE | `is_published`: quiz sinh bằng AI nằm ở `false` cho tới khi instructor duyệt xong từng câu. Câu hỏi bị **khóa** khi đang xuất bản — có người đang làm dở thì sửa đáp án là chấm họ trên một đề khác (quy tắc ở service, mã lỗi `QUIZ_PUBLISHED`) |
| `quiz_questions` | `quiz_id`, `question`, `options` (JSONB), `correct_index`, `explanation`, `position`, `ai_generated`, `reviewed_at` | `uq_quiz_questions_position` (`quiz_id`,`position`) **DEFERRABLE INITIALLY DEFERRED**; `ck_quiz_questions_options`; `ck_quiz_questions_not_empty`; `ck_quiz_questions_review_ai_only` (`ai_generated OR reviewed_at IS NULL`) | quiz → CASCADE | Thiết kế ban đầu để service kiểm `correct_index < len(options)`; **đã đưa xuống CHECK**: `options` phải là mảng 2–6 phần tử và `correct_index` phải trỏ vào trong mảng. Lý do: task sinh quiz bằng AI ghi thẳng JSON của model vào bảng, mà câu hỏi có đáp án đúng trỏ ra ngoài danh sách thì sai lặng lẽ — học viên bị chấm sai chứ không có lỗi nào nổi lên. Viết bằng `CASE` vì `jsonb_array_length` ném lỗi trên giá trị không phải mảng và Postgres không hứa thứ tự đánh giá của `AND`. **Hai cột thêm ở revision `ca9e1c7ffdbb`** (sinh quiz AI): `ai_generated` là câu do Gemini soạn, `reviewed_at` là lúc giảng viên duyệt câu đó. Service từ chối xuất bản quiz còn câu AI chưa duyệt, vì model rẻ đã được đo là có lúc sinh đáp án sai. Theo dõi từng câu chứ không theo cả quiz, vì một quiz có thể trộn câu tự gõ với câu AI soạn. CHECK giữ `reviewed_at` chỉ có trên câu AI: câu tự gõ mà mang dấu "đã duyệt" sẽ bị đếm nhầm thành bản nháp AI được chấp nhận |
| `quiz_attempts` | `quiz_id`, `user_id`, `answers` (JSONB), `score`, `started_at`, `submitted_at`, `time_limit_s`, `expired` | `ix_quiz_attempts_quiz_user`; `uq_quiz_attempts_open` — UNIQUE (`quiz_id`,`user_id`) **WHERE `submitted_at IS NULL`**; `ck_quiz_attempts_finished`; `ck_quiz_attempts_score`; `ck_quiz_attempts_expired_scores_zero` | quiz → CASCADE, user → CASCADE | `started_at` do backend ghi; hết giờ tính theo `started_at + time_limit_s`, **không tin client**. Hai cột thêm so với thiết kế gốc: `time_limit_s` chụp lại đồng hồ lúc bắt đầu (sửa quiz không được dời hạn của người đang làm), `expired` ghi việc đồng hồ — chứ không phải học viên — kết thúc lượt làm. Chỉ một lượt chưa nộp cho mỗi người mỗi quiz: mở 4 tab không thành 4 đồng hồ |

---

## 6. Thương mại

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `carts` | `user_id` | **`uq_carts_user_id`** — một giỏ/user | user → CASCADE | Dòng giỏ tạo **lười**, lần đầu người dùng bỏ khóa học vào; tài khoản chỉ học khóa miễn phí thì không có dòng nào. `GET /cart` của tài khoản chưa có giỏ trả giỏ rỗng chứ không 404 |
| `cart_items` | `cart_id`, `course_id` | **`uq_cart_items_cart_course`** — thiếu trong bản cũ; `ix_cart_items_cart_created` (`cart_id`, `created_at DESC`) | cart → CASCADE, course → CASCADE | **Không có cột giá và không có cột số lượng.** Giá đóng băng ở `order_items.unit_price` lúc trả tiền; giỏ hiện giá hôm nay vì đó là giá bấm thanh toán bây giờ sẽ phải trả. Không mua một khóa hai lần nên không có `quantity`. Trần `MAX_CART_ITEMS = 50` (`app/models/commerce.py`) — không phải giới hạn lưu trữ mà là thứ cho phép `GET /cart` trả nguyên giỏ không phân trang, vì tổng tiền phải phủ hết mọi dòng |
| `wishlists` | `user_id`, `course_id` | **`uq_wishlists_user_course`** — thiếu trong bản cũ; `ix_wishlists_user_created` (`user_id`, `created_at DESC`) | user → CASCADE, course → CASCADE | Bảng phẳng, **không có bảng cha** như `carts`: đây là tập sự kiện "người này muốn khóa này", không phải một vật chứa. Nhận cả khóa người dùng đã ghi danh (khác giỏ hàng, vì không có gì được trả tiền từ đây) |
| `coupons` | `code`, `discount_type` (`percent`/`fixed`), `value`, `scope` (`site`/`courses`), `max_uses`, `used_count`, `valid_from`, `valid_to` | `uq_coupons_code`; `ck_coupons_code_upper` (`code = upper(code)`), `ck_coupons_code_length`; `ck_coupons_discount_type`, `ck_coupons_scope`; `ck_coupons_value_positive`, **`ck_coupons_percent_range`** (`discount_type <> 'percent' OR value <= 100`); `ck_coupons_period` (`valid_to IS NULL OR valid_to > valid_from`); `ck_coupons_max_uses`, `ck_coupons_used_count`, `ck_coupons_uses_left` (`max_uses IS NULL OR used_count <= max_uses`) | — | **`used_count`** là cột mới; tăng bằng `UPDATE … WHERE used_count < max_uses` để tránh vượt lượt khi đồng thời. `max_uses` NULL = không giới hạn lượt, `valid_to` NULL = không có hạn kết thúc — **không có cột `is_active`**, thu mã sớm là đặt `valid_to`. Mã lưu chữ hoa nên tra mã là phép so bằng trên `uq_coupons_code` chứ không phải `upper(code) = …` quét cả bảng, và `TET2026` với `tet2026` không thể cùng tồn tại |
| `coupon_courses` | `coupon_id`, `course_id` | PK (`coupon_id`,`course_id`) | CASCADE cả hai | **Bảng mới** — coupon phạm vi khóa học cụ thể. `scope='site'` thì không có dòng nào. **Lệch quy ước khóa chính UUID có chủ ý** (như `refresh_tokens` lệch quy ước hai cột thời gian): cặp id *chính là* sự kiện, thêm `id` thì vẫn phải thêm UNIQUE làm đúng việc của khóa chính. Chỉ có `created_at`, vì cả hai cột của dòng đều là khóa nên không có gì để `updated_at` mô tả |
| `orders` | `user_id`, **`code`**, **`subtotal`**, **`discount`**, `total`, `coupon_id`, **`coupon_code`**, `status`, `payment_provider`, `provider_txn_id`, `paid_at`, **`failure_code`** | **`uq_orders_provider_txn`** (`payment_provider`,`provider_txn_id`) partial `WHERE provider_txn_id IS NOT NULL`; `uq_orders_code`; `ix_orders_user_created`; `ck_orders_status`, `ck_orders_provider`, `ck_orders_amounts_non_negative`, **`ck_orders_total`** (`total = subtotal - discount`), **`ck_orders_paid_evidence`** (`(status='paid') = (paid_at IS NOT NULL AND provider_txn_id IS NOT NULL)`) | user → RESTRICT, coupon → SET NULL | Đây là chốt chặn idempotent thật cho IPN — không thể chỉ dựa vào code. **`paid_at`** là cột mới. Bốn cột thêm so với thiết kế gốc, mỗi cột một lý do: **`code`** là `vnp_TxnRef` và là thứ người mua đọc lên khi hỏi hỗ trợ (`DP` + yymmdd + 6 ký tự, bảng chữ bỏ I/O/0/1); **`subtotal`** + **`discount`** để hóa đơn tự cộng khớp mà không phải đọc lại `coupons` — chiến dịch sửa sau đó thì con số cũ vẫn đúng; **`coupon_code`** vì `coupon_id` là SET NULL, xóa chiến dịch mà hóa đơn quên mất mã đã dùng là hóa đơn không cộng ra tổng; **`failure_code`** giữ `vnp_ResponseCode` để trang kết quả phân biệt "bạn đã hủy" với "thẻ không đủ số dư" |
| `order_items` | `order_id`, `course_id`, `unit_price`, **`discount`** | **`uq_order_items_order_course`** — thiếu trong bản cũ; `ck_order_items_unit_price`; **`ck_order_items_discount`** (`0 <= discount <= unit_price`); **`ix_order_items_course_id`** | order → CASCADE, course → RESTRICT | `unit_price` là giá tại thời điểm mua, không đọc lại `courses.price`. Không có cột số lượng, cùng lý do với `cart_items`. **`discount`** (từ 24/09/2026, revision `3f7c33c23e64`) là phần của `orders.discount` rơi vào dòng này, chia **lúc bán** và đóng băng như `unit_price` — xem đoạn "Doanh thu thuộc về khóa nào" bên dưới. Tổng các dòng bằng `orders.discount`; CHECK không nhìn được sang dòng khác nên luật này là của service |
| `payment_events` | `order_id`, `provider`, `payload` (JSONB), `signature_valid` | `ix_payment_events_order_id`; `ck_payment_events_provider` | order → CASCADE | **Append-only**: không UPDATE, không DELETE, và chỉ có `created_at` (như `refresh_tokens`) vì không có gì để `updated_at` mô tả. **`order_id` nullable** — lệch thiết kế gốc có chủ ý: callback mang mã không khớp đơn nào là dòng đáng giữ nhất (hoặc mình sai mã, hoặc có người dò endpoint), mà NOT NULL thì cách duy nhất để lưu nó là không lưu. `signature_valid` lưu lại chứ không tính lại: đổi secret thì dòng tháng trước không được biến thành hàng giả |

**Khóa học rời sàn thì rời giỏ** (từ 23/09/2026, `app/services/commerce.py`): mọi truy vấn liệt kê giỏ hàng và danh sách yêu thích đều mang sẵn `courses.deleted_at IS NULL AND courses.status = 'published'`, nên khóa học bị gỡ hoặc hạ về nháp biến khỏi hai danh sách cùng lúc nó biến khỏi catalogue — và không được tính vào tổng tiền. Dòng trong bảng **vẫn còn**, không xóa sau lưng người dùng; số đếm của danh sách yêu thích cũng đi qua đúng bộ lọc ấy để "trang 2 / 7" không hứa một trang mà bộ lọc làm rỗng.

Dòng giỏ hàng của khóa học người dùng **đã ghi danh trong lúc nó nằm trong giỏ** (ghi danh miễn phí ở tab khác) vẫn hiện, kèm cờ `already_enrolled`, nhưng bị trừ khỏi tổng tiền. Thêm mới thì bị chặn thẳng (409 `ALREADY_ENROLLED`) — để lời từ chối rơi vào lúc bấm nút chứ không rơi vào giữa màn thanh toán.

**Gõ mã giảm giá không tiêu lượt** (từ 23/09/2026, `app/services/coupons.py`): `POST /cart/coupon` chỉ đọc, `used_count` chỉ nhích trong `consume()` lúc đơn hàng được trả tiền — nếu không, một chiến dịch 100 lượt có thể cạn vì người ta mở trang giỏ hàng. Thứ tự hỏi là một phần của thiết kế: giỏ có gì phải trả không (409 `CART_EMPTY`, hỏi **trước** cả việc tra mã, vì "mã không tồn tại" trên giỏ rỗng đẩy người đọc đi sửa nhầm chỗ) → có mã này không (404 `COUPON_NOT_FOUND`) → mã còn sống không (409 `COUPON_NOT_STARTED` / `COUPON_EXPIRED` / `COUPON_EXHAUSTED`, mỗi câu kèm ngày hoặc số lượt) → áp được vào giỏ này không (409 `COUPON_NOT_APPLICABLE`).

**Ai được quyền nói là đã trả tiền** (24/09/2026, `app/services/orders.py`): chỉ IPN — callback VNPay gọi thẳng từ máy chủ của họ vào backend. Trình duyệt quay về từ ngân hàng mang đúng những tham số ấy, nhưng trình duyệt là thứ chủ nó sửa được, nên trang kết quả chỉ lấy mã đơn từ URL rồi **hỏi lại API**; tin vào query string nghĩa là ai gõ được `vnp_ResponseCode=00` cũng tự ghi danh được. Thứ tự kiểm trong IPN: chữ ký (trước khi tin bất kỳ tham số nào) → tìm đơn → khớp số tiền → trạng thái. Toàn bộ việc sau đó — ghi `payment_events`, chuyển đơn sang `paid`, ghi danh từng khóa, trừ lượt coupon, bỏ các dòng đã mua khỏi giỏ — nằm trong **một transaction**: hỏng giữa chừng sẽ để lại đơn đã trả tiền mà người mua không mở được khóa học, đúng cái hỏng làm người ta mất tiền. Callback trả lời bằng tiếng của VNPay (`{"RspCode","Message"}`, luôn HTTP 200 kể cả khi từ chối) vì VNPay gửi lại bất cứ thứ gì nó không đọc được — envelope lỗi của dự án là để nói với frontend, cổng thanh toán chưa nghe bao giờ.

Lượt coupon trừ ở đây, và **nếu chiến dịch hết lượt trong lúc chờ callback thì đơn vẫn được tính**: tiền đã chuyển rồi, lựa chọn còn lại là ghi nhận hoặc từ chối người đã trả tiền, mà vế sau không phải là một lựa chọn. Lượt đó không được ghi (CHECK `ck_coupons_uses_left` không cho lưu phần vượt), nên `orders.coupon_id` mới là bản ghi thật về ai đã dùng mã nào.

Số tiền giảm **chỉ tính trên phần đang thật sự phải trả**: dòng `already_enrolled` và khóa đã rời sàn đều đã nằm ngoài tổng tiền thì cũng nằm ngoài đây. **Phần trăm làm tròn tới đồng**, và làm tròn trên số tiền giảm chứ không trên tổng — VND không có đơn vị nhỏ hơn đồng, cổng thanh toán nhận số nguyên, mà làm tròn trên tổng thì ba con số trên màn hình không cộng khớp nhau nữa. **Số tiền cố định không vượt quá phần nó được trừ** (voucher 500.000 ₫ trên giỏ 399.000 ₫ giảm đúng 399.000 ₫): tổng sàn ở 0 chứ không thành tín dụng mà không bảng nào giữ. Giới hạn theo người ("mỗi tài khoản một lần") **chưa biểu diễn được** — không có bảng redemption, `orders.coupon_id` mới là chỗ trả lời, nên `max_uses` giới hạn chiến dịch chứ không giới hạn người.

**Doanh thu thuộc về khóa nào** (24/09/2026, `app/services/coupons.py::split_discount`): một đơn có một con số giảm giá, nhưng mỗi khóa có một giảng viên, và coupon giới hạn một khóa (`scope='courses'`) không được trừ vào doanh thu của khóa đứng cạnh nó trong cùng đơn. Đọc lại `coupon_courses` về sau không trả lời được, vì phạm vi chiến dịch sửa được sau khi đã bán. Nên phần giảm được **chia một lần lúc tạo đơn** trên đúng các dòng coupon áp vào, theo tỉ lệ giá, làm tròn xuống tới đồng; các đồng lẻ còn dư đi lần lượt vào những dòng bị làm tròn xuống nhiều nhất (hòa thì dòng đứng trước). Hai tính chất được ghim bằng test viết tay số: tổng các phần bằng đúng `orders.discount`, và không dòng nào giảm quá giá của nó (một phần chỉ chạm giá khi giảm bằng cả tổng tiền, lúc đó mọi phần đều chẵn và không dư đồng nào). Đơn cũ hơn cột này được migration chia lại bằng đúng luật ấy — chép vào migration chứ không import, vì migration phải giữ nguyên nghĩa lúc nó chạy.

**Số liệu dashboard giảng viên** (24/09/2026, `app/services/instructor_stats.py`, không có bảng riêng — mọi con số là phép gộp trên bảng đã có):

- **Doanh thu** = `sum(order_items.unit_price - order_items.discount)` của các khóa thuộc giảng viên, chỉ đơn `status='paid'`, theo `paid_at`. Là số tiền người mua thực trả, **chưa trừ phí sàn** — chia sẻ doanh thu nằm ở "Hướng phát triển" của đề cương.
- **Một ngày là một ngày ở Việt Nam**: gom nhóm bằng `date_trunc(..., timezone('Asia/Ho_Chi_Minh', ...))`, nên đơn trả lúc 00:10 ở Hà Nội thuộc ngày mới dù ở UTC vẫn là 17:10 hôm trước. Dùng **tên** múi giờ chứ không dùng chuỗi `'+07:00'`: trong `AT TIME ZONE`, Postgres hiểu chuỗi offset theo kiểu POSIX (dương là **phía tây** Greenwich), lệch 14 giờ. Test đã chạy thử cả hai cách sai để chắc là bắt được.
- **Học viên mới** = người có lượt ghi danh **đầu tiên** vào một khóa của giảng viên này nằm trong kỳ. Học hai khóa cùng buổi chiều là hai lượt ghi danh nhưng một học viên mới.
- **Tỉ lệ hoàn thành** = lượt ghi danh có `completed_at` / tổng lượt ghi danh; **tiến độ trung bình** = số bài đã xong / số bài của khóa, trên mọi lượt ghi danh, trong đó lượt đã hoàn thành tính là xong mọi bài (`completed_at` là nguồn có thẩm quyền; khóa thêm bài sau đó không làm ai "chưa xong" lại, và trên một dòng tiến độ không bao giờ thấp hơn tỉ lệ hoàn thành). Cả hai tính từ trước tới nay và trả `null` chứ không phải 0 khi không có ai để đo.
- Kỳ `7d`/`30d`/`90d` chia theo ngày, `12m` chia theo tháng dương lịch (tính cả tháng hiện tại); "kỳ trước" là khoảng cùng độ dài ngay trước đó. Khóa đã gỡ vẫn nằm trong bảng từng khóa chừng nào còn học viên hoặc từng bán được.

---

## 7. Cộng đồng, thông báo, gamification, AI

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `qa_threads` | `lesson_id`, `user_id`, `title` (varchar 200), `body`, `resolved_at` | **`ix_qa_threads_lesson_created`** (`lesson_id`,`created_at`); CHECK `length(title) > 0`, `length(body) > 0` | lesson → CASCADE, user → CASCADE | Một câu hỏi về **một bài học**. `resolved_at` = lúc người hỏi (hoặc giảng viên của khóa) bấm "đã giải quyết", bấm lần hai giữ nguyên mốc đầu. Index có thêm `created_at` so với thiết kế ban đầu (`ix_qa_threads_lesson_id`): mọi lần đọc là "câu hỏi của bài này, mới nhất trước", một B-tree trả lời cả lọc lẫn thứ tự. Số vote, số trả lời và "giảng viên đã trả lời chưa" **tính lúc đọc** bằng subquery, không có cột đếm để phải giữ khớp |
| `qa_replies` | `thread_id`, `user_id`, `body`, `is_instructor_reply` | **`ix_qa_replies_thread_created`** (`thread_id`,`created_at`); CHECK `length(body) > 0` | thread → CASCADE, user → CASCADE | `is_instructor_reply` tính lúc tạo (người trả lời là `courses.instructor_id` lúc đó), không join lại — huy hiệu nói ai trả lời **thay mặt khóa học** vào lúc ấy. Admin là staff nhưng không phải người dạy khóa, nên trả lời của admin không mang huy hiệu. Đọc theo thứ tự viết (cuộc trò chuyện), index cũng phục vụ đếm và `EXISTS` trên danh sách |
| `qa_votes` | `thread_id`, `user_id` | `uq_qa_votes_thread_user` | thread → CASCADE, user → CASCADE | **Không có cột `value`** (thiết kế ban đầu có `CHECK value IN (-1,1)`): kế hoạch chỉ cần upvote, và một cột chỉ có thể mang giá trị 1 là cách viết thứ hai của "dòng này tồn tại". Điểm = số dòng; unique giữ mỗi người một phiếu, vote là `INSERT … ON CONFLICT DO NOTHING` như bookmark. Người hỏi không vote câu của mình (409 ở service) |
| `notifications` | `user_id`, `type` (varchar 40), `payload` (JSONB, mặc định `'{}'`), `read_at` | `ix_notifications_user_unread` (`user_id`,`created_at DESC`) partial `WHERE read_at IS NULL`; **`ix_notifications_user_created`** (`user_id`,`created_at DESC`, không partial — thêm ở `c7c21bbd1a9b`); **`ck_notifications_type`** (`type IN ('qa_reply','qa_question','course_approved','course_rejected','course_taken_down')`); **`ck_notifications_payload_object`** (`jsonb_typeof(payload) = 'object'`) | user → CASCADE | Dựng ở revision `8f1cea268f50` cùng Q&A vì câu trả lời là thứ đầu tiên cần báo cho ai đó; chuông + danh sách là task kế tiếp. Ghi **trong cùng transaction** với việc được báo (trả lời rollback thì không ai được báo). `payload` là **ảnh chụp** — id để dựng link và chữ để hiện (tiêu đề câu hỏi, tên người trả lời), chép lúc ghi; câu hỏi bị sửa/xóa sau đó thì thông báo vẫn đọc như lúc nó xảy ra. `type` là danh sách đóng: mỗi loại có payload riêng, loại không ai biết hiển thị là dòng không ai đọc được, nên thêm loại là một migration có chủ đích. `qa_reply` = người khác trả lời câu bạn hỏi (tự trả lời câu mình thì không); `qa_question` (thêm ở `c7c21bbd1a9b`) = học viên đặt câu hỏi trong khóa bạn dạy (giảng viên tự hỏi thì không). Ba loại thêm ở `6e27fe4795b3` báo giảng viên về quyết định của admin, ghi cùng transaction với quyết định: `course_approved` (payload `course_id`, `course_slug`, `course_title`), `course_rejected` và `course_taken_down` (payload `course_id`, `course_title`, `reason` — nguyên văn lý do admin viết). **Đánh dấu đã đọc idempotent và giữ `read_at` đầu tiên**; "đọc hết" là một câu `UPDATE … WHERE read_at IS NULL` |
| `reports` | `reporter_id`, `target_type`, `target_id`, `reason` (varchar 20), **`details`** (TEXT, null được), `status` (mặc định `'open'`), **`resolved_by`**, **`resolved_at`**, **`resolution_note`**, **`content_removed`** (bool, mặc định `false`) | **`ix_reports_status`** (`status`,`created_at`); **`ix_reports_target`** (`target_type`,`target_id`); **`uq_reports_pending_per_reporter`** (`reporter_id`,`target_type`,`target_id`) partial `WHERE status IN ('open','reviewing')`; CHECK `ck_reports_target_type` (`course`,`review`,`qa_thread`,`qa_reply`), **`ck_reports_reason`** (`spam`,`offensive`,`copyright`,`misleading`,`other`), `ck_reports_status`, **`ck_reports_other_has_details`** (`reason <> 'other' OR details IS NOT NULL`), **`ck_reports_closed_at`** (`(status IN ('resolved','dismissed')) = (resolved_at IS NOT NULL)`), **`ck_reports_removed_only_when_resolved`** (`NOT content_removed OR status = 'resolved'`) | reporter → CASCADE, resolved_by → SET NULL | Dựng ở revision `6e27fe4795b3` (30/09/2026). `target_id` là UUID **không có FK** (đa hình) — nội dung có thể bị xóa (bởi tác giả, hoặc bởi chính admin xử lý báo cáo) mà báo cáo vẫn phải còn, vì "đã báo gì, đã xử lý ra sao" là hồ sơ của admin. `reason` là **danh sách đóng** thay vì chữ tự do để hàng đợi đọc được trong một liếc; chữ của người báo cáo nằm ở `details`, bắt buộc khi chọn `other`. **Chỉ báo cáo được thứ mình xem được** (luật đọc có sẵn của từng loại: `courses.get_course_for_viewer`, khóa của đánh giá, `qa.visible_thread`) và không phải của mình (409 `CANNOT_REPORT_OWN_CONTENT`). **Mỗi người một báo cáo đang chờ trên một nội dung**: partial unique + `INSERT … ON CONFLICT DO NOTHING` (409 `ALREADY_REPORTED`), báo lại được sau khi báo cáo cũ đã đóng. **Quyết định là về nội dung, không về một người báo cáo**: xử lý hoặc bỏ qua đóng **mọi** báo cáo đang chờ trên cùng `(target_type, target_id)` bằng một câu `UPDATE` — đó là lý do có `ix_reports_target`. Xử lý kèm gỡ nội dung chạy **cùng transaction** với việc đóng báo cáo: khóa học → `published→draft` + thông báo `course_taken_down` (không xóa mềm, học viên đã mua giữ lượt ghi danh), đánh giá → xóa + tính lại `rating_avg`/`rating_count` như khi tác giả tự rút, câu hỏi Q&A → xóa kèm câu trả lời, câu trả lời → xóa. `content_removed` ghi **điều thật sự xảy ra**: nội dung đã mất từ trước hoặc khóa học không còn đang bán thì vẫn là `false`. Admin thấy nội dung **như hiện tại** (tra theo từng loại cho đúng trang đang đọc), không chép lúc báo cáo |
| `xp_events` | `user_id`, `amount`, `reason`, `ref_type`, `ref_id` | `ix_xp_events_user_created` (`user_id`,`created_at`); `uq_xp_events_ref` (`user_id`,`reason`,`ref_type`,`ref_id`); CHECK `amount > 0`; **`ck_xp_events_reason_ref`** — mỗi `reason` chỉ đi với đúng một `ref_type`: `lesson_completed`↔`lesson`, `quiz_passed`↔`quiz`, `exercise_solved`↔`code_exercise` | user → CASCADE | **Sổ cái append-only, nguồn chân lý duy nhất của XP** — tổng XP là `sum(amount)`, không lưu tổng chạy ở đâu cả; **không có `updated_at`** (giống `payment_events`). Unique là luật "chỉ lần đầu": cộng XP là `INSERT … ON CONFLICT DO NOTHING`, nên bỏ tick rồi tick lại, qua quiz hai lần hay job chấm bài giao hai lần đều chỉ ra một dòng. `amount` lưu theo từng dòng (10 / 20 / 30 lúc ghi) để đổi mức thưởng về sau không viết lại lịch sử. `ref_id` **không có FK** (đa hình) — xóa bài học thì XP vẫn còn, vì học viên đã thật sự học xong nó. Chỉ cộng cho người **có ghi danh**: giảng viên tự làm thử khóa mình được chấm như mọi người nhưng không được XP |
| `streaks` | `user_id`, `current_streak`, `longest_streak`, `last_active_date` (DATE) | **`uq_streaks_user_id`** — 1 dòng/user; **`ck_streaks_counts`** (`current_streak >= 1 AND longest_streak >= current_streak`) | user → CASCADE | Dòng sinh ra ở ngày hoạt động đầu tiên nên chuỗi đã lưu không bao giờ bằng 0. **Không job nào chạy lúc nửa đêm để cắt chuỗi**: người đọc tự suy — `last_active_date` trước hôm qua thì chuỗi hiện tại đọc là 0, bằng hôm qua thì vẫn còn (hôm nay chưa hết). Cập nhật bằng **một câu** `INSERT … ON CONFLICT DO UPDATE … WHERE last_active_date < ngày` để hai request cùng lúc không cùng đọc "hôm qua" rồi cùng cộng; ngày cũ hơn tới muộn (request vắt qua nửa đêm) không làm gì. **Ngày = ngày ở Việt Nam** (UTC+7 cố định — Việt Nam không có giờ mùa hè). Ngày được tính là ngày học viên **nộp** một thứ: hoàn thành bài học, nộp lượt quiz (kể cả trượt, trừ nộp quá giờ), nộp bài code (không tính chạy thử); xem video mà chưa xong thì không tính |
| `doc_chunks` | `course_id`, `lesson_id`, **`chunk_index`**, `content`, `token_count`, `embedding` (`vector(768)`), **`embedding_model`** | **`uq_doc_chunks_lesson_chunk`** (`lesson_id`,`chunk_index`); `ix_doc_chunks_course_id`; `ix_doc_chunks_embedding` HNSW (`embedding` vector_cosine_ops); CHECK `chunk_index >= 0`, `length(content) > 0`, `token_count > 0` | course → CASCADE, lesson → CASCADE | Xóa/ingest lại theo `lesson_id` — kể cả khi bài học hết chữ: lần ingest sau xóa chunk cũ của nó thay vì để lại cho chatbot trích dẫn (từ 18/09/2026; unpublish thì **không** xóa, truy vấn top-k phải tự lọc khóa đang published) — và unique (`lesson_id`,`chunk_index`) làm việc ingest lại **idempotent** — job chết giữa chừng rồi chạy lại không nhân đôi chunk. `lesson_id` **không null**: chunk không trích nguồn được thì không dùng được, mà "trả lời kèm trích nguồn" là điều kiện gate của Phase 4. `course_id` là cột **denormalize** (đi vòng lesson → section → course vẫn ra) vì mọi truy vấn top-k đều lọc theo nó, trả giá hai phép join quanh một lần quét vector là cái giá trả mãi mãi. **768 chiều**: cỡ gốc của `text-embedding-004`, cũng là mức cắt Matryoshka hợp lệ của `gemini-embedding-001`, và nằm dưới trần 2000 chiều mà index HNSW của pgvector chấp nhận cho kiểu `vector` (3072 chiều thì phải đổi sang `halfvec`). **`embedding_model`** ghi model đã sinh ra vector: hai model cùng số chiều vẫn đặt cùng một câu ở hai chỗ khác nhau, bảng trộn cả hai trả kết quả vô nghĩa mà không báo lỗi gì |
| `chat_sessions` | `user_id`, `course_id`, **`title`** (varchar 120, null được) | `ix_chat_sessions_user_course` (`user_id`,`course_id`) | user → CASCADE, course → CASCADE | Một cuộc trò chuyện của một học viên trong **một** khóa — khóa nằm trên phiên chứ không trên từng tin, vì nó quyết định chunk nào được trích. `title` = câu hỏi đầu tiên cắt cho vừa, null tới khi có câu được trả lời. `updated_at` được đặt bằng lúc câu trả lời gần nhất xong, danh sách phiên sắp theo nó |
| `chat_messages` | `session_id`, `role`, `content`, `cited_lesson_ids` (JSONB, mặc định `'[]'`) | `ix_chat_messages_session_created` (`session_id`,`created_at`); CHECK `role IN ('user','assistant')`, `length(content) > 0`, `jsonb_typeof(cited_lesson_ids) = 'array'` | session → CASCADE | Ghi **theo cặp, sau khi trả lời xong**: câu trả lời hỏng giữa chừng thì cả câu hỏi cũng không được lưu, để lịch sử (gửi lại làm ngữ cảnh ở các lượt sau) không có câu hỏi mồ côi. Hai dòng cùng transaction thì `now()` trùng nhau, nên service tự đặt `created_at`: câu hỏi = lúc tới, câu trả lời = lúc xong. `cited_lesson_ids` là mảng UUID các bài câu trả lời **thật sự** trích (`[n]` đọc từ chữ), không có FK — bài bị xóa sau này để lại id treo, trung thực hơn là sửa lại lời trợ giảng đã nói |
| `course_embeddings` | `course_id`, **`source_text`**, `embedding` (`vector(768)`), **`embedding_model`** | **`uq_course_embeddings_course_id`** (`course_id`, unique — 1 dòng/khóa); `ix_course_embeddings_embedding` HNSW (`embedding` vector_cosine_ops); CHECK `length(source_text) > 0` | course → CASCADE | Nửa **content-based** của recommender: mỗi khóa một vector của `title + subtitle + danh mục + description`, so cosine để ra "Khóa học tương tự". Khác `doc_chunks` ở đơn vị — thứ đem so ở đây **là cả khóa học**, nên khóa nào cũng chỉ một điểm để đo. `source_text` lưu **nguyên văn chuỗi đã nhúng**, không băm: so `source_text == course_text(...)` là thứ quyết định có tốn quota nhúng lại hay không, băm cũng trả lời được câu đó nhưng làm câu "vì sao khóa này bị nhúng lại" thành không trả lời được. Cắt ở 1000 token (≈3500 ký tự) — quá trần 2048 token của model thì API **cắt im lặng**, để lại một khóa nhúng dở trông y hệt khóa nhúng đủ. Nhúng bằng `taskType=SEMANTIC_SIMILARITY` (hai vế cùng loại) chứ không phải `RETRIEVAL_DOCUMENT` như `doc_chunks`. Unpublish **không** xóa vector (xuất bản lại sẽ phải trả tiền nhúng lần nữa) — lọc khóa `published` nằm trong chính câu truy vấn, giống `doc_chunks` |
| `recommendations` | `user_id`, `course_ids` (JSONB), `strategy`, `computed_at` | `uq_recommendations_user_strategy` (`user_id`,`strategy`) | user → CASCADE | Cache batch; bản nóng ở Redis |
| `banners` | `title`, `image_url`, `link_url`, `position`, `is_active`, `starts_at`, `ends_at` | `ix_banners_active` partial `WHERE is_active` | — | **Bảng mới** — banner trang chủ do admin quản lý ([Phase 5](plan/phase-5-commerce-admin.md)). Nằm ở mục cắt giảm số 4, bỏ được mà không ảnh hưởng bảng khác |

---

## 8. Cột trạng thái — giá trị hợp lệ & chuyển trạng thái

| Cột | Giá trị hợp lệ | Chuyển hợp lệ | Ai đổi |
|---|---|---|---|
| `courses.status` | `draft`, `pending_review`, `published`, `rejected` | draft \| rejected→pending_review (gửi duyệt); pending_review→published \| rejected; published→draft (gỡ khỏi sàn) | Giảng viên gửi duyệt và tự gỡ; **admin** duyệt, từ chối (kèm lý do) và gỡ (kèm lý do) — `app/services/moderation.py`, khóa dòng `FOR UPDATE` trước khi đọc trạng thái. Không còn cờ auto-approve (bỏ 30/09/2026): gửi duyệt luôn dừng ở `pending_review`, và job ingest RAG + nhúng khóa học chỉ được xếp khi admin **duyệt** |
| `video_assets.status` | `uploading`, `processing`, `ready`, **`failed`** | uploading→processing→ready \| failed; failed→processing (thử lại) | Worker transcode |
| `submissions.status` | `pending`, `running`, `done`, `error` | pending→running→done \| error | Worker chấm bài |
| `submissions.verdict` | `AC`,`WA`,`TLE`,`MLE`,`RE`,`CE`,`SE` | Chỉ khác NULL khi `status='done'` | Worker chấm bài |
| `orders.status` | `pending`, `paid`, `failed`, `refunded` | pending→paid \| failed; paid→refunded | Chỉ đổi sang `paid` khi verify chữ ký IPN thành công |
| `reports.status` | `open`, `reviewing`, `resolved`, `dismissed` | open→reviewing (tùy chọn, "đang có người xem"); open \| reviewing→resolved \| dismissed. Đã đóng thì không mở lại (409 `REPORT_ALREADY_CLOSED`) | Admin |
| `enrollments` | không có cột status | `completed_at` khác NULL = hoàn thành 100%. **Tính ra chứ không ai khai báo**: `app/services/progress.py` đặt/xóa nó mỗi khi một bài học đổi trạng thái hoàn thành, nên hai con số không bao giờ lệch nhau | Service tiến độ |

`failed` của `video_assets` và bảng giá trị của `reports.status` là hai chỗ bản cũ bỏ trống — không có chúng thì lỗi transcode và hàng đợi báo cáo vi phạm đều không biểu diễn được.

---

## 9. Index và truy vấn tương ứng

Mỗi index dưới đây gắn với một truy vấn có thật trong kế hoạch. Index không giải thích được thì không thêm.

| Index | Bảng | Cột | Phục vụ truy vấn | Phase |
|---|---|---|---|---|
| `ix_courses_listing` | courses | (`status`,`published_at DESC`) partial `WHERE deleted_at IS NULL` | Danh sách khóa học mới nhất | 2 |
| `ix_courses_rating` | courses | (`status`,`rating_avg DESC`) partial như trên | Sắp xếp theo đánh giá | 2 |
| `ix_courses_search_vector` | courses | GIN (`search_vector`) | Full-text search | 2 |
| `ix_courses_category_id` | courses | `category_id` | Lọc theo danh mục | 2 |
| `ix_courses_instructor_id` | courses | `instructor_id` | Dashboard giảng viên | 2 |
| `ix_enrollments_user_id` | enrollments | `user_id` | Trang "Khóa học của tôi" | 2 |
| ~~`ix_lesson_progress_enrollment`~~ | lesson_progress | — | **Không tạo.** `uq_lesson_progress_enrollment_lesson` đã dẫn đầu bằng `enrollment_id` nên index này là bản sao thứ hai của cùng một B-tree, phải trả giá ở mọi lần heartbeat mà không ai đọc | 2 |
| `ix_submissions_user_exercise` | submissions | (`user_id`,`exercise_id`,`created_at DESC`) partial `WHERE is_trial = false` | Lịch sử nộp bài — điều kiện `where` vì lịch sử không bao giờ hiện bài chạy thử, mà học viên dùng "chạy thử" nhiều hơn hẳn | 3 |
| `ix_submissions_status` | submissions | `status` partial `WHERE status IN ('pending','running')` | Giám sát hàng đợi chấm | 3 |
| `ix_doc_chunks_course_id` | doc_chunks | `course_id` | Giới hạn top-k trong phạm vi một khóa học | 4 |
| `ix_doc_chunks_embedding` | doc_chunks | HNSW (`embedding` vector_cosine_ops) | Truy vấn top-k RAG — lớp toán tử phải khớp toán tử `<=>` của truy vấn, sai thì planner bỏ qua index và quét tuần tự mà không báo lỗi; đã xác nhận bằng `EXPLAIN` trong `docs/report/assets/phase-4/hnsw-index.txt` | 4 |
| `uq_course_embeddings_course_id` | course_embeddings | `course_id` (unique) | Một vector/khóa — rebuild ghi đè tại chỗ, có dòng thứ hai thì "vector của khóa này" thành câu hỏi về thứ tự chèn | 4 |
| `ix_course_embeddings_embedding` | course_embeddings | HNSW (`embedding` vector_cosine_ops) | "Khóa học tương tự" — cùng lý do khớp lớp toán tử như `ix_doc_chunks_embedding`. Với catalogue vài chục khóa Postgres vẫn quét tuần tự và **nên** thế; index dựng cho cỡ vài nghìn dòng chứ không phải cỡ đang test | 4 |
| `ix_notifications_user_unread` | notifications | (`user_id`,`created_at DESC`) partial `WHERE read_at IS NULL` | Số trên chuông (`GET /notifications/unread-count`, hỏi mỗi phút) và tab "Chưa đọc" | 5 |
| `ix_notifications_user_created` | notifications | (`user_id`,`created_at DESC`) | Trang `/thong-bao` và dropdown của chuông: mọi thông báo của một người, mới nhất trước — index partial ở trên không chứa dòng đã đọc. Cũng là index tìm dòng của một user khi user bị xóa (CASCADE) | 5 |
| `ix_qa_threads_lesson_created` | qa_threads | (`lesson_id`,`created_at`) | Hỏi đáp của một bài học, mới nhất trước (`GET /lessons/{id}/qa-threads`) | 5 |
| `ix_qa_replies_thread_created` | qa_replies | (`thread_id`,`created_at`) | Câu trả lời của một câu hỏi theo thứ tự viết; đếm trả lời và "giảng viên đã trả lời" trên danh sách | 5 |
| `ix_xp_events_user_created` | xp_events | (`user_id`,`created_at`) | Lịch sử XP mới nhất trước (`GET /users/me/xp-events`); tổng XP theo tuần/tháng và rebuild leaderboard | 5 |
| `ix_orders_user_status` | orders | (`user_id`,`status`) | Lịch sử đơn hàng | 5 |
| `ix_order_items_course_id` | order_items | `course_id` | Doanh thu theo khóa trên dashboard giảng viên — `uq_order_items_order_course` dẫn đầu bằng `order_id` nên không dùng được | 5 |
| `ix_enrollments_course_created` | enrollments | (`course_id`,`created_at`) | Ghi danh mới theo khóa và theo thời gian trên dashboard giảng viên — `uq_enrollments_user_course` dẫn đầu bằng `user_id` | 5 |

---

## 10. Điểm cần chú ý khi hiện thực

- **`search_vector`** cập nhật bằng trigger Postgres (không phụ thuộc service nào quên gọi); index GIN.
- **Số liệu denormalize** (`rating_avg`, `rating_count`, `students_count`, `duration_total_s`) cập nhật trong cùng transaction với review/enrollment. Kèm `backend/scripts/rebuild_course_stats.py` tính lại từ nguồn — chạy được bất cứ lúc nào, dùng luôn làm bằng chứng "số liệu tái tạo được" cho báo cáo.
- **Leaderboard:** nguồn chân lý là `xp_events`, Redis sorted set chỉ là view (`services/leaderboard.py`).
  - Ba bảng: `lb:xp:week:<năm ISO>-W<tuần>` (thứ Hai → Chủ nhật), `lb:xp:month:<YYYY-MM>` và `lb:xp:all`. Tuần và tháng tính theo giờ Việt Nam. Key tuần sống 35 ngày, key tháng 400 ngày, `all` không hết hạn.
  - **Cộng sau commit:** `award()` chỉ ghi tạm vào `session.info`, bên gọi `commit()` xong mới `publish_awards` (`ZINCRBY`). Rollback thì phần đã ghi tạm bị bỏ, nên Redis không nhận điểm của transaction không tồn tại. Redis lỗi thì chỉ ghi log, request vẫn thành công.
  - **Dựng lại** từ `xp_events` bằng `ZADD` vào key tạm rồi `RENAME` đè lên (người đọc không bao giờ thấy bảng dựng dở). Bảng được dựng lại trong ba trường hợp: lúc đọc nếu thiếu marker `<key>:built` (Redis vừa restart/flush), mỗi đêm 03:30 bằng Celery beat, và khi chạy tay `scripts.rebuild_leaderboard`.
  - **Chấp nhận lệch tạm thời:** điểm cộng rơi đúng vào khoảng giữa câu truy vấn và cú `RENAME` của một lần dựng lại sẽ mất cho tới lần dựng sau. Người dùng đã xóa vẫn còn dòng trong Redis tới lần dựng sau; trang bỏ qua dòng đó nhưng hạng của người phía dưới vẫn tính nó.
- **`payment_events` append-only**; trạng thái `orders` chỉ đổi khi verify chữ ký IPN thành công.
- **Soft delete:** chỉ `courses`. Mọi truy vấn public đi qua một hàm dùng chung đã lọc `deleted_at IS NULL` — không rải điều kiện này khắp nơi rồi quên một chỗ.
- **`gen_random_uuid()`** không cần extension: từ Postgres 13 nó là hàm dựng sẵn, và dự án chốt Postgres 16. `pgcrypto` vì thế **không** được bật — bản đặc tả trước ghi cần là nhầm.
- **Extension bật trong migration đầu tiên:** `vector` (embedding RAG, Phase 4), `unaccent` và `pg_trgm` (tìm kiếm tiếng Việt, Phase 2). Dùng `CREATE EXTENSION IF NOT EXISTS` nên chạy được cả trên DB đã có sẵn extension (máy dev qua `infra/postgres/init/`) lẫn DB trắng (CI, VPS). Chiều `downgrade` cố tình **không** drop extension.
- **Migration đầu tiên (Phase 1)** chỉ tạo `users`, `categories`, `courses`. Các bảng còn lại tạo đúng phase dùng tới chúng, theo vertical slice.

## 11. Trạng thái hiện thực

| Nhóm bảng | Trạng thái | Revision |
|---|---|---|
| `users`, `categories`, `courses` | ✅ đã có trong DB | `576c29b76f4e` |
| `refresh_tokens` | ✅ đã có trong DB | `adab7334f140` |
| `course_sections`, `lessons`, `video_assets` | ✅ đã có trong DB | `f7d37ee5caf2` |
| Trigger `courses_search_vector_update` | ✅ đã có trong DB | `0c55c726cc39` |
| `enrollments` | ✅ đã có trong DB | `991bc02a257b` |
| `lesson_progress` | ✅ đã có trong DB | `b6dea13f199c` |
| `notes`, `bookmarks` | ✅ đã có trong DB | `852a7bf2510b` |
| `reviews` | ✅ đã có trong DB | `7b60984bf439` |
| `code_exercises`, `test_cases`, `submissions`, `submission_results` | ✅ đã có trong DB | `86a5023fa0b8`, `123eb876dda5` (`is_trial`) |
| `doc_chunks` | ✅ đã có trong DB | `a03e9e2f9ce9` |
| `quizzes`, `quiz_questions`, `quiz_attempts` | ✅ đã có trong DB | `50ccf4fc23fb`, `ca9e1c7ffdbb` (cột duyệt câu AI) |
| `chat_sessions`, `chat_messages` | ✅ đã có trong DB | `42fff7804290` |
| `course_embeddings` | ✅ đã có trong DB | `17e181ed9f26` |
| `recommendations` | ⛔ **không dựng bảng** — kết quả gợi ý nằm ở cache Redis (`rec:v2:user:*` từ 20/09/2026 — tiền tố lên v2 khi mỗi mục mang thêm `sources`, mục cũ v1 bị bỏ lại và tự hết hạn; TTL 48 giờ), job Celery beat dựng lại mỗi đêm; bảng chỉ cần nếu sau này phải truy vết gợi ý cũ. Lý do: `docs/report/assets/decisions.md`, mục "Gợi ý tính offline, endpoint chỉ đọc cache"; số đo ở `phase-4/recommendation-batch.txt` | |
| `carts`, `cart_items`, `wishlists` | ✅ đã có trong DB | `45c681ca42af` |
| `coupons`, `coupon_courses` | ✅ đã có trong DB | `d23158098a8c` |
| `orders`, `order_items`, `payment_events` | ✅ đã có trong DB | `99c7ba304d8d`, `3f7c33c23e64` (`order_items.discount` + hai index cho dashboard giảng viên) |
| `xp_events`, `streaks` | ✅ đã có trong DB | `e9d78af241e6` |
| `certificates` | ✅ đã có trong DB | `b6fc99d6b6af` (thêm 3 cột đóng băng tên/khóa/giảng viên) |
| `qa_threads`, `qa_replies`, `qa_votes`, `notifications` | ✅ đã có trong DB | `8f1cea268f50` (`qa_votes` không có cột `value` — chỉ upvote), `c7c21bbd1a9b` (index danh sách thông báo + loại `qa_question`) |
| `reports` | ✅ đã có trong DB | `6e27fe4795b3` (thêm `details` + 4 cột hồ sơ xử lý; cùng revision mở rộng `ck_notifications_type`) |
| `banners` | ⏳ Phase 5 | |

`search_vector` **đã có hành vi** từ revision `0c55c726cc39` (tính năng danh sách khóa học, Phase 2 tuần 5):

- Trigger `courses_search_vector_update` chạy `BEFORE INSERT OR UPDATE OF title, subtitle, description`, gọi hàm `courses_search_vector_refresh()`.
- Cấu hình FTS: `to_tsvector('simple', unaccent(...))` — `simple` vì văn bản là tiếng Việt, cấu hình `english` sẽ stem sai; `unaccent` để người gõ "lap trinh" vẫn ra "Lập trình". **Phía truy vấn bắt buộc dùng đúng cặp này** (`websearch_to_tsquery('simple', unaccent(q))`, xem `app/services/catalog.py`), lệch một bên là không bao giờ khớp.
- Trọng số `A`/`B`/`C` cho `title`/`subtitle`/`description`, `ts_rank` xếp hạng theo đó.
- Chọn trigger thay vì generated column vì `unaccent()` là STABLE chứ không IMMUTABLE, Postgres từ chối nó trong generated column lẫn biểu thức index.

`students_count` **đã có hành vi** từ revision `991bc02a257b` (ghi danh, Phase 2 tuần 5): tăng bằng `UPDATE ... SET students_count = students_count + 1` trong cùng transaction với dòng `enrollments`, chứ không đọc-sửa-ghi trong Python — hai người ghi danh cùng lúc sẽ mất một lượt. Câu lệnh đó ghim luôn `updated_at` về chính nó, vì cột này là "khóa học đổi lần cuối lúc nào" và người khác đăng ký học không phải là một thay đổi của khóa học.

`rating_avg`, `rating_count` **đã có hành vi** từ revision `7b60984bf439` (đánh giá khóa học, Phase 2 tuần 5), xem `app/services/reviews.py`. Phép tính lại nằm ở `app/services/course_stats.py` từ 19/09/2026:

- **Tính lại, không cộng dồn.** `students_count` cộng `+ 1` được vì ghi danh chỉ đi một chiều; điểm trung bình đổi cả hai chiều khi người dùng sửa hoặc xóa đánh giá, nên mỗi lần ghi đều chạy lại `round(avg(rating), 2)` và `count(*)` trên toàn bộ `reviews` của khóa học đó.
- **Khóa dòng `courses` trước khi tính lại** (`SELECT ... FOR UPDATE`). Hai người đánh giá cùng lúc nếu không khóa sẽ mỗi người tính trung bình trên một ảnh chụp chưa thấy dòng của người kia, và lượt ghi sau xóa lượt ghi trước khỏi tổng. Tranh chấp chỉ trong phạm vi một khóa học và vùng khóa dài đúng hai câu lệnh.
- Câu `UPDATE` ghim `updated_at` về chính nó, cùng lý do như `students_count`: người khác đánh giá không phải là một thay đổi của khóa học.
- Quyền ghi: chỉ học viên **đã ghi danh** (403 `NOT_ENROLLED`), và giảng viên không đánh giá được khóa của chính mình (409 `CANNOT_REVIEW_OWN_COURSE`). Khóa học không nhìn thấy được trả 404 trước mọi kiểm tra khác, để endpoint này không thành cách dò khóa học nháp.

`duration_total_s` **đã có hành vi** từ 19/09/2026 (không đổi schema, không có revision mới), xem `app/services/course_stats.py`:

- **Nguồn:** `sum(video_assets.duration_s)` của các video `status = 'ready'` gắn vào bài học của khóa. Video đang chuyển mã chưa có độ dài, video `failed` sẽ không bao giờ phát được, nên cả hai không tính.
- **Tính lại, không cộng dồn**, trong cùng transaction với thay đổi, ở bốn chỗ: worker transcode xong (cả khi `failed`), thay video (asset cũ bị xóa lúc cấp URL upload mới), xóa bài học có video, xóa chương. Cùng quy tắc với `rating_avg`: khóa dòng `courses` trước khi tính, và ghim `updated_at`. Worker chạy nền xong việc cũng không phải là giảng viên sửa khóa học.

`video_assets.transcript_key` **đã có hành vi** từ 19/09/2026 (cột có sẵn từ `f7d37ee5caf2`, không có revision mới), xem `app/services/transcripts.py`:

- Trỏ tới tệp **gốc** giảng viên tải lên, lưu cạnh video: `videos/<asset>/transcript.srt` hoặc `.txt`. Dòng thời gian được giữ để về sau làm phụ đề và trích nguồn tới từng phút.
- Chỉ ghi sau khi tệp đã lên bucket thành công. Bucket từ chối thì hàng giữ nguyên. Tải lại ở định dạng khác thì tệp cũ bị xóa.
- Thuộc về asset. Thay video là xóa asset cũ cùng mọi object dưới prefix của nó, transcript đi theo. Ingest đọc lại tệp từ bucket. Đọc không được thì bài đó giữ nguyên chunk cũ (`unreadable`), không bị coi là hết chữ.

`backend/scripts/rebuild_course_stats.py` (`--dry-run` để chỉ báo) tính lại cả bốn cột từ nguồn cho mọi khóa, kể cả khóa đã xóa mềm. Script dùng đúng các định nghĩa mà đường ghi dùng, khóa dòng trước khi đọc, và in ra từng số đã sửa. Chạy trên CSDL lành mạnh thì báo 0 chỗ lệch, và đó là bằng chứng "số liệu tái tạo được": `docs/report/assets/phase-4/course-stats-rebuild.txt`. `scripts/seed_courses.py` và `scripts/seed_interactions.py` cũng tính lại qua module này thay vì tự viết phép tính riêng.
