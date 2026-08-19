# Thiết kế CSDL

> File này phải luôn khớp với schema thật (xem skill `db-migration`). ERD chi tiết vẽ ở Phase 1; dưới đây là danh mục bảng theo nhóm nghiệp vụ.

## Quy ước chung

PK `id UUID`; mọi bảng có `created_at`, `updated_at`; tiền `NUMERIC(12,2)` VND; tên bảng snake_case số nhiều.

## Nhóm bảng

### Người dùng & phân quyền
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| users | email, password_hash (nullable nếu OAuth), full_name, avatar_url, role (`student`/`instructor`/`admin`), oauth_provider, oauth_sub | Một role duy nhất/user cho đơn giản |
| refresh_tokens | user_id, token_hash, expires_at, revoked_at | Hoặc lưu Redis |

### Danh mục khóa học
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| categories | name, slug, parent_id | 2 cấp |
| courses | instructor_id, category_id, title, slug, description, thumbnail_url, price, status (`draft`/`pending_review`/`published`/`rejected`), level, language, search_vector (tsvector), deleted_at | |
| course_sections | course_id, title, position | |
| lessons | section_id, title, type (`video`/`article`/`quiz`/`code_exercise`), position, is_preview, video_asset_id, article_content | |
| video_assets | storage_key, duration_s, hls_manifest_key, status (`uploading`/`processing`/`ready`) | R2 |
| reviews | course_id, user_id, rating 1–5, comment | unique (course_id, user_id) |

### Học tập
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| enrollments | user_id, course_id, source (`purchase`/`free`), completed_at | unique (user_id, course_id) |
| lesson_progress | enrollment_id, lesson_id, last_position_s, completed_at | Ghi nhớ vị trí xem |
| notes | user_id, lesson_id, timestamp_s, content | Ghi chú theo timestamp |
| bookmarks | user_id, lesson_id | |
| certificates | enrollment_id, code (QR verify), pdf_key, issued_at | |

### Bài tập code & chấm bài ⭐
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| code_exercises | lesson_id, statement_md, language, starter_code, time_limit_ms, memory_limit_mb | |
| test_cases | exercise_id, input, expected_output, is_hidden, position, score_weight | expected_output của hidden KHÔNG BAO GIỜ trả qua API |
| submissions | user_id, exercise_id, code, language, status (`pending`/`running`/`done`/`error`), verdict (`AC`/`WA`/`TLE`/`MLE`/`RE`/`CE`/`SE`), score, run_time_ms, peak_memory_mb | |
| submission_results | submission_id, test_case_id, verdict, run_time_ms, stdout_trunc (chỉ sample test) | |

### Quiz
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| quizzes | lesson_id, time_limit_s, pass_score, ai_generated | |
| quiz_questions | quiz_id, question, options (JSONB), correct_index, explanation, position | |
| quiz_attempts | quiz_id, user_id, answers (JSONB), score, started_at, submitted_at | Tính giờ ở backend |

### Thương mại
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| carts / cart_items | user_id / cart_id, course_id | |
| wishlists | user_id, course_id | |
| coupons | code, discount_type (`percent`/`fixed`), value, scope (sàn/khóa học), max_uses, valid_from/to | |
| orders | user_id, total, coupon_id, status (`pending`/`paid`/`failed`/`refunded`), payment_provider, provider_txn_id | |
| order_items | order_id, course_id, unit_price | Giá tại thời điểm mua |
| payment_events | order_id, provider, payload (JSONB), signature_valid | Log IPN/webhook để đối soát |

### Cộng đồng & thông báo
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| qa_threads | lesson_id, user_id, title, body, resolved_at | |
| qa_replies | thread_id, user_id, body, is_instructor_reply | |
| qa_votes | thread_id, user_id, value | unique (thread_id, user_id) |
| notifications | user_id, type, payload (JSONB), read_at | |
| reports | reporter_id, target_type, target_id, reason, status | Admin xử lý |

### Gamification
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| xp_events | user_id, amount, reason, ref_type/ref_id | Tổng XP = SUM; leaderboard đọc từ Redis sorted set |
| streaks | user_id, current_streak, longest_streak, last_active_date | |

### AI
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| doc_chunks | course_id, lesson_id, content, embedding (vector), token_count | pgvector, index HNSW |
| chat_sessions / chat_messages | user_id + course_id / session_id, role, content, cited_lesson_ids | |
| recommendations | user_id, course_ids (JSONB), strategy, computed_at | Cache batch; bản nóng ở Redis |

## Điểm cần chú ý khi hiện thực

- `search_vector` cập nhật bằng trigger hoặc trong service khi title/description đổi; index GIN.
- Leaderboard: nguồn chân lý là `xp_events`, Redis sorted set là view — có script rebuild.
- `payment_events` là append-only; trạng thái order chỉ đổi khi verify chữ ký IPN thành công.
