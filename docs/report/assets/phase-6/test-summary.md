# Bảng tổng hợp test

Thu ngày **05/10/2026** cho mục "bảng tổng hợp test" của Phase 6 (skill `thesis-report`) và chương 5. Số test lấy từ **lần chạy CI thật**, không đếm lại bằng tay: [run 37263170818](https://github.com/acquy66666/DevPath/actions/runs/37263170818), PR #84, commit `0bae373`, 6/6 job xanh. Phân theo tệp lấy bằng `pytest --collect-only` trên cùng commit; tổng khớp với số CI chạy (mục "Cách tái tạo").

## 1. Theo bộ test (CI 05/10/2026)

| Bộ | Công cụ | Ở đâu | Số ca | Kết quả CI | Thời gian |
|---|---|---|---|---|---|
| Backend: API + service + worker | pytest, **Postgres + Redis thật** (mỗi test một transaction bị rollback) | `backend/tests/` | 1.856 | 1.854 passed, 2 skipped | 15 phút 04 s |
| Grader: image, runner, verdict, tấn công sandbox, proxy (luật + HTTP) | pytest, **Docker thật** | `grader/tests/` | 283 | 266 passed, 17 skipped | 63 s |
| Grader **qua Docker proxy** (chạy lại) | pytest, proxy thật trên runner | verdict + 7 ca tấn công + runner core + tấn công proxy | 59 | 59 passed | 52 s |
| Service backup CSDL | pytest | `infra/backup/` | 43 | 43 passed | 0,1 s |
| Monitor trên host | pytest | `infra/monitor/` | 52 | 52 passed | 0,2 s |
| Frontend: đơn vị | `node --test` | `frontend/lib/**/*.test.ts` | 4 | 4 passed | < 1 s |
| E2E luồng vàng | Playwright + Chromium, **cả stack compose** | `frontend/e2e/golden-flow.spec.ts` | 1 (7 bước) | 1 passed | 45 s (cả job 4 phút 05 s) |
| **Tổng ca test tự động** | | | **2.239** (+ 59 lượt chạy lại qua proxy) | **0 failed** | |

Skipped có lý do, đều được phủ ở chỗ khác:

- **2 ca backend** là test chuyển mã HLS cần `ffmpeg`, mà runner CI không cài. Hai ca này chạy trong container dev (`docker compose exec backend pytest tests/workers/test_transcode.py`).
- **17 ca grader** là bộ tấn công proxy (`test_docker_proxy_live.py`). Chúng cần proxy đang chạy, nên bị bỏ qua ở lượt chạy thẳng và chạy ở dòng "qua Docker proxy" ngay dưới.

Ngoài pytest, CI còn **kiểm cấu hình** — các bước đỏ nếu điều kiện sai, không phải test case:

- **Job "Migrations & seed on an empty database"**: 28 migration `upgrade head` → `downgrade base` → `upgrade head`; `alembic check` (model không lệch migration); seed chạy hai lần không ghi trùng; `seed_interactions` chạy hai lần.
- **Job "Deploy config"**, 13 bước kiểm:
  - compose hợp lệ; chỉ nginx publish cổng và không bind mount; chỉ Docker proxy cầm socket; mọi service xoay vòng log;
  - biến môi trường khớp code (`check_env_examples.py`); shellcheck;
  - nginx nhận config đã render: header bảo mật, không ép buffer SSE, route media giữ `Host`;
  - monitor cài và chạy dưới systemd thật;
  - image production build được; image backup từ chối đoán nơi lưu; image frontend mang đúng tên miền phía server và không mang phía trình duyệt; image frontend khởi động và phục vụ được.
- **Job "Frontend"**: ESLint + `next build` (26 trang tĩnh).
- **Ruff**: chạy ở mọi bộ Python.

## 2. Backend theo phân hệ (1.856 ca)

| Phân hệ | Số ca | Tệp tiêu biểu |
|---|---|---|
| Tài khoản, xác thực, phân quyền, bảo mật HTTP | 434 | `test_authorization_matrix.py` (222 — mọi route × vai người gọi), `test_auth.py` (46), `test_google_*` (56), `test_security.py`, `test_rate_limit.py`, `test_auth_rate_limit.py`, `test_http_hardening.py`, `test_auth_concurrency.py` (hai kết nối thật) |
| AI: RAG, chatbot, sinh quiz, recommender | 429 | `test_content_based.py` (32), `test_quiz.py` (32), `test_chat.py` (30), `test_recommendations.py` (26), `test_collaborative.py` (22), `test_eval_chatbot.py` (22), `test_eval_recommender.py` (21), `test_llm*.py` (44) |
| Khóa học, nội dung, học tập | 250 | `test_courses.py` (39), `test_curriculum.py` (31), `test_catalog.py` (26), `test_video_upload.py` (25), `test_study.py` (22 — ghi chú, bookmark), `test_progress.py`, `test_enrollment.py` |
| Thương mại và thống kê giảng viên | 145 | `test_orders.py` (37 — IPN hợp lệ/sai chữ ký/trùng), `test_commerce.py` (30), `test_coupons.py` (30), `test_vnpay.py` (20 — chuỗi canonical viết tay từ đặc tả), `test_instructor_stats.py` (21) |
| Vận hành, lưu trữ, mô hình dữ liệu | 143 | `test_models.py` (77 — model khớp `database-design.md`), `test_celery_app.py` (17), `test_orphans.py` (14), `test_init_storage.py` (11), `test_readiness.py` |
| Chấm code (phía backend: API, hàng đợi, worker, sự kiện) | 139 | `api/test_grading.py` (55), `workers/test_grading.py` (50), `test_grading_events.py` (23), `test_grading_queue.py` (11) |
| Gamification, chứng chỉ, Q&A, thông báo | 121 | `test_qa.py` (32), `test_gamification.py` (28), `test_certificates.py` (22), `test_leaderboard.py` (16 API + 13 hàm thuần: lịch tuần/tháng, đồng hạng), `test_notifications.py` (10) |
| Quản trị | 101 | `test_reports.py` (25), `test_admin_courses.py` (19), `test_banners.py` (17), `test_admin_coupons.py` (15), `test_admin_categories.py`, `test_admin_users.py`, `test_admin_stats.py` |
| Script dữ liệu demo và đo | 94 | `test_seed_data.py` (23), `test_seed_interactions.py` (21), `test_seed_coupons.py`, `test_seed_cart.py`, `test_seed_sales.py`, `test_seed_study.py`, `test_purge_e2e.py`, `test_stage_load_test.py` |

## 3. Grader theo tệp (283 ca)

| Tệp | Số ca | Nội dung |
|---|---|---|
| `test_docker_proxy_policy.py` | 144 | luật của proxy: body create thật được nhận, ~80 biến thể "lối thoát" bị chặn đúng luật, route, quyền sở hữu |
| `test_runner_core.py` | 20 | giới hạn đọc từ trong container, hai lớp timeout, OOM, dọn container |
| `test_output_comparison.py` | 18 | so sánh output có chuẩn hóa |
| `test_verdict_rules.py` | 18 | thứ tự ưu tiên verdict |
| `test_docker_proxy_live.py` | 17 | tấn công proxy với daemon thật (chỉ chạy qua proxy) |
| `test_classify.py` | 16 | phân loại kết quả chạy |
| `test_docker_proxy_server.py` | 16 | lớp HTTP của proxy: chunked, hai Content-Length, half-close |
| `test_verdict_end_to_end.py` | 15 | đủ 7 verdict trong sandbox thật |
| `test_python_image.py` | 12 | tính chất image sandbox |
| `test_sandbox_attacks.py` | 7 | **7 ca tấn công**: network, fork bomb, đọc file ngoài mount, ghi rootfs… — 0 ca thoát |

## 4. Coverage backend (đo một lần, 05/10/2026)

*(điền sau khi lượt đo chạy xong)*

## 5. Cách tái tạo

Số ca theo tệp, backend (trong container dev):

```bash
docker compose -f infra/docker-compose.yml exec -T backend sh -c 'python -m pytest --collect-only -q -p no:cacheprovider | grep "::" | sed -E "s#::.*##" | sort | uniq -c'
```

Grader (image backend có sẵn pytest; chỉ thu thập, không chạy):

```bash
docker run --rm -v "$PWD/grader:/g" -w /g devpath-backend:dev python -m pytest --collect-only -q -p no:cacheprovider
```

Kết quả CI của một commit:

```bash
gh run view <run-id> --log | grep -E "[0-9]+ passed|# (tests|pass|fail)"
```
