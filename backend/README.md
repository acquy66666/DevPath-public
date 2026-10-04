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
scripts/                   seed.py, seed_interactions.py, seed_transcripts.py, ingest_course.py, rebuild_recommendations.py, rebuild_course_embeddings.py, rebuild_course_stats.py, bench_grading.py, eval_chatbot.py, eval_token_estimate.py, lock.sh
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

Kiểm tra: `http://127.0.0.1:8000/api/v1/health` (liveness — tiến trình sống, không chạm gì), `http://127.0.0.1:8000/api/v1/health/ready` (readiness — CSDL và Redis trả lời trong 2 giây, không thì 503 `NOT_READY` kèm `checks` nói phụ thuộc nào là `down`/`timeout`; lý do chi tiết chỉ vào log vì endpoint công khai) và tài liệu API ở `/docs` (tự tắt khi `ENV=production`).

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

**Duyệt khóa học là việc của admin** (từ 30/09/2026 — cờ `AUTO_APPROVE_COURSES` của Phase 2 đã bị bỏ hẳn): gửi duyệt luôn dừng ở `pending_review`, `POST /admin/courses/{id}/approve` mới đưa khóa học lên sàn **và** xếp job ingest RAG + nhúng khóa học sau commit (`services/moderation.py`). Test cần một khóa học công khai tạo qua API thì dùng `tests/api/publishing.py::publish_via_review` (gửi duyệt rồi một admin mới tinh duyệt). Dashboard toàn sàn (`services/platform_stats.py`, `GET /admin/stats/overview` + `/hot-courses`) dùng chung lịch ngày/tháng giờ Việt Nam với dashboard giảng viên; **người dùng hoạt động** là ai có ít nhất một dấu vết trong ngày ở các bảng vốn đã ghi — `refresh_tokens.created_at` (đăng nhập và mỗi lần mở lại phiên), tiến độ bài, XP, quiz, nộp code, hỏi trợ giảng AI, hỏi đáp, ghi chú, đặt hàng, ghi danh — không thêm bảng, không ghi gì mỗi request. Danh mục, mã giảm giá toàn sàn và banner trang chủ cũng nằm dưới `/admin/*`; banner có dữ liệu demo `python -m scripts.seed_banners` (ảnh gradient PNG tự sinh bằng `zlib`, có `--purge`). Khu quản trị còn có khóa/mở tài khoản (`services/admin_users.py` — khóa là thu hồi mọi refresh token ngay, admin không khóa được) và báo cáo vi phạm (`services/reports.py`, `POST /reports` cho mọi tài khoản).

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

**Tải lên lần nữa là thay hẳn video cũ:** hàng cũ bị xóa và toàn bộ object dưới prefix của nó bị dọn. Giữ lại thì bài học phát một video trong khi bucket trả tiền cho hai. Xóa bài học cũng xóa hàng `video_assets` của nó — bài học là đường duy nhất tới một video, giữ hàng lại là giữ thứ không ai chạm tới được nữa. Tệp của nó thì để job dọn object mồ côi lo (xóa bài học phải chạy được cả trên máy chưa cấu hình bucket).

**Dọn object mồ côi** (`services/orphans.py`, beat `sweep-orphan-objects-nightly` 04:00, chạy tay `python -m scripts.sweep_orphans [--apply] [--force]` — mặc định chỉ báo cáo). Object mồ côi sinh ra theo những đường bình thường: xóa bài học, `--purge`/dọn E2E xóa chứng chỉ mà để lại PDF, URL đã ký được dùng nhưng không ai xác nhận (avatar chọn rồi bỏ, banner không lưu), và mọi lần `delete_quietly` mà bucket từ chối. Chỉ bốn prefix được xét — `videos/<asset>/…` (có hàng `video_assets`), `avatars/<user>/<tệp>` và `banners/<tệp>` (đúng tệp mà một URL trong bảng nhắc tới, đọc từ đường dẫn chứ không từ base URL hiện tại, nên đổi tên miền bucket không làm ảnh cũ thành "mồ côi"), `certificates/<code>.pdf` (có hàng `certificates`) — còn lại không bao giờ bị đụng. Quy tắc: object dưới 1 ngày tuổi để yên (upload đang dở); lần đầu thấy thì **chỉ đánh dấu** vào `orphan_objects`, xóa khi dấu đủ **14 ngày** mà vẫn không ai nhận (bằng số bản backup CSDL — bucket không bật versioning, backup không chứa tệp); một đêm mà quá nửa một prefix sắp bị đánh dấu (≥ 20 object) thì **dừng hẳn**, không ghi gì, log lỗi — thường là đang đọc nhầm CSDL; xóa bằng đúng danh sách key và đọc lại key nào bucket từ chối (giữ dấu cho đêm sau). Test đột biến: bỏ thời gian cách ly, bỏ van, bỏ ân hạn 1 ngày — mỗi cái làm đúng một test đỏ.

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

`run_time_ms` là case chậm nhất chứ không phải tổng — giới hạn thời gian nói về một lần chạy. Không có cột bộ nhớ: sandbox báo *bị giết vì bộ nhớ*, không báo *đã dùng bao nhiêu* — Docker không có con số đỉnh của container đã thoát, và đo từ bên trong sandbox thì phải chạy thêm một tiến trình cạnh bài nộp. Cột `peak_memory_mb` cũ (luôn NULL) đã bỏ ở migration `503c1217538c`.

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

## Giỏ hàng & danh sách yêu thích (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /cart` | Cả giỏ hàng: các dòng + tổng tiền. Không phân trang |
| `PUT /cart/courses/{id}` · `DELETE /cart/courses/{id}` | Thêm / bỏ một khóa học, **trả về cả giỏ sau thao tác** |
| `DELETE /cart` | Dọn sạch giỏ (204) |
| `GET /wishlist` | Khóa học đã lưu, mới nhất trước, có phân trang |
| `GET /wishlist/course-ids` | Chỉ id — để tô trái tim trên thẻ khóa học có sẵn trên trang |
| `PUT /wishlist/courses/{id}` · `DELETE /wishlist/courses/{id}` | Lưu / bỏ lưu (204) |

Mọi endpoint ở đây **chỉ trả lời về chính người gọi** — không cái nào nhận `user_id`, nên không cái nào chĩa được vào giỏ người khác. Thêm và bỏ là `PUT`/`DELETE` chứ không `POST`: bỏ một khóa vào giỏ hai lần vẫn ra đúng cái giỏ ấy, nên phép toán là idempotent và nên được viết đúng như thế.

**Giỏ hàng và danh sách yêu thích bị soi hai chuẩn khác nhau, có chủ ý.** Giỏ dẫn tới một lần trả tiền nên chỉ nhận thứ thật sự mua được: khóa đã ghi danh (409 `ALREADY_ENROLLED`), khóa mình dạy (409 `CANNOT_BUY_OWN_COURSE`) và khóa không ở trên sàn (404 `COURSE_NOT_FOUND`) đều bị chặn ngay lúc bấm — thay vì để lời từ chối nổi lên giữa màn thanh toán, sau khi người ta đã chọn xong cách trả tiền. Danh sách yêu thích không dẫn tới đâu cả nên nhận tất, kể cả khóa đã ghi danh; thứ duy nhất nó từ chối là khóa không còn bán.

