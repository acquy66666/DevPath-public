# Nhật ký quyết định kỹ thuật

Ghi ngay khi quyết định, 1–2 dòng mỗi mục, để Phase 7 viết chương 4 (Xây dựng hệ thống) không phải nhớ lại. Chỉ ghi quyết định **có đánh đổi**; những thứ chỉ có một cách làm thì không cần.

Định dạng: **Quyết định** — bối cảnh → lựa chọn → lý do / cái phải trả giá.

## Phase 1 — Foundation

**Postgres + pgvector thay vì thêm vector database riêng** — RAG ở Phase 4 cần similarity search. Chọn `pgvector` ngay trong Postgres. Ít thành phần phải vận hành, đủ cho quy mô demo; đổi lại không có các tính năng chuyên sâu của Pinecone/Qdrant.

**Extension khai báo ở cả init script lẫn migration** — `infra/postgres/init/` chỉ chạy khi volume Postgres còn trống, nên database của CI hoặc VPS mới sẽ không có gì. Migration đầu tiên tự `CREATE EXTENSION IF NOT EXISTS`. Trả giá bằng một chỗ trùng lặp, đổi lại schema dựng được từ số không ở mọi môi trường.

**`gen_random_uuid()` không cần `pgcrypto`** — từ Postgres 13 đây là hàm dựng sẵn. Bản đặc tả CSDL đầu tiên ghi cần `pgcrypto` là nhầm, đã sửa trong `docs/database-design.md`.

**Enum nghiệp vụ là `VARCHAR` + `CHECK`, không dùng Postgres ENUM** — thêm giá trị mới cho `courses.status` sau này chỉ là sửa constraint, không phải `ALTER TYPE` kèm khóa bảng.

**Chỉ `courses` có soft delete** — nghiệp vụ thật duy nhất: khóa học bị gỡ khỏi sàn nhưng học viên đã mua vẫn phải học được. Càng ít bảng soft delete thì càng ít chỗ quên lọc `deleted_at IS NULL`.

**Số liệu khóa học lưu sẵn trong `courses`** — `rating_avg`, `students_count`... denormalize để trang danh sách sắp xếp được bằng index. Rủi ro lệch số được bù bằng `backend/scripts/rebuild_course_stats.py` tính lại từ nguồn.

**`bcrypt` trực tiếp thay vì `passlib`** — passlib không còn được bảo trì và vỡ với bcrypt 4.x. Mật khẩu quá 72 byte **ném lỗi** thay vì bị cắt âm thầm: bcrypt bỏ qua phần đuôi, nên cắt sẽ khiến hai mật khẩu dài khác nhau mở được cùng một tài khoản.

**Frontend cần hai URL backend** — Server Component phân giải được tên service `backend` trong mạng Docker, trình duyệt thì không. `lib/api/client.ts` chọn theo `typeof window`. Không tách thì gate "frontend gọi được backend" sẽ vỡ khi Phase 2 thêm client component đầu tiên.

**`pydantic-settings` phải tắt JSON decode cho `cors_origins`** — thư viện tự `json.loads` các field kiểu `list` lấy từ biến môi trường, trước cả validator tách chuỗi. Dùng `NoDecode`. Lỗi này ẩn khi chạy trên host (không có `.env` nên dùng giá trị mặc định) và chỉ lộ ra trong container.

**Hot reload frontend không hoạt động trong Docker trên Windows** — Turbopack không nhận thay đổi qua bind mount dù đã cấu hình `watchOptions.pollIntervalMs` và xác nhận mtime tới được container. Backend thì reload bình thường nhờ polling. Cách làm việc: chạy Next native trên host, phần còn lại trong Docker (ghi trong `infra/README.md`).

**CI có job migration riêng** — test backend không chạm database nên hai job lint/test không thể fail vì migration hỏng. Job thứ ba chạy upgrade → downgrade → upgrade → `alembic check` → seed hai lần, trên database trắng không có init script. (Từ Phase 2 test backend có chạm database — xem mục cuối phần dưới.)

## Phase 2 — Core Platform

**Access token là JWT, refresh token là chuỗi ngẫu nhiên** — access token phải xác thực được mà không truy vấn DB, nên là JWT HS256 sống 15 phút. Refresh token cần **thu hồi được**, mà JWT thì không thu hồi được nếu không tra bảng — vậy nên nó chỉ là 48 byte `secrets` ngẫu nhiên, tra thẳng bảng `refresh_tokens`.

