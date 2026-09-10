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
| `rejection_reason` | TEXT | ✓ | | Bắt buộc khi `status='rejected'` |
| `published_at` | TIMESTAMPTZ | ✓ | | Bắt buộc khi `status='published'` |
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
| `certificates` | `enrollment_id`, `code`, `pdf_key`, `issued_at` | **`uq_certificates_code`**, `uq_certificates_enrollment` | enrollment → RESTRICT | `code` là mã công khai trên QR: chuỗi ngẫu nhiên ≥16 ký tự, **không đoán được** |


> **`notes` và `bookmarks` gắn vào `user_id`, không phải `enrollment_id`** — khác `lesson_progress` một cách có chủ ý. Tiến độ mô tả *một lượt học* và đáng bị xóa nếu người ta học lại từ đầu; còn ghi chú là thứ người ta **viết ra**, mất nó vì enrolment bị dựng lại là mất công sức của họ. Quyền viết ghi chú/bookmark cũng chính là quyền *đọc* bài học (chủ khóa học, bài học thử, hoặc đã ghi danh) — không có luật riêng.

---

## 4. Bài tập code & chấm bài ⭐

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `code_exercises` | `lesson_id`, `statement_md`, `language`, `starter_code`, `time_limit_ms`, `memory_limit_mb` | `uq_code_exercises_lesson` (`lesson_id`); `ck_code_exercises_language`; CHECK `time_limit_ms BETWEEN 100 AND 10000`, `memory_limit_mb BETWEEN 16 AND 512` | lesson → CASCADE | Giới hạn có trần cứng để instructor không đặt số làm sập VPS — con số trên form này được nhân với **mọi** học viên nộp bài. Trần chặn hai lớp: Pydantic trả 422, CHECK constraint là lớp cuối |
| `test_cases` | `exercise_id`, `input`, `expected_output`, `is_hidden`, `position`, `score_weight` | `uq_test_cases_position` (`exercise_id`,`position`) — **DEFERRABLE INITIALLY DEFERRED**; CHECK `score_weight > 0` | exercise → CASCADE | `expected_output` của test hidden **không bao giờ** ra khỏi backend — cưỡng chế bằng schema riêng (`TestCaseSample` không có trường nào để chứa nó) chứ không bằng lời hứa của service. `is_hidden` mặc định `true` |
| `submissions` | `user_id`, `exercise_id`, `code`, `language`, `status`, `verdict`, `score`, `run_time_ms`, `peak_memory_mb`, **`message`** | `ck_submissions_verdict_requires_done` CHECK `status='done' OR verdict IS NULL`; `ck_submissions_status`; `ck_submissions_verdict`; `ck_submissions_score` CHECK `score BETWEEN 0 AND 100` | user → CASCADE, exercise → CASCADE | Ngăn worker ghi verdict khi bài chưa chấm xong. **`message`** là cột thêm so với bản thiết kế đầu: CE không có kết quả theo từng test case, thiếu chỗ chứa lời của trình biên dịch thì học viên nhận đúng hai chữ "CE" và không hành động được gì. SE cũng dùng cột này để ghi lỗi phía hệ thống |
| `submission_results` | `submission_id`, `test_case_id`, `verdict`, `run_time_ms`, `stdout_trunc` | `uq_submission_results` (`submission_id`,`test_case_id`); `ck_submission_results_verdict` | submission → CASCADE, test_case → CASCADE | `stdout_trunc` chỉ điền cho test sample — in lại thứ chương trình xuất ra trên input bí mật cũng chính là lộ input, chỉ chậm hơn một nhịp |

---