**Trả về cả giỏ sau mỗi thao tác** thay vì 204: một cú bấm làm đổi cùng lúc con số trên chuông giỏ hàng, tổng tiền và cái nút vừa bấm, mà cả ba đều đọc từ một object. Trả 204 thì trang phải hỏi lại — một request nữa, chạy đua với chính nó.

**Khóa rời sàn thì rời giỏ**: bộ lọc `published` + `deleted_at IS NULL` nằm trong chính câu truy vấn liệt kê, và số đếm của wishlist đi qua đúng bộ lọc đó. Dòng trong bảng vẫn còn — không xóa sau lưng người dùng — nhưng không hiện và không bị tính tiền. Khóa học mua mất rồi (ghi danh ở tab khác) thì dòng vẫn hiện kèm cờ `already_enrolled`, bị trừ khỏi tổng.

**Giỏ không phân trang, đổi lại có trần `MAX_CART_ITEMS = 50`.** Tổng tiền phải phủ hết mọi dòng nên một trang các dòng không bao giờ mang nổi một tổng đáng tin; chặn kích thước giỏ là cách trung thực để giữ nguyên một response. Hai cú bấm chạy đua nhau có thể vượt trần đúng một đơn vị — nó chặn cỡ response, không phải một bất biến mà thứ gì đó dựa vào.

**Không có cột giá trong `cart_items`.** Giá đóng băng lúc trả tiền, ở `order_items.unit_price`; giỏ hiện giá hôm nay vì đó là giá bấm thanh toán bây giờ sẽ phải trả. Đợt giảm giá bắt đầu trong lúc khóa nằm trong giỏ phải làm tổng giảm xuống, chứ không bị bỏ qua vì một con số đã được chép vào tuần trước.

### Dữ liệu demo

Một giỏ hàng *đầy* là thứ duy nhất ở đây không bấm ra được trong lúc demo — phải có người bỏ vào từ trước. `scripts/seed_cart.py` làm việc đó cho ba học viên seed:

```bash
docker compose exec backend python -m scripts.seed_cart
docker compose exec backend python -m scripts.seed_cart --purge
```

| Tài khoản | Giỏ hàng | Yêu thích |
|---|---|---|
| `hocvien01@seed.devpath.example` | 3 khóa, **798.000 ₫** (có 1 khóa miễn phí) | 2 khóa |
| `hocvien13@seed.devpath.example` | 2 khóa, **998.000 ₫** | 2 khóa |
| `hocvien25@seed.devpath.example` | 2 khóa, **898.000 ₫** | 2 khóa |

Mật khẩu là `SEED_LEARNER_PASSWORD` (mặc định `devpath-learner`), tài khoản do `scripts.seed_interactions` tạo — **chạy script đó trước**, vì seed gốc không có tài khoản học viên nào và chỉ có đúng một khóa có phí.

**Script ghi qua `app/services/commerce.py` chứ không ghi thẳng vào bảng.** Luật nằm ở service (khóa phải đang bán, không phải khóa học viên đã có, không phải khóa họ dạy), nên seed ghi thẳng bảng có thể dựng ra một trạng thái mà chính API từ chối tạo — rồi demo trình bày một cái giỏ không người dùng nào có được. Đi qua cùng một cánh cửa với UI thì điều đó không xảy ra được: dòng nào sai, script dừng ngay kèm đúng câu lỗi cái nút sẽ hiện.

Ba giỏ cố ý khác nhau (mở hai tài khoản cạnh nhau không ra cùng một màn hình), và một giỏ có khóa miễn phí vì giỏ nhận khóa 0đ có chủ ý — tổng 0đ là trường hợp thanh toán phải xử lý khi có coupon 100%. `--purge` chỉ gỡ đúng những dòng trong kế hoạch: khóa ai đó tự thêm vào lúc demo thì giữ nguyên.

## Mã giảm giá (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `POST /cart/coupon` | Thử một mã lên giỏ hiện tại, trả về `{coupon, course_ids, subtotal, discount, total}` |

**`POST` nhưng không ghi gì.** Lượt dùng chỉ tăng lúc đơn hàng được trả tiền (`coupons_service.consume`), không phải lúc gõ mã — nếu không, một chiến dịch giới hạn 100 lượt có thể bị người ta mở trang giỏ hàng cho cạn. Dùng `POST` thay vì `GET` để mã không nằm trong URL, tức không nằm trong log của nginx, lịch sử trình duyệt và header `Referer`.

**Bốn câu hỏi, hỏi theo đúng thứ tự này** — thứ tự là thứ làm cho lời từ chối đọc được:

| Thứ tự | Câu hỏi | Lời từ chối |
|---|---|---|
| 1 | Giỏ có gì để trả tiền không? | 409 `CART_EMPTY` |
| 2 | Có mã này không? | 404 `COUPON_NOT_FOUND` |
| 3 | Mã còn sống không? | 409 `COUPON_NOT_STARTED` / `COUPON_EXPIRED` / `COUPON_EXHAUSTED` |
| 4 | Có áp được vào giỏ này không? | 409 `COUPON_NOT_APPLICABLE` |

Giỏ rỗng được trả lời **trước** cả việc tra mã: "mã không tồn tại" trên một cái giỏ rỗng là câu đúng nhưng đẩy người đọc đi sửa nhầm chỗ. Ba câu ở bước 3 tách riêng vì mỗi câu dẫn tới một hành động khác nhau — quay lại ngày mai, đổi mã khác, hay thôi — và câu của backend kèm ngày (`"đã hết hạn ngày 24/08/2026"`) nên frontend cố ý không đè hai mã đó bằng câu chung.

**Chỉ giảm trên phần đang thật sự phải trả.** Dòng người dùng đã ghi danh giữa chừng đã bị trừ khỏi `CartView.total` thì cũng bị trừ khỏi đây: giảm 50% trên một giỏ mà nửa số dòng đã sở hữu sẽ ra số tiền giảm lớn hơn cả hóa đơn. Khóa rời sàn cũng vậy — bộ lọc `published` nằm trong câu truy vấn giỏ hàng nên coupon không bao giờ nhìn thấy nó.

**Phần trăm làm tròn tới đồng, làm tròn trên số tiền giảm chứ không trên tổng.** VND không có đơn vị nhỏ hơn đồng và cổng thanh toán nhận số nguyên, nên 14.999,85 ₫ là con số không ai trả được; làm tròn trên số tiền giảm thì `tổng = tạm tính − giảm` vẫn đúng từng đồng và trang hiện được cả ba con số cộng khớp nhau. **Số tiền cố định không bao giờ vượt quá thứ nó được trừ**: voucher 500.000 ₫ trên giỏ 399.000 ₫ giảm đúng 399.000 ₫, tổng sàn ở 0 chứ không thành tín dụng mà hệ thống không có chỗ giữ.