**Refresh token chỉ đi trong cookie `HttpOnly`, giới hạn `Path=/api/v1/auth`** — JavaScript không đọc được nên một lỗ XSS ở frontend không lấy được phiên 30 ngày. Giới hạn path để cookie không bị gửi kèm mọi request khác (giảm bề mặt CSRF). `SameSite=lax` chứ không `strict`: vào site từ kết quả tìm kiếm Google không được hiện ra như chưa đăng nhập.

**DB chỉ lưu SHA-256 của refresh token, không dùng bcrypt** — token là 384 bit ngẫu nhiên, không có "mật khẩu yếu" để làm chậm kẻ dò, nên bcrypt chỉ tốn thời gian ở **mỗi lần refresh**. Lộ dump DB vẫn không đăng nhập lại được vì không có token thô.

**Xoay vòng refresh token + coi tái sử dụng là bị đánh cắp** — mỗi lần refresh thành công thu hồi token cũ. Token đã thu hồi quay lại ⇒ thu hồi **toàn bộ** phiên của user đó (`REFRESH_TOKEN_REUSED`). Không phân biệt được bản của kẻ trộm với bản của nạn nhân nên phải cắt cả hai; giá phải trả là người dùng bị đăng xuất mọi thiết bị trong một số tình huống lành tính (hai tab cùng refresh sau khi đã đăng xuất).

**Email sai và mật khẩu sai trả cùng một lỗi `INVALID_CREDENTIALS`, kèm bcrypt "mồi"** — nếu tài khoản không tồn tại mà trả lời ngay thì thời gian phản hồi khác biệt biến form đăng nhập thành công cụ dò xem một email có đăng ký ở đây không. Tài khoản chỉ đăng nhập Google (`password_hash IS NULL`) cũng rơi vào nhánh này.

**Khóa tài khoản kiểm tra *sau* khi so mật khẩu** — trả `ACCOUNT_LOCKED` trước khi biết mật khẩu đúng hay sai cũng là một cách lộ "email này có tài khoản".

**Vai trò không nhận từ request body** — `register_user()` tự đặt `role='student'`; gửi kèm `"role": "admin"` bị bỏ qua. Chống mass assignment ngay từ chữ ký hàm chứ không bằng việc nhớ lọc field.

**Test backend từ nay chạy trên Postgres thật** — auth có quá nhiều hành vi ở tầng DB (unique email, cascade, xoay vòng token) để mock cho đáng tin. Mỗi test nằm trong một transaction bị rollback (`join_transaction_mode="create_savepoint"` nên `commit()` thật trong service vẫn chạy). Job `backend` của CI vì thế phải thêm service Postgres; máy dev không có DB thì nhóm test này tự skip, nhưng khi biến `CI` được đặt thì fail — CI không được phép xanh nhờ bỏ qua test.

**Access token giữ trong bộ nhớ React, không lưu `localStorage`** — không có kho nào để script chèn vào trang đọc trộm, và token chết theo tab. Cái phải trả: mỗi lần F5 phải gọi `/auth/refresh` để dựng lại phiên (một nhịp "đang tải" ở header), và `middleware.ts` của Next không guard được route vì cookie refresh thuộc origin của backend — guard sẽ làm ở client khi có trang cần bảo vệ.

**Mọi lời gọi refresh của frontend gom vào một promise** — xoay vòng token gặp React StrictMode (chạy effect hai lượt trong dev) thành ra tự đăng xuất: request thứ hai mang đúng token mà request thứ nhất vừa thu hồi, backend coi là bị đánh cắp và hủy sạch phiên. Đã tái hiện thật rồi mới sửa. Còn sót tình huống hai tab mở song song; nếu gặp nhiều thì thêm khoảng ân hạn ở backend, đổi lại token bị trộm sẽ dùng được trong khoảng đó.

**URL backend cho trình duyệt phải là `localhost`, không phải `127.0.0.1`** — trình duyệt coi đây là hai site khác nhau, cookie `SameSite=lax` sẽ không được gửi kèm. Biểu hiện rất khó đoán: đăng nhập được nhưng F5 là mất phiên.

**Google OAuth: authorization code phía backend, không dùng Google Identity Services phía trình duyệt** — client secret nằm lại máy chủ, trình duyệt không cầm gì dùng lại được, và cùng một chỗ cấp refresh token như đăng nhập bằng mật khẩu. Trả giá: thêm một vòng chuyển hướng và phải tự lo `state`.

**Callback không nhét token vào URL, mà đặt cookie rồi 302 về frontend** — token trong query string sẽ nằm lại lịch sử trình duyệt, header `Referer` và log server. SPA lấy phiên bằng `/auth/refresh` như mọi lần tải trang khác, nên không có đường đi riêng nào phải bảo trì.