## 5. Quiz

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `quizzes` | `lesson_id`, `time_limit_s`, `pass_score`, `ai_generated`, `is_published` | `uq_quizzes_lesson` (`lesson_id`); CHECK `pass_score BETWEEN 0 AND 100` | lesson → CASCADE | **`is_published`** là cột mới: quiz sinh bằng AI nằm ở `false` cho tới khi instructor duyệt xong từng câu (yêu cầu của [Phase 4](plan/phase-4-ai-features.md)) |
| `quiz_questions` | `quiz_id`, `question`, `options` (JSONB), `correct_index`, `explanation`, `position` | `uq_quiz_questions_position` (`quiz_id`,`position`); CHECK `correct_index >= 0` | quiz → CASCADE | Service kiểm `correct_index < len(options)` |
| `quiz_attempts` | `quiz_id`, `user_id`, `answers` (JSONB), `score`, `started_at`, `submitted_at` | `ix_quiz_attempts_quiz_user` | quiz → CASCADE, user → CASCADE | `started_at` do backend ghi; hết giờ tính theo `started_at + time_limit_s`, **không tin client** |

---

## 6. Thương mại

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `carts` | `user_id` | **`uq_carts_user_id`** — một giỏ/user | user → CASCADE | |
| `cart_items` | `cart_id`, `course_id` | **`uq_cart_items_cart_course`** — thiếu trong bản cũ | cart → CASCADE, course → CASCADE | |
| `wishlists` | `user_id`, `course_id` | **`uq_wishlists_user_course`** — thiếu trong bản cũ | user → CASCADE, course → CASCADE | |
| `coupons` | `code`, `discount_type`, `value`, `scope`, `max_uses`, `used_count`, `valid_from`, `valid_to` | `uq_coupons_code`; CHECK `value > 0`, `valid_to > valid_from`, `used_count <= max_uses` | — | **`used_count`** là cột mới; tăng bằng `UPDATE … WHERE used_count < max_uses` để tránh vượt lượt khi đồng thời |
| `coupon_courses` | `coupon_id`, `course_id` | PK (`coupon_id`,`course_id`) | CASCADE cả hai | **Bảng mới** — coupon phạm vi khóa học cụ thể. `scope='site'` thì không có dòng nào |
| `orders` | `user_id`, `total`, `coupon_id`, `status`, `payment_provider`, `provider_txn_id`, `paid_at` | **`uq_orders_provider_txn`** (`payment_provider`,`provider_txn_id`) partial `WHERE provider_txn_id IS NOT NULL` | user → RESTRICT, coupon → SET NULL | Đây là chốt chặn idempotent thật cho IPN — không thể chỉ dựa vào code. **`paid_at`** là cột mới |
| `order_items` | `order_id`, `course_id`, `unit_price` | **`uq_order_items_order_course`** — thiếu trong bản cũ | order → CASCADE, course → RESTRICT | `unit_price` là giá tại thời điểm mua, không đọc lại `courses.price` |
| `payment_events` | `order_id`, `provider`, `payload` (JSONB), `signature_valid` | `ix_payment_events_order_id` | order → CASCADE | **Append-only**: không UPDATE, không DELETE |

---

## 7. Cộng đồng, thông báo, gamification, AI

