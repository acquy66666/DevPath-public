# Backend — FastAPI

REST API duy nhất của hệ thống: auth, quản lý khóa học, học tập, chấm bài, thương mại, AI.

## Cấu trúc

```
app/
├── api/v1/<domain>.py     Router — chỉ khai báo route và gọi service
├── services/<domain>.py   Business logic, ranh giới transaction
├── models/<domain>.py     SQLAlchemy models
├── schemas/<domain>.py    Pydantic: <Entity>Create / Update / Out
├── core/                  Config, deps (get_db, get_current_user, require_role), bảo mật
└── workers/               Celery tasks: chấm bài (grading), transcode video (media)
tests/api/                 pytest theo domain
scripts/                   seed.py, seed_interactions.py, ingest_course.py, rebuild_recommendations.py, rebuild_course_stats.py, bench_grading.py, lock.sh
```

## Nguyên tắc

- **Layering nghiêm ngặt:** router → service → model. Router không chứa business logic, không truy vấn DB trực tiếp.
- **Authorization nằm ở service**, không ở router — kể cả ownership check (giảng viên chỉ sửa khóa học của mình).
- **Schema thay đổi luôn qua Alembic migration**, cập nhật [docs/database-design.md](../docs/database-design.md) trong cùng commit.
- Định dạng lỗi thống nhất: `{"detail": {"code": "COURSE_NOT_FOUND", "message": "..."}}` — frontend dựa vào `code`.

Chi tiết đầy đủ: skill `fastapi-endpoint` và `db-migration` trong `.claude/skills/`.

## Chạy local

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -e ".[dev]" -c requirements.lock
```

`-c requirements.lock` là bắt buộc: `pyproject.toml` chỉ ghi cận dưới, lock mới là thứ chốt phiên bản — Dockerfile và CI đều cài qua nó, nên máy dev cũng phải vậy thì mới chạy đúng những gì CI đã test.

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Kiểm tra: `http://127.0.0.1:8000/api/v1/health` và tài liệu API ở `/docs` (tự tắt khi `ENV=production`).

Test và lint:

```bash
.venv\Scripts\python.exe -m pytest
```

```bash
.venv\Scripts\python.exe -m ruff check .
```

Test auth chạy trên Postgres thật (mỗi test nằm trong một transaction bị rollback, không để lại dữ liệu). Không có Postgres thì nhóm test đó **tự skip** khi chạy ở máy dev, nhưng **fail** khi biến `CI` được đặt — CI không bao giờ xanh nhờ bỏ qua test.

Cấu hình đọc từ biến môi trường hoặc `backend/.env` — copy từ [.env.example](.env.example).

## Dependency và lockfile

`pyproject.toml` khai báo dependency **và cận dưới** — đó là chỗ thêm hoặc bỏ một thư viện. `requirements.lock` chốt **đúng phiên bản** của mọi gói, kể cả gói kéo theo, và được sinh từ `pyproject.toml` chứ không sửa tay. Một lock dùng cho mọi nơi: image Linux, CI và máy Windows (gói nào chỉ có trên một nền tảng thì mang marker, không tách file). Lock liệt kê cả công cụ dev, nhưng dùng làm file ràng buộc (`-c`) thì nó chỉ chốt phiên bản của gói *được cài*, không tự cài thêm gì — nên image production vẫn không có pytest/ruff.

Sau khi sửa `pyproject.toml`, sinh lại lock (PowerShell, đứng ở `backend/`; không cần cài `uv` lên máy):

```bash
docker run --rm -v "${PWD}:/src" -w /src python:3.12-slim sh -c "pip install -q uv==0.12.17 && sh scripts/lock.sh"
```

Lệnh giữ nguyên mọi phiên bản đang chốt, trừ khi `pyproject.toml` loại chúng ra. Muốn chủ động nâng thì thêm cờ vào cuối `sh scripts/lock.sh`: `--upgrade-package fastapi` cho một gói, `--upgrade` cho tất cả — rồi chạy lại toàn bộ test trước khi commit.

CI chạy lại đúng lệnh này và **fail nếu lock đổi**: thêm dependency vào `pyproject.toml` mà quên sinh lại lock thì gói đó sẽ được cài ở bản mới nhất của hôm đó mà không ai hay. Phiên bản `uv` được chốt trong `scripts/lock.sh`, vì bản `uv` khác có thể trình bày cùng một kết quả theo cách khác.

## Auth (Phase 2)

| Endpoint | Mô tả |
|---|---|
| `POST /api/v1/auth/register` | Tạo tài khoản `student`, trả access token + đặt cookie refresh |
| `POST /api/v1/auth/login` | Đăng nhập email + mật khẩu |
| `POST /api/v1/auth/refresh` | Đổi cookie refresh lấy access token mới (có xoay vòng token) |
| `POST /api/v1/auth/logout` | Thu hồi phiên hiện tại, xóa cookie |
| `GET /api/v1/auth/me` | Hồ sơ người đang đăng nhập (`Authorization: Bearer <access_token>`) |
| `GET /api/v1/auth/google/authorize` | Bắt đầu đăng nhập Google (302 sang accounts.google.com) |
| `GET /api/v1/auth/google/callback` | Google trả trình duyệt về đây, kết thúc bằng 302 về frontend |
| `POST /api/v1/users/me/instructor` | Tự nâng cấp tài khoản lên `instructor` |
| `PATCH /api/v1/users/me` | Sửa hồ sơ của chính mình (hiện chỉ `full_name`) |
| `POST /api/v1/users/me/password` | Đổi mật khẩu, thu hồi mọi phiên khác |

## Khóa học (Phase 2)

