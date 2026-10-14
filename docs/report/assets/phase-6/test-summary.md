# Bảng tổng hợp test

Thu ngày **05/10/2026** cho mục "bảng tổng hợp test" của Phase 6 (skill `thesis-report`) và chương 5. **Cập nhật 13/10/2026** cho mục gate "toàn bộ test xanh trong CI" (mục 5). Số test lấy từ **lần chạy CI thật**, không đếm lại bằng tay: [run 38420744606](https://github.com/acquy66666/DevPath/actions/runs/38420744606), PR #91, commit `9c623dd` (= `main` `8072ae4` + bước ffmpeg của mục 5), 6/6 job xanh. Lần thu trước: [run 37263170818](https://github.com/acquy66666/DevPath/actions/runs/37263170818), PR #84, commit `0bae373`. Phân theo tệp lấy bằng `pytest --collect-only` trên cùng mã; tổng khớp với số CI chạy (mục "Cách tái tạo").

## 1. Theo bộ test (CI 13/10/2026)

| Bộ | Công cụ | Ở đâu | Số ca | Kết quả CI | Thời gian |
|---|---|---|---|---|---|
| Backend: API + service + worker | pytest, **Postgres + Redis thật** (mỗi test một transaction bị rollback) | `backend/tests/` | 1.873 | **1.873 passed, 0 skipped** | 15 phút 18 s |
| Grader: image, runner, verdict, tấn công sandbox, proxy (luật + HTTP) | pytest, **Docker thật** | `grader/tests/` | 283 | 266 passed, 17 skipped | 61 s |
| Grader **qua Docker proxy** (chạy lại) | pytest, proxy thật trên runner | verdict + 7 ca tấn công + runner core + tấn công proxy | 59 | 59 passed, 0 skipped | 52 s |
| Service backup CSDL | pytest | `infra/backup/` | 43 | 43 passed | 0,1 s |
| Monitor trên host | pytest | `infra/monitor/` | 52 | 52 passed | 0,2 s |
| Frontend: đơn vị | `node --test` | `frontend/lib/**/*.test.ts` | 4 | 4 passed | < 1 s |
| E2E luồng vàng | Playwright + Chromium, **cả stack compose** | `frontend/e2e/golden-flow.spec.ts` | 1 (7 bước) | 1 passed (lần đầu, không "flaky") | 1,1 phút (cả job 5 phút 30 s) |
| **Tổng ca test tự động** | | | **2.256** (+ 59 lượt chạy lại qua proxy) | **0 failed**; 17 skipped = tấn công proxy, chạy ở dòng "qua Docker proxy" | |

Skipped có lý do, được phủ ở chỗ khác:

- **17 ca grader** là bộ tấn công proxy (`test_docker_proxy_live.py`). Chúng cần proxy đang chạy, nên bị bỏ qua ở lượt chạy thẳng và chạy ở dòng "qua Docker proxy" ngay dưới.
- Backend không còn ca skip nào. Tới 05/10 có **2 ca** chuyển mã HLS cần `ffmpeg` bị skip vì runner CI không cài; từ 13/10 job cài ffmpeg và hai ca chạy thật (mục 5). Runner CI có ffmpeg 6.1.1 của Ubuntu 24.04, còn image backend có 7.1.5 của Debian 13: cùng lệnh, hai bản, đều qua.

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

## 2. Backend theo phân hệ (1.873 ca, đếm lại 13/10)

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
| Script dữ liệu demo và đo | 111 | `test_seed_data.py` (23), `test_seed_interactions.py` (21), `test_seed_coupons.py` (15), `test_seed_sales.py` (11), `test_seed_study.py` (10), `test_seed_community.py` (8), `test_seed_cart.py`, `test_purge_e2e.py`, `test_stage_load_test.py` |

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

**94,5 %** (dòng + nhánh gộp) trên `backend/app/`: 95,4 % dòng (8.587/9.006), 88,8 % nhánh (1.248/1.406). Đo bằng coverage.py 7.13.5 (`--branch`), chạy cả bộ backend trong container dev, trên CSDL + Redis dev, commit `5ac1c3c` (mã `app/` giống `0bae373` của CI). Báo cáo đầy đủ từng tệp kèm số dòng chưa chạy: `coverage-backend.txt`.

| Gói | Câu lệnh | Dòng | Nhánh | Gộp |
|---|---|---|---|---|
| `app/services` (business logic) | 5.268 | 96,1 % | 89,8 % | 94,9 % |
| `app/api` (router) | 1.081 | 97,2 % | 78,9 % | 96,6 % |
| `app/schemas` | 1.326 | 99,1 % | 85,7 % | 98,3 % |
| `app/models` | 662 | 93,5 % | — | 93,5 % |
| `app/core` | 279 | 93,2 % | 86,4 % | 92,3 % |
| `app/workers` (Celery) | 376 | 70,7 % | 78,3 % | 71,6 % |
| **Tổng** | **9.006** | **95,4 %** | **88,8 %** | **94,5 %** |

**Lần đo đầu ra 83,4 % và đó là con số sai.** Coverage.py mặc định chỉ theo dõi luồng thường. SQLAlchemy async thì chạy phần đồng bộ bên trong greenlet, nên tracer mất dấu khung hàm sau mỗi `await session.…`. Ví dụ: `list_tree` trong `services/categories.py` có test gọi qua `GET /categories`, nhưng các dòng 78–83 ngay sau `await session.scalars(…)` bị báo là chưa chạy, và cả tệp chỉ được 53 %. Đo lại với `--concurrency=greenlet,thread` thì tệp đó lên 98 %, tổng lên 94,5 %. Ai đo lại coverage cho dự án này **phải bật cờ đó**.

Chỗ coverage thấp nhất, và phần đó được kiểm ở đâu khác:

| Tệp | Gộp | Phần chưa chạy | Được kiểm ở |
|---|---|---|---|
| `workers/rag.py`, `workers/content_based.py`, `workers/orphans.py` | 42–55 % | lớp vỏ task Celery (`asyncio.run` + mở session) | service bên trong có test riêng (`test_ingest.py`, `test_content_based.py`, `test_orphans.py`); vỏ chạy thật trong worker ở các buổi diễn tập (`phase-4/rag-ingest.txt`, `phase-6/orphan-sweep.txt`) |
| `services/storage.py` | 69 % | các phương thức gọi boto3 thật của `R2Storage` | test dùng storage giả; S3 thật được kiểm bằng smoke 21/21 (prod) và 10/10 (dev) ở `phase-6/rustfs-compose/`, cộng 20 kiểm ở `phase-6/storage-decision/` |
| `api/v1/grading.py` | 71 % | thân endpoint WebSocket `/submissions/{id}/events` (dòng 351–390) | pytest chỉ chạm phần từ chối của ma trận phân quyền; nhánh chạy thật được **E2E** kiểm — spec đỏ nếu tiến độ từng case và verdict không tới qua WebSocket (`phase-6/polling-progress-decision.txt`) |

Trong container dev, lượt đo có **3 ca đỏ, không phải lỗi mã** (trên CI cả ba đều xanh):

- 2 ca `test_storage_that_was_never_configured_answers_503`: trong container, storage tự rơi về bucket dev nên không bao giờ "chưa cấu hình".
- `test_deploy_passes_the_seed_passwords_into_the_container`: test đọc `infra/scripts/deploy.sh`, mà container backend chỉ mount `backend/`.

Phần còn lại: 1.851 passed, 2 skipped, mất 16 phút 21 s. Coverage không phải một bước của CI và không có ngưỡng chặn merge: đây là số đo một lần cho báo cáo, không phải chỉ tiêu.

## 5. Gate Phase 6: "xanh trong CI" nghĩa là test đã chạy thật

Mục gate đòi toàn bộ test (unit + E2E + bảo mật sandbox) xanh trong CI. Một job xanh chưa đủ để kết luận điều đó. Có ba cách để test không chạy mà CI vẫn xanh, và lượt kiểm 13/10 rà cả ba:

**a) Test tự skip khi thiếu phụ thuộc.** Bộ test có 9 chỗ skip có điều kiện, để chạy được trên máy dev thiếu dịch vụ. Trên CI (biến `CI` luôn được GitHub đặt), 8 chỗ đã tự đổi thành **fail**:

| Thiếu gì | Ở đâu | Trên CI |
|---|---|---|
| Docker (image sandbox, 7 ca tấn công, đủ 7 verdict) | `grader/tests/conftest.py` | `pytest.fail` |
| Postgres | `backend/tests/conftest.py`, `test_auth_concurrency.py` | `raise` |
| Redis | `test_health.py`, `test_leaderboard.py`, `test_rate_limit.py` | `raise` |
| Mã `grader/runner` | `workers/test_grading_queue.py` | `raise` |
| Pango cho WeasyPrint (PDF chứng chỉ) | `api/test_certificates.py` | không skip; job cài thư viện |
| **ffmpeg** | `workers/test_transcode.py` | **trước 13/10: skip** |

Chỗ thứ 9 là ffmpeg. Runner CI không có ffmpeg, nên 2 ca chuyển mã HLS thật **chưa từng chạy trên CI**: "1.854 passed, 2 skipped" ở mục 1 cũ chính là hai ca đó. Hai ca này kiểm đúng dòng lệnh ffmpeg của worker video: manifest VOD, phân đoạn ≤ `SEGMENT_SECONDS` + 1 nhờ ép keyframe, tệp không phải video thì báo lỗi chứ không sập. Sửa 13/10 (PR #91):

- job backend cài `ffmpeg` cạnh thư viện PDF;
- skip đổi thành fail khi có `CI`, cùng luật với các chỗ trên;
- bước pytest của backend và grader chạy với `-rs`, nên log in lý do của mọi ca skip.

Kiểm ba trường hợp trong container backend dev:

- có ffmpeg: 11 passed;
- giấu ffmpeg khỏi `PATH`: 9 passed, 2 skipped, có in lý do;
- giấu ffmpeg và đặt `CI=1`: **2 failed** (`FileNotFoundError: 'ffmpeg'`).

Trên CI của PR #91, log backend in "1873 passed" và không có dòng `SKIPPED` nào.

Skip duy nhất còn lại trên CI là **17 ca tấn công proxy** (`test_docker_proxy_live.py`) ở lượt grader chạy thẳng. `-rs` in ra lý do: 15 ca "needs DOCKER_HOST pointed at the proxy", 2 ca "needs DEVPATH_REAL_DOCKER_HOST to set up a container to attack". Chúng chạy ở bước kế tiếp, qua proxy thật: 59 passed, 0 skipped. Không có `xfail`, `skip` vô điều kiện hay `importorskip` nào trong `backend/tests`, `grader/tests`, `infra/backup`, `infra/monitor`; không có `test.skip`/`fixme`/`.only` trong `frontend/e2e` (đã grep 13/10).

**b) E2E qua nhờ chạy lại.** `playwright.config.ts` đặt `retries: 1` trên CI. Ca đỏ lần đầu mà xanh lần sau sẽ in "1 flaky", và job vẫn xanh. Vì vậy tiêu chí ở đây là dòng **"1 passed"**, không phải màu của job. Trên commit `8072ae4` (main sau PR #90 font tự host), job E2E chạy 4 lần: lượt gốc 06/10, cộng 3 lần chạy lại 13/10 (attempt 2–4 của run 37496238512). Cả 4 lần đều "1 passed", qua ngay lần đầu, mất 30,5 / 55,0 / 51,9 / 55,2 s. Run của PR #91 cũng "1 passed" (1,1 phút). Lỗi E2E đỏ ngẫu nhiên trên main ngày 06/10 (`self-hosted-fonts.txt`) có nguyên nhân là build tải font từ Google, ước khoảng 1/60 lần hỏng. Bốn lần xanh không chứng minh được tần suất ấy. Bằng chứng thật là phép build `--network none` trong tệp đó: build không còn gọi ra mạng.

**c) Bước test không nằm trong job.** Mỗi bộ ở mục 1 có một bước riêng trong `.github/workflows/ci.yml`, với dòng tổng kết riêng trong log. Lượt grader qua proxy liệt kê tệp tường minh (verdict, tấn công sandbox, runner core, tấn công proxy), nên không thể "chạy 0 ca mà xanh".