**`used_count` là một cột chứ không phải số đếm từ `orders`.** Đếm là câu trả lời chuẩn hóa hơn và sai: luật phải giữ là "lượt thứ 100 được, lượt 101 không", thứ cần một dòng để khóa chứ không phải một aggregate mà hai lần thanh toán đồng thời cùng đọc ra 99. `consume` là `UPDATE … WHERE used_count < max_uses`, ai không khớp dòng nào thì bị từ chối; CHECK `ck_coupons_uses_left` là lớp sàn bên dưới, khiến một lần ghi đè mất dấu không lưu được. Mã lưu chữ hoa (CHECK `code = upper(code)`) nên tra mã là một phép so bằng trên `uq_coupons_code`, và `TET2026` với `tet2026` không thể cùng tồn tại.

**Chưa có ở đây**: gắn coupon vào đơn hàng (`orders.coupon_id` tới cùng task thanh toán) và giới hạn theo người ("mỗi tài khoản một lần") — không có bảng redemption, `orders.coupon_id` mới là chỗ trả lời câu đó. `max_uses` giới hạn chiến dịch, không giới hạn người.

### Dữ liệu demo

Một mã còn hạn chứng minh được đúng một thứ. Cái cần cho buổi demo là **các luật** — và mỗi luật cần một mã ở đúng trạng thái đó, thứ không bấm ra được:

```bash
docker compose exec backend python -m scripts.seed_coupons
docker compose exec backend python -m scripts.seed_coupons --purge
```

| Mã | Giảm | Dùng để xem |
|---|---|---|
| `CHAOMUNG50` | 50% toàn sàn | đường thành công — giỏ `hocvien01` 798.000 → **399.000 ₫** |
| `GIAM100K` | 100.000 ₫ | giảm số tiền cố định, không giới hạn lượt, không hạn kết thúc |
| `PYTHON30` | 30%, 2 khóa Python | phạm vi từng khóa — giỏ `hocvien25` 898.000 → **748.300 ₫** (chỉ khóa Python được giảm) |
| `HETHAN` | 40% | 409 `COUPON_EXPIRED` kèm ngày hết hạn |
| `SAPCHAY` | 25% | 409 `COUPON_NOT_STARTED` kèm ngày mở |
| `HETLUOT` | 50.000 ₫ | 409 `COUPON_EXHAUSTED` (10/10 lượt) |

**Ngày tính tương đối với lúc chạy script**, không bao giờ là ngày tuyệt đối: seed viết ngày cứng là cái demo chạy được cho tới một buổi sáng nào đó thì lặng lẽ thôi chạy, trước mặt người đang xem. Chạy sau `scripts.seed` và `scripts.seed_interactions` (`PYTHON30` gọi tên hai khóa Python thật, mỗi script tạo một khóa). Script này **ghi thẳng bảng**, khác `seed_cart.py` đi qua service: coupon chưa có service tạo (màn hình quản trị thuộc task admin), và luật ở đây nằm trong chính bảng — mỗi dòng sai dừng script bằng một vi phạm CHECK gọi đúng tên nó.

## Thanh toán VNPay (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `POST /orders` | Biến giỏ hàng thành đơn hàng theo giá hôm nay. Body nhiều nhất là `{coupon_code}` |
| `GET /orders/{code}` | Một đơn của chính mình — **đây là câu trả lời có thẩm quyền** cho "đã thanh toán chưa" |
| `POST /orders/{code}/payment-url` | URL VNPay đã ký, sống 15 phút |
| `GET /payments/vnpay/ipn` | Callback của VNPay. Không xác thực bằng token, trả `{"RspCode","Message"}` |

**Chỉ IPN được quyền nói là đã trả tiền.** VNPay gọi thẳng từ máy chủ của họ vào backend; trình duyệt quay về từ ngân hàng mang đúng những tham số ấy nhưng là thứ chủ nó sửa được, nên trang kết quả chỉ lấy mã đơn từ URL rồi hỏi lại `GET /orders/{code}`. Tin vào query string nghĩa là ai gõ được `vnp_ResponseCode=00` cũng tự ghi danh được.

**Thứ tự kiểm trong IPN, và lý do của thứ tự đó:**

| Bước | Kiểm | Trả về |
|---|---|---|
| 1 | Chữ ký HMAC-SHA512, trước khi tin bất kỳ tham số nào | `97` Invalid signature |
| 2 | Có đơn mang mã này không | `01` Order not found |
| 3 | Số tiền có khớp đơn không | `04` Invalid amount |
| 4 | Đơn còn `pending` không | `02` Order already confirmed |
| 5 | `vnp_ResponseCode` **và** `vnp_TransactionStatus` đều `00` | `00` Confirm Success |

Bước 4 là chỗ chống trùng — VNPay gửi lại IPN cho tới khi nhận được `00`, nên callback lặp là chuyện thường ngày chứ không phải ca hiếm; câu `SELECT ... FOR UPDATE` xếp hai callback song song thành hàng, còn `uq_orders_provider_txn` (partial unique) là chốt chặn ở tầng bảng: một giao dịch ngân hàng chỉ gắn được vào đúng một đơn, bất kể code làm gì. Bước 5 kiểm **cả hai** mã: `vnp_ResponseCode` nói "yêu cầu có ổn không", `vnp_TransactionStatus` nói "giao dịch có đi qua không", và chúng có thể khác nhau.

**Mọi callback được ghi vào `payment_events` trước khi bị phán xét** — kể cả cái sai chữ ký, nhất là cái sai chữ ký. Đó là bản ghi duy nhất về việc cổng thanh toán thật sự nói gì, thứ cần đọc khi trạng thái đơn và sao kê ngân hàng không khớp nhau, tức đúng lúc không thể tin vào lời kể của chính đoạn code.

**Một transaction cho tất cả**: ghi log, chuyển đơn sang `paid`, ghi danh từng khóa (`enrollments.source='purchase'`), trừ lượt coupon, bỏ các dòng đã mua khỏi giỏ. Hỏng giữa chừng sẽ để lại đơn đã trả tiền mà người mua không mở được khóa học.

**Callback trả lời bằng tiếng của VNPay** (`{"RspCode","Message"}`, luôn HTTP 200 kể cả khi từ chối) vì VNPay gửi lại bất cứ thứ gì nó không đọc được — trả 404 cho "không tìm thấy đơn" là mua thêm một vòng lặp gửi lại chứ không phải một câu trả lời.

**Chữ ký là toàn bộ giao thức** (`app/services/vnpay.py`): mọi tham số `vnp_` có giá trị, sắp theo tên, nối `key=value&…` với cả hai vế url-encode kiểu `quote_plus`, HMAC-SHA512 bằng secret. Sai một dấu cách là chữ ký không khớp và VNPay từ chối không kèm lý do, nên chuỗi đó dựng ở đúng **một** chỗ (`canonical()`) và cả URL đi lẫn callback về đều đi qua nó. Ba chi tiết dễ sai: số tiền tính bằng 1/100 đồng (399.000 ₫ → `39900000`), thời gian là giờ Việt Nam `yyyyMMddHHmmss` không kèm múi (cố định +07:00, Việt Nam không đổi giờ mùa), và **tham số rỗng bị loại khỏi chữ ký** như bản của VNPay làm.