| Endpoint | Ai gọi được | Mô tả |
|---|---|---|
| `POST /api/v1/courses` | instructor | Tạo khóa học, mở ở trạng thái `draft` |
| `GET /api/v1/courses/me` | instructor | Khóa học của chính mình, mọi trạng thái, có phân trang |
| `GET /api/v1/courses/{id}` | ai cũng được | Công khai khi `published`; trước đó chỉ chủ sở hữu và admin |
| `PATCH /api/v1/courses/{id}` | chủ sở hữu / admin | Sửa nội dung — `status` và `instructor_id` không nằm trong schema |
| `DELETE /api/v1/courses/{id}` | chủ sở hữu / admin | Soft delete (`deleted_at`) |
| `POST /api/v1/courses/{id}/submit` | chủ sở hữu | `draft`\|`rejected` → `pending_review` (→ `published` khi bật cờ) |
| `POST /api/v1/courses/{id}/unpublish` | chủ sở hữu | `published` → `draft` (gỡ khỏi sàn) |

**Phân quyền tách hai tầng:** *ai được gọi endpoint này* là `require_role` ở dependency; *khóa học này của ai* là ownership check ở service — tầng duy nhất có hàng dữ liệu để so.

**Khóa học nháp trả 404 chứ không 403** cho người ngoài: thứ chưa xuất bản thì không nên xác nhận là có tồn tại. Ngược lại, *sửa* khóa học của người khác trả 403 — id là UUID nên không lộ gì, mà "không phải của bạn" dễ xử lý hơn nhiều khi giảng viên lỡ đăng nhập nhầm tài khoản.

**Soft delete đi qua đúng một hàm** (`_active_courses()`), để không có truy vấn nào quên `deleted_at IS NULL`.

**`AUTO_APPROVE_COURSES`** (mặc định `true`): gửi duyệt là xuất bản luôn. Phase 5 tắt cờ này và thay bằng hàng đợi duyệt thật của admin — lúc đó khóa học dừng ở `pending_review`, đúng như test `test_submitting_waits_for_review_when_the_flag_is_off` mô tả.

**Slug** sinh từ tiêu đề (bỏ dấu tiếng Việt, `đ` → `d`) kèm hậu tố ngẫu nhiên 6 ký tự, và **không đổi khi đổi tiêu đề** — URL đã chia sẻ phải còn sống. Hậu tố ngẫu nhiên thay cho bộ đếm `-2`, `-3`: bộ đếm cần một truy vấn để tìm số trống và hai request cùng lúc vẫn chọn trúng nhau.

Mọi endpoint trả danh sách dùng chung phong bì `{items, total, page, page_size}` (`schemas/pagination.py`), `page_size` mặc định 20, tối đa 100.

### Danh mục

| Endpoint | Mô tả |
|---|---|
| `GET /categories` | Cây danh mục hai tầng, công khai, không phân trang |

Không phân trang vì đây là bảng phân loại do admin biên tập, cỡ một tá dòng, chứ không phải dữ liệu người dùng sinh ra — con trỏ trang cho mười dòng chỉ là nghi thức. Trả về cây (`children` luôn có mặt, rỗng thì là `[]`) để form dựng `<optgroup>` mà không phải tự ghép lại.

### Curriculum (chương & bài học)

| Endpoint | Mô tả |
|---|---|
| `GET /courses/{id}/curriculum` | Mục lục — công khai khi khóa học đã xuất bản |
| `POST /courses/{id}/sections` · `PATCH /sections/{id}` · `DELETE /sections/{id}` | CRUD chương |
| `PUT /courses/{id}/sections/order` | Sắp xếp lại toàn bộ chương |
| `POST /sections/{id}/lessons` · `PATCH /lessons/{id}` · `DELETE /lessons/{id}` | CRUD bài học |
| `PUT /sections/{id}/lessons/order` | Đặt lại **toàn bộ nội dung** một chương, có thể kéo bài từ chương khác sang |
| `GET /lessons/{id}` | Nội dung đầy đủ một bài học |

**Sắp xếp là "gửi cả danh sách", không phải "gửi lệnh di chuyển".** Client đã biết danh sách trông thế nào sau khi kéo-thả, nên gửi nguyên trạng thái đích: không có chuỗi cập nhật từng phần nào có thể dừng giữa chừng và để lại thứ tự sai. Danh sách phải liệt kê **đúng một lần** mỗi phần tử, thiếu là `400 INVALID_ORDER`.

**Unique `(parent, position)` khai báo `DEFERRABLE INITIALLY DEFERRED`** — một lần sắp xếp lại ghi nhiều dòng, và giữa chừng chắc chắn có hai dòng cùng đòi một vị trí. Deferred nghĩa là Postgres kiểm lúc COMMIT, khi thứ tự cuối cùng đã hình thành. Ràng buộc vẫn còn nguyên hiệu lực — test ép kiểm bằng `SET CONSTRAINTS ALL IMMEDIATE` để chứng minh.

**`position` liền mạch từ 0**: xóa hay chuyển bài đi đều renumber phần còn lại, nên "thêm vào cuối" chỉ là `len(hiện có)`.

**Mục lục không mang nội dung.** `LessonSummary` (trong cây curriculum) và `LessonOut` (bài học đầy đủ) là hai model tách rời, nên không ai thêm nhầm một trường vào model chung rồi lộ nội dung trả phí. Đọc một bài: chủ sở hữu xem được tất, bài `is_preview` của khóa đã xuất bản thì ai cũng đọc được, còn lại `403 LESSON_LOCKED` — **403 chứ không 404**, vì mục lục đã công khai là bài đó tồn tại, người dùng chỉ cần biết là phải đăng ký.

### Video

| Endpoint | Mô tả |
|---|---|
| `POST /lessons/{id}/video` | Xin một URL đã ký để trình duyệt tự tải video lên |
| `POST /video-assets/{id}/complete` | Trình duyệt báo đã tải xong → `processing` + đẩy job Celery |
| `POST /video-assets/{id}/retry` | Xử lý lại một video `failed` — tệp vẫn còn trong bucket |
| `GET /video-assets/{id}` | Trạng thái xử lý — màn hình upload hỏi lại theo chu kỳ |
| `PUT /lessons/{id}/transcript` | Gắn transcript `.srt`/`.txt` cho video của bài học (thay tệp cũ nếu có) |
| `DELETE /lessons/{id}/transcript` | Gỡ transcript; khóa đang xuất bản thì chunk của bài đó bị gỡ ở lần nạp kế |