**Gộp tài khoản theo email chỉ khi Google báo `email_verified: true`** — thiếu điều kiện này thì ai tạo được tài khoản Google mang email chưa xác thực là chiếm được tài khoản tương ứng ở đây. Claim thiếu hoặc "truthy nhưng không phải `true`" đều tính là chưa xác thực; đã kiểm bằng test đột biến (nới thành `bool()` là 4 test đỏ).

**Ưu tiên `sub` hơn email khi nhận diện** — email Google đổi tên được, và trên Workspace còn cấp lại cho người khác; `sub` thì không đổi. Nhận theo `sub` trước, email chỉ dùng ở lần liên kết đầu tiên.

**Adapter Google nằm sau `Protocol` + dependency của FastAPI** — test thay bằng bản giả nên không cần mạng, không cần credential; chạy được ở CI của repo private. Cùng khuôn với adapter LLM sẽ làm ở Phase 4.

**Test phải chạm được đường thật, không chỉ bản giả** — bản giả cắm ở tầng dependency của FastAPI chứng minh route đúng, nhưng vẫn xanh trên một bản build mà PyJWT **không verify nổi RS256**: `cryptography` là extra tùy chọn, thiếu nó thì đăng nhập Google chết ngay lần đầu người thật bấm nút. Chỗ này lộ ra khi dựng thêm một "Google giả" chạy trên `127.0.0.1` (ký RS256 thật, phục vụ JWKS thật) để test đúng đoạn `httpx` → đổi mã → verify chữ ký. Dependency sửa thành `pyjwt[crypto]`.

**`require_role` so khớp chính xác, admin không phải superset** — `require_role("instructor")` không ngầm cho admin qua; endpoint cho cả hai phải viết `require_role("instructor", "admin")`. Phân cấp ngầm tiết kiệm vài ký tự nhưng tạo ra quy tắc không ai nhớ ở endpoint thứ ba mươi, và lúc đó lỗ hổng là im lặng.

**Vai trò đọc từ DB chứ không từ claim trong access token** — token là ảnh chụp lúc phát hành, sống 15 phút; thu hồi quyền mà phải chờ 15 phút mới có hiệu lực là quá lâu. Giá phải trả: mỗi request có thêm một truy vấn `users` — chấp nhận được vì `get_current_user` vốn đã phải tra để biết tài khoản có bị khóa không.

**Nâng cấp giảng viên là self-service, không hàng đợi duyệt** — một mình vận hành thì hàng đợi duyệt chỉ là hàng đợi không ai xử lý. Chốt chặn thật nằm ở chỗ khác: khóa học của giảng viên mới vẫn phải qua trạng thái `pending_review` trước khi công khai. Admin gọi endpoint này bị từ chối 409 thay vì lặng lẽ không làm gì, vì với admin thì đây là **mất** quyền chứ không phải thêm.

**Đổi mật khẩu thu hồi mọi phiên khác, nhưng giữ thiết bị vừa đổi** — người ta đổi mật khẩu phần lớn vì nghi có người khác biết nó, nên các thiết bị khác phải văng ra; đăng xuất luôn cả thiết bị vừa làm đúng việc thì lại là một hình phạt vô lý. Endpoint vì thế trả về cặp token mới kèm cookie mới.

**Vẫn đòi mật khẩu hiện tại dù người gọi đã đăng nhập** — access token sống 15 phút và có thể đang nằm trong tay người vừa ngồi xuống chiếc laptop chưa khóa màn hình; mật khẩu là thứ chỉ chủ tài khoản biết. Đây là lý do form đổi mật khẩu ở mọi hệ thống nghiêm túc đều có ô "mật khẩu hiện tại".

**Email không sửa được trong form hồ sơ** — địa chỉ mới phải xác thực xong mới tin được (nó là khóa để gộp tài khoản Google, và là đường khôi phục tài khoản). Đó là một luồng riêng có bước gửi thư, không phải một ô input.

**Thêm cờ `has_password` vào payload người dùng** — frontend cần biết tài khoản Google-only để không hiện form đổi mật khẩu chắc chắn lỗi 409. Là một boolean *về* tài khoản, không phải thông tin *về* mật khẩu; test rò rỉ được siết lại thành "không có `$2b$` và không có plaintext" thay vì chặn thô theo chuỗi "password".