`tests/test_vnpay.py` ghim chuỗi canonical **viết tay từ đặc tả** chứ không đọc ngược từ code — đó là thứ duy nhất không thể kiểm bằng cách chạy thử khi chưa có tài khoản merchant.

### Cấu hình

```bash
# infra/.env
VNPAY_TMN_CODE=...
VNPAY_HASH_SECRET=...
```

Trống thì `POST /orders/{code}/payment-url` trả 503 `PAYMENT_NOT_CONFIGURED` và IPN từ chối mọi callback (không có secret thì không kiểm được chữ ký nào). Đăng ký merchant sandbox ở <https://sandbox.vnpayment.vn/devreg/>, rồi trong phần cấu hình của merchant khai **IPN URL** là `<địa chỉ công khai>/api/v1/payments/vnpay/ipn` — VNPay gọi thẳng vào backend nên `localhost` không dùng được. **Cloudflare Quick Tunnel không dùng được cho việc này** — mỗi lần chạy là một URL mới, mà IPN URL khai một lần với VNPay; máy dev dùng một domain ngrok cố định trỏ vào `backend:8000`. Cổng merchant sandbox không có ô tự khai IPN URL: phải gửi URL cho kỹ thuật VNPay qua email.

### Chạy thử khi chưa có tài khoản merchant

```bash
docker compose exec backend python -m scripts.simulate_vnpay_ipn DP260924ABC123
docker compose exec backend python -m scripts.simulate_vnpay_ipn DP260924ABC123 --fail
```

Script ký callback bằng **đúng secret backend dùng để kiểm** rồi gọi vào chính endpoint IPN — cùng route, cùng bước kiểm chữ ký, cùng handler. Nó chứng minh được mọi thứ xảy ra sau khi tiền chuyển (chữ ký, chống trùng, ghi danh, giỏ hàng rỗng đi), tức đúng phần mà sai sót làm người ta mất khóa học; thứ nó không chứng minh được là trang của VNPay có nhận URL của mình không — cái đó cần `VNPAY_TMN_CODE` thật. Đặt hai biến bằng giá trị bất kỳ ở máy dev là chạy được.

## Dashboard giảng viên (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /instructor/stats/overview?period=7d\|30d\|90d\|12m` | Tổng của kỳ và của kỳ trước, chuỗi theo ngày (theo tháng với `12m`) có đủ cả ô trống, cùng số liệu từ trước tới nay |
| `GET /instructor/stats/courses?period=…&page=…` | Từng khóa: học viên, hoàn thành, tiến độ TB, ghi danh mới và doanh thu trong kỳ. Khóa bán chạy nhất kỳ đứng đầu |

Chỉ `instructor` (khớp đúng vai trò, admin cũng 403), và không path nào mang id giảng viên — mọi con số đã được lọc theo `instructor.id` ngay trong câu truy vấn, nên không có dashboard của người khác để hỏi. Không bảng riêng, không cache: toàn bộ là phép gộp trên `orders`/`order_items`/`enrollments`/`lesson_progress`, với hai index dựng cho đúng hai kiểu đọc này (`ix_order_items_course_id`, `ix_enrollments_course_created`).

**Mỗi con số chỉ mang một nghĩa**, và test ghim đúng nghĩa đó (`tests/api/test_instructor_stats.py`):

- **Doanh thu** là tiền người mua thực trả cho khóa của mình: `unit_price − discount` của **từng dòng**, chỉ đơn `paid`, theo `paid_at`. Không phải `orders.total` (một đơn có thể chứa khóa của nhiều giảng viên), và không phải `unit_price` (phần coupon là tiền không ai nhận). Chưa trừ phí sàn — chia sẻ doanh thu là hướng phát triển.
- **Phần giảm theo dòng** (`order_items.discount`) chia **lúc tạo đơn** trên đúng các dòng coupon áp vào, rồi đóng băng. Coupon `PYTHON30` trong một đơn có cả khóa React không được trừ vào doanh thu khóa React. Xem `coupons.split_discount` và `tests/test_discount_split.py`.
- **Ngày là ngày Việt Nam**: đơn trả lúc 00:10 thuộc ngày mới. Gom nhóm bằng tên múi `Asia/Ho_Chi_Minh` — chuỗi `'+07:00'` trong `AT TIME ZONE` bị Postgres đọc thành *UTC−7*.
- **Học viên mới** là người lần đầu ghi danh một khóa của mình trong kỳ; **tỉ lệ hoàn thành** và **tiến độ TB** tính từ trước tới nay, lượt đã hoàn thành tính là xong mọi bài, và trả `null` chứ không phải 0 khi chưa có ai.

### Dữ liệu demo

Mọi lượt ghi danh seed rơi vào đúng ngày chạy seed, và thanh toán là việc người ta làm tay từng lần — biểu đồ sẽ là một cột và một đường phẳng. `scripts/seed_sales.py` nạp **77 đơn (139 lượt bán) của 40 người mua riêng** trải trong 12 tháng, tăng dần về hiện tại:

```bash
docker compose exec backend python -m scripts.seed_sales
docker compose exec backend python -m scripts.seed_sales --purge
```

Mỗi lần mua **đi qua đúng đường thật** — `add_to_cart` → `create_from_cart` (một phần tư có mã `BANHANG20`) → callback VNPay có chữ ký vào `handle_vnpay_ipn`, handler ghi danh, trừ lượt coupon và ghi `payment_events`. Thứ duy nhất ghi thẳng bảng là **đồng hồ**: sau đó đơn, lượt ghi danh và sự kiện thanh toán được lùi về thời điểm trong kế hoạch. Callback ký bằng một secret cục bộ đưa vào bản sao của settings, nên chạy được ở máy chưa có tài khoản merchant và không chạm vào secret thật. Người mua là `nguoimuaNN@sales.devpath.example` (mật khẩu `devpath-buyer`), **không phải** học viên seed — `seed_interactions` và test của nó ghim chính xác ai học khóa nào. Các lượt ghi danh này có đi vào recommender như mọi lượt khác, nên **`--purge` trước khi chạy `scripts.eval_recommender`**. Chạy sau `scripts.seed` và `scripts.seed_interactions`; ngày tính tương đối với lúc chạy.

Đăng nhập `mai.anh@devpath.example` hoặc `khoa.tran@devpath.example` (mật khẩu giảng viên seed) rồi mở `/giang-day/thong-ke`.

## XP và chuỗi ngày học (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /users/me/gamification` | Tổng XP, chuỗi hiện tại, chuỗi dài nhất, ngày hoạt động gần nhất, hôm nay đã tính chưa |
| `GET /users/me/xp-events?page=…&page_size=…` | Từng lần được cộng XP, mới nhất trước, kèm bài học (và khóa) mà nó thưởng cho |

Cả hai chỉ trả dữ liệu của chính người gọi. Không route nào nhận id người dùng, vì XP của người khác là việc của leaderboard.