Vòng đời: `uploading → processing → ready`, nhánh hỏng là `failed` kèm `error_message` viết cho giảng viên đọc, không phải cho log. `failed → processing` là đường quay lại: phần lớn lỗi không phải tại tệp mà tại bucket chớp nháy hay worker bị giết giữa chừng, và bắt tải lên nửa gigabyte lần nữa là câu trả lời sai.

**Worker bắt mọi lỗi thay vì ném ra ngoài.** Ném thì Celery sẽ thử lại một video hỏng mãi mãi và người duy nhất cần biết lại không bao giờ thấy. Job giao lại cũng an toàn: `transcode()` bỏ qua asset không ở trạng thái `processing`, nên một lần restart worker không tái xuất bản video đã xong.

**Byte không đi qua backend.** Trình duyệt `PUT` thẳng lên R2 bằng URL đã ký; API chỉ ký rồi đứng ngoài. Đẩy vài trăm MB qua FastAPI sẽ giữ chặt một tiến trình suốt thời gian upload và trả tiền băng thông hai lần, đổi lại chẳng được gì — chữ ký đã nói rõ ai được ghi và ghi vào đúng key nào. `Content-Type` nằm trong phần được ký, nên URL đó không dùng lại được để tải thứ khác lên cùng tên.

**Chưa cấu hình bucket thì trả 503 `STORAGE_NOT_CONFIGURED`**, giống hệt Google OAuth: phần còn lại của hệ thống chạy bình thường, test vẫn xanh, chỉ ba endpoint này ngừng. Cách tạo bucket + khóa: [docs/huong-dan-cloudflare-r2.md](../docs/huong-dan-cloudflare-r2.md).

**`services/storage.py` là Protocol, không phải boto3 rải khắp nơi.** Router không biết boto3 tồn tại, test không chạm Cloudflare — cùng khuôn với `google_oauth.py`. `R2_ENDPOINT_URL` cho phép trỏ sang bất kỳ server nào nói giao thức S3 (MinIO chẳng hạn), để trống thì endpoint suy ra từ `R2_ACCOUNT_ID`.

**Tải lên lần nữa là thay hẳn video cũ:** hàng cũ bị xóa và toàn bộ object dưới prefix của nó bị dọn. Giữ lại thì bài học phát một video trong khi bucket trả tiền cho hai. Xóa bài học cũng xóa hàng `video_assets` của nó — bài học là đường duy nhất tới một video, giữ hàng lại là giữ thứ không ai chạm tới được nữa.

Bảng `video_assets` đã có sẵn từ migration mục lục, nên task này **không cần migration mới**.

Hai loại token đi hai đường khác nhau:

- **Access token** — JWT HS256, sống 15 phút, trả trong body JSON. Frontend giữ trong bộ nhớ và gửi qua header `Authorization`. Không thu hồi được, nên thời hạn phải ngắn.
- **Refresh token** — chuỗi ngẫu nhiên 48 byte, sống 30 ngày, chỉ đi trong cookie `HttpOnly` giới hạn path `/api/v1/auth`. DB chỉ lưu SHA-256 của nó (bảng `refresh_tokens`), lộ DB cũng không đăng nhập lại được.

**Xoay vòng (rotation):** mỗi lần refresh thành công thì token cũ bị thu hồi và cấp token mới. Token đã thu hồi mà quay lại ⇒ coi như bị đánh cắp: thu hồi **toàn bộ** phiên của user đó, trả `REFRESH_TOKEN_REUSED`.

Mã lỗi: `EMAIL_ALREADY_REGISTERED` (409), `INVALID_CREDENTIALS` (401), `ACCOUNT_LOCKED` (403), `REFRESH_TOKEN_MISSING` / `INVALID_REFRESH_TOKEN` / `REFRESH_TOKEN_REUSED` / `NOT_AUTHENTICATED` (401).

### Đăng nhập Google

Luồng **authorization code**, backend là confidential client — client secret không bao giờ rời máy chủ, trình duyệt không cầm thứ gì dùng lại được.

```
trình duyệt → /auth/google/authorize → 302 → accounts.google.com
trình duyệt → /auth/google/callback?code=… (sau khi người dùng đồng ý)
backend     → oauth2.googleapis.com/token (code + client secret)
backend     ← id_token (JWT do Google ký, verify bằng JWKS: chữ ký + aud + iss)
```

Callback **không trả token trong URL**: nó đặt cookie refresh rồi 302 về frontend, SPA tự gọi `/auth/refresh` để lấy access token. Lỗi thì 302 về `/dang-nhap?loi=<CODE>` để người dùng đọc được, không phải JSON giữa trình duyệt.

Chống CSRF bằng `state`: `authorize` sinh chuỗi ngẫu nhiên, đặt vào cookie `HttpOnly` sống 10 phút, callback so lại bằng `secrets.compare_digest`. Không khớp ⇒ `GOOGLE_STATE_INVALID`, chưa đổi mã với Google.

**Gộp tài khoản** theo thứ tự: (1) khớp `oauth_sub` → đúng tài khoản đó, kể cả khi email đã đổi; (2) khớp email → liên kết vào tài khoản sẵn có, **chỉ khi** Google báo `email_verified: true` — không có điều kiện này thì ai đặt được email chưa xác thực lên tài khoản Google là chiếm được tài khoản ở đây; (3) không khớp gì → tạo tài khoản `student` không mật khẩu. Liên kết chỉ *thêm* một đường vào: mật khẩu, họ tên, avatar người dùng tự đặt đều giữ nguyên.