**Test viết sau hành vi thì phải kiểm bằng đột biến** — bộ test "auth flow" phủ các hành vi đã có sẵn nên nó xanh ngay từ lần chạy đầu, mà xanh ngay thì không chứng minh được gì. Cách kiểm: phá tạm đúng chỗ cần bảo vệ (bỏ kiểm tra tài khoản bị khóa lúc refresh; cho `logout` thu hồi mọi phiên thay vì phiên hiện tại) và xác nhận đúng hai test đó đỏ, rồi khôi phục. Đây là bằng chứng "test có răng" cho chương kiểm thử, rẻ hơn nhiều so với đo độ phủ.

**Slug khóa học dùng hậu tố ngẫu nhiên, không dùng bộ đếm** — bộ đếm `-2`, `-3` cần một truy vấn để tìm số trống, và hai request cùng lúc vẫn chọn trúng cùng một số; hậu tố 6 ký tự ngẫu nhiên để unique index quyết định, không tốn round trip. Slug **không đổi khi đổi tiêu đề**: URL đã chia sẻ phải còn sống.

**Khóa học nháp trả 404 cho người ngoài, nhưng sửa nhầm khóa của người khác trả 403** — hai câu trả lời khác nhau vì hai mối lo khác nhau: thứ chưa xuất bản thì không nên xác nhận là tồn tại, còn khi người dùng *đã* biết khóa học đó (đang đứng ở trang quản lý, lỡ đăng nhập nhầm tài khoản) thì "không phải của bạn" hữu ích hơn 404 nhiều.

**Soft delete đi qua đúng một hàm dựng truy vấn** — `_active_courses()` là điểm vào duy nhất, nên không thể có truy vấn thứ tám quên `deleted_at IS NULL`. Đây chính là cạm bẫy `database-design.md` cảnh báo khi chốt chỉ `courses` được soft delete.

**Auto-approve là feature flag, không phải code tạm** — `AUTO_APPROVE_COURSES=true` cho Phase 2 demo được vòng đời khóa học mà chưa cần màn duyệt của admin; Phase 5 tắt cờ là luồng `pending_review` chạy thật. Có test cho **cả hai** nhánh nên lúc tắt cờ không phải cầu may.

**`updated_at` do Postgres tính nên phải `refresh()` sau UPDATE** — SQLAlchemy đánh dấu thuộc tính hết hạn sau khi UPDATE có `onupdate=now()`, và đọc lại nó trong ngữ cảnh async ném `MissingGreenlet` chứ không phải lỗi dữ liệu. Mất một SELECT mỗi lần sửa, đổi lại giữ được đồng hồ của DB làm nguồn chân lý thay vì đồng hồ của app.

**Unique `(parent, position)` để DEFERRABLE thay vì né bằng offset tạm** — sắp xếp lại chương/bài ghi nhiều dòng trong một transaction và chắc chắn đi qua trạng thái hai dòng cùng vị trí. Cách phổ biến là cộng tạm 1000 vào tất cả rồi gán lại; cách này để Postgres kiểm lúc COMMIT, đúng ngữ nghĩa "trạng thái cuối mới cần hợp lệ". Trả giá: ràng buộc không báo lỗi ngay tại câu lệnh sai, và trong test (chạy trong savepoint) phải ép bằng `SET CONSTRAINTS ALL IMMEDIATE` mới thấy nó bắn.

**API sắp xếp nhận cả danh sách, không nhận lệnh di chuyển** — client đã biết thứ tự sau khi kéo-thả nên gửi nguyên trạng thái đích; không có chuỗi cập nhật từng phần nào có thể dừng giữa chừng. Danh sách phải đủ và không lặp, thiếu là 400 — vì một danh sách thiếu sẽ để lại những dòng bị bỏ quên ở vị trí cũ.

**Kéo bài học sang chương khác dùng chính endpoint sắp xếp của chương đích** — payload là "toàn bộ nội dung chương này, theo thứ tự này", nên bài đến từ chương khác được nhận nuôi luôn và chương cũ tự renumber. Không cần endpoint "move" riêng, và không có trạng thái trung gian nào mà bài học thuộc về cả hai chương.

**Mục lục và bài học là hai model tách rời** — `LessonSummary` không có `article_content`, nên không ai vô tình thêm một trường vào model dùng chung rồi lộ nội dung trả phí ra trang công khai. Bài không phải preview trả **403 `LESSON_LOCKED`** chứ không 404: mục lục đã công khai là bài đó tồn tại, giấu tiếp chỉ làm người dùng bối rối.

**`video_assets` tạo sớm, dù luồng upload chưa làm** — để `lessons.video_asset_id` có khóa ngoại thật ngay từ migration này thay vì `ALTER TABLE` thêm FK sau. `ON DELETE SET NULL`: mất video thì bài học vẫn còn và giữ nguyên vị trí trong mục lục.