**XP** (`services/gamification.py`, mức thưởng ở `XP_AMOUNTS`) chỉ tính **lần đầu** cho mỗi (người, lý do, đối tượng):

| Lý do | Khi nào | XP |
|---|---|---|
| `lesson_completed` | Hoàn thành một bài học bất kỳ: tick "đã xong", quiz đạt, hoặc bài code AC | 10 |
| `quiz_passed` | Lần đầu đạt điểm qua một quiz. Cộng thêm vào XP của bài học chứa nó | 20 |
| `exercise_solved` | Lần đầu nộp bài code (không phải chạy thử) được AC. Cộng thêm vào XP của bài học | 30 |

"Lần đầu" được đảm bảo bằng `uq_xp_events_ref` chứ không bằng một phép kiểm trong code. Cộng XP là `INSERT … ON CONFLICT DO NOTHING`, nên các trường hợp sau đều không làm XP tăng thêm: bỏ tick rồi tick lại, qua quiz hai lần, hay job chấm bài bị giao hai lần. XP được ghi **trong cùng transaction** với việc hoàn thành bài (với bài code là transaction của verdict). Nhờ vậy completion bị rollback thì XP cũng không còn.

Chỉ người **có ghi danh** mới được cộng XP. Giảng viên tự làm thử quiz hay bài code của khóa mình vẫn được chấm bình thường, nhưng không nhận XP và không tính chuỗi.

**Chuỗi ngày học:** một ngày (theo giờ Việt Nam) được tính khi học viên *nộp* một thứ gì đó:
- hoàn thành bài học;
- nộp lượt quiz, kể cả khi trượt;
- nộp bài code, tính lúc nộp chứ không phải lúc được chấm.

Những việc sau **không** tính: xem video mà chưa xong (heartbeat của player), chạy thử code, và nộp quiz quá giờ. Không có job chạy lúc nửa đêm để cắt chuỗi. Chuỗi có ngày cuối trước hôm qua thì API trả `current_streak: 0`; ngày cuối là hôm qua thì chuỗi vẫn còn.

Hiển thị ở đầu trang `/khoa-hoc-cua-toi`: ba thẻ số, 5 lần cộng XP gần nhất và lối vào bảng xếp hạng.

## Bảng xếp hạng (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /leaderboard?period=week\|month\|all&page=…&page_size=…` | Một trang của bảng, mỗi dòng có hạng, tên, avatar, XP và `is_me`. Kèm `me` (hạng và XP của người đọc, kể cả khi không nằm trên trang này) và ngày đầu/cuối của kỳ |

Cần đăng nhập, vì đây là danh sách tên học viên. API chỉ trả tên và avatar, không trả email.

Redis giữ ba sorted set, là **view** của `xp_events` (`services/leaderboard.py`):
- `lb:xp:week:2026-W40`: tuần ISO, thứ Hai → Chủ nhật theo giờ Việt Nam;
- `lb:xp:month:2026-09`;
- `lb:xp:all`.

**Đồng hạng xếp kiểu thi đấu** (1, 2, 2, 4). Hạng của một dòng là số người có điểm **lớn hơn hẳn** cộng 1 (`ZCOUNT key (score +inf`). Vì vậy trang 2 bắt đầu giữa một nhóm đồng điểm vẫn ra đúng hạng.

**Ghi:** `gamification.award()` chỉ ghi tạm vào `session.info`. Tiến độ bài học, nộp quiz và worker chấm bài gọi `leaderboard.publish_awards()` **sau** `commit()`. Rollback thì bỏ phần đã ghi tạm. Redis lỗi thì chỉ ghi log, vì XP đã nằm an toàn trong Postgres.

Redis được gọi bằng client **đồng bộ** chạy trong thread (`asyncio.to_thread`). Lý do: một client dùng chung được cho cả event loop của API lẫn worker chấm bài, mà worker lại tạo một loop mới cho mỗi job.

**Dựng lại** từ `xp_events` trong ba trường hợp:
- lúc đọc, nếu bảng chưa từng được dựng (Redis vừa restart hoặc bị flush);
- mỗi đêm 03:30 (beat `rebuild-leaderboards-nightly`, queue mặc định);
- khi chạy tay:

```bash
docker compose exec backend python -m scripts.rebuild_leaderboard
```

### Dữ liệu demo

XP chỉ có từ ngày tính năng ra đời, nên trên máy dev ba bảng sẽ giống hệt nhau. `scripts/seed_study.py` cho **40 người mua của `seed_sales`** học trong 70 ngày gần nhất:
- học các khóa họ đã mua;
- tham gia thêm 0–2 khóa miễn phí có nhiều bài;
- có người học mỗi ngày, có người học từng đợt, có người bỏ giữa chừng;
- quiz thỉnh thoảng trượt rồi làm lại.

```bash
docker compose exec backend python -m scripts.seed_study
docker compose exec backend python -m scripts.seed_study --purge
```

Mọi thao tác **đi qua service thật**: `save_position(completed=True)`, `start_attempt`/`submit_attempt`, `enrol_free`. Chỉ **đồng hồ** là ghi thẳng bảng: sau mỗi thao tác, các dòng được lùi về thời điểm trong kế hoạch. Chuỗi ngày học được phát lại theo từng ngày qua `record_active_day`, rồi bảng xếp hạng được dựng lại. Bài tập code bị bỏ qua vì cần sandbox.

Thứ tự chạy: `scripts.seed_sales` trước, rồi đến script này. Kế hoạch có seed cố định, ngày tính tương đối với lúc chạy. Chạy lần hai không ghi thêm gì. Các lượt ghi danh miễn phí có đi vào recommender, nên **`--purge` trước `scripts.eval_recommender`**.

Kết quả ngày 28/09/2026: 648 bài học, 21 lượt quiz đạt, 3 lượt trượt, 49 lượt tham gia khóa miễn phí. Bảng tuần có 4 người (hôm đó là thứ Hai), bảng tháng 27 người, mọi thời gian 40 người. Đăng nhập `nguoimuaNN@sales.devpath.example` (mật khẩu `devpath-buyer`) rồi mở `/bang-xep-hang`.

## Chứng chỉ hoàn thành (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /certificates/{code}` | **Công khai.** Trả đúng những gì in trên tờ chứng chỉ: tên, khóa, giảng viên, ngày, mã; kèm `course_slug` (khi khóa còn trên sàn) và `pdf_ready`. Không có email hay id người dùng. Mã sai định dạng và mã không tồn tại cùng trả 404 `CERTIFICATE_NOT_FOUND`; mã gõ thường hoặc có gạch vẫn nhận |
| `GET /certificates/{code}/pdf` | **Công khai.** Trả tệp PDF (đọc từ storage qua API, nên không phụ thuộc host MinIO/R2 có phân giải được từ trình duyệt hay không). PDF chưa vẽ thì trả 409 `CERTIFICATE_NOT_READY` **và đẩy lại job** |