| Bảng | Cột | Khóa & ràng buộc bổ sung | ON DELETE | Ghi chú |
|---|---|---|---|---|
| `qa_threads` | `lesson_id`, `user_id`, `title`, `body`, `resolved_at` | `ix_qa_threads_lesson_id` | lesson → CASCADE, user → CASCADE | |
| `qa_replies` | `thread_id`, `user_id`, `body`, `is_instructor_reply` | `ix_qa_replies_thread_id` | thread → CASCADE, user → CASCADE | `is_instructor_reply` tính lúc tạo, không join lại |
| `qa_votes` | `thread_id`, `user_id`, `value` | `uq_qa_votes_thread_user`; CHECK `value IN (-1,1)` | thread → CASCADE, user → CASCADE | |
| `notifications` | `user_id`, `type`, `payload` (JSONB), `read_at` | `ix_notifications_user_unread` (`user_id`,`created_at DESC`) partial `WHERE read_at IS NULL` | user → CASCADE | |
| `reports` | `reporter_id`, `target_type`, `target_id`, `reason`, `status` | `ix_reports_status`; CHECK `target_type IN ('course','review','qa_thread','qa_reply')` | reporter → CASCADE | `target_id` là UUID không có FK (đa hình) — chấp nhận, admin xử lý thủ công |
| `xp_events` | `user_id`, `amount`, `reason`, `ref_type`, `ref_id` | `ix_xp_events_user_created` (`user_id`,`created_at`); `uq_xp_events_ref` (`user_id`,`reason`,`ref_type`,`ref_id`) | user → CASCADE | Unique chống cộng XP hai lần cho cùng một hành động |
| `streaks` | `user_id`, `current_streak`, `longest_streak`, `last_active_date` | **`uq_streaks_user_id`** — 1 dòng/user | user → CASCADE | |
| `doc_chunks` | `course_id`, `lesson_id`, `content`, `embedding` (vector), `token_count` | `ix_doc_chunks_course_id`; HNSW index trên `embedding` | course → CASCADE, lesson → CASCADE | Xóa/ingest lại theo `lesson_id` |
| `chat_sessions` | `user_id`, `course_id` | `ix_chat_sessions_user_course` | user → CASCADE, course → CASCADE | |
| `chat_messages` | `session_id`, `role`, `content`, `cited_lesson_ids` (JSONB) | `ix_chat_messages_session_created` | session → CASCADE | `cited_lesson_ids` là mảng UUID |
| `recommendations` | `user_id`, `course_ids` (JSONB), `strategy`, `computed_at` | `uq_recommendations_user_strategy` (`user_id`,`strategy`) | user → CASCADE | Cache batch; bản nóng ở Redis |
| `banners` | `title`, `image_url`, `link_url`, `position`, `is_active`, `starts_at`, `ends_at` | `ix_banners_active` partial `WHERE is_active` | — | **Bảng mới** — banner trang chủ do admin quản lý ([Phase 5](plan/phase-5-commerce-admin.md)). Nằm ở mục cắt giảm số 4, bỏ được mà không ảnh hưởng bảng khác |

---

## 8. Cột trạng thái — giá trị hợp lệ & chuyển trạng thái

| Cột | Giá trị hợp lệ | Chuyển hợp lệ | Ai đổi |
|---|---|---|---|
| `courses.status` | `draft`, `pending_review`, `published`, `rejected` | draft→pending_review; pending_review→published \| rejected; rejected→draft; published→draft (gỡ khỏi sàn) | Instructor gửi duyệt, admin duyệt/từ chối |
| `video_assets.status` | `uploading`, `processing`, `ready`, **`failed`** | uploading→processing→ready \| failed; failed→processing (thử lại) | Worker transcode |
| `submissions.status` | `pending`, `running`, `done`, `error` | pending→running→done \| error | Worker chấm bài |
| `submissions.verdict` | `AC`,`WA`,`TLE`,`MLE`,`RE`,`CE`,`SE` | Chỉ khác NULL khi `status='done'` | Worker chấm bài |
| `orders.status` | `pending`, `paid`, `failed`, `refunded` | pending→paid \| failed; paid→refunded | Chỉ đổi sang `paid` khi verify chữ ký IPN thành công |
| `reports.status` | `open`, `reviewing`, `resolved`, `dismissed` | open→reviewing→resolved \| dismissed | Admin |
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
| `ix_submissions_user_exercise` | submissions | (`user_id`,`exercise_id`,`created_at DESC`) | Lịch sử nộp bài | 3 |
| `ix_submissions_status` | submissions | `status` partial `WHERE status IN ('pending','running')` | Giám sát hàng đợi chấm | 3 |
| `ix_doc_chunks_embedding` | doc_chunks | HNSW (`embedding` vector_cosine_ops) | Truy vấn top-k RAG | 4 |
| `ix_notifications_user_unread` | notifications | (`user_id`,`created_at DESC`) partial `WHERE read_at IS NULL` | Chuông thông báo | 5 |
| `ix_xp_events_user_created` | xp_events | (`user_id`,`created_at`) | Rebuild leaderboard, biểu đồ XP | 5 |
| `ix_orders_user_status` | orders | (`user_id`,`status`) | Lịch sử đơn hàng | 5 |

---

## 10. Điểm cần chú ý khi hiện thực