Bật tính năng: tạo OAuth client (loại *Web application*) ở [Google Cloud Console](https://console.cloud.google.com/apis/credentials), thêm đúng `GOOGLE_REDIRECT_URI` vào danh sách *Authorised redirect URIs*, rồi điền `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` vào `.env`. Chưa cấu hình thì hai endpoint trả 503 `GOOGLE_OAUTH_NOT_CONFIGURED` — có chủ đích, không phải lỗi.

Test không bao giờ gọi Google: `get_google_oauth_client` là dependency của FastAPI nên test thay bằng bản giả (`tests/api/test_google_auth.py`).

### Phân quyền

`require_role("instructor")` trong `core/deps.py` là dependency factory, so khớp **chính xác** — admin **không** tự động qua được cửa của instructor. Endpoint nào cho cả hai thì viết rõ: `require_role("instructor", "admin")`. Phân cấp ngầm kiểu "vai cao hơn thì qua tất" là loại quy tắc viết một lần rồi không ai nhớ ở endpoint thứ ba mươi.

Vai trò đọc từ **hàng trong DB**, không đọc claim trong token: thu hồi quyền có hiệu lực ngay thay vì chờ access token hết hạn. Claim `role` trong token chỉ để frontend vẽ giao diện.

Ranh giới: quy tắc theo vai trò nằm ở dependency, còn **ownership check** ("khóa học này có phải của bạn không") nằm ở service — vì nó cần chính đối tượng đang bị đụng tới.

Tự nâng cấp lên giảng viên là **self-service**, không có hàng đợi duyệt: `POST /users/me/instructor`, không nhận id nên không thể trỏ vào người khác. Gọi hai lần không phải lỗi; tài khoản `admin` thì bị từ chối 409 `ROLE_CHANGE_NOT_ALLOWED` vì nâng cấp sẽ làm **mất** quyền. Cái giữ cho nó an toàn nằm ở phía sau: khóa học của giảng viên mới vẫn ở trạng thái nháp và phải qua duyệt.

### Hồ sơ & đổi mật khẩu

`PATCH /users/me` chỉ nhận `full_name`. **Email cố tình không sửa được ở đây**: địa chỉ mới phải xác thực xong mới tin được, đó là một luồng riêng chứ không phải một ô trong form. `role` cũng không có trong schema — không ai tự thăng chức bằng cách sửa hồ sơ.

`POST /users/me/password` **vẫn đòi mật khẩu hiện tại** dù người gọi đã đăng nhập: access token có thể đã 15 phút tuổi và đang nằm trong tay người vừa ngồi xuống chiếc laptop chưa khóa màn hình, còn mật khẩu là thứ chỉ chủ tài khoản biết.

Đổi xong thì **thu hồi toàn bộ phiên** của user đó rồi cấp lại một phiên mới cho chính thiết bị vừa đổi — lý do phần lớn người ta đổi mật khẩu là nghi có người khác biết nó. Endpoint vì thế trả `TokenOut` kèm cookie mới; không nhận cặp token mới thì thiết bị đang đổi cũng bị đăng xuất theo. Access token cũ vẫn sống tới khi hết hạn (tối đa 15 phút) vì hệ thống không có danh sách đen token — đánh đổi có chủ đích của việc không tra DB mỗi request.

Tài khoản chỉ đăng nhập Google (`password_hash IS NULL`) nhận 409 `PASSWORD_NOT_SET`. Payload `UserOut` có cờ `has_password` để frontend biết mà không hiện form vô nghĩa — đây là một boolean về tài khoản, không phải thông tin về mật khẩu.

`JWT_SECRET` phải đặt thật khi `ENV=production` — app từ chối khởi động nếu vẫn còn giá trị mặc định trong `.env.example`.

## Chấm bài (Phase 3)

`POST /code-exercises/{id}/submissions` ghi một dòng `pending` rồi đẩy job vào hàng đợi `grading`. Worker ở `app/workers/grading.py` nhận job, gọi runner trong `grader/` (sandbox Docker), rồi ghi verdict, điểm và kết quả từng test case.

**Thứ tự commit rồi mới enqueue là bắt buộc, không phải thói quen.** Worker nhanh hơn nhiều so với phần còn lại của request: enqueue trước commit thì nó được đưa một id chưa có trong cơ sở dữ liệu. Cái giá của thứ tự này là một hàng nộp bài tồn tại trong lúc Redis chết — nên trường hợp đó được ghi vào chính hàng đó (`status = error`) rồi trả 503 `GRADING_UNAVAILABLE`, thay vì trả 201 cho một bài không ai chấm.

**Chỉ SE mới thử lại.** Sai (WA), chạy lỗi (RE), quá giờ (TLE), tràn bộ nhớ (MLE), không biên dịch được (CE) đều là câu trả lời *về bài nộp*: chạy lại chỉ tốn gấp ba để nhận cùng một câu. SE là lỗi phía mình (daemon chết, image chưa build) nên thử lại 3 lần, giãn 15s rồi 30s.

**Dead letter là một dòng trong bảng, không phải một hàng đợi.** Redis không có chỗ để một message không ai xử lý được, và một dòng log thì học viên lẫn giảng viên đều không thấy. Hết lượt thử, hàng nộp bài chuyển `status = error`, `verdict` vẫn NULL — không có gì được chấm — kèm `message` bằng tiếng Việt. Câu lỗi kỹ thuật ở lại trong log worker: "bind source path does not exist" chỉ khiến học viên đi đọc lại code đúng của mình.

**Ràng buộc CSDL đứng sau cả hai đường:** `ck_submissions_verdict_requires_done` không cho một hàng mang verdict trước khi `done`, nên cả đường retry lẫn đường dead letter đều không thể vô tình đóng một bài nộp lại bằng một chữ cái.

Điểm tính theo **trọng số**, không theo số test case: `round(100 × tổng trọng số các case AC / tổng trọng số)`. Một bài khởi động 1 điểm không đáng bằng case mà cả bài tập nói về.

`run_time_ms` là case chậm nhất chứ không phải tổng — giới hạn thời gian nói về một lần chạy. `peak_memory_mb` để NULL: sandbox báo *bị giết vì bộ nhớ*, không bao giờ báo *đã dùng bao nhiêu*, và một con số bịa ra ở đây sẽ bị đọc như một phép đo.

Output của test case ẩn **không được ghi xuống** (`stdout_trunc` NULL). API đã từ chối trả nó; đây là lớp trước đó, vì một cột không bao giờ được điền thì không endpoint nào viết sau này làm rò được.

`message` cũng bị cắt về cùng hạn mức: lời trình biên dịch đi qua trần 1 MB của sandbox, và cột này được đọc lại trong mọi trang lịch sử nộp bài.

Bốn route trả `TestCaseOut` đầy đủ (`POST`/`PATCH`/`DELETE` test case và `PUT .../order`) không chọn model theo người gọi — chúng **từ chối** người gọi. Học viên đã ghi danh nhận 403, và đó là người duy nhất mà chỉ còn mỗi lớp kiểm tra quyền đứng chắn giữa họ và đáp án; có test đi hết từng route.

**Verdict của case ẩn vẫn trả về, và đó là một oracle đã biết:** nộp chương trình kiểu "nếu input bắt đầu bằng 'A' thì in đáp án đúng" rồi đọc AC/WA là dò được input ẩn. Đúng với mọi hệ thống chấm báo kết quả theo từng test case. Không chặn, vì chặn nghĩa là bỏ luôn kết quả theo case; thứ làm nó không đáng bỏ công là rate limit — dò một input 20 ký tự cần hàng chục giờ, và mỗi bước để lại một dòng mang tên tài khoản trong `submissions`.

`judge()` là chỗ duy nhất trong backend biết kiểu dữ liệu của runner tồn tại, và nó import bên trong hàm: container API chỉ enqueue nên không cần grader lẫn Docker để khởi động được.

### Không quá nhanh

`POST .../submissions` đi qua hai cửa trong Redis trước khi ghi dòng nào: cooldown **10 giây** cho mỗi (học viên, bài tập), và **40 bài/giờ** cho mỗi học viên trên toàn bộ bài tập. Cả hai chỉnh được bằng `SUBMISSION_COOLDOWN_SECONDS` và `SUBMISSION_HOURLY_LIMIT`.

Cooldown chặn nút bấm hai lần và script quay vòng một bài; hạn mức theo giờ chặn script kiên nhẫn ngồi đợi hết cooldown — thứ mà riêng cooldown không bao giờ chặn được. Mỗi cửa là **một lệnh Redis** (`SET NX EX`, `INCR`) chứ không phải đọc-rồi-ghi: API chạy nhiều tiến trình, hai request của cùng một cú double-click rơi vào hai worker, cả hai cùng đọc "chưa có gì".

Cửa chặn nằm **sau** mọi kiểm tra quyền và trước khi ghi: người không xem được bài tập phải nhận 404, không phải nhận thông tin về hạn mức của hệ thống.

Từ chối trả 429 kèm `Retry-After` ở header **và** `retry_after` trong `detail` — header cho proxy/curl, trường JSON cho trang vẽ đồng hồ đếm ngược. Lần bị từ chối **không** đẩy lùi hạn chờ: cooldown để giãn nhịp, không để phạt.

Giới hạn gắn với **user id chứ không phải IP**: một phòng máy của trường ngồi sau một IP NAT, chặn theo IP là chặn nhầm cả lớp vì một người.

**Redis chết thì cho qua**, có chủ đích và chỉ ở đây: Redis cũng là broker của Celery, nên lúc nó chết thì bài vừa được cho qua cũng không vào được hàng đợi và API trả 503 ngay sau. Từ chối ở đây là đổi "hàng đợi hở một lúc" lấy "không ai nộp được bài", để bảo vệ một hàng đợi vốn không chạy.

### Chạy thử

`POST /code-exercises/{id}/trial-runs` chấm code với **chỉ test case mẫu** và không đưa vào lịch sử nộp bài. Cùng hàng đợi, cùng worker, cùng sandbox, cùng kênh tiến độ — khác đúng hai điều: chấm với cái gì, và có được ghi vào hồ sơ hay không.

**Cùng bảng, một cột `is_trial`.** Bảng riêng sẽ phải nhân đôi hàng đợi, worker, kênh tiến độ, và mọi luật về ai được đọc bài nộp nào; một boolean thì không. Đổi lại, mọi truy vấn nói về "bài đã nộp" phải nhớ lọc — nên chỗ duy nhất làm việc đó là `list_submissions`, và index `ix_submissions_user_exercise` cũng partial `WHERE is_trial = false`.

**Route riêng chứ không phải cờ trong body.** Hai thao tác để lại hai dấu vết khác nhau trong hồ sơ học viên, mà một boolean trong body là thứ client làm sai trong im lặng — và sai theo hướng biến mọi lần tập dượt thành bài nộp thật.

**Case ẩn không được nạp, chứ không phải nạp rồi lọc.** Worker gọi `_cases_of(..., samples_only=submission.is_trial)`: test case ẩn không bao giờ đi vào tiến trình của một lần chạy thử, nên không có thời điểm nào nó cầm đáp án ẩn trong tay. Mạnh hơn hẳn "chạy hết rồi xóa kết quả đi".

**`total_cases` đếm theo đúng lần chạy này.** Một lần chạy thử hiện "1/2", không phải "1/8" — mẫu số phải mô tả lần chạy đang diễn ra, nếu không thanh tiến độ đang nói về một bài nộp không tồn tại.

**Thời gian chờ riêng, hạn mức giờ chung.** Luồng mà trang dạy học viên làm là "chạy thử rồi nộp"; một thời gian chờ dùng chung sẽ trả lời đúng luồng ấy bằng 429. Nhưng hạn mức 40 lần/giờ thì dùng chung, vì một script đổi qua đổi lại giữa hai route vẫn tốn đúng ngần ấy container. Câu từ chối gọi tên đúng nút vừa bấm: "bạn vừa **chạy thử**", không phải "bạn vừa nộp bài".

**`NO_SAMPLE_TEST_CASES` (409)** khi bài tập không có test mẫu nào. Khác `EXERCISE_NOT_READY`: bài tập ấy vẫn nộp được bình thường, chỉ là không có gì để tập dượt — trang khóa một nút thay vì báo lỗi.

### Xem bài đang được chấm

`WS /api/v1/submissions/{id}/events` phát tiến độ trong lúc worker chạy: một sự kiện khi bắt đầu (mang **tổng số test case**, tức mẫu số của "test 3/8"), một sự kiện sau mỗi case, một sự kiện khi xong.

**Cơ sở dữ liệu vẫn là nguồn chân lý, kênh chỉ là lời kể.** Redis pub/sub không có bộ nhớ: gửi cho ai đang nghe tại đúng khoảnh khắc đó, không hàng đợi, không phát lại, không xác nhận. Nên mỗi socket **mở đầu bằng một snapshot đọc từ Postgres**, và cứ 10 giây im lặng lại đọc thêm một cái nữa. Một cơ chế trả lời bốn hỏng hóc khác nhau:

| Hỏng hóc | Vì sao snapshot xử lý được |
|---|---|
| Client kết nối sau khi chấm xong | Sự kiện đã đi qua từ lâu; snapshot đầu tiên trả lời ngay |
| Thông điệp phát trong lúc subscription chưa sẵn sàng | Lần đọc kế tiếp bù lại |
| Kết nối Redis đứt giữa chừng | Im lặng, và im lặng được trả lời bằng một lần đọc |
| Worker chết để lại dòng `running` | Snapshot cuối cùng chạm trần 5 phút và đóng socket |

Vì vậy **Redis chết không làm mất tính năng**: `subscribe` thất bại thì socket nhận `SilentStream` và tự hạ cấp thành vòng đọc CSDL mỗi 2 giây — đúng là polling, chỉ khác là chạy trên WebSocket. `publish` thất bại thì bị nuốt kèm log WARNING: tiến độ là lời kể về công việc mà dòng dữ liệu đã ghi xong, không bao giờ được phép làm hỏng việc chấm.

**Token đi trong `Sec-WebSocket-Protocol`.** Trình duyệt không cho đặt header `Authorization` cho WebSocket; cách phổ biến nhất — query string — ghi một chứng danh còn sống vào log nginx. Client chào `["bearer", "<access token>"]`, server nhận với `bearer`. Đúng hai giá trị, giá trị của mình đứng trước: đoán xem phần tử nào là chứng danh chính là cách đọc nhầm chứng danh ở trường khác.

**Quyền xem socket là quyền đọc bài nộp**, theo đúng nghĩa đen: `snapshot_for()` gọi chính `get_submission()` mà endpoint REST dùng. Không có snapshot thì không có socket — nên không tồn tại trạng thái nào mà ai đó đã subscribe được vào kênh của một bài nộp họ không được xem. Mã đóng nằm trong dải ứng dụng: **4401** (lấy token mới rồi kết nối lại) và **4404** (thôi đừng hỏi nữa).

**Sự kiện không mang kết quả.** `GradingEvent` không có trường nào chứa output, input, message hay code — nó là thanh tiến độ, không phải bảng điểm. Kết quả lấy từ `GET /submissions/{id}`, chỗ duy nhất luật test case ẩn được viết ra và được test. Nhờ vậy quy tắc "output case ẩn không rời máy chủ" không cần thêm một câu lệnh lọc nào ở đây.

**Socket không giữ session CSDL.** Mỗi snapshot mở một session, đọc, trả lại ngay — nếu giữ, 30 tab đang mở là 30 kết nối bị ghim khỏi pool. Tài khoản cũng được tra lại mỗi lần, nên socket mở từ một giờ trước không tiếp tục trả lời cho tài khoản vừa bị khóa.

**Đường lùi phía client** nằm ở `frontend/lib/api/submissions.ts`: `watchSubmission()` thử WebSocket, và chuyển sang polling `GET /submissions/{id}` mỗi 2 giây nếu không mở được, hoặc nếu socket đóng trước khi chấm xong. Ngoại lệ duy nhất là 4404 — hỏi lại không làm một bài nộp không tồn tại hiện ra. Hai đường phát ra cùng một kiểu `GradingEvent`, và `SubmissionDetail` mang sẵn `total_cases` để đường polling cũng vẽ được "3/8" y hệt.

## Trạng thái

Toàn bộ API của Phase 2–3 và phần Phase 4 đã làm (quiz, gợi ý, ingest RAG, chat RAG) đều có ở `app/api/v1/`, mỗi router kèm test trong `tests/`. Tóm tắt cập nhật nhất ở mục "Trạng thái hiện tại" của [CLAUDE.md](../CLAUDE.md), checkbox chi tiết ở [docs/plan/](../docs/plan/00-overview.md).

Migration là một chuỗi thẳng 13 revision, một head (`alembic heads` để kiểm):

| Revision | Nội dung |
|---|---|
| `576c29b76f4e` | `users`, `categories`, `courses` + extension `vector`, `unaccent`, `pg_trgm` |
| `adab7334f140` | `refresh_tokens` |
| `f7d37ee5caf2` | `course_sections`, `lessons`, `video_assets` |
| `0c55c726cc39` | trigger `search_vector` cho tìm kiếm toàn văn |
| `991bc02a257b` | `enrollments` |
| `b6dea13f199c` | `lesson_progress` |
| `852a7bf2510b` | `notes`, `bookmarks` |
| `7b60984bf439` | `reviews` |
| `86a5023fa0b8` | `code_exercises`, `test_cases`, `submissions`, `submission_results` |
| `123eb876dda5` | `submissions.is_trial` (chạy thử) |
| `a03e9e2f9ce9` | `doc_chunks` + index HNSW |
| `50ccf4fc23fb` | `quizzes`, `quiz_questions`, `quiz_attempts` |
| `42fff7804290` | `chat_sessions`, `chat_messages` |

Chạy migration cần Postgres — dựng bằng `docker compose` rồi chạy từ venv trên host:

```bash
.venv\Scripts\python.exe -m alembic upgrade head
```

Sau khi migration chạy xong, nạp dữ liệu (một tài khoản admin, 8 danh mục 2 cấp, 2 giảng viên và 4 khóa học lập trình có mục lục đầy đủ):

```bash
.venv\Scripts\python.exe -m scripts.seed
```

Script chạy lại bao nhiêu lần cũng được — lần thứ hai trở đi không tạo thêm gì; một khóa học đã có thì bỏ qua nguyên vẹn, kể cả khi ai đó đã sửa tay.

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `SEED_ADMIN_EMAIL` | `admin@devpath.example` | Tài khoản quản trị |
| `SEED_ADMIN_PASSWORD` | `devpath-admin` (kèm cảnh báo) | Mật khẩu quản trị |
| `SEED_INSTRUCTOR_PASSWORD` | `devpath-instructor` (kèm cảnh báo) | Mật khẩu 2 tài khoản giảng viên |
| `SEED_SAMPLE_HLS_URL` | luồng demo công khai của hls.js | Video cho mọi bài học dạng video |

### Dữ liệu tương tác để đo recommender

Bốn khóa học seed đủ để demo nhưng không đủ để **đo** một hệ gợi ý: bốn khóa thì "cụm sở thích" gần như không diễn đạt được. `scripts/seed_interactions.py` thêm 20 khóa chia thành bốn cụm (frontend, backend, Python/dữ liệu, khoa học máy tính — mỗi cụm neo vào một khóa seed thật) và 48 học viên có lịch sử tập trung trong cụm của mình:

```bash
docker compose exec backend python -m scripts.seed_interactions
docker compose exec backend python -m scripts.rebuild_recommendations
```

Chạy sau `scripts.seed` (script này tra cứu khóa neo và giảng viên, không tự tạo). Idempotent như phần seed còn lại; hạt giống cố định nên mọi máy sinh ra đúng cùng một tập dữ liệu, và đó là điều kiện để số đo trong báo cáo tái tạo được. Số liệu và cách kiểm: [docs/report/assets/phase-4/interaction-seed.txt](../docs/report/assets/phase-4/interaction-seed.txt).

**Dữ liệu này là giả lập.** Nó chứng minh đường ống khôi phục được cấu trúc đã biết là có trong dữ liệu, không chứng minh học viên thật thấy gợi ý hữu ích. 20 khóa giả lập chỉ có một bài học giới thiệu — chúng tồn tại để đo, không để học. Gỡ sạch khi cần catalogue thật để demo:

```bash
docker compose exec backend python -m scripts.seed_interactions --purge
```

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `SEED_LEARNER_PASSWORD` | `devpath-learner` (kèm cảnh báo) | Mật khẩu 48 tài khoản học viên giả lập |

### Nạp dữ liệu cho chatbot RAG

Khi một khóa học được publish, API đẩy job Celery `app.workers.rag.ingest_course`: mỗi bài học có chữ được cắt thành chunk ~500 token có overlap, nhúng bằng Gemini và ghi vào `doc_chunks`. Chạy tay khi cần demo hoặc tái tạo số liệu:

```bash
docker compose exec backend python -m scripts.ingest_course --all --dry-run   # chỉ đếm, 0 quota
docker compose exec backend python -m scripts.ingest_course --all
docker compose exec backend python -m scripts.ingest_course <slug-hoặc-id>
```

Chạy lại **không tốn quota**: trước khi nhúng, mỗi bài học được so với các dòng đang có (cùng số chunk, cùng nội dung, cùng tên model thì bỏ qua). Đổi `GEMINI_EMBEDDING_MODEL` là lý do chính đáng để nhúng lại toàn bộ — hai model có thể cùng 768 chiều mà đặt cùng một câu ở hai chỗ khác hẳn nhau.

Chưa có key thì job ghi log cảnh báo rồi kết thúc êm, không làm task đỏ; phần còn lại của nền tảng chạy bình thường.

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `GEMINI_API_KEY` | trống (tắt) | Khóa Google AI Studio |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Model nhúng; đổi là nhúng lại toàn bộ |

Lý do chọn model và cách đo: [docs/report/assets/phase-4/embedding-model.txt](../docs/report/assets/phase-4/embedding-model.txt). Số liệu chạy thật: [rag-ingest.txt](../docs/report/assets/phase-4/rag-ingest.txt).

**Transcript video** (từ 19/09/2026). Giảng viên gắn tệp `.srt` hoặc `.txt` cho video của bài học qua `PUT /lessons/{id}/transcript` (khối "Transcript cho trợ giảng AI" trong trình soạn bài học). Tệp **đi qua API chứ không qua URL đã ký** như video. Transcript chỉ vài chục KB, nên đi qua backend thì đọc được trước khi giữ:
- tệp không phải UTF-8 (trình duyệt giải mã ra `U+FFFD`) hoặc `.srt` không có dòng thời gian bị trả 422 `TRANSCRIPT_UNREADABLE`, kèm câu hướng dẫn sửa;
- tệp không còn câu thoại nào bị trả 422 `TRANSCRIPT_EMPTY`;
- chưa có video thì trả 409 `LESSON_HAS_NO_VIDEO`.

Tệp **gốc** được lưu cạnh video (`videos/<asset>/transcript.srt`), ghi vào `video_assets.transcript_key`. Ingest đọc lại tệp đó từ bucket và bóc chữ bằng đúng hàm đã kiểm lúc upload: bỏ số thứ tự, dòng thời gian, thẻ `<i>`/`{\an8}`, và gộp câu lặp của phụ đề cuộn. Khóa đang xuất bản thì upload/gỡ/thay video đều xếp hàng nạp lại ngay. Khóa nháp thì nạp khi xuất bản.

**Transcript đọc không được thì giữ nguyên chunk cũ**, và bài đó được đếm là `unreadable` chứ không phải "hết chữ". Tình huống này xảy ra khi bucket chớp nháy, hoặc worker thiếu khóa lưu trữ. Coi là rỗng thì chỉ một lần mạng chập chờn cũng xóa sạch trí nhớ của chatbot về mọi video, và nạp lại tốn quota lần nữa. Script `ingest_course` đọc transcript từ MinIO nên phải chạy **trong container** (`docker compose exec worker ...`), vì Windows không phân giải được `minio.localhost`. Bằng chứng: [transcript-ingest.txt](../docs/report/assets/phase-4/transcript-ingest.txt).

### Trợ giảng AI (chat RAG)

Từ 19/09/2026. Router `app/api/v1/chat.py`, logic ở `app/services/chat.py`:

| Endpoint | Việc |
|---|---|
| `POST /courses/{id}/chat-sessions` | Tạo cuộc trò chuyện — chỉ học viên đã ghi danh khóa đang xuất bản (403 `NOT_ENROLLED`) |
| `GET /courses/{id}/chat-sessions` | Phiên của mình trong khóa, phiên vừa được trả lời lên đầu |
| `GET /chat-sessions/{id}/messages` | Đọc lại một phiên, tin cũ trước |
| `DELETE /chat-sessions/{id}` | Xóa phiên và mọi tin nhắn |
| `POST /chat-sessions/{id}/messages` | **Hỏi** — trả về luồng SSE: `sources` → `delta`… → `done` (hoặc `error`) |

Hỏi là SSE qua `POST`, đọc bằng `fetch`. `EventSource` không dùng được vì nó không gửi được body, cũng không gửi được header `Authorization`. Mọi lời từ chối đều có mã trạng thái và JSON thường như các endpoint khác: chưa ghi danh, khóa đã gỡ xuất bản, hỏi quá nhanh (429 `CHAT_RATE_LIMITED`, cooldown 3 giây và 60 câu/giờ), chưa có key hay Gemini không trả lời (503). Các lời từ chối này xảy ra trước khi luồng bắt đầu. Chỉ khi model hỏng **giữa** câu trả lời (hoặc phiên bị xóa ở tab khác trong lúc đang trả lời) thì mới có `event: error`, và lúc đó không có gì được lưu.

**Bắt buộc: chỉ khóa đang xuất bản, chỉ người đã ghi danh.** Hai điều kiện này được kiểm trước để báo lỗi rõ ràng, và **được viết thẳng vào câu truy vấn top-k** (`retrieve`). Unpublish cố ý giữ chunk lại (xuất bản lại khỏi tốn quota nhúng lại), nên câu truy vấn là lớp cuối giữ chunk đó khỏi câu trả lời. Giảng viên chủ khóa cũng không hỏi được, vì giảng viên không ghi danh được vào khóa của chính mình.

Câu trả lời chỉ dựa trên tài liệu, ghi `[n]` sau mỗi ý, trong đó `n` là số của **bài học** trong `sources`. Nếu tài liệu không đủ thì trợ giảng từ chối lịch sự. Câu hỏi nối tiếp được tìm hai lần trong một lần gọi nhúng, một lần riêng câu đó và một lần ghép với câu hỏi trước, rồi gộp kết quả (lý do và số đo ở file bằng chứng).

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash-lite` | Model viết câu trả lời, chọn theo số đo |
| `GEMINI_CHAT_THINKING_LEVEL` | `minimal` | Mức "suy nghĩ" của model họ 3. Model họ 2.5 thì để trống, vì chúng nhận budget chứ không nhận level. Token suy nghĩ bị trừ vào giới hạn đầu ra |

Bằng chứng chạy thật: chọn model (TTFT 1,3 s so với 6 s và 503/429 ở các model khác), luồng SSE qua HTTP, hạ khóa về nháp mà truy vấn trả 0 dòng, và lỗi 503 **giữa chừng** mà Gemini gửi dưới dạng JSON trần sau khi đã stream một phần. Tất cả ở [chat-api.txt](../docs/report/assets/phase-4/chat-api.txt).

### Đo hiệu năng chấm bài

`scripts/bench_grading.py` đo cả đường thật — API → hàng đợi Celery → worker → sandbox Docker — nên phải chạy khi stack đang lên:

```bash
docker compose exec backend python -m scripts.bench_grading --submissions 10 --cases 5
```

Nó dựng một khóa học, một bài tập và **một học viên cho mỗi bài nộp** (mười bài từ một tài khoản là phép đo rate limit, không phải phép đo tải), bắn tất cả cùng lúc, rồi lấy mốc thời gian từ chính kênh tiến độ Redis để tách *chờ hàng đợi* khỏi *thời gian chấm*. Dọn sạch mọi thứ đã tạo khi xong, trừ khi có `--keep`. Số liệu và kết luận cấu hình: [docs/report/assets/phase-3/benchmark.md](../docs/report/assets/phase-3/benchmark.md).

Nội dung khóa học nằm ở `scripts/seed_courses.py`. **Video là của người khác:** mọi bài học video đều trỏ vào một luồng HLS mẫu công khai, nên khóa học seed phát được cả trên máy chưa cấu hình R2 — đặt `SEED_SAMPLE_HLS_URL` để trỏ sang manifest của bạn. Seed không upload gì lên bucket; upload thật đi qua luồng presigned URL và worker transcode.

Chưa có (đã ghi thành checkbox Phase 6): endpoint readiness kiểm tra DB/Redis, và job dọn object mồ côi — một URL đã ký mà không ai tải lên, hoặc bài học bị xóa, đều để lại file trong bucket không còn hàng nào trỏ tới. Upload avatar đã có từ Phase 2 (`POST /users/me/avatar` + `/complete`).