Người học thấy mã chứng chỉ ở `certificate_code` của `GET /enrollments/me` và `GET /courses/{id}/progress`. Frontend có nút "Chứng chỉ" ở `/khoa-hoc-cua-toi`, link "Xem chứng chỉ" trong trang học, và trang xác thực công khai `/cert/{code}` (render phía server, trả 404 thật khi mã sai, `noindex`).

**Cấp:** trong cùng transaction với lúc khóa học chuyển sang hoàn thành (`progress._refresh_course_completion`).
- Mỗi lượt ghi danh một chứng chỉ (`uq_certificates_enrollment`); bỏ tick rồi hoàn thành lại vẫn là chứng chỉ cũ.
- Tên người học, tựa khóa và tên giảng viên được **chép lúc cấp**, không đổi theo các lần sửa sau.
- Mã: 16 ký tự, 32 ký tự không gây nhầm, 80 bit ngẫu nhiên; trùng mã thì bốc lại.

**Vẽ PDF:** job Celery `render_certificate` (queue mặc định, worker media).
- `after_commit.run` đẩy job **sau commit**, cùng chỗ với việc đẩy điểm bảng xếp hạng. Rollback thì không có job nào.
- WeasyPrint vẽ trang HTML A4 ngang; mã QR là SVG do `segno` sinh, trỏ tới `FRONTEND_URL/cert/{code}`.
- Job idempotent: chứng chỉ đã có PDF thì bỏ qua. Lỗi storage thì thử lại 3 lần.

**Thư viện hệ thống:** WeasyPrint cần Pango và HarfBuzz; font là DejaVu (image slim không có font nào, thiếu font thì chữ có dấu thành ô vuông). Image backend và CI đều cài `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core`.
- Trên Windows không có Pango, nên code chỉ import WeasyPrint trong hàm vẽ.
- Test vẽ PDF **skip trên host và bắt buộc trên CI**. Chạy ở local bằng:

```bash
docker compose exec backend pytest tests/api/test_certificates.py
```

**Cấp bù** cho các lượt đã hoàn thành trước khi có tính năng (qua đúng `certificates.issue`, ghi ngày là ngày hoàn thành thật), rồi vẽ PDF ngay tại chỗ. Chạy lại không làm gì thêm:

```bash
docker compose exec backend python -m scripts.issue_certificates [--dry-run]
```

Chạy thật ngày 29/09/2026: cấp 233 chứng chỉ (87 của học viên seed, 146 của người mua mẫu sau `seed_study`), vẽ 233 PDF trong 98 giây. Mã QR giải ra đúng URL xác thực (kiểm bằng OpenCV trên ảnh PDF render 200 dpi).

## Hỏi đáp theo bài học (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /lessons/{id}/qa-threads?sort=newest\|top` | Câu hỏi của một bài, mới nhất trước hoặc nhiều người hỏi nhất trước; mỗi câu kèm `vote_count`, `voted` (người đọc đã vote chưa), `reply_count`, `has_instructor_reply` |
| `POST /lessons/{id}/qa-threads` | Đặt câu hỏi (`title` ≤ 200, `body` ≤ 5000 ký tự, Markdown) |
| `GET /qa-threads/{id}` | Một câu hỏi, kèm khóa và bài của nó |
| `PATCH /qa-threads/{id}` | Sửa `title`/`body` (chỉ người hỏi) hoặc `resolved` (người hỏi hoặc staff của khóa). Yêu cầu chỉ được làm một nửa thì không làm gì cả |
| `DELETE /qa-threads/{id}` | Người hỏi hoặc staff; câu trả lời và vote đi theo |
| `PUT` / `DELETE /qa-threads/{id}/vote` | "Tôi cũng có câu hỏi này". Idempotent cả hai chiều; tự vote câu của mình → 409 `CANNOT_VOTE_OWN_THREAD` |
| `GET` / `POST /qa-threads/{id}/replies` | Câu trả lời, cũ nhất trước (một cuộc trò chuyện) / trả lời |
| `DELETE /qa-replies/{id}` | Người viết hoặc staff |
| `GET /instructor/qa-threads?course_id=&unanswered=true` | Hộp thư của giảng viên: câu hỏi ở mọi khóa mình dạy. `unanswered` = chưa có trả lời của giảng viên **và** người hỏi chưa đánh dấu giải quyết |

**Ai tham gia:** học viên đã ghi danh, giảng viên của khóa, admin. Người khác nhận 403 `NOT_ENROLLED`, kể cả ở bài học thử: ai cũng *xem* được bài thử, nhưng câu hỏi bên dưới là chuyện của lớp. Khóa bị hạ về nháp thì 404 với học viên, đúng như trang học.

**Huy hiệu giảng viên:** `is_instructor_reply` quyết định lúc viết (người trả lời là giảng viên của khóa lúc đó). Admin là staff nhưng không mang huy hiệu.

**Thông báo:** trả lời câu hỏi của người khác ghi `notifications` (`type='qa_reply'`) cho người hỏi; học viên đặt câu hỏi ghi `qa_question` cho giảng viên của khóa. Cả hai **cùng transaction** với việc được báo, và không ai được báo về lời của chính mình.

Frontend: tab "Hỏi đáp" cạnh "Ghi chú" dưới bài học (`?hoi-dap=<id>` mở thẳng một câu hỏi), và trang `/giang-day/hoi-dap` cho giảng viên (giảng viên không ghi danh được khóa của mình nên không vào trang học được; lối vào ở nút "Hỏi đáp" của `/giang-day` và menu người dùng).

## Thông báo in-app (Phase 5)

| Endpoint | Mô tả |
|---|---|
| `GET /notifications?unread=true&page=` | Thông báo của chính người gọi, mới nhất trước; `payload` trả nguyên như lúc ghi (mỗi `type` một dạng) |
| `GET /notifications/unread-count` | Số trên chuông — request riêng và rẻ (đọc index partial), frontend hỏi mỗi 60 giây và mỗi lần cửa sổ được focus lại |
| `POST /notifications/{id}/read` | Idempotent, giữ `read_at` đầu tiên. Không phải của mình hoặc không tồn tại → 404 `NOTIFICATION_NOT_FOUND` |
| `POST /notifications/read-all` | Mọi dòng chưa đọc của mình → đã đọc; trả `{"marked": n}` |

Hai loại hiện có: `qa_reply` (người khác trả lời câu bạn hỏi → link `/hoc/{course_slug}?bai={lesson_id}&hoi-dap={thread_id}`) và `qa_question` (học viên hỏi trong khóa bạn dạy → link `/giang-day/hoi-dap?cau-hoi={thread_id}`). Câu chữ và link do frontend dựng từ `type` + `payload` (`components/notifications/notification-items.tsx`), vì server không biết route của frontend; loại mới mà trang chưa biết vẫn hiện một dòng chung, trỏ về `/thong-bao`. Không có WebSocket: một câu trả lời đợi được một phút.

Frontend: chuông trên header (badge đỏ, `9+` khi quá 9; dropdown 8 thông báo gần nhất, chỉ tải khi mở; bấm một dòng = đánh dấu đã đọc + đi tới link) và trang `/thong-bao` (tab Tất cả / Chưa đọc, "Đánh dấu đã đọc hết", phân trang).