- **`search_vector`** cập nhật bằng trigger Postgres (không phụ thuộc service nào quên gọi); index GIN.
- **Số liệu denormalize** (`rating_avg`, `rating_count`, `students_count`, `duration_total_s`) cập nhật trong cùng transaction với review/enrollment. Kèm `backend/scripts/rebuild_course_stats.py` tính lại từ nguồn — chạy được bất cứ lúc nào, dùng luôn làm bằng chứng "số liệu tái tạo được" cho báo cáo.
- **Leaderboard:** nguồn chân lý là `xp_events`, Redis sorted set chỉ là view; có script rebuild.
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
| Bài tập code, quiz, thương mại, cộng đồng, AI | ⏳ Phase 3–5 | |

`search_vector` **đã có hành vi** từ revision `0c55c726cc39` (tính năng danh sách khóa học, Phase 2 tuần 5):

- Trigger `courses_search_vector_update` chạy `BEFORE INSERT OR UPDATE OF title, subtitle, description`, gọi hàm `courses_search_vector_refresh()`.
- Cấu hình FTS: `to_tsvector('simple', unaccent(...))` — `simple` vì văn bản là tiếng Việt, cấu hình `english` sẽ stem sai; `unaccent` để người gõ "lap trinh" vẫn ra "Lập trình". **Phía truy vấn bắt buộc dùng đúng cặp này** (`websearch_to_tsquery('simple', unaccent(q))`, xem `app/services/catalog.py`), lệch một bên là không bao giờ khớp.
- Trọng số `A`/`B`/`C` cho `title`/`subtitle`/`description`, `ts_rank` xếp hạng theo đó.
- Chọn trigger thay vì generated column vì `unaccent()` là STABLE chứ không IMMUTABLE, Postgres từ chối nó trong generated column lẫn biểu thức index.

`students_count` **đã có hành vi** từ revision `991bc02a257b` (ghi danh, Phase 2 tuần 5): tăng bằng `UPDATE ... SET students_count = students_count + 1` trong cùng transaction với dòng `enrollments`, chứ không đọc-sửa-ghi trong Python — hai người ghi danh cùng lúc sẽ mất một lượt. Câu lệnh đó ghim luôn `updated_at` về chính nó, vì cột này là "khóa học đổi lần cuối lúc nào" và người khác đăng ký học không phải là một thay đổi của khóa học.

`rating_avg`, `rating_count` **đã có hành vi** từ revision `7b60984bf439` (đánh giá khóa học, Phase 2 tuần 5), xem `app/services/reviews.py`:

- **Tính lại, không cộng dồn.** `students_count` cộng `+ 1` được vì ghi danh chỉ đi một chiều; điểm trung bình đổi cả hai chiều khi người dùng sửa hoặc xóa đánh giá, nên mỗi lần ghi đều chạy lại `round(avg(rating), 2)` và `count(*)` trên toàn bộ `reviews` của khóa học đó.
- **Khóa dòng `courses` trước khi tính lại** (`SELECT ... FOR UPDATE`). Hai người đánh giá cùng lúc nếu không khóa sẽ mỗi người tính trung bình trên một ảnh chụp chưa thấy dòng của người kia, và lượt ghi sau xóa lượt ghi trước khỏi tổng. Tranh chấp chỉ trong phạm vi một khóa học và vùng khóa dài đúng hai câu lệnh.
- Câu `UPDATE` ghim `updated_at` về chính nó, cùng lý do như `students_count`: người khác đánh giá không phải là một thay đổi của khóa học.
- Quyền ghi: chỉ học viên **đã ghi danh** (403 `NOT_ENROLLED`), và giảng viên không đánh giá được khóa của chính mình (409 `CANNOT_REVIEW_OWN_COURSE`). Khóa học không nhìn thấy được trả 404 trước mọi kiểm tra khác, để endpoint này không thành cách dò khóa học nháp.

Còn lại của `courses` chưa có hành vi:

- `duration_total_s` — chờ tổng thời lượng video được cộng khi asset chuyển `ready`.

Chưa có script `rebuild_course_stats.py` như mục 10 mô tả: nó tính lại cả bốn cột nên chỉ viết được khi `duration_total_s` đã có nguồn.