## 6. Cách tái tạo

Số ca theo tệp, backend (trong container dev):

```bash
docker compose -f infra/docker-compose.yml exec -T backend sh -c 'python -m pytest --collect-only -q -p no:cacheprovider | grep "::" | sed -E "s#::.*##" | sort | uniq -c'
```

Grader (image backend có sẵn pytest; chỉ thu thập, không chạy):

```bash
docker run --rm -v "$PWD/grader:/g" -w /g devpath-backend:dev python -m pytest --collect-only -q -p no:cacheprovider
```

Coverage backend. `coverage` không nằm trong lock (chỉ đo một lần), nên cài tạm vào container dev; mất cùng lần dựng lại container. Thiếu `--concurrency=greenlet,thread` thì số đo sai (mục 4):

```bash
docker compose -f infra/docker-compose.yml exec -T backend sh -c 'pip install -q "coverage==7.13.*" && COVERAGE_FILE=/tmp/devpath.coverage python -m coverage run --branch --concurrency=greenlet,thread --source=app -m pytest -q -p no:cacheprovider; COVERAGE_FILE=/tmp/devpath.coverage python -m coverage report -m --skip-empty'
```

Kết quả CI của một commit:

```bash
gh run view <run-id> --log | grep -E "[0-9]+ (passed|skipped|flaky)|SKIPPED \[|# (tests|pass|fail)"
```

Chạy lại riêng job E2E của một run (mỗi lần một attempt mới, chờ xong rồi mới chạy lại được; đọc dòng "1 passed" / "1 flaky" của Playwright):

```bash
job=$(gh run view <run-id> --json jobs -q '.jobs[] | select(.name | startswith("E2E")) | .databaseId')
gh run rerun <run-id> --job "$job" && gh run watch <run-id>
gh run view <run-id> --job <id-job-mới> --log | grep -E "[0-9]+ (passed|flaky|failed)"
```