## Trạng thái

Toàn bộ API của Phase 2–3 và phần Phase 4 đã làm (quiz, gợi ý, ingest RAG, chat RAG) đều có ở `app/api/v1/`, mỗi router kèm test trong `tests/`. Tóm tắt cập nhật nhất ở mục "Trạng thái hiện tại" của [CLAUDE.md](../CLAUDE.md), checkbox chi tiết ở [docs/plan/](../docs/plan/00-overview.md).

Migration là một chuỗi thẳng 23 revision, một head (`alembic heads` để kiểm):

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
| `ca9e1c7ffdbb` | `quiz_questions.ai_generated`, `reviewed_at` (duyệt câu hỏi AI sinh) |
| `17e181ed9f26` | `course_embeddings` (vector khóa học cho "Khóa học tương tự") |
| `45c681ca42af` | `carts`, `cart_items`, `wishlists` |
| `d23158098a8c` | `coupons`, `coupon_courses` |
| `99c7ba304d8d` | `orders`, `order_items`, `payment_events` |
| `3f7c33c23e64` | `order_items.discount` (phần giảm theo dòng, chia lại cho đơn cũ) + index cho dashboard giảng viên |
| `e9d78af241e6` | `xp_events` (sổ cái XP, append-only), `streaks` (chuỗi ngày học) |
| `b6fc99d6b6af` | `certificates` (chứng chỉ hoàn thành, tên/khóa/giảng viên đóng băng lúc cấp) |
| `8f1cea268f50` | `qa_threads`, `qa_replies`, `qa_votes` (hỏi đáp theo bài học, chỉ upvote), `notifications` |
| `c7c21bbd1a9b` | `ix_notifications_user_created` (trang thông báo) + loại thông báo `qa_question` |

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
docker compose exec backend python -m scripts.rebuild_course_embeddings
docker compose exec backend python -m scripts.rebuild_recommendations
```

Thứ tự ba lệnh này có ý nghĩa: từ khi có hệ lai, `rebuild_recommendations` đọc `course_embeddings` cho nửa content-based. Bảng trống thì nó vẫn chạy xong và ghi ra danh sách **chỉ có collaborative** — trông hoàn toàn bình thường mà không phải thứ cặp job hằng đêm sinh ra (có một dòng cảnh báo trong log, không có gì khác để nhìn).

Chạy sau `scripts.seed` (script này tra cứu khóa neo và giảng viên, không tự tạo). Idempotent như phần seed còn lại; hạt giống cố định nên mọi máy sinh ra đúng cùng một tập dữ liệu, và đó là điều kiện để số đo trong báo cáo tái tạo được. Số liệu và cách kiểm: [docs/report/assets/phase-4/interaction-seed.txt](../docs/report/assets/phase-4/interaction-seed.txt).

**Dữ liệu này là giả lập.** Nó chứng minh đường ống khôi phục được cấu trúc đã biết là có trong dữ liệu, không chứng minh học viên thật thấy gợi ý hữu ích. 20 khóa giả lập chỉ có một bài học giới thiệu — chúng tồn tại để đo, không để học. Gỡ sạch khi cần catalogue thật để demo:

```bash
docker compose exec backend python -m scripts.seed_interactions --purge
```

Còn dữ liệu của `seed_sales` thì lệnh trên **dừng lại, không xóa gì** và in thứ tự cần gỡ trước (`seed_study --purge`, `seed_sales --purge`): đơn hàng mẫu cũng mua các khóa giả, và đơn hàng — sổ tiền — trỏ vào khóa và người mua bằng khóa ngoại RESTRICT. Trước 02/10/2026 chỗ này ra traceback `ForeignKeyViolationError`. Thứ tự nạp/gỡ của mọi script demo: mục "Dữ liệu demo đầy đủ" ở [README gốc](../README.md).

### Vector khóa học cho "Khóa học tương tự"

Nửa content-based của recommender đọc bảng `course_embeddings`, và bảng đó trống cho tới khi có ai bấm publish hoặc job beat 02:30 chạy. Để có ngay:

```bash
docker compose exec backend python -m scripts.rebuild_course_embeddings --dry-run
```

```bash
docker compose exec backend python -m scripts.rebuild_course_embeddings
```

`--dry-run` in ra đúng chuỗi sẽ được nhúng của từng khóa mà không gọi API — dùng để xem description có bị cắt hay không trước khi tiêu quota. Chạy lại lần hai không tốn gì: khóa nào `source_text` và tên model không đổi thì bỏ qua. Thêm một slug (hoặc id) ở cuối để chỉ làm một khóa. Cần `GEMINI_API_KEY`; không có key thì script dừng và nói rõ, còn job Celery chỉ ghi log cảnh báo rồi thôi — phần còn lại của nền tảng không phụ thuộc vào khối gợi ý này.

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

**Lời giảng cho khóa seed** (từ 20/09/2026). Video seed là luồng HLS mẫu không có tiếng, nên nếu chỉ có vài bài viết thì chatbot gần như không có gì để tìm. `scripts/seed_transcripts.py` gắn lời giảng viết sẵn (`scripts/seed_data/transcripts/<slug>/<chương>-<bài>.srt|txt`) cho video của khóa Python, qua đúng `put_transcript` với tư cách giảng viên chủ khóa. Chạy sau `scripts.seed`, **trong container** (cần MinIO). Khóa đang xuất bản thì được xếp một job ingest cho cả khóa:

```bash
docker compose exec backend python -m scripts.seed_transcripts
```

Không chạy bước này thì số đo của đánh giá chatbot (xem "Trợ giảng AI" bên dưới) không tái tạo được: khóa chỉ còn 4/17 bài có chữ thay vì 15/17.

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

**Đọc lại một phiên cũ vẫn biết `[2]` là bài nào** nhờ trường `citations: [{number, lesson_id}]` của `ChatMessageOut` (thêm cùng UI chat). Câu trả lời lưu nguyên dấu `[n]` theo cách đánh số của lượt hỏi đó, nhưng cột `cited_lesson_ids` chỉ giữ các bài được trích theo thứ tự nhắc đến, không giữ số. Số được suy lại mà không cần migration (`numbered_citations`): số thật đều ≤ số nguồn, còn số bị loại đều lớn hơn, nên số thật chính là `len(cited_lesson_ids)` số nhỏ nhất xuất hiện trong bài, giữ thứ tự nhắc đến. Nếu hai bên không khớp nữa thì trả rỗng, vì thà không có link còn hơn link sai bài.

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash-lite` | Model viết câu trả lời, chọn theo số đo |
| `GEMINI_CHAT_THINKING_LEVEL` | `minimal` | Mức "suy nghĩ" của model họ 3. Model họ 2.5 thì để trống, vì chúng nhận budget chứ không nhận level. Token suy nghĩ bị trừ vào giới hạn đầu ra |

Bằng chứng chạy thật: chọn model (TTFT 1,3 s so với 6 s và 503/429 ở các model khác), luồng SSE qua HTTP, hạ khóa về nháp mà truy vấn trả 0 dòng, và lỗi 503 **giữa chừng** mà Gemini gửi dưới dạng JSON trần sau khi đã stream một phần. Tất cả ở [chat-api.txt](../docs/report/assets/phase-4/chat-api.txt).

**Câu từ chối không bao giờ được lưu kèm số nguồn** (từ 20/09/2026). Quy tắc 3 của system prompt cho câu mở đầu nguyên văn (`REFUSAL_OPENING`: "Nội dung này nằm ngoài phạm vi tài liệu của khóa học."). Nếu câu đầu tiên của câu trả lời là câu đó, `is_refusal` coi đây là câu từ chối: service gỡ mọi `[n]` rồi mới lưu, và không lưu bài nào vào `cited_lesson_ids`. Sự kiện `done` mang bản đã gỡ, và trang thay chữ đang stream bằng bản này. Lý do: prompt đã cấm, nhưng model vẫn gắn `[1][3][4]` khi gợi ý chủ đề khác (3/18 câu từ chối), nên trang hiện "Nguồn" ngay dưới câu "không có tài liệu". Khi service phải gỡ, log ghi một dòng. **Không có ngưỡng điểm** để từ chối trước khi gọi model: câu hợp lệ thấp nhất đo được (0,633, hỏi bằng tiếng Anh) còn thấp hơn câu phải từ chối cao nhất (0,692).

**Đánh giá** bằng bộ 20 câu (`scripts/eval_data/chatbot_questions.json`), mỗi câu hỏi 3 lần qua đúng `prepare_answer`/`answer_events`, chấm bằng máy và in nguyên văn để đọc lại:

```bash
docker compose -f infra/docker-compose.yml exec -T backend python -m scripts.eval_chatbot > docs/report/assets/phase-4/chatbot-eval.md   # từ thư mục gốc repo
docker compose exec backend python -m scripts.eval_chatbot --scores-only   # chỉ điểm truy hồi, không gọi model sinh
```

Kết quả, cách chấm và những chỗ máy chấm sai: [chatbot-eval.txt](../docs/report/assets/phase-4/chatbot-eval.txt).

### Sinh quiz bằng AI

Từ 19/09/2026. Logic ở `app/services/quiz_generation.py`, route nằm trong `app/api/v1/quiz.py`:

| Endpoint | Việc |
|---|---|
| `POST /quizzes/{id}/generate` | `{source_lesson_id, count}` (1–10): Gemini đọc một bài cùng khóa (bài viết, hoặc transcript nếu là video) rồi soạn nháp, nối vào cuối quiz nháp |
| `POST /quiz-questions/{id}/approve` | Duyệt một câu nháp đúng như đang có. Idempotent, lần duyệt đầu được giữ |

**Câu AI soạn chưa ai đọc thì quiz không xuất bản được** (409 `QUIZ_NEEDS_REVIEW`). Duyệt, sửa (`PATCH`, vì form sửa hiện cả câu hỏi, phương án và đáp án) hoặc xóa đều gỡ chặn cho câu đó. Theo dõi từng câu bằng `quiz_questions.ai_generated` / `reviewed_at`. Lý do bắt buộc: cả hai model đã thử đều từng sinh đáp án sai trông như đúng.

**Không tin model cho tới khi kiểm xong.** `responseSchema` giữ hình dạng câu trả lời, nhưng không giữ được đáp án trỏ ra ngoài danh sách, phương án trùng nhau, hay câu lặp lại câu đã có. Mỗi câu đi qua đúng `check_question_shape` như câu gõ tay. Câu hỏng bị loại và đếm vào `dropped`; nếu không câu nào dùng được thì trả 503 `QUIZ_GENERATION_FAILED` và không lưu gì. Phương án được xáo trước khi lưu, vì model hiếm khi đặt đáp án đúng ở vị trí cuối (3/60).

**`QuestionOut.key_warning`** gắn cờ câu nháp chưa duyệt có lời giải thích trích một phương án khác nhiều hơn hẳn đáp án. Đây là kiểu của câu sai duy nhất trong 60 câu đã đo, và phép so từ bắt đúng 1/60 câu đó. Chỉ là gợi ý cho người duyệt, không từ chối gì.

Mọi lời từ chối xảy ra **trước** khi gọi model: bài không có chữ (409 `LESSON_HAS_NO_TEXT`), bài khác khóa (400 `SOURCE_NOT_IN_COURSE`), quiz đã xuất bản (409 `QUIZ_PUBLISHED`), hỏi quá nhanh (429 `QUIZ_GENERATION_RATE_LIMITED`, cooldown 10 giây và 20 lần/giờ). Gọi đồng bộ, không qua Celery: một lần gọi khoảng 3 giây, và người chờ là giảng viên vừa bấm nút.

| Biến môi trường | Mặc định | Dùng cho |
|---|---|---|
| `GEMINI_QUIZ_MODEL` | `gemini-3.5-flash-lite` | Model soạn câu hỏi, chọn theo số đo (thắng `3.5-flash` 30/30 so với 29/30 đáp án đúng, 3,0 s so với 11,5 s) |
| `GEMINI_QUIZ_THINKING_LEVEL` | `minimal` | Như của chat |
| `GEMINI_QUIZ_MAX_OUTPUT_TOKENS` | `8192` | 5 câu tốn khoảng 600 token; JSON bị cắt giữa chừng thì vô dụng, nên để dư |

Bằng chứng: [quiz-generation.txt](../docs/report/assets/phase-4/quiz-generation.txt), gồm 60 câu chấm tay, bẫy `int(12.9)`, và một lượt sinh → duyệt → xuất bản trên Chrome.

### Đo hiệu năng chấm bài

`scripts/bench_grading.py` đo cả đường thật — API → hàng đợi Celery → worker → sandbox Docker — nên phải chạy khi stack đang lên:

```bash
docker compose exec backend python -m scripts.bench_grading --submissions 10 --cases 5
```

Nó dựng một khóa học, một bài tập và **một học viên cho mỗi bài nộp** (mười bài từ một tài khoản là phép đo rate limit, không phải phép đo tải), bắn tất cả cùng lúc, rồi lấy mốc thời gian từ chính kênh tiến độ Redis để tách *chờ hàng đợi* khỏi *thời gian chấm*. Dọn sạch mọi thứ đã tạo khi xong, trừ khi có `--keep`. Số liệu và kết luận cấu hình: [docs/report/assets/phase-3/benchmark.md](../docs/report/assets/phase-3/benchmark.md).

Nội dung khóa học nằm ở `scripts/seed_courses.py`. **Video là của người khác:** mọi bài học video đều trỏ vào một luồng HLS mẫu công khai, nên khóa học seed phát được cả trên máy chưa cấu hình R2 — đặt `SEED_SAMPLE_HLS_URL` để trỏ sang manifest của bạn. Seed không upload gì lên bucket; upload thật đi qua luồng presigned URL và worker transcode.

Upload avatar đã có từ Phase 2 (`POST /users/me/avatar` + `/complete`). Endpoint readiness và job dọn object mồ côi có từ 04/10/2026 (mục "Dọn object mồ côi").
