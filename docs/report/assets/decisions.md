# Nhật ký quyết định kỹ thuật

Ghi ngay khi quyết định, 1–2 dòng mỗi mục, để Phase 8 viết chương 4 (Xây dựng hệ thống) không phải nhớ lại. Chỉ ghi quyết định **có đánh đổi**; những thứ chỉ có một cách làm thì không cần.

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

**Auto-approve là feature flag, không phải code tạm** — `AUTO_APPROVE_COURSES=true` cho Phase 2 demo được vòng đời khóa học mà chưa cần màn duyệt của admin; Phase 5 tắt cờ là luồng `pending_review` chạy thật. Có test cho **cả hai** nhánh nên lúc tắt cờ không phải cầu may. *(Cập nhật 30/09/2026, Phase 5:)* cờ đã được **bỏ hẳn** chứ không chỉ tắt — một cờ còn đó là một cách để bản production lỡ bật lại việc xuất bản không qua ai. Chỗ dễ vỡ nhất của việc bỏ cờ không nằm ở trạng thái mà ở hai job treo trên khoảnh khắc xuất bản (ingest RAG, nhúng khóa học): chúng dời sang endpoint **duyệt** của admin, và `tests/api/test_course_ingest.py` được viết lại để ghim đúng điều đó (gửi duyệt → 0 job, duyệt → 1 + 1); bằng chứng chạy thật ở `phase-5/admin-moderation.txt`.

**`updated_at` do Postgres tính nên phải `refresh()` sau UPDATE** — SQLAlchemy đánh dấu thuộc tính hết hạn sau khi UPDATE có `onupdate=now()`, và đọc lại nó trong ngữ cảnh async ném `MissingGreenlet` chứ không phải lỗi dữ liệu. Mất một SELECT mỗi lần sửa, đổi lại giữ được đồng hồ của DB làm nguồn chân lý thay vì đồng hồ của app.

**Unique `(parent, position)` để DEFERRABLE thay vì né bằng offset tạm** — sắp xếp lại chương/bài ghi nhiều dòng trong một transaction và chắc chắn đi qua trạng thái hai dòng cùng vị trí. Cách phổ biến là cộng tạm 1000 vào tất cả rồi gán lại; cách này để Postgres kiểm lúc COMMIT, đúng ngữ nghĩa "trạng thái cuối mới cần hợp lệ". Trả giá: ràng buộc không báo lỗi ngay tại câu lệnh sai, và trong test (chạy trong savepoint) phải ép bằng `SET CONSTRAINTS ALL IMMEDIATE` mới thấy nó bắn.

**API sắp xếp nhận cả danh sách, không nhận lệnh di chuyển** — client đã biết thứ tự sau khi kéo-thả nên gửi nguyên trạng thái đích; không có chuỗi cập nhật từng phần nào có thể dừng giữa chừng. Danh sách phải đủ và không lặp, thiếu là 400 — vì một danh sách thiếu sẽ để lại những dòng bị bỏ quên ở vị trí cũ.

**Kéo bài học sang chương khác dùng chính endpoint sắp xếp của chương đích** — payload là "toàn bộ nội dung chương này, theo thứ tự này", nên bài đến từ chương khác được nhận nuôi luôn và chương cũ tự renumber. Không cần endpoint "move" riêng, và không có trạng thái trung gian nào mà bài học thuộc về cả hai chương.

**Mục lục và bài học là hai model tách rời** — `LessonSummary` không có `article_content`, nên không ai vô tình thêm một trường vào model dùng chung rồi lộ nội dung trả phí ra trang công khai. Bài không phải preview trả **403 `LESSON_LOCKED`** chứ không 404: mục lục đã công khai là bài đó tồn tại, giấu tiếp chỉ làm người dùng bối rối.

**`video_assets` tạo sớm, dù luồng upload chưa làm** — để `lessons.video_asset_id` có khóa ngoại thật ngay từ migration này thay vì `ALTER TABLE` thêm FK sau. `ON DELETE SET NULL`: mất video thì bài học vẫn còn và giữ nguyên vị trí trong mục lục.

**Kéo-thả dùng dnd-kit, không dùng nút lên/xuống** — đây là dependency UI đầu tiên ngoài shadcn, đổi lại được thao tác đúng như giảng viên mong đợi ở một nền tảng kiểu Udemy. Điều kiện kèm theo: phải dùng được bằng bàn phím (tay nắm → phím cách → mũi tên → phím cách) và có thông báo tiếng Việt cho screen reader, vì dnd-kit chỉ kèm sẵn tiếng Anh và đọc ra UUID của phần tử.

**Trong lúc kéo một chương, mọi bài học bị tắt vai trò điểm thả** — chương đang kéo đi ngang qua chính các bài học của nó, mà mỗi bài đều là một droppable, nên mũi tên xuống dừng lại ở từng bài một thay vì nhảy sang chương kế. `disabled: { draggable: false, droppable: true }` theo loại phần tử đang kéo sửa cả đường chuột lẫn đường bàn phím, vì `sortableKeyboardCoordinates` cũng chỉ xét các droppable còn bật.

**Kéo-thả cập nhật lạc quan rồi mới gọi API** — thứ tự mới ghi thẳng vào cache của TanStack Query lúc thả, request đi sau; lỗi thì `invalidate` để sự thật từ server ghi đè và hiện một dòng báo lỗi. Kéo mà phải chờ round trip mới thấy hàng di chuyển là cảm giác của một trang hỏng.

**Trạng thái cây chỉ tồn tại trong lúc kéo** — `dragTree` giữ bản làm việc từ lúc nhấc đến lúc thả (để bài học *nhìn thấy được* là đã rời chương này sang chương kia), ngoài lúc đó cache của query là nguồn chân lý duy nhất. Không đồng bộ server → state bằng `useEffect`: đó là cách chắc chắn nhất để có hai nguồn chân lý cãi nhau.

**Endpoint `GET /categories` sinh ra vì form tạo khóa học cần nó** — không phân trang, trả cả cây hai tầng: đây là bảng phân loại admin biên tập chứ không phải dữ liệu người dùng, và `<optgroup>` cần đúng hình dạng đó.

**Cổng giảng viên ở client loại cả admin** — `require_role("instructor")` khớp chính xác nên admin gọi API quản lý khóa học sẽ ăn 403; cho admin thấy màn hình đó chỉ để họ gặp lỗi ở mọi thao tác. Cổng này là phép lịch sự với người dùng, còn quyền thật vẫn nằm ở backend.

**Cạm bẫy khi test kéo-thả bằng bàn phím** — nếu trang còn cuộn được và đích đến nằm dưới điểm giữa màn hình, `KeyboardSensor` của dnd-kit **cuộn trang** thay vì di chuyển phần tử. Với người dùng thật thì trang cuộn vài nhịp rồi mới bắt đầu di chuyển, không sao; với script kiểm thử thì trông y hệt một tính năng hỏng. Cách kiểm đúng: đặt viewport đủ cao để trang hết cuộn.

**Video đi thẳng từ trình duyệt lên R2, backend chỉ ký URL** — đẩy vài trăm MB qua FastAPI sẽ giữ chặt một tiến trình suốt thời gian upload và trả tiền băng thông hai lần, trong khi chữ ký đã nói đủ: ai được ghi, ghi vào key nào, trong bao lâu. `Content-Type` nằm trong phần được ký nên một URL đã ký không dùng lại được để tải thứ khác lên cùng tên.

**Luôn chuyển mã lại, không bao giờ `-c copy`** — file từ điện thoại có thể là HEVC, VP9, hoặc mang track âm thanh không trình duyệt nào phát. Phát hiện điều đó lúc phát, trên máy người khác, là chỗ tệ nhất để phát hiện. Trả giá bằng CPU của worker.

**`-pix_fmt yuv420p` là bắt buộc, không phải tùy chọn** — bài học rút ra từ chính test: nguồn 4:4:4 khiến libx264 thoát mã -22 và không sinh ra file nào, vì `-profile:v main` chỉ định nghĩa cho 4:2:0. Đây là loại lỗi mà test giả lập ffmpeg sẽ vui vẻ bỏ qua; chỉ có test chạy ffmpeg thật mới bắt được.

**Trạng thái video là một hàng trong bảng, không phải một exception** — worker bắt mọi lỗi, ghi `failed` kèm `error_message` viết cho giảng viên đọc. Ném exception ra ngoài thì Celery sẽ thử lại một video hỏng mãi mãi, và người duy nhất cần biết lại không bao giờ thấy.

**Job chạy lại không làm hỏng video đã xong** — Celery giao lại task khi worker chết giữa chừng, nên `transcode()` bỏ qua mọi asset không ở trạng thái `processing`. Không có bước này thì một lần restart worker sẽ tái xuất bản video đã hoàn tất.

**`services/storage.py` là Protocol** — cùng khuôn với `google_oauth.py`: router không biết boto3 tồn tại, test không chạm Cloudflare. `R2_ENDPOINT_URL` cho phép trỏ sang server S3 khác, nhờ đó **toàn bộ luồng đã được kiểm chứng end-to-end với MinIO chạy local trước khi có tài khoản R2** — ký URL, trình duyệt PUT, CORS preflight, worker tải về, ffmpeg, tải HLS lên, phát công khai.

**Tải lên lần nữa là thay hẳn video cũ** — hàng cũ bị xóa và object dưới prefix của nó bị dọn. Giữ lại thì bài học phát một video còn bucket trả tiền cho hai. Việc dọn chạy **sau** commit và nuốt lỗi: một object mồ côi tốn dung lượng, còn một lần xóa hỏng sẽ tốn của giảng viên cả lần upload.

**Hỏi trạng thái tạm dừng khi tab bị ẩn** — mặc định của TanStack Query, và đúng ở đây: chuyển mã mất vài phút, giảng viên chuyển tab đi làm việc khác, quay lại là `refetchOnWindowFocus` cho kết quả ngay. Hệ quả cho người viết test: script chạy trong pane không được focus sẽ thấy trạng thái đứng im, trông y hệt tính năng hỏng.

**Tổng duyệt stack production trên máy dev trước khi có VPS** — chạy đúng `docker-compose.prod.yml`, image target `production`, nginx và TLS thật, chỉ thay tên miền bằng `localhost` và chứng chỉ Let's Encrypt bằng chứng chỉ tự ký. Đổi lại vài giờ, được cái chắc chắn rằng khi có máy chủ thì chỉ còn đúng hai ẩn số là DNS và ACME. Nó đã trả công ngay: bắt được lỗi tài khoản seed không đăng nhập được.

**Email seed dùng `.example` chứ không phải `.local`** — seed ghi thẳng vào bảng `users` nên không đi qua kiểm tra nào, còn `/auth/login` kiểm địa chỉ bằng `EmailStr` và `email-validator` từ chối `.local` như một tên miền dành riêng. Ba tài khoản tồn tại mà không đăng nhập được, kể cả tài khoản giảng viên mà kịch bản demo yêu cầu. `.example` (RFC 2606) vừa hợp lệ vừa không thể thuộc về ai. Bài học đáng viết vào báo cáo: lỗi nằm ở khe giữa hai đường ghi vào cùng một bảng, nên không test đơn vị nào của một trong hai đường bắt được — chỉ có chạy thật mới thấy.

**Deploy bằng tay, không nối vào CI** — với một khóa luận, việc bấm deploy là quyết định chứ không phải thao tác lặp. `scripts/deploy.sh` cố tình không `git pull`: người deploy phải tự chọn commit nào lên production.

**nginx không `depends_on` backend** — upstream được phân giải theo từng request qua biến, nên nginx sống một mình và trả 502 trong lúc chờ. Nhờ đó `init-tls.sh` xin được chứng chỉ trên máy chủ chưa build image lần nào, và một container ứng dụng khởi động lại với IP mới không cần restart nginx. Trả giá bằng một truy vấn DNS nội bộ mỗi request, có `valid=10s` chặn.

**Bundle frontend không mang tên miền** — `NEXT_PUBLIC_*` bị nướng vào bundle lúc `next build`, nên để `https://<domain>` ở đó có nghĩa là mỗi lần đổi URL công khai đều phải build lại image. Đặt biến rỗng và quy ước rỗng = "cùng origin với trang": sau nginx thì điều đó luôn đúng vì `/api` về backend trên chính origin ấy. Được ba thứ cùng lúc — một bản build chạy trên URL tunnel ngẫu nhiên, trên tên miền thật, hay trên IP trần; không còn request khác site nên cookie refresh `SameSite=lax` không bao giờ bị bỏ; và deploy đổi tên miền chỉ là sửa `.env.prod`. Trả giá bằng một quy ước phải nhớ: rỗng khác với không đặt, và phía server phải dùng `||` thay `??` vì URL tương đối không có ý nghĩa trong Node.

**URL công khai bằng Cloudflare Quick Tunnel thay vì thuê máy chủ sớm** — giai đoạn Phase 2–5 cần một link người khác mở được, không cần một máy chủ đứng suốt ngày. Tunnel cho đúng chừng đó với 0đ, không tài khoản, không tên miền, và chứng chỉ hợp lệ thật. Trả giá bằng ba thứ đã biết trước: URL ngẫu nhiên đổi sau mỗi lần khởi động, sống đúng bằng thời gian máy dev bật, và đăng nhập Google không dùng được vì redirect URI phải đăng ký trước. Điều kiện tiên quyết là bundle frontend đã bỏ tên miền — nếu còn nướng domain vào bundle thì mỗi URL tunnel mới lại phải build lại image.

**Tunnel trỏ vào nginx chứ không trỏ thẳng vào Next** — `/api` phải về backend trên cùng origin với trang, và nginx là thứ làm điều đó đúng. Trỏ vào `frontend:3000` sẽ cho một trang mở được nhưng 404 ở mọi lời gọi API. Đây cũng là lý do dùng overlay `docker-compose.tunnel.yml` cộng vào stack production, thay vì chạy cloudflared rời trên host: trong mạng compose thì `nginx` là một hostname có sẵn.

## Phase 3 — Code Grading ⭐

**Image sandbox dùng user riêng `sandbox` (uid 10001) thay vì `nobody`** — kế hoạch viết "user nobody", nhưng 65534 là đúng cái uid mà những thứ khác trên máy chủ đã ánh xạ vào, rõ nhất là NFS squash. Một uid riêng trong dải của mình là con số worker sẽ dùng khi quyết định ai sở hữu file được mount vào; hai tiến trình không liên quan dùng chung một danh tính là trùng hợp nên tránh chứ không nên dựa vào. `USER` đặt sẵn trong image nên `--user` của runner trở thành lớp thứ hai chứ không phải lớp duy nhất — test chạy **không** truyền `--user` để chứng minh đúng điều đó.

**"Tối giản" ở đây là tối giản nội dung, không phải dung lượng** — image 187 MB, base 189 MB. Xóa pip/ensurepip và làm rỗng site-packages không tiết kiệm được bao nhiêu byte; cái nó mua là **tính tái lập của verdict**: image đúng bằng thư viện chuẩn, hôm nay và sau mỗi lần bump base, nên một bài AC tháng 9 không thể WA tháng 11 vì một gói lặng lẽ đổi phiên bản.

**Không xóa apt/dpkg khỏi image** — với `--network none` thì apt không tải được gì, với rootfs read-only và uid không đặc quyền thì nó không ghi được vào đâu. Xóa đi chỉ để trông gọn là an ninh trình diễn; giữ lại thì còn `dpkg -l` để kiểm kê image chứa gì. Thứ thật sự được xóa là **bit setuid**: base có 11 binary (`su`, `mount`, `passwd`...), image sandbox còn 0 — `--cap-drop ALL` và `no-new-privileges` đã vô hiệu hóa chúng, nhưng cả hai đều là cờ trên dòng lệnh của người khác, còn bit thì không.

**`PYTHONHASHSEED=0` và `PYTHONUNBUFFERED=1` là quyết định chấm bài, không phải quyết định bảo mật** — Python mặc định ngẫu nhiên hóa hash chuỗi theo tiến trình, nên một bài in ra `set` sẽ AC hay WA tùy worker nào nhặt được, trên cùng một dòng code. Còn bài bị giết vì quá giờ chết đúng kiểu `os._exit`: đo thật trên base thì output đã in **mất sạch**, trên image sandbox thì còn nguyên. Học viên đáng được thấy chương trình mình chạy tới đâu trước khi bị cắt.

**Test khẳng định từ bên trong container đang chạy, không đọc `docker inspect`** — inspect chỉ nói image *khai báo* gì; chỉ chạy một chương trình mới biết nhân *cho phép* gì. Mỗi test đều được đối chứng với `python:3.12-slim` nguyên bản trước khi tin: một test mà image thường cũng qua là một test không kiểm gì cả (bảng đối chứng ở `docs/report/assets/phase-3/sandbox-image.txt`).

**Thiếu Docker: skip trên máy dev, fail trong CI** — cùng quy tắc mà bộ test backend đã dùng cho Postgres. Một bộ test sandbox bị skip im lặng biến "chưa bao giờ kiểm sandbox" thành một dấu tick xanh, đúng cái kết cục mà bộ test này sinh ra để chặn.

**`--init` là bắt buộc, vì PID 1 nuốt tín hiệu** — nhân không áp dụng hành vi mặc định của tín hiệu cho PID 1, nên bài nộp chạy làm PID 1 sẽ bỏ qua SIGXCPU và giới hạn CPU mềm trở thành vô nghĩa. Đo được: cùng `--ulimit cpu=1:2`, không `--init` thì exit 137 sau 2.72s (giới hạn cứng giết), có `--init` thì exit 152 sau 1.88s (giới hạn mềm, đúng hạn). Hệ quả kép: giới hạn trong bắn đúng hạn, **và** mã thoát 152 phân biệt được "quá giờ" với "crash" — thứ mà bước gán verdict sắp cần.

**Đồng hồ tường suy ra từ ngân sách CPU, không chọn rời** — `wall = (cpu_seconds + 1) / cpus + grace`. Container được nửa nhân cần hai giây tường cho mỗi giây CPU; chọn 5s tường cho 5s CPU (phỏng đoán tự nhiên nhất) thì lớp ngoài luôn bắn trước, lớp trong không bao giờ áp dụng, và thời gian một bài được chạy lặng lẽ trở thành hàm của việc máy chủ đang bận đến đâu. Cộng thêm 1 giây CPU vì đó là khoảng ân hạn của chính nhân giữa SIGXCPU và SIGKILL.

**Runner trả về *sự việc*, không trả về verdict** — `Outcome` nói chương trình kết thúc bằng đường nào (thoát, hết giờ CPU, hết giờ tường, hết bộ nhớ, lỗi hệ thống). Ánh xạ sang AC/WA/TLE/MLE/RE/CE/SE là việc của bước sau. Nhờ ranh giới này, luật verdict test được mà không cần container, còn container test được mà không cần khái niệm "đáp án đúng".

**Đọc output có trần bằng luồng riêng, không đọc hết rồi cắt** — bao nhiêu byte được in ra là quyết định của bài nộp, nên nếu đọc hết thì bài nộp quyết định worker tốn bao nhiêu RAM. Vẫn phải **tiếp tục đọc và vứt** phần vượt trần: dừng đọc hẳn thì chương trình kẹt ở pipe đầy, không tốn CPU nữa, giới hạn CPU không còn tác dụng và chỉ còn đồng hồ tường kết thúc được nó.

**`write_bytes` chứ không `write_text` khi ghi mã nguồn và stdin** — trên Windows `write_text` đổi `\n` thành `\r\n`, thêm carriage return vào cuối mỗi dòng input của test case. Một bài đúng sẽ bị chấm sai vì một ký tự không nhìn thấy được, và lỗi này chỉ lộ ra ở máy dev Windows chứ không lộ trên VPS Linux — đúng loại lỗi mà "chạy được trên máy tôi" nói ngược.

**Thư mục mount chỉ chứa đúng `main.py`** — file stdin và mọi thứ khác của runner nằm ngoài mount. Để chung thì bài nộp vừa đọc được input đáng lẽ phải giải mù, vừa có thể `import` bất cứ thứ gì nó thấy ở đó.

**Container không dùng `--rm`, mà `create` → `start` → `inspect` → `rm --force`** — `--rm` xóa container trước khi kịp đọc `State.OOMKilled`, mà đó là câu trả lời duy nhất phân biệt "bị nhân giết vì hết bộ nhớ" với "bị giết vì lý do khác" (cả hai đều exit 137). Tách `create` khỏi `start` còn làm cho lỗi tạo container (thiếu image, daemon chết) không thể bị nhầm thành mã thoát của bài nộp.

**Mọi container mang nhãn `devpath.grading=1`** — worker chết giữa chừng thì đống container còn lại tìm và dọn được bằng một lệnh không thể quét trúng thứ gì khác trên máy chủ.

**Chuẩn hóa output tha lỗi của trình soạn thảo, không tha quyết định của chương trình** — bỏ khoảng trắng cuối dòng, CRLF và dòng trống ở cuối; giữ nguyên thụt đầu dòng, khoảng trắng giữa dòng, thứ tự dòng, hoa/thường. Đo được: 8 trong 14 ca đối chứng là bài làm đúng bị so sánh byte chấm sai, và không ca nào theo chiều ngược lại.

**Không dùng `str.splitlines()` để tách dòng** — nó cắt dòng trên 11 ký tự chứ không phải 1, nên `a\x0bb` và `a\nb` bằng nhau: một bài in ra ký tự điều khiển được chấm như đã xuống dòng. Chỉ tách trên LF, sau khi quy CRLF/CR về LF.

**Output bị cắt vì quá trần 1 MB thì không bao giờ AC** — một đoạn đầu trùng đáp án không nói gì về phần còn lại. Thiếu luật này thì chính cái trần bảo vệ bộ nhớ worker lại thành lỗ hổng chấm điểm: in đúng đáp án rồi in thêm 500 MB rác vẫn AC.

**Thứ tự ưu tiên verdict: SE → giới hạn → crash → so output** — mỗi bậc bảo vệ học viên khỏi một câu trả lời sai về chương trình của chính họ. Lỗi phía mình (SE) không bao giờ tính vào học viên. Bài bị giới hạn giết chưa chạy xong nên thứ nó in ra chưa từng là câu trả lời — gọi WA sẽ chỉ học viên sai chỗ. Bài in đúng đáp án rồi mới chết vẫn không đậu.

**Verdict của cả bài lấy theo case hỏng đầu tiên, không phải case "nặng nhất"** — test case do giảng viên xếp, dễ trước, nên "case 3 quá giờ" là câu học viên hành động được.

**Hàng đợi `grading` tách khỏi hàng đợi mặc định** — một bài nộp là vài container và vài giây; để chung thì một đợt nộp bài làm email xác thực và job transcode nằm chờ sau nó. Tách hàng đợi còn cho phép chỉnh riêng concurrency của việc chấm theo tài nguyên máy chủ.

**Retry chỉ dành cho lỗi phía mình, không dành cho lỗi của bài nộp** — daemon chết hay hết chỗ đĩa thì giao lại; bài nộp crash hay sai đáp án thì không, vì chạy lại mười lần vẫn ra đúng kết quả đó và chỉ tốn thêm mười lần tài nguyên.

**Rate limit hai cửa: cooldown 10 giây và hạn mức 40 bài mỗi giờ** — cooldown chặn nút bị bấm hai lần và script hammer; hạn mức chặn script kiên nhẫn biết chờ hết cooldown. Cả hai đều cao hơn nhiều so với nhịp làm bài thật.

**Test case ẩn: API không trả input lẫn đáp án, kể cả khi case đó sai** — đúng lúc học viên muốn biết nhất cũng là lúc không được nói. Mạnh hơn thế: worker **không nạp** case ẩn khi chạy thử (`samples_only=submission.is_trial`), nên không tồn tại thời điểm nào một lần chạy thử cầm đáp án ẩn.

**Chạy thử và nộp bài dùng chung hàng đợi, worker, sandbox và kênh tiến độ** — khác nhau đúng một cờ `submissions.is_trial`. Bảng riêng cho chạy thử sẽ phải nhân đôi hàng đợi, worker, kênh realtime và mọi luật về ai được đọc bài nộp nào.

**Tiến độ chấm đi bằng Redis pub/sub → WebSocket, có fallback polling** — publish thất bại thì ghi log WARNING chứ không làm hỏng lần chấm: kênh realtime hỏng thì học viên nhận kết quả chậm mười giây, không phải mất kết quả. Đã xảy ra thật một lần, và chính dòng log ấy chỉ ra lỗi.

**`GradingEvent` không có trường nào chứa input, output hay message** — bí mật của case ẩn không rò qua kênh realtime vì kiểu dữ liệu không chỗ nào đựng nó. Đây là tính chất của kiểu, không phải kết quả của một câu lệnh lọc.

**Monaco tự phục vụ từ `public/monaco`, không lấy từ CDN** — trang quan trọng nhất của đồ án không được phụ thuộc vào mạng của căn phòng đúng hôm bảo vệ. Kiểm bằng danh sách request thật: 19 file, tất cả cùng origin.

**Tiêu đề "đang chấm test n/N" bị kẹp ở N** — có khung mà cả N case đã xong nhưng worker còn đang ghi bảng điểm (`completed_cases = N`, `status` vẫn `running`). Không kẹp thì tiêu đề hiện "đang chấm test 9/8".

**Trang không đoán trạng thái của case mà máy chủ chưa nói gì** — nằm im ở "Chờ". Có riêng trạng thái "Đã chấm" (xong nhưng không rõ verdict) cho tình huống ảnh chụp báo nhiều case hơn số sự kiện nhận được.

**Nhánh polling không nhích giữa chừng, và chấp nhận như vậy** — worker ghi toàn bộ `submission_results` trong một commit lúc chấm xong, nên khi polling thì CSDL thật sự không biết case nào đã chạy. Commit sau mỗi case sẽ tốn 8 lần ghi + 8 lần commit mỗi bài nộp thay vì 1, đổi lấy trải nghiệm của nhánh chỉ chạy khi Redis hoặc WebSocket hỏng. Xem lại ở Phase 6 nếu tunnel/proxy chặn WebSocket thường xuyên.

**`GRADING_CONCURRENCY=2`, chọn công bằng chứ không chọn throughput cao nhất** — chạy 8 bài song song làm `run_time_ms` của chính chương trình học viên tăng gấp đôi (248 → 516 ms), trong khi giới hạn là 2000 ms: một bài đúng nhưng sát biên có thể ăn TLE chỉ vì nộp trúng lúc chín người khác cũng nộp. Ở 2 slot độ lệch là 21%. Muốn nhanh hơn thì tăng vCPU trước, 1 slot cho mỗi vCPU dôi ra.

**Benchmark đo bằng chính kênh realtime mà trang web đang nghe** — không cắm đồng hồ riêng vào worker, không thêm cột nào vào CSDL. Hệ quả: thứ được đo đúng là thứ học viên đang nhìn.

**AC ghi `lesson_progress.completed_at` trong cùng transaction với verdict** — một dấu hoàn thành ghi tách ra có thể sống sót qua một rollback của chính cái verdict biện minh cho nó, và một bài học được tick mà không có hàng AC nào đứng sau là loại lỗi không ai tìm ra. Chạy thử AC **không** tick: qua test mẫu không phải là giải được bài.

**Bài học video và bài đọc vẫn phải tự bấm hoàn thành** — không có cách nào biết người ta đã đọc xong, còn bài tập code thì có. Không suy diễn từ thời lượng xem.

**Test bảo mật khẳng định sự từ chối, không khẳng định cơ chế từ chối** — CI cho thấy `/proc/kcore` bị chặn ở cả hai máy nhưng bằng hai lớp khác nhau: daemon che bằng `/dev/null` trên máy dev, quyền `0400` gặp user không đặc quyền trên runner GitHub. Ghim test vào cơ chế của một máy là để nó đỏ trên một máy an toàn không kém. Điều này cũng sửa lại một câu trong báo cáo: "Docker che `/proc`" không phải tính chất chung của mọi máy chạy Docker.

**Test dùng CSDL phải tự dựng lấy tiền đề của nó** — test seed từng gọi thẳng `seed_courses()` và mượn hàng danh mục có sẵn trong CSDL dev, nên xanh ở máy và đỏ trong CI. Phần tiền đề đi mượn là phần không được kiểm.

---

## Phase 4 — AI Features ⭐

**Bảng `doc_chunks` dựng trước khi có API key Gemini** — việc chọn số chiều vector, khóa ngoại và index là quyết định schema, không phải quyết định model. Làm trước nghĩa là task ingest sau này chỉ còn phần gọi API, và cũng nghĩa là phần không phụ thuộc bên ngoài không bị chặn bởi phần phụ thuộc bên ngoài.

**Vector 768 chiều, chốt trong kiểu cột** — đúng cỡ gốc của `text-embedding-004` và là mức cắt Matryoshka hợp lệ của `gemini-embedding-001`, nên đổi model không nhất thiết phải viết lại cả bảng. Quan trọng hơn: 768 nằm dưới trần **2000 chiều** mà index HNSW của pgvector chấp nhận cho kiểu `vector` — chọn 3072 chiều là tự đẩy mình sang `halfvec` ngay từ dòng đầu tiên.

**`lesson_id` không null, dù về mặt dữ liệu có thể để trống** — chunk nào không chỉ được về một bài học thì không trích nguồn được, mà "trả lời kèm trích nguồn" là điều kiện gate của phase này. Ràng buộc đặt ở schema để không có đường nào tạo ra chunk không trích nguồn được.

**`course_id` denormalize, biết là dư và vẫn giữ** — đi vòng lesson → section → course vẫn ra đúng giá trị đó, nhưng mọi truy vấn top-k đều lọc theo khóa học, và hai phép join quanh một lần quét vector là chi phí trả ở *mỗi câu hỏi người dùng đặt*. Job ingest ghi cả hai cột cùng lúc, ingest lại xóa theo `lesson_id`, nên hai cột không lệch nhau được trừ khi có người sửa tay.

**Phạm vi khóa học cưỡng chế bằng `WHERE`, không bằng lời dặn trong prompt** — "chỉ trả lời trong phạm vi khóa học" mà chỉ viết trong prompt thì model phá được; viết thành điều kiện lọc hàng thì không. Đã có test: một chunk của khóa khác khớp câu hỏi hoàn hảo vẫn không được trả về.

**Cột `embedding_model` ghi model đã sinh ra vector** — hai model cùng 768 chiều vẫn đặt cùng một câu ở hai vị trí khác nhau, nên bảng trộn vector của hai model trả kết quả vô nghĩa **mà không báo lỗi**. Kế hoạch đã liệt "Gemini API đổi/giới hạn quota" vào rủi ro chính; cột này biến ngày đó thành một câu truy vấn thay vì một cuộc điều tra.

**Unique (`lesson_id`,`chunk_index`) để ingest lại là idempotent** — pipeline ingest xóa rồi ghi lại theo bài học; nếu job chết giữa chừng và chạy lại, ràng buộc này là thứ từ chối bản sao thứ hai.

**Index HNSW được xác nhận bằng `EXPLAIN` chứ không bằng việc nó tồn tại** — dựng HNSW sai lớp toán tử (`vector_l2_ops` trong khi truy vấn dùng `<=>`) không sinh ra lỗi nào: Postgres lặng lẽ quét tuần tự. Đo trên 3000 chunk: planner chọn `Index Scan using ix_doc_chunks_embedding`, 1,33 ms và 1239 buffer, so với 5,89 ms và 9055 buffer khi tắt index scan. Chưa đo recall — HNSW là tìm kiếm xấp xỉ, và câu hỏi "top-5 nó trả về có đúng là top-5 thật không" cần embedding thật, để đo cùng precision@k. Xem `phase-4/hnsw-index.txt`.

**Tham số `m`/`ef_construction` để mặc định** — tinh chỉnh HNSW là đánh đổi recall lấy tốc độ, mà recall thì chưa đo được khi chưa có embedding thật. Chỉnh sớm là chỉnh mù.

**Đồng hồ làm bài đặt ở máy chủ, trình duyệt chỉ hiển thị** — hạn nộp tính bằng `started_at + time_limit_s`, cả hai đọc từ hàng `quiz_attempts`, không có endpoint nào nhận thời gian từ client. Bộ đếm ngược trên trang chỉ đếm con số `seconds_remaining` mà máy chủ vừa trả về; tab bị treo, bị throttle hay chỉnh giờ máy đều không đổi được kết quả. Test chứng minh bằng cách kéo `started_at` lùi về quá khứ rồi nộp một bài **đúng hết**: vẫn 0 điểm.

**Ân hạn 10 giây sau hạn nộp** — học viên bấm nộp kịp giờ nhưng request mất vài giây trên đường truyền; từ chối bài đó là phạt đường truyền chứ không phạt hành vi. Cửa sổ 10 giây quá ngắn để mua thêm được câu trả lời nào, nên nó không phải là lỗ hổng.

**Không lưu đáp án dở trong lúc làm** — đổi lại: hết giờ mà chưa bấm nộp thì không có gì để chấm, và lượt đó là 0 điểm. Chọn như vậy để bảng `quiz_attempts` không phải nhận một lượt ghi cho mỗi cú click. Nếu sau này muốn chấm phần đã làm khi hết giờ thì phải thêm autosave trước — và ràng buộc `ck_quiz_attempts_expired_scores_zero` sẽ là chỗ báo cho người sửa biết quy tắc cũ là gì.

**Mỗi người mỗi quiz chỉ một lượt chưa nộp** — cưỡng chế bằng UNIQUE một phần (`WHERE submitted_at IS NULL`), không bằng câu lệnh kiểm tra trong service. Không có nó thì mở 4 tab là 4 đồng hồ và học viên giữ lại lượt nào đẹp nhất. Hệ quả phải xử lý kèm: lượt bỏ dở sẽ khóa slot vĩnh viễn, nên bất kỳ ai nhìn tới nó sau khi hết giờ đều đóng nó lại (`submitted_at` = đúng thời điểm hết giờ, không phải lúc phát hiện).

**`time_limit_s` chụp lại trên từng lượt làm** — cùng lý do `submissions` chép `language`: giảng viên sửa quiz không được phép dời hạn của người đang làm dở.

**Câu hỏi bị khóa khi quiz đang xuất bản** — chấm bài đọc `correct_index` tại thời điểm nộp, nên sửa đáp án giữa chừng là chấm học viên trên một đề họ chưa từng thấy. Muốn sửa thì gỡ xuất bản, mà gỡ xuất bản lại bị từ chối khi đang có người làm dở — hai quy tắc khép lại cùng một lỗ hổng từ hai phía.

**`correct_index < len(options)` đưa xuống CHECK của CSDL** — thiết kế ban đầu giao cho service. Nhưng service không phải nơi duy nhất ghi vào bảng này: task kế tiếp sinh câu hỏi bằng Gemini và ghi thẳng JSON của model xuống. Câu hỏi có đáp án đúng trỏ ra ngoài danh sách phương án không gây lỗi ở đâu cả — nó chỉ làm học viên bị chấm sai. Viết bằng `CASE` chứ không phải chuỗi `AND`, vì `jsonb_array_length` ném lỗi trên giá trị không phải mảng còn Postgres không hứa thứ tự đánh giá của `AND`.

**Đáp án và giải thích không có chỗ trên model trả về cho học viên đang làm bài** — `QuestionForAttempt` không có hai trường đó, `QuestionReview` (chỉ dựng sau khi đã nộp) mới có. Cùng một cách làm với test case ẩn ở Phase 3: quy tắc nằm ở chỗ *không có trường để lọt*, chứ không nằm ở việc nhớ xóa trường. Test kiểm trên **thân response dạng text**, không phải trên field đã parse.

**Đạt quiz thì đóng bài học, trong cùng transaction** — đúng quy tắc AC đóng bài tập code ở Phase 3, và dùng lại chính `progress_service.mark_lesson_solved` chứ không viết bản thứ hai.

**Collaborative filtering chọn item-based, không chọn ALS** — kiến trúc cho phép cả hai. Quyết định dựa trên dữ liệu nền tảng sẽ thực sự có: vài chục user, không phải vài chục nghìn. ALS học vector ẩn từ khởi tạo ngẫu nhiên; trên ma trận nhỏ cỡ này các vector đó phần lớn là nhiễu đổi theo seed — không kiểm tay được và không nói được vì sao gợi ý. Item-item cosine trên cùng ma trận thì tất định, mọi con số tính được trên giấy (test làm đúng như vậy), và mỗi gợi ý mang theo khóa học đã tạo ra nó — thứ trang "Học tiếp theo" trích được thành "vì bạn đã học …". ALS có tốt hơn không là câu hỏi cho `eval_recommender.py`, trả lời bằng precision@k chứ không bằng tranh luận.

**Trọng số lấy mức mạnh nhất, không cộng dồn** — hoàn thành thì chắc chắn đã đăng ký, viết review thì chắc chắn đã đăng ký; cộng dồn là đếm một sự thật hai ba lần và đẩy thang 1–3 lên 6.

**Đánh giá ≤2★ kéo trọng số về mức "đăng ký"** — ma trận implicit không có số âm, nên "học xong và thấy tệ" không đẩy được khóa học ra xa. Nhưng ít nhất nó không được tính là tín hiệu thích mạnh như một lần hoàn thành bình thường. 3★ không đổi gì.

**Tính bằng cộng dồn theo từng user, không nhân ma trận** — mỗi user đóng góp `w_a · w_b` cho mọi cặp khóa họ cùng học. Chi phí là tổng (số khóa mỗi user)², đúng bằng số cặp thật sự xuất hiện; nhân ma trận thì trả giá cho mọi cặp trong catalogue dù không ai học chung. Trọng số là số nguyên nên tổng chính xác tuyệt đối và không phụ thuộc thứ tự nạp dữ liệu — hai lần chạy batch cho cùng một kết quả, kể cả thứ tự khi bằng điểm.

**Người chưa có lịch sử nhận danh sách rỗng từ mô hình này** — cold start là việc của phần hybrid. Trả "khóa phổ biến" từ đây là giấu một mô hình thứ hai bên trong mô hình thứ nhất, và phép blend sau này sẽ cộng độ phổ biến hai lần.

**Khóa nháp và khóa đã gỡ bị loại ngay ở truy vấn** — tương tác với khóa đã gỡ vẫn nói lên sở thích, nhưng giữ nó trong ma trận nghĩa là nó có thể được gợi ý, và lọc lại ở đầu ra là một quy tắc thứ hai mà mọi nơi đọc mô hình phải nhớ.

**Chưa thêm shrinkage cho cặp khóa ít người học chung** — hai khóa chỉ có một người học chung vẫn ra cosine rất cao; đây là điểm yếu đã biết của item-based trên dữ liệu thưa. Không chỉnh bây giờ vì hệ số shrinkage là thứ phải chọn bằng precision@k, mà CSDL dev lúc viết mới có 5 tương tác / 4 user / 1 cặp học chung. Chỉnh trước khi đo là chỉnh mù — cùng lý do để mặc định tham số HNSW.

**Gợi ý tính offline, endpoint chỉ đọc cache** — dựng ma trận tương đồng phải đọc toàn bộ lượt đăng ký của nền tảng; một đêm một lần thì hợp lý, mỗi lần tải trang một lần thì vô lý. Job Celery beat 03:00 ghi top-20 mỗi người vào Redis, endpoint đọc ra.

**Nhưng cache vẫn bị kiểm lại ở đầu ra** — cache cũ tới một ngày, và trong một ngày đó khóa học có thể bị gỡ xuất bản, bị xóa mềm, hoặc — ca hay xảy ra nhất — được chính người đang được gợi ý đăng ký mất rồi. Job không thể biết những chuyện xảy ra sau khi nó chạy, nên ba phép kiểm đó nằm ở tầng đọc. Đây cũng là lý do cache giữ 20 khóa trong khi trang chỉ hiện 8: lọc xong vẫn còn đủ.

**Không có key khác với key chứa danh sách rỗng** — "chưa ai tính cho người này" (`generated_at: null`) và "đã tính, không gợi ý được gì" (`items: []` kèm mốc thời gian) là hai câu trả lời khác nhau. Gộp chúng lại thì phần hybrid sau này không biết lúc nào nên rẽ sang "khóa phổ biến theo danh mục".

**TTL 48 giờ, dài gấp đôi khoảng cách giữa hai lần chạy** — mất một đêm thì gợi ý hôm qua vẫn hơn một trang trống, và `generated_at` đi kèm để trang tự biết dữ liệu cũ bao lâu.

**Job đi vào queue mặc định `celery`, không tạo queue mới** — compose đã để worker `media` nghe cả `media,celery` với comment ghi rõ là để dành cho task thêm về sau. Một job chạy vài giây mỗi đêm không cần container riêng, và tuyệt đối không được nằm trên queue `grading`: những core đó dành cho bài nộp đang có người ngồi chờ.

**Thêm `scripts/rebuild_recommendations.py` thay vì bắt người ta gọi task Celery** — demo không chờ được cron, và số liệu trong báo cáo phải tái tạo được bằng một lệnh chứ không bằng cách để container chạy qua đêm. Script gọi đúng hàm `rebuild` mà task Celery gọi.

**Một beat và chỉ một beat** — hai tiến trình beat sẽ đẩy mỗi job hằng đêm hai lần, mà file lịch nằm trong `/tmp` của từng container nên không bên nào biết bên nào. Đã ghi thành comment ở cả hai file compose.

## Dữ liệu tương tác giả lập (18/09/2026)

**Script sinh cả catalogue lẫn học viên, không chỉ học viên** — kế hoạch chỉ ghi "tạo ~50 user", nhưng CSDL dev khi đó có bốn khóa học. Trên bốn khóa thì "cụm sở thích" gần như không diễn đạt được, và precision@k đo kích thước catalogue chứ không đo mô hình. Nên script thêm 20 khóa chia bốn cụm, mỗi cụm neo vào một khóa seed thật để dữ liệu giả lập chạm được vào catalogue thật.

**Một hạt giống cố định, viết thẳng trong code** — một số đo không tái tạo được là một giai thoại. `DEFAULT_SEED` là mặc định chứ không phải tham số bắt buộc, vì phép đo chỉ tái tạo được khi *mặc định* tái tạo được nó.

**Phần sinh dữ liệu tách hẳn khỏi phần ghi CSDL** — `build_population()` thuần túy: không CSDL, không đồng hồ, không random toàn cục. Nhờ vậy tính chất quan trọng nhất (mô hình gợi ý đúng cụm) kiểm được bằng test chạy trong 2 giây, không cần Postgres.

**Mỗi học viên bỏ trống ít nhất 2 khóa trong cụm của mình** — trần số khóa mỗi người đặt thấp hơn kích thước cụm đúng hai đơn vị. Người đã học hết cụm thì không còn gì đúng để gợi ý, và sẽ kéo precision@k xuống vì lý do nằm ở dữ liệu chứ không ở mô hình.

**Mỗi cụm có 40% học viên học một khóa ngoài cụm** — không nhiễu thì các cụm thành đảo rời nhau và mô hình nào cũng đạt điểm tuyệt đối; nhiều nhiễu quá thì không còn cụm để tìm. Đây cũng là chỗ thang trọng số bị thử: khóa ngoài cụm được chấm 1–3★, đúng nhánh mà `interaction_weight` dùng để hủy tín hiệu "đã hoàn thành".

**Hoàn thành và đánh giá được bốc độc lập, rồi để `interaction_weight` hòa giải** — nếu bốc thẳng ra trọng số thì dữ liệu đang *giả định* hàm đó đúng thay vì *chạy qua* nó.

**Một khóa trong cụm được gán chứ không bốc, xoay vòng theo học viên** — đảm bảo không khóa nào không có người học. Khóa không ai học thì không bao giờ được gợi ý, và mỗi khóa như vậy kéo precision@k xuống vì một lý do không phải lỗi mô hình.

**Có `--purge` ngay từ đầu** — 20 khóa giả lập là thứ làm cho recommender đo được và làm cho catalogue trông độn. Đường gỡ ra phải có sẵn trước khi có người cần nó gấp, và nó hoàn nguyên cả `students_count`/`rating_avg` của bốn khóa thật.

**Test khẳng định trạng thái cuối, không khẳng định số dòng vừa tạo** — bài học trả giá ngay trong phiên: bộ test xanh trên CSDL trắng rồi đỏ ngay sau khi chính script được chạy thật, vì lần hai không tạo dòng nào. Trên máy đã seed một lần thì mọi bộ đếm đều bằng 0.

## Đường ống ingest RAG (18/09/2026)

**Chọn `gemini-embedding-001` chứ không phải `gemini-embedding-2`** — đo được chứ không suy từ số phiên bản: bản 2 trả về **cùng một vector** cho `RETRIEVAL_DOCUMENT` và `RETRIEVAL_QUERY` (cosine = 1,000000), tức `taskType` không có tác dụng; bản 001 cho 0,893094. Bất đối xứng câu hỏi/đoạn văn là thứ RAG cần. Bản 2 nhỉnh hơn ở phép thử truy hồi ba tài liệu (cách biệt 0,1904 so với 0,1758) nhưng chênh lệch đó nằm trong nhiễu nên không lấy làm căn cứ.

**Tự chuẩn hóa vector ngay trong adapter** — ở 768 chiều, model 001 trả về vector chưa chuẩn hóa (norm ≈ 0,57) vì đó là bản cắt Matryoshka từ 3072 gốc. Cosine distance vốn tự chuẩn hóa nên không làm gì vẫn ra đúng thứ hạng — nhưng mọi con số kiểm tay trong tệp bằng chứng sẽ sai, và nếu sau này đổi sang inner product thì sẽ sai âm thầm. Vector norm = 0 bị từ chối thay vì chia cho 0.

**Ước lượng token thay vì gọi `countTokens` cho từng chunk** — một lần gọi mạng cho mỗi chunk còn chậm hơn chính lần gọi embedding mà nó đang lập ngân sách. Hằng số 3,5 ký tự/token đo được từ 4 mẫu thật và cố tình thấp hơn mọi số đo văn xuôi: ước lượng cao số token thì chunk ra nhỏ hơn mục tiêu, thay vì vượt giới hạn model.

**`MAX_CHUNK_TOKENS = 700` dù model nhận tới 2048** — khoảng dư đó để hấp thụ sai số của chính phép ước lượng trên, vì mã nguồn đặc gấp rưỡi văn xuôi (2,32 so với 3,92 ký tự/token).

**Overlap tính theo đơn vị trọn vẹn, và có đường lui xuống mức câu** — cắt overlap giữa câu là tái tạo đúng cái mảnh vụn mà việc chia theo đoạn/câu sinh ra để tránh. Bài học trả giá trong phiên: bản đầu chỉ mang được **nguyên đoạn**, mà một đoạn văn xuôi thường 80–100 token, lớn hơn ngân sách overlap 75 → không mang được gì, và các chunk lát kín bài học **không chồng nhau chút nào**. Test vẫn xanh vì dữ liệu test lặp lại một đoạn duy nhất nên câu nào cũng có mặt ở mọi chunk. Sửa cả hai: khẳng định overlap bằng dấu hiệu vị trí thay vì tìm chuỗi con, và thêm đường lui cắt theo câu.

**Nhúng theo lô** — `batchEmbedContents` nhận cả `taskType` lẫn `outputDimensionality`, nên một bài học 40 chunk tốn 1 lần gọi mạng chứ không phải 40. Thứ tự là thứ duy nhất nối một vector về đúng chunk của nó, nên nó được khẳng định bằng test chứ không giả định.

**Ingest theo từng bài học, commit theo từng bài học** — một khóa học là hàng chục lần gọi API trên một key mà kế hoạch đã ghi là rủi ro quota. Làm cả khóa trong một transaction nghĩa là key chết ở hai phần ba đường sẽ không để lại gì. Commit dần thì lần chạy sau tiếp tục được, và phép so sánh dưới đây làm việc tiếp tục đó gần như miễn phí.

**So sánh trước khi nhúng lại, kèm cả tên model** — publish là cái nút bấm được nhiều lần. Trước khi tốn quota, so từng chunk sẽ sinh ra với dòng đang có: cùng số lượng, cùng nội dung, cùng model → bỏ qua. Đo thật: lần chạy thứ hai trên 24 khóa tốn 0 lần gọi API. Tên model nằm trong phép so sánh vì hai model có thể cùng 768 chiều mà đặt cùng một câu ở hai chỗ khác hẳn nhau.

**Xóa rồi ghi lại, không cập nhật tại chỗ** — chữ mới có thể sinh ra ít chunk hơn chữ cũ, và các dòng ở những chỉ số không còn nữa sẽ nằm lại, vẫn truy hồi được, vẫn trích dẫn một phiên bản bài học mà không ai đọc được nữa. `uq_doc_chunks_lesson_chunk` không bắt được lỗi này vì những chỉ số đó đơn giản là không bao giờ được ghi lại.

**Task ingest không tự retry** — lỗi mong đợi là hết quota, và retry mặc định của Celery sẽ tiêu lần thử tiếp theo vào đúng cái key đang cạn, rồi lại nữa. Vì đã commit theo từng bài, chạy lại sau khi quota hồi là tiếp tục chứ không làm lại. Chạy lại là cái nút trong tay giảng viên (publish) và một lệnh trong tay người vận hành — tốt hơn một cơn bão retry không ai nhìn thấy.

**Thiếu key thì bỏ qua chứ không làm task đỏ** — phần còn lại của nền tảng chạy được mà không cần chatbot. Một task đỏ sau mỗi lần publish sẽ dạy mọi người quen với việc bỏ qua task đỏ.

**Ingest móc vào lúc publish, không móc vào mỗi lần sửa bài học** — chatbot được quyền trích dẫn một khóa học đúng lúc học viên vào học được, không sớm hơn. Job được đẩy **sau** commit, vì worker mở connection riêng và sẽ đọc phải trạng thái cũ nếu đẩy trước.

**Tiêu đề bài học đi kèm chữ của bài học vào từng chunk** — truy hồi so câu hỏi với chính chunk, không so với dòng `lessons` treo phía trên nó, nên một chunk không bao giờ nhắc tên chủ đề của mình chỉ có thể tìm thấy qua những từ tình cờ nằm bên trong.

## Phân loại MLE khi Docker quên cờ OOM (18/09/2026)

Bổ sung sau khi Phase 3 đã đóng — truy gốc và số đo ở `docs/report/assets/phase-3/oom-classification.txt`.

**Exit 137 được đọc thêm theo đồng hồ, không chỉ theo `State.OOMKilled`** — quyết định "container không dùng `--rm`" ở trên coi cờ đó là câu trả lời duy nhất phân biệt giết vì bộ nhớ với giết vì lý do khác. Trên runner CI Docker đôi khi trả cờ false cho một container vừa bị nhân giết vì bộ nhớ, và bài ăn quá bộ nhớ bị chấm TLE. Ràng buộc vật lý của chính sandbox cho câu trả lời thứ hai: ở soft limit kernel kết thúc bằng SIGXCPU (152), SIGKILL của giới hạn CPU chỉ tới ở hard limit, sớm nhất (N+1)/cpus giây thật. Một 137 đến trước đó thì không phải giới hạn CPU. Cờ vẫn được tin khi nó nói true.

**Ngưỡng ở điểm giữa soft và hard limit, không ở soft, không sát hard** — đặt ở soft (N/cpus) thì an toàn quá mức: trên máy dev, giới hạn 1 giây CPU (giảng viên đặt được, không chỉ là giá trị trong test) cứu được 15/20 lần giả lập mất cờ. Đặt sát hard thì cược vào độ chính xác của timestamp và quota CFS. Điểm giữa (N+0,5)/cpus cứu 20/20 lần mà vẫn cách hard limit một giây thật.

**Đọc thời gian sống của container (`StartedAt` → `FinishedAt`), không đọc đồng hồ của worker** — bản sửa đầu dùng đồng hồ worker, và đo mới thấy nó bấm cả `docker start`: ~1 giây trên Docker Desktop, nhiều hơn trên máy chủ đang tải — đủ đẩy một lần giết vì bộ nhớ qua ngưỡng và làm quy tắc âm thầm vô dụng. Hai timestamp nằm trong đúng lời gọi `inspect` vốn đã có. Cả hai đồng hồ đều chỉ có thể đo *dư* thời gian chương trình chạy, nên quy tắc chỉ có thể lùi về gọi TLE thật là TLE, không bao giờ biến TLE thật thành MLE.

## Job chấm bài bị giao lại (18/09/2026)

Bổ sung sau khi Phase 3 đã đóng — dòng 3/8 của mục "Dọn nợ trước khi đi tiếp", `docs/plan/don-no-2026-09-18.md`.

**Bài đã có kết quả thì không chấm lại, kể cả khi hàng đợi giao lại job** — `task_acks_late` + `task_reject_on_worker_lost` (chọn để worker bị OOM killer giết không làm mất job) có một mặt trái: worker chết *sau* khi commit verdict mà *trước* khi ack thì job được giao cho worker khác, cho một bài đã chấm xong. Trước đây `run_grading` không nhìn `status`, đặt lại `running` trên một dòng còn mang verdict — ràng buộc `ck_submissions_verdict_requires_done` chặn ngay ở commit đầu — mọi lần thử đều hỏng, hết retry thì park thành `error` và **xóa verdict học viên đã thấy**. Nay bài ở trạng thái kết thúc (`done`/`error`) được trả lời từ chính dòng DB bằng kiểu riêng `AlreadyFinished`, task Celery không coi đó là lỗi để retry. `running` vẫn được chấm lại: đó là dấu vết của worker chết giữa chừng, và kết quả ghi cùng một commit với verdict nên dòng `running` không có kết quả nào để va chạm.

**Lần giao lại vẫn phát lại event kết thúc** — Redis pub/sub không giữ bản sao; `done` của lần đầu có thể đã tới tay không ai. Trang nào kết nối giữa hai lần giao đang chờ đúng event đó.

**`park_submission` không bao giờ ghi đè một bài đã có kết quả** — park là thao tác duy nhất được phép xóa verdict, nên nó là hàng rào cuối: dù đường nào dẫn tới việc bỏ cuộc cho một bài đã chấm (ví dụ CSDL chập chờn làm các lần giao lại hỏng trước cả khi đọc được `status`), phán quyết đã có vẫn được giữ.

## Storage trên máy dev: MinIO thay R2 (18/09/2026)

Dòng 4/8 của mục "Dọn nợ trước khi đi tiếp". Bằng chứng: `docs/report/assets/phase-4/dev-storage-minio.txt`.

**Server S3 local trong compose dev, không phải bucket R2 thật cho máy dev** — R2 đòi thẻ thanh toán, còn kế hoạch giữ hạ tầng 0đ tới Phase 6. App chỉ nói S3 qua `R2Storage`/boto3, và `R2_ENDPOINT_URL` vốn đã cho ghi đè endpoint, nên thay storage ở máy dev là thay cấu hình, không đụng code. Compose prod không có MinIO: production vẫn là R2.

**Một tên host cho cả hai phía: `minio.localhost`** — URL ký sẵn chỉ hợp lệ cho đúng host đã ký, mà cùng một URL được trình duyệt (PUT, phát video) và worker (tải bản gốc, đẩy HLS) dùng. `localhost:9000` thì container không tới được, `minio:9000` thì trình duyệt không phân giải được. Chrome/Edge tự đưa `*.localhost` về loopback, còn alias mạng compose làm cùng tên đó trỏ vào service. Cái giá: trình phân giải của Windows không biết tên này, nên script đụng storage phải chạy trong container.

**Để trống thì về MinIO, kể cả khi định dùng R2** — ba biến `R2_*` mặc định trỏ vào MinIO để một bản clone mới chạy upload được ngay. Mặt trái: ai điền R2 thật mà quên `R2_ENDPOINT_URL` sẽ âm thầm nói chuyện với MinIO. Đã ghi rõ ở `.env.example`, `infra/README.md` và hướng dẫn R2, thay vì thêm một biến chuyển chế độ riêng.

**Image `bitnamilegacy/minio`, đông cứng** — `minio/minio` và `minio/mc` đã bị gỡ khỏi Docker Hub (API trả 404, trong khi `library/redis` trả 200), `bitnami/minio` không còn tag nào. Bản legacy của Bitnami là bản còn kéo về được, và nó tự tạo bucket kèm policy nên khỏi cần container init. Nó không còn được cập nhật, nên chỉ bind `127.0.0.1` và chỉ dùng ở dev. Điều này cũng loại "MinIO trên VPS" khỏi các lựa chọn production ở Phase 6, trừ khi tự build từ source.

## Chunk của bài học hết chữ (18/09/2026)

Dòng 5/8 của mục "Dọn nợ trước khi đi tiếp". Bằng chứng: `docs/report/assets/phase-4/rag-ingest.txt` mục 5.

**Bài không còn gì để nạp thì cũng không còn gì trong kho** — trước đây bài học hết chữ (xóa nội dung article, đổi sang video chưa có transcript) chỉ được đếm `skipped`, còn chunk của lần trước vẫn nằm trong `doc_chunks` cho chatbot trích dẫn như nguồn. Giờ lần ingest sau xóa chúng theo `lesson_id`, trong cùng vòng lặp từng bài với commit từng bài như phần còn lại. Report có thêm `removed`, chỉ đếm bài thật sự mất dòng, để con số nói kho vừa co lại bao nhiêu chứ không lặp lại số bài video mỗi lần chạy.

**Unpublish không xóa chunk** — publish lại là nút bấm được nhiều lần; xóa khi unpublish nghĩa là trả tiền embedding cho cả khóa ở lần publish sau, trên đúng cái quota mà kế hoạch gọi tên là rủi ro. Giữ chunk của khóa không còn public khỏi câu trả lời thuộc về truy vấn top-k (lọc `courses.status = 'published'` và người hỏi đã ghi danh), đã ghi thành yêu cầu bắt buộc của task Chat API. Chỗ này rẻ hơn và đúng hơn: một bộ lọc ở chỗ đọc bảo vệ được cả những đường đưa chunk vào kho mà chưa ai nghĩ tới.

## Transcript video (19/09/2026)

Task "Pipeline ingest transcript video" của Phase 4. Bằng chứng: `docs/report/assets/phase-4/transcript-ingest.txt`.

**Transcript đi qua API, không qua URL đã ký.** Video và avatar đi thẳng từ trình duyệt lên bucket, vì một bài giảng nặng hàng trăm MB và đẩy qua FastAPI sẽ giữ chặt một tiến trình. Transcript chỉ vài chục KB, nên lý do đó không còn. Đi qua backend thì được một thứ URL đã ký không cho: tệp được đọc trước khi giữ. Tệp lưu bằng Windows-1258 (trình duyệt giải mã UTF-8 ra `U+FFFD`), hay `.srt` không có dòng thời gian, bị từ chối ngay kèm câu hướng dẫn sửa. Nếu đi đường khác, tệp đó sẽ được nạp, rồi vài tuần sau bị chatbot trích lại thành chữ vỡ. Được thêm cái lợi là không có object mồ côi từ những lần upload bỏ dở.

**Lưu tệp gốc, không lưu chữ đã bóc.** Dòng thời gian vô ích với việc tìm kiếm, nhưng cần cho phụ đề trong player (có trong danh sách cắt giảm, mục 2) và cho việc trích nguồn tới từng phút về sau. Chữ đã bóc thì không dựng lại được tệp gốc. Tệp gốc thì một parser tốt hơn luôn đọc lại được.

**Transcript thuộc về video asset, không thuộc về bài học.** Cột `video_assets.transcript_key` có sẵn từ migration mục lục. Thay video là thay asset, và transcript của bản ghi hình cũ đi theo nó, thay vì âm thầm gắn vào một video mới có thể không khớp. Giá phải trả: giảng viên chỉ encode lại cùng một bài giảng cũng phải tải transcript lên lại. Khóa đang xuất bản thì lúc thay video sẽ được nạp lại, để chatbot thôi trích lời của một video không còn ai xem được.

**Đọc lỗi không phải là hết chữ.** Transcript có mà đọc không được (bucket chớp nháy, worker thiếu khóa lưu trữ) thì bài đó được đếm `unreadable`, và chunk cũ được giữ nguyên. Coi là rỗng thì chỉ một lần mạng chập chờn cũng xóa sạch trí nhớ của chatbot về mọi video, và nạp lại tốn quota embedding lần nữa. Quy tắc "hết chữ thì gỡ chunk" (mục trên) chỉ áp dụng khi transcript thật sự bị gỡ.

## Sinh quiz bằng AI (19/09/2026)

Task "Sinh quiz AI" của Phase 4. Bằng chứng: `docs/report/assets/phase-4/quiz-generation.txt`.

**Duyệt từng câu là bắt buộc, không phải tùy chọn.** Câu AI soạn được lưu với `reviewed_at = NULL`, và quiz còn câu như vậy thì không xuất bản được. Lý do là số đo, không phải thận trọng chung chung: với prompt trơn, `flash-lite` đổi `int(12.9)` của bài học thành `int("12.9")` nhưng vẫn giữ đáp án 12, trong khi Python báo lỗi. Còn `flash`, trên 30 câu, sinh một đáp án sai mà lời giải thích lại chép nguyên văn phương án đúng. Đáp án sai sẽ chấm sai học viên, chứ không chấm sai model. Không có nút "duyệt tất cả" vì cùng lý do.

**Chọn model rẻ hơn, và đảo lại lựa chọn ban đầu.** Lần thăm dò đầu chọn `flash` vì `flash-lite` rơi vào bẫy trên. Sau khi thêm quy tắc "chép đúng đoạn mã trong tài liệu" vào prompt và đo lại trên 6 bài: `flash-lite` đúng 30/30 đáp án, mất 3,0 s; `flash` đúng 29/30, mất 11,5 s, và cạn quota free tier trước. Model không phải chỗ duy nhất có thể sửa: prompt tốt hơn làm model rẻ vượt model đắt. Và vì mọi câu đều qua duyệt, sai số còn lại của model rẻ không đi tới học viên.

**Kiểm bằng code thay vì hỏi thêm model.** Câu nháp đi qua đúng `check_question_shape` như câu gõ tay, rồi bị loại nếu lặp câu đã có. Câu có lời giải thích mâu thuẫn với đáp án được gắn cờ bằng phép so từ đơn giản, bắt đúng 1/60 câu sai và không báo nhầm câu nào. Không gọi model lần hai để "tự kiểm": tốn gấp đôi quota, và vẫn là model chấm model.

**Xáo phương án trước khi lưu.** Trước khi xáo, đáp án đúng nằm ở vị trí cuối 3/60 lần, trong khi ngẫu nhiên phải là 15. Một học viên chỉ cần "không bao giờ chọn D" là có lợi.

**Đồng bộ, không qua Celery.** Một lần gọi khoảng 3 giây, và người chờ là giảng viên vừa bấm nút. Hàng đợi chỉ thêm vòng hỏi trạng thái mà không ai được lợi. Khác với ingest RAG, ở đó không ai ngồi chờ và cả khóa là hàng chục lần gọi.

## Đánh giá chatbot (20/09/2026)

Task "Đánh giá chatbot: bộ 20 câu hỏi" của Phase 4. Bằng chứng: `docs/report/assets/phase-4/chatbot-eval.txt` (diễn giải), `chatbot-eval.md` (kết quả cuối, script sinh), `chatbot-eval-truoc-sua.md` (mốc so sánh).

**Làm dày kho ngữ liệu trước khi đo.** Khóa seed tốt nhất chỉ có 4 bài có chữ, và top-6 trả về cả khóa với mọi câu hỏi. Đo trên kho đó là đo model, không đo truy hồi. Vì vậy mười một video được viết lời giảng, tải lên qua đúng `put_transcript` (`scripts/seed_transcripts.py`), nâng kho lên 15/17 bài, 20 chunk. Trên kho mới, bài đúng vẫn đứng hạng 1 ở 126/126 lượt hỏi.

**Chạy mỗi câu ba lần, chấm bằng máy và đọc lại bằng người.** Model không trả lời một câu hai lần giống nhau: q14 lúc có trích nguồn, lúc không. Một lần chạy chỉ là giai thoại. Máy chấm bằng regex dữ kiện (`must_match`) và luật trích nguồn, nên chạy lại được và cãi lại được. Người đọc bắt được chỗ máy sai (q05: máy đòi `None` cho câu hỏi "vì sao"). Thước đo không được sửa sau khi đã thấy kết quả.

**Câu từ chối không được mang số nguồn, và phải chặn bằng code chứ không chỉ bằng prompt.** Prompt đã cấm, nhưng model vẫn gắn `[1][3][4]` khi gợi ý chủ đề khác, ở 4/15 rồi 3/18 câu từ chối. Khi đó trang hiện "Nguồn" ngay dưới câu "không có tài liệu". Quy tắc 3 giờ có câu mở đầu nguyên văn. `chat.is_refusal` đọc câu đầu tiên đó và gỡ mọi `[n]` trước khi lưu. Prompt mới giảm lỗi còn 1/18, code đưa phần học viên thấy về 0/18. Chỉ đọc câu đầu, để câu trả lời có một phần từ chối vẫn giữ trích dẫn thật của phần còn lại.

**Không đặt ngưỡng từ chối trước khi gọi model.** Trên 20 câu và 11 câu thăm dò, câu hợp lệ thấp nhất (hỏi bằng tiếng Anh, 0,633) nằm dưới câu phải từ chối cao nhất ("vòng lặp for trong JavaScript", 0,692). Câu "gần mà ngoài" chỉ model phân biệt được, và nó làm đúng 36/36 lượt. Ngưỡng hữu ích nhỏ nhất chỉ cách một câu hợp lệ 0,033, lại đo trên một khóa, trong khi áp cho mọi khóa. Cái được là bớt một lần gọi rẻ, không đáng rủi ro từ chối nhầm.

**Cho phép ví dụ mã ghép từ tài liệu.** Mọi ví dụ model tự viết mà quan sát được đều lắp từ mảnh có trong bài (`pi = 3.14159`, `int(input(...))`). Cấm chúng làm trợ giảng lập trình kém hữu ích hơn hẳn. Quy tắc 2 cho phép, nhưng bắt câu dẫn ghi nguồn. Script vẫn đếm dòng mã không nguyên văn để lần sau phát hiện ví dụ vượt khỏi tài liệu.

**Giữ `CHARS_PER_TOKEN = 3,5` dù số đo nói nó ước thấp.** `countTokens` trên 43 chunk cho 3,41 ký tự/token. Lý do cũ "thấp hơn mọi số đo nên an toàn" sai với lời giảng lẫn mã. Nhưng chunk lớn nhất chỉ 557/2048 token: lớp an toàn thật là `MAX_CHUNK_TOKENS`. Đổi hằng số sẽ phải nhúng lại toàn bộ kho chỉ để nhích một mục tiêu vốn là "khoảng 500".

## Nửa content-based của recommender (20/09/2026)

Task "Content-based: embedding title+description+category cho mọi course → cosine similarity" của Phase 4 tuần 10. Bằng chứng: `docs/report/assets/phase-4/content-based.txt`.

**Bảng riêng `course_embeddings`, không thêm cột vào `courses`.** Bảng `courses` là bảng nóng nhất của hệ thống, còn vector là thứ chỉ recommender đọc. Bảng riêng cũng là chỗ để cột `source_text` và `embedding_model` — hai cột không nói gì về một khóa học mà nói về **lần nhúng** nó.

**Một vector cho cả khóa, không phải một vector mỗi chunk.** Khác `doc_chunks` ở đơn vị so sánh: RAG cắt bài học thành đoạn vì một câu hỏi được trả lời bởi một đoạn, còn ở đây thứ đem so **là cả khóa học**, mà khóa cắt thành nhiều mảnh thì không còn điểm nào để đo. Chuỗi đủ ngắn để nhúng nguyên, nên nhúng lại một khóa cũng chỉ là một lần gọi.

**`taskType = SEMANTIC_SIMILARITY`, không phải `RETRIEVAL_DOCUMENT`.** Hai vế của phép so ở đây cùng loại (mô tả khóa với mô tả khóa), trong khi embedding truy hồi được huấn luyện cho trường hợp bất đối xứng câu hỏi ngắn với đoạn văn dài. Dùng sai không bị API báo lỗi, chỉ ra thứ hạng tệ hơn — đúng kiểu hỏng mà không ai phát hiện.

**Lưu nguyên văn `source_text`, không lưu băm.** Băm cũng trả lời được "chữ có đổi không", nhưng làm câu "vì sao khóa này bị nhúng lại" thành không trả lời được. Chuỗi nhiều nhất vài trăm ký tự.

**Cắt ở 1000 token dù dữ liệu thật dài nhất 162 token.** Quá trần 2048 token thì Gemini cắt im lặng: một khóa nhúng dở trông y hệt khóa nhúng đủ, không có lỗi nào để bắt. Cắt cũng là quyết định chất lượng — phần đầu mô tả nói khóa học dạy gì, phần cuối là chính sách hoàn tiền và tiểu sử giảng viên, những chữ mà mọi khóa đều có.

**Phụ đề được thêm vào chuỗi dù kế hoạch chỉ ghi "title+description+category".** Trên dữ liệu thật, phụ đề là câu nói rõ khóa dành cho ai — đúng thứ phân biệt hai khóa cùng chủ đề khác trình độ.

**Khóa bị gỡ xuống vẫn giữ vector.** Giống `doc_chunks`: xuất bản lại sẽ phải trả tiền nhúng lần nữa. Việc giữ khóa đã gỡ ra khỏi kết quả là việc của câu truy vấn, không phải của thứ đã đổi trạng thái.

**Endpoint công khai, và hai kiểu rỗng không gộp làm một.** Khóa công chúng không xem được trả 404; khóa xem được nhưng chưa có vector trả `items: []`. Trả `[]` cho trường hợp đầu sẽ thành lời khẳng định "không có khóa nào giống khóa này" — điều hệ thống không biết.

**Thêm một lần chạy beat lúc 02:30 bên cạnh việc nhúng lúc publish.** `PATCH /courses/{id}` đổi tiêu đề và mô tả mà không đụng `status`, nên không có cái nút nào để treo job vào. Không có lần chạy đêm, một khóa sửa lời giới thiệu sẽ giữ mãi vector tả chữ cũ, và không có chỗ nào báo. Đêm bình thường tốn vài truy vấn và 0 lời gọi API.

## Hệ lai: trộn hai nửa và phương án dự phòng (20/09/2026)

Task "Hybrid blend + fallback" của Phase 4 tuần 10. Bằng chứng: `docs/report/assets/phase-4/hybrid-blend.txt`.

**Trộn theo hạng, không theo điểm.** Đo trước khi viết code trộn: điểm collaborative chạy 0,0206–5,7892 (một **tổng**, lớn dần theo lượng lịch sử), cosine content-based chạy 0,7472–0,8923 với độ lệch chuẩn 0,0271. Không cùng thang, và nửa content-based cho **mọi** khóa ít nhất 0,747 trong khi nửa collaborative cho 0 với khóa không ai học cùng — cộng lại thì một khóa chẳng liên quan vượt một khóa có tín hiệu thật. Reciprocal Rank Fusion (Cormack–Clarke–Buettcher 2009, k = 60) chỉ dùng thứ tự, mà thứ tự thì đúng.

**Trọng số hai nửa bằng nhau, và không chỉnh theo chỉ số hiện có.** Trên chỉ số "top-3 đúng cụm" của dữ liệu giả lập, hybrid được 0,8056 — **thấp hơn** collaborative đơn thuần (0,8333). Không tinh chỉnh để kéo lên, vì thước đo ấy thiên vị CF một cách có hệ thống: dữ liệu được *sinh ra* từ cấu trúc cụm, nên "đúng cụm" là "khôi phục được bộ sinh", mà CF đọc thẳng từ ma trận đồng xuất hiện chứa nguyên cấu trúc đó. Chỉnh theo nó là tối ưu cho bộ sinh dữ liệu giả. Việc đó thuộc `eval_recommender.py` với tập held-out.

**Cái giá và thứ mua được, đo bằng số.** Mô phỏng từng khóa một ở trạng thái vừa xuất bản (gỡ mọi tương tác chạm tới nó, khớp lại CF): **0/24** khóa mới lọt được top-10 của bất kỳ ai với CF, **24/24** với hybrid, mỗi khóa tới được 13–35 trong 48 học viên. 0/24 không phải con số tinh chỉnh được — thông tin không có trong ma trận. Mất 2,8 điểm trên một chỉ số giả lập, được toàn bộ khả năng gợi ý khóa mới.

**Dự phòng là hàng lấp chỗ, không phải chế độ riêng.** Một luật phủ cả ba cảnh: người mới batch chưa từng thấy, người mà mô hình không có gì để nói, và người có danh sách bị cắt ngắn bởi vòng kiểm tra lại. Chạy lúc phục vụ chứ không qua cache, vì một tài khoản đăng ký sau batch đêm qua không tồn tại lúc batch chạy.

**Hàng phổ biến không hóa trang thành điểm của mô hình.** `score` = 0, `because` = null, `sources` = `["popular"]`. `generated_at` vẫn chỉ có một nghĩa — lần cuối batch chạy cho người này — nên vẫn null với tài khoản mới, dù khối đã có khóa học trong đó.

**Danh mục đọc từ `enrollments`, không từ cache.** Người vừa ghi danh sáng nay đã có gu mà batch đêm qua chưa thấy.

**`sources` đi tới tận API.** "Cả hai nửa đều gợi ý khóa này" là điều hệ lai tồn tại để nói được; một hệ lai không nói được nửa nào đã lên tiếng thì không ai kiểm được.

## Phase 5 — Commerce, Gamification & Admin

*Bổ sung 05/10/2026 trong lượt rà kho bằng chứng: các quyết định dưới đây đã được ghi khi làm (23/09–30/09), nhưng chỉ trong ghi chú task của [`docs/plan/phase-5-commerce-admin.md`](../../plan/phase-5-commerce-admin.md) và mã nguồn, chưa có trong tệp này. Bằng chứng: `docs/report/assets/phase-5/`.*

### Giỏ hàng, coupon (23/09)

**Giỏ chỉ nhận thứ mua được, wishlist nhận mọi khóa** — giỏ từ chối khóa đã ghi danh (409), khóa mình dạy (409), khóa không trên sàn (404), vì từ giỏ có tiền được trả. Wishlist không dẫn tới thanh toán nên không cần những luật đó.

**`cart_items` không có cột giá** — giỏ luôn hiện giá hiện tại; giá chỉ đóng băng ở `order_items.unit_price` lúc tạo đơn. Khóa rời sàn thì rời giỏ nhờ bộ lọc `published` nằm trong chính câu truy vấn, dòng vẫn còn trong bảng. Cái giá: giỏ không phân trang, nên có trần `MAX_CART_ITEMS = 50`.

**Mọi thao tác giỏ trả về cả cái giỏ** — một cú bấm cập nhật cùng lúc chuông, tổng tiền và nút, không có trạng thái lệch nhau giữa ba chỗ.

**Gõ mã không tiêu lượt; lượt trừ lúc đơn được trả tiền bằng `UPDATE … WHERE used_count < max_uses`** — đọc rồi mới ghi thì hai lần thanh toán cùng đọc được 99 và cùng ghi 100. Điều kiện nằm trong chính câu UPDATE, CHECK `ck_coupons_uses_left` là lớp sàn. Cái giá: chưa biểu diễn được giới hạn theo từng người, vì chưa có bảng redemption.

**Phần trăm được làm tròn tới đồng trên số tiền giảm, không trên tổng** — cổng thanh toán nhận số nguyên, và "tạm tính − giảm giá = tổng" trên màn hình phải cộng khớp.

**Phần giảm được chia cho từng dòng ngay lúc tạo đơn (`order_items.discount`, 24/09)** — coupon giới hạn một khóa không được trừ vào doanh thu của khóa khác trong cùng đơn. Phạm vi coupon sửa được sau khi bán, nên không thể chia lại về sau. Chia theo tỉ lệ giá, làm tròn xuống tới đồng, đồng dư dồn cho dòng có phần dư lớn nhất. Đơn cũ được migration chia lại theo đúng luật ấy; code được chép vào migration chứ không import.

### Thanh toán VNPay (24/09)

**Chỉ IPN được quyền nói là đã trả tiền** — trình duyệt quay về từ ngân hàng mang đúng các tham số ấy, nhưng người dùng sửa được chúng. Trang kết quả chỉ lấy mã đơn rồi hỏi lại API mỗi 3 giây, tối đa 90 giây, vì IPN tới sau cú chuyển trang vài giây.

**Ghi `payment_events` trước khi phán xét, kể cả callback sai chữ ký** — `order_id` nullable để giữ được cả callback không khớp đơn nào. Lúc có tranh chấp, log append-only là thứ duy nhất nói được VNPay đã gửi gì.

**Thứ tự kiểm cố định:** chữ ký → tìm đơn (`01`) → khớp tiền (`04`) → đơn còn `pending` (`02`) → `vnp_ResponseCode` **và** `vnp_TransactionStatus` đều là `00`. Chống trùng bằng `SELECT … FOR UPDATE` cộng partial unique `uq_orders_provider_txn`, vì VNPay gửi lại IPN tới khi nhận được `00`.

**Một transaction cho cả chuỗi:** log → `paid` → ghi danh → trừ lượt coupon → bỏ khóa đã mua khỏi giỏ. Coupon hết lượt giữa chừng thì **vẫn tính đơn**, vì tiền đã chuyển; khi đó `orders.coupon_id` là bản ghi thật về việc mã đã được dùng.

**Chữ ký dựng ở đúng một chỗ (`canonical()`); test ghim chuỗi canonical viết tay từ đặc tả** — test mà dựng chuỗi bằng chính code đang kiểm thì sai cùng với code. Cái giá: đổi đặc tả là phải viết tay lại chuỗi mẫu.

**MoMo bị cắt (01/10)** — đây là mục cắt giảm số 1. MoMo vướng cùng loại chặn từ bên ngoài như VNPay (merchant cộng IPN công khai), mà một cổng đã đủ cho gate.

### Dashboard giảng viên (24/09)

**Không bảng mới, không cache — mọi số là một phép gộp lúc đọc** — ở quy mô này một phép gộp trên `orders`/`enrollments` đủ nhanh, và không có bảng thống kê nào để lệch khỏi dữ liệu gốc. Cái giá: nếu sàn lớn lên thì truy vấn chậm dần theo số đơn. Doanh thu = `unit_price − discount` của đơn `paid`, theo `paid_at`, chưa trừ phí sàn.

**Gom ngày bằng tên vùng `Asia/Ho_Chi_Minh`, không bằng `'+07:00'`** — `AT TIME ZONE '+07:00'` được Postgres đọc theo quy ước POSIX thành UTC−7. Test bắt được cả hai cách sai.

**Biểu đồ cột HTML tự dựng, không thêm thư viện chart** — chỉ cần hai biểu đồ cột. Tự dựng thì có tooltip, điều hướng bằng phím mũi tên và nút "Xem dạng bảng" cho trình đọc màn hình, mà không thêm dependency nào.

### XP, chuỗi ngày học, bảng xếp hạng (28/09)

**`xp_events` là sổ cái append-only và là nguồn chân lý của XP** — "lần đầu" được bảo đảm bằng unique `uq_xp_events_ref` + `ON CONFLICT DO NOTHING`, ghi trong **cùng transaction** với lúc hoàn thành bài/verdict. Làm lại không được cộng hai lần, và rollback thì không còn XP mồ côi. Chỉ người có ghi danh mới được XP, nên giảng viên làm thử khóa mình vẫn được chấm nhưng không có XP.

**Ngày vào chuỗi là ngày Việt Nam có *nộp* một thứ; chuỗi bị cắt lúc đọc, không có job nửa đêm** — xem video không tính, nộp quiz trượt thì có tính. Ngày được cập nhật bằng một câu upsert có `WHERE last_active_date < ngày`. Không có job nửa đêm nên không có gì quên chạy.

**Bảng xếp hạng là *view* của `xp_events` trên Redis sorted set, và tự lành** — điểm chỉ được đẩy sau commit: ghi tạm vào `session.info`, rollback thì bỏ. Bảng được dựng lại khi thiếu marker, mỗi đêm 03:30 và bằng script; dựng vào key tạm rồi `RENAME`. Redis lỗi thì chỉ ghi log, vì XP vẫn nằm đủ trong Postgres.

**Client Redis đồng bộ, gọi qua `asyncio.to_thread`** — API và worker Celery (mỗi job một event loop) dùng chung được một client. Đồng hạng theo kiểu thi đấu (1, 2, 2, 4), tính bằng `ZCOUNT` các điểm lớn hơn hẳn.

### Chứng chỉ PDF (29/09)

**Cấp chứng chỉ trong cùng transaction với lúc khóa học chuyển sang hoàn thành, còn PDF thì vẽ sau commit bằng Celery** — chứng chỉ không thể tồn tại mà khóa học chưa hoàn thành, còn việc vẽ PDF (WeasyPrint, mất vài giây) không giữ transaction. Chưa có PDF thì endpoint tải trả 409 và đẩy lại job. Bỏ tick bài học không thu hồi chứng chỉ.

**Đóng băng tên người học, tựa khóa và tên giảng viên lúc cấp** (thêm 3 cột so với đặc tả) — chứng chỉ là lời xác nhận tại một thời điểm, không được đổi theo khi người học đổi tên hay khóa học bị đổi tựa.

**Mã 16 ký tự từ bảng 32 ký tự không gây nhầm (80 bit), có CHECK định dạng** — mã được gõ lại từ bản in (hiển thị thành 4 nhóm, nhận cả chữ thường và gạch ngang), nên bảng chữ bỏ `I`, `O`, `0`, `1`.

### Hỏi đáp và thông báo (29/09)

**Chỉ upvote: `qa_votes` bỏ cột `value` của đặc tả** — một dòng là một phiếu (unique mỗi người), người hỏi không tự vote. Số phiếu, số trả lời và "có giảng viên trả lời" đều tính lúc đọc bằng subquery, không có cột đếm nào để lệch.

**Huy hiệu "giảng viên trả lời" được quyết lúc viết** (`is_instructor_reply` = người viết là giảng viên của khóa) — admin không mang huy hiệu. Giảng viên không ghi danh được khóa của mình nên trả lời ở hộp thư `/giang-day/hoi-dap`, không ở trang học.

**Thông báo ghi cùng transaction với sự kiện; payload là ảnh chụp** (id + tiêu đề + tên người) — câu chữ và link do frontend dựng từ `type` + `payload`. Thêm một loại thông báo là ba chỗ (danh sách type, migration đổi CHECK, một nhánh `describe()`), còn backend không phải dịch gì.

**Chuông không dùng WebSocket** — hỏi số chưa đọc mỗi 60 giây và khi cửa sổ được focus lại; dropdown chỉ tải danh sách khi mở. Một kênh realtime thứ hai không đáng với một con số thay đổi vài lần mỗi ngày.

### Quản trị (30/09)

**Bỏ hẳn cờ `AUTO_APPROVE_COURSES`; chỉ lúc duyệt mới xếp ingest RAG + nhúng khóa học, sau commit** — kho chatbot và recommender chỉ được chứa khóa đã công khai. Gate xác nhận 14 bề mặt công khai đều 404 hoặc không liệt kê khóa đang chờ duyệt.

**Quyết định của admin đóng mọi báo cáo đang chờ trên cùng nội dung; "gỡ nội dung" chạy cùng transaction** — khóa học bị đưa về `draft` chứ không xóa mềm, nên giảng viên sửa rồi gửi duyệt lại được. Đánh giá bị gỡ thì rating được tính lại.

**Khóa tài khoản = `locked_at` + thu hồi mọi refresh token ngay lúc khóa** — kiểm access token vốn đã đọc `locked_at` (từ Phase 2), nên khóa có hiệu lực ngay ở request kế tiếp chứ không đợi token hết hạn. Khóa người dùng không gỡ nội dung của họ, và admin không khóa được admin.

**DAU suy từ dấu vết ở các bảng vốn đã ghi, không thêm bảng hay ghi gì mỗi request** — gồm `refresh_tokens` (đăng nhập và mỗi lần mở lại phiên), tiến độ, XP, quiz, nộp code, chat, Q&A, ghi chú, đơn hàng, ghi danh. Cái giá: người chỉ đọc mà không mở phiên mới trong ngày thì không được tính.

**Mã giảm giá toàn sàn bất biến ở phần mã; kết thúc sớm = `valid_to = now`; mã đã dùng không xóa được** — đơn cũ phải giữ được bản ghi của mã đã áp vào nó.

## Rà soát bảo mật (01/10/2026)

Task 1 của Phase 6. Bằng chứng: `docs/report/assets/phase-6/security-review.txt`.

**Phân quyền kiểm bằng một bảng phủ mọi route, không bằng đọc code** — 159 route, mỗi route một luật (công khai / admin / thuộc về ai / chỉ về người gọi / mở cho mọi người đã đăng nhập), test đọc danh sách route từ chính app nên route mới chưa có luật là đỏ. Người ngoài là ca khó (bạn cùng lớp đã ghi danh, giảng viên khác) và chủ thật phải qua được, để một id gõ sai không làm cả bảng xanh suông. Trả giá: bảng phải sửa mỗi lần thêm route — chính là điều muốn có.

**Giới hạn đăng nhập đếm mọi lần thử, theo cả email lẫn IP** — đếm riêng lần sai cần thêm một vòng Redis sau bcrypt; 10 lần/15 phút/email không chạm người thật. Theo IP để chặn rải một mật khẩu lên nhiều tài khoản, ngưỡng 100 để một phòng máy sau NAT không tự khóa mình. Trả giá: người lạ giữ được cửa đăng nhập bằng mật khẩu của một địa chỉ trong 15 phút.

**nginx ghi đè X-Forwarded-For thay vì nối thêm** — uvicorn tin mọi proxy (`*`) và lấy phần tử đầu danh sách; nối thêm thì phần tử đầu là thứ client tự viết. Đúng chừng nào nginx còn là bước đầu tiên; đặt CDN phía trước thì phải đổi.

**CSP đầy đủ ở chế độ Report-Only** — chỉ bản build production trên trình duyệt thật mới cho biết chính sách có làm gãy trang không; bật enforce sau khi luồng vàng chạy trên tên miền thật với console sạch. `frame-ancestors 'none'` thì enforce từ trước.

## Xử lý kết quả /security-review (01/10/2026)

Task 2 của Phase 6. Bằng chứng: `docs/report/assets/phase-6/security-review-codebase.txt`.

**Google chứng minh email thì mật khẩu chưa ai chứng minh bị xóa** — đăng ký không gửi thư xác nhận, nên mật khẩu trên một tài khoản có thể do người khác đặt trước (pre-account takeover). Chọn xóa mật khẩu + thu hồi phiên khi liên kết thay vì từ chối liên kết: từ chối thì chủ thật của email bị khóa ngoài vĩnh viễn (không có luồng quên mật khẩu). Trả giá: người tự đăng ký bằng mật khẩu rồi dùng Google sẽ mất đăng nhập bằng mật khẩu, chỉ còn Google.

**Đơn có hạn thanh toán 30 phút, nhưng không bao giờ bị hủy** — hạn chặn việc *bắt đầu* thanh toán mới (không ký URL mới, URL nào cũng hết hạn trước hạn đơn), còn IPN tới sau hạn cho một lần trả tiền bắt đầu trong hạn vẫn được ghi nhận. Hủy đơn lúc quá hạn thì một IPN đến trễ sẽ gặp đơn đã hủy: tiền đã chuyển mà không được ghi danh.

**Kiểm `?next=` bằng chính bộ phân tích URL thay vì so tiền tố** — trình duyệt đọc `/\evil` và `/<tab>/evil` thành `//evil`; danh sách ký tự cấm luôn thiếu một ký tự. Phân giải như router, giữ khi origin không đổi, trả về đường dẫn đã phân giải.

**Test đơn vị frontend bằng `node --test`, không cài Vitest** — Node chạy TypeScript bằng cách bỏ kiểu; một hàm thuần không cần cả framework. Tệp `*.test.ts` nằm ngoài tsconfig vì Node cần import có đuôi `.ts` còn cấu hình bundler của Next từ chối.

## E2E luồng vàng (02/10/2026)

Task 3 của Phase 6. Bằng chứng: `docs/report/assets/phase-6/e2e-golden-flow.txt`.

**E2E chạy vào stack compose có sẵn, Playwright không tự dựng** — luồng vàng cần cùng lúc API, Postgres, Redis, bucket, worker chấm bài trong sandbox Docker và worker vẽ chứng chỉ; không có stack nhỏ hơn mà vẫn nói thật về luồng này. CI dựng chính stack dev từ số không trong một job riêng. Trả giá: job chậm (build 3 image) và phụ thuộc Docker của runner.

**Mọi bước của học viên đi qua UI; phần của người khác đi qua API** — giảng viên soạn khóa và admin duyệt là câu chuyện khác, đã có test riêng; làm qua API mất vài giây thay vì một trình duyệt thứ hai. IPN của VNPay không có trình duyệt nào đi được: ký bằng script của backend chạy trong container, nên secret không ra khỏi container mà request vẫn qua bước kiểm chữ ký thật.

**Chờ verdict tổng, không chờ nhãn đầu tiên** — "Đúng" hiện trên test 1 khi test 2 còn đang chấm; test đầu tiên viết theo nhãn ấy đã xanh quá sớm. Bài học chung cho E2E giao diện realtime: assertion phải gắn vào trạng thái cuối, không vào chữ.

**Suite tự dọn dữ liệu của mình** — mỗi lượt ghi dữ liệu thật vào CSDL nó chạy; nhận diện bằng một tên miền email riêng (`@e2e.devpath.example`) thay vì đánh dấu từng bảng, rồi xóa theo thứ tự 5 khóa ngoại RESTRICT.

## Load test nhẹ (02/10/2026)

Task 4 của Phase 6. Bằng chứng: `docs/report/assets/phase-6/load-test.md`.

**k6 thay vì locust** — một binary trong image Docker chính thức, không thêm gói Python nào vào `pyproject.toml`/lock; có sẵn WebSocket với subprotocol (cách trang nộp bài xác thực) và executor `per-vu-iterations` bắn cả lớp cùng một khoảnh khắc. Chạy trong container trên mạng compose, nên trên VPS chạy y nguyên mà không cài gì.

**Đo stack production dựng trên máy dev, không đo stack dev** — stack dev là uvicorn `--reload` một tiến trình, log SQL, `next dev`: đo nó là đo công cụ phát triển. Trả giá: dựng thêm một stack (project riêng, volume riêng) và tạm dừng stack dev trong lúc đo.

**Lớp học dựng bằng script ghi thẳng bảng và mint token** — 21 lần đăng ký từ một địa chỉ vượt giới hạn 50/giờ/IP từ lượt thứ ba, và đăng nhập không phải thứ đang đo. Token ký bằng chính khóa của API nên mọi request vẫn đi qua xác thực thật.

**Thư mục workspace chấm bài được chown bởi một service compose chạy một lần, không phải một bước trong runbook** — lỗi chỉ lộ trên máy trắng, nên bước tay là bước sẽ bị quên đúng lần nó quan trọng. Một container root chạy `chown` rồi thoát, chỉ mount đúng thư mục đó; worker vẫn uid 10001.

**Mỗi lượt đo kèm một mốc hiệu chuẩn trước và sau** — lượt đầu chậm gấp năm vì Docker Desktop đang bận (sau build, và vì chính vòng `docker stats` đang ghi CPU); không có mốc thì đã kết luận sai rằng frontend bão hòa ở 25 người. Thay vòng `docker stats` liên tục bằng một ảnh giữa mỗi mức.

## Sửa bug UX tồn đọng (02/10/2026)

Task 5 của Phase 6. Bằng chứng: `docs/report/assets/phase-6/ux-polish.txt` + `ux/`. *(Mục này và bốn mục 02/10 kế tiếp được bổ sung 05/10, trong lượt rà kho bằng chứng.)*

**Đo tràn ngang thay vì nhìn ước** — một script Playwright mở 47 trang × 2 bề rộng dưới 5 vai và so `scrollWidth` với `clientWidth`: trước sửa 14/94 lượt xem bị tràn, sau sửa 0/94. Header được đo từng phần tới khi vừa máy 360 px; lần sửa đầu chỉ ước lượng nên vẫn rộng 379 px.

**Trang chi tiết khóa học là lưới 3 phần tử (đầu trang | thẻ giá | phần còn lại)** — trên điện thoại thẻ giá lên ngay dưới tên giảng viên (trước đó ở y ≈ 1.700 px), trên màn rộng vẫn là cột phải dính. Một component ở một chỗ trong DOM, không phải hai bản ẩn/hiện theo bề rộng.

**Ảnh bìa dự phòng là gradient nhạt, mỗi khóa một màu cố định (băm id)** — trình soạn chưa có chỗ tải ảnh bìa, mà thêm chỗ tải là tính năng mới, trái với đóng băng. Tô theo danh mục thì 9 khóa cùng danh mục thành một hàng y hệt nhau, nên đổi sang tô theo khóa.

## Proxy cho Docker socket (02/10/2026)

Task nợ sandbox của Phase 6. Bằng chứng: `docs/report/assets/phase-6/docker-socket-proxy.txt`.

**Tự viết proxy đọc body, không dùng proxy có sẵn** — các proxy có sẵn lọc theo endpoint. Runner cần `POST /containers/create`, mà mở endpoint đó là mở luôn create có `Privileged` + bind `/`. Nguy hiểm nằm trong body nên phải đọc body: Python thư viện chuẩn, ~600 dòng, đủ nhỏ để đọc hết.

**Danh sách cho phép chép từ lưu lượng thật của CLI; mọi trường khác phải ở giá trị zero** — trường Docker thêm về sau bị chặn tới khi có người quyết nó vô hại. Cái giá: đổi một cờ trong `runner/sandbox.py` mà quên `proxy/policy.py` thì mọi bài nộp thành SE. Điều này đã ghi vào skill `sandbox-grading`.

**Quyền sở hữu container xét bằng nhãn do daemon xác nhận, không bằng tên** — sau khi inspect, CLI đổi sang ID 64 hex nên tên không đủ. Proxy tự inspect trước mỗi thao tác, và đó là phần lớn chi phí đo được (~4 %/lượt chấm).

**Proxy là container duy nhất cầm socket, trên mạng internal chỉ chung với worker** — CI đỏ nếu service khác mount socket. Worker bị chiếm giờ chỉ tạo được đúng loại sandbox mà học viên nào cũng tạo được bằng cách nộp bài.

## Backup CSDL tự động (02/10/2026)

Task vận hành của Phase 6. Bằng chứng: `docs/report/assets/phase-6/db-backup-restore.txt`.

**Service compose, không crontab trên host** — nằm trong repo, `up` là có, VPS reboot là tự lên; không có bước tay nào trên máy chủ để quên.

**Image dựng từ chính image của Postgres** — `pg_dump` luôn cùng major version với server. Lệch version là loại lỗi chỉ lộ vào đúng đêm cần khôi phục; Debian bookworm/trixie chỉ có client 15/17.

**Bucket riêng, private; service từ chối nếu trùng bucket media** — bucket media cho đọc ẩn danh, còn bản dump chứa email và hash mật khẩu của mọi người dùng.

**Giữ 14 bản theo số, không theo tuổi** — đồng hồ sai hay một tháng không chạy cũng không làm nó xóa bản cuối cùng.

**Khôi phục vào CSDL phụ rồi đổi tên, không ghi đè CSDL đang chạy** — site vẫn chạy trong lúc khôi phục; app chỉ dừng ~20 giây lúc đổi tên, và bản cũ được cất lại để quay lui.

**Production không có nơi lưu thì service unhealthy và `deploy.sh` dừng** — muốn chạy không backup phải ghi rõ `BACKUP_ENABLED=false`. Im lặng không backup là lỗi không ai thấy cho tới lúc cần.

## Giám sát tối thiểu (02/10/2026)

Task vận hành của Phase 6. Bằng chứng: `docs/report/assets/phase-6/monitoring.txt`.

**Log là json-file xoay vòng (5 × 10 MB, nén) cho mọi service; không dựng Loki/ELK** — mặc định của Docker là giữ log không giới hạn, mà với một VPS thì `docker compose logs` là đủ. CI đỏ nếu service mới quên gắn anchor. Cái giá: container bị thay khi deploy mang log theo, nên phải đọc log trước khi deploy lại.

**Monitor chạy trên host bằng systemd timer, không trong container** — đọc health của container là nói chuyện với Docker daemon, mà compose giữ cam kết chỉ một container cầm socket.

**Kiểm cả danh mục khóa học qua nginx, không chỉ `/health`** — `/health` cố ý không chạm CSDL, nên tắt Postgres mà trang chủ và `/health` vẫn 200 (đã diễn tập). Hỏi qua `127.0.0.1:443` với SNI thật để TLS và định tuyến nằm trong đường đi.

**Báo qua ntfy, sau 2 lượt liên tiếp, có tin "đã ổn lại", nhắc mỗi 6 giờ** — không cần tài khoản. Container bị thay lúc deploy không phải là sự cố. Uptime nhìn từ bên ngoài (cả máy chết) là UptimeRobot, không phải cron của GitHub Actions: 5 phút một lần tốn gấp ~3 lần hạn mức phút của gói Pro.

**nginx tự reload mỗi 6 giờ** — certbot gia hạn tệp chứng chỉ, nhưng không có gì bảo nginx đọc lại. Không deploy trong 90 ngày thì site sẽ phục vụ chứng chỉ hết hạn. Lỗi tìm ra lúc thiết kế monitor.

## Chạy trên máy trắng (02/10/2026)

Task vận hành của Phase 6. Bằng chứng: `docs/report/assets/phase-6/fresh-machine.txt`.

**README chỉ đòi Git + Docker; mọi lệnh migrate/seed chạy trong container** — README cũ hỏng ở bước thứ ba trên máy trắng (không có `.venv`, thiếu bước migrate).

**Đối chiếu biến môi trường bằng script trong CI, không bằng đọc** — `check_env_examples.py` so ba tệp compose/example/`Settings` và bắt được một lỗi production thật: compose prod không truyền `VNPAY_*`, nên thanh toán trên VPS sẽ luôn 503.

**Gỡ dữ liệu demo sai thứ tự thì dừng kèm hướng dẫn, không xóa gì** — đơn hàng không bao giờ bị script xóa, nên `seed_interactions --purge` khi còn đơn của `seed_sales` sẽ từ chối và in thứ tự đúng.

## Tiến độ chấm khi không có WebSocket (04/10/2026)

Task nợ sandbox của Phase 6. Bằng chứng: `docs/report/assets/phase-6/polling-progress-decision.txt`.

**Kết quả từng test case vẫn ghi trong một commit lúc chấm xong** — nhánh polling dự phòng vì thế không nhích từng case. Phase 3 hoãn với lý do "8 lần commit"; đo lại chỉ thêm ~1,2 ms/case, nên lý do thật là khác: runner chạy tiếp sau một case SE, commit từng case sẽ để học viên đọc được dòng SE của một lượt sắp chấm lại, và retry/dead letter phải dọn dòng dở. Điều kiện để xem lại (proxy chặn WebSocket) chưa từng xảy ra.

**Biến điều kiện xem lại thành test** — E2E luồng vàng đòi tiến độ từng case và verdict phải tới qua WebSocket; trước đó polling che mất một proxy chặn WebSocket. Gate "luồng vàng trên tên miền thật" vì thế kiểm luôn WebSocket qua nginx của VPS.

## Bộ nhớ đỉnh của bài nộp (04/10/2026)

Task nợ sandbox của Phase 6. Bằng chứng: `docs/report/assets/phase-6/peak-memory-decision.txt`.

**Bỏ cột `submissions.peak_memory_mb` thay vì đo** — cột luôn NULL từ Phase 3. Trên cgroup v2, API `stats` của Docker không có mức đỉnh khi container chạy và trả rỗng sau khi thoát; con số chỉ có bên trong sandbox (`memory.peak`). Đo được bằng một `sh` đứng trước bài nộp (đã đo: chỉ thêm ~0,2 MiB), nhưng nó báo qua stderr mà bài nộp giả được và chen vào mã thoát mà verdict TLE/MLE dựa vào — đổi sandbox ngay trước khi đóng băng tính năng cho một con số không trang nào hiển thị. Công thức để làm sau ghi trong tệp bằng chứng.

## Endpoint readiness (04/10/2026)

Task vận hành của Phase 6. Bằng chứng: `docs/report/assets/phase-6/readiness-endpoint.txt`.

**Hai endpoint, không gộp** — `/health` (liveness) vẫn không chạm gì vì healthcheck container đọc nó: Postgres khởi động lại không được làm một tiến trình đang ổn thành unhealthy. `/health/ready` hỏi CSDL + Redis, dành cho `deploy.sh` và uptime check bên ngoài. Monitor trên host không dùng nó: đã có liveness + danh mục để tách "API chết" khỏi "CSDL chết", thêm readiness chỉ làm một sự cố báo hai tin.

**Mỗi phụ thuộc tối đa 2 giây, chạy song song, kết nối riêng** — probe treo theo một CSDL bị pause thì người gọi hết giờ chờ và đọc thành "cả site chết". CSDL hỏi qua engine `NullPool` riêng thay vì pool của request; trả giá: readiness không thấy pool cạn kết nối.

**503 vẫn đi trong envelope lỗi chung, nói phụ thuộc nào chứ không nói vì sao** — `DomainError` có thêm `extra` để mang `checks`; lỗi gốc (host, cổng, user) chỉ vào log vì endpoint công khai.

## Dọn object mồ côi (04/10/2026)

Task vận hành của Phase 6. Bằng chứng: `docs/report/assets/phase-6/orphan-sweep.txt`.

**Đánh dấu trước, xóa sau 14 ngày, thay vì xóa ngay khi thấy** — bucket không bật versioning và backup đêm chỉ có CSDL, nên tệp xóa nhầm là mất hẳn. 14 ngày bằng số bản backup được giữ: khôi phục bản nào cũng còn đủ tệp nó nhắc tới. Trả giá một bảng (`orphan_objects`) và tệp rác sống thêm hai tuần — vài xu lưu trữ.

**Van an toàn theo từng prefix** — một đêm mà quá nửa một prefix sắp bị đánh dấu thì dừng, không ghi gì. Xét từng prefix vì phép tra avatar hỏng sẽ bị hàng trăm video còn ổn che mất nếu chỉ nhìn tổng.

**Nhận tệp theo đường dẫn trong URL, không theo base URL hiện tại** — hàng lưu URL tuyệt đối; đổi tên miền bucket không được biến ảnh cũ thành rác. Khớp thừa chỉ giữ lại tệp, không xóa nhầm.

**Không đổi các lần xóa ngay khi thay video/avatar/banner** — đó là thao tác chủ ý của người dùng; đưa chúng qua cách ly là đổi bốn service ngay trước khi đóng băng tính năng.

## SSE của trợ giảng qua nginx (04/10/2026)

Task nợ của Phase 6. Bằng chứng: `docs/report/assets/phase-6/sse-through-nginx.txt`.

**Đo ở phía client, kèm đối chứng âm, thay vì đọc cấu hình** — "nginx có buffer không" là câu hỏi về hành vi, nên đo thời điểm từng sự kiện được đọc khỏi socket (HTTP/1.1 và Chrome thật qua HTTP/2), rồi tạm ép nginx buffer để chứng minh phép đo thấy được kiểu hỏng cần loại trừ.

**Chỉ chặn trong CI thứ đã đo là hỏng** — bỏ qua `X-Accel-Buffering` thì dồn cục (đã đo), nên CI đỏ nếu config có nó. Gzip trên event-stream thì đo ra vô hại, nên không cấm, dù nhiều hướng dẫn khuyên tắt.

## Địa chỉ gốc của site trong image frontend (05/10/2026)

Task nợ của Phase 6. Bằng chứng: `docs/report/assets/phase-6/site-url.txt`.

**Nướng `https://${DOMAIN}` vào lúc build, không đọc lúc chạy** — `metadataBase` cần URL tuyệt đối, và trang được prerender lúc build sẽ chốt giá trị của lúc build; một biến server-only đọc lúc chạy chỉ đúng với trang render động, sai im lặng với trang tĩnh nào sau này thêm URL tương đối. Cái giá là image mang tên miền ở phía server (bundle trình duyệt vẫn không — nguyên tắc Phase 2 giữ nguyên), nhưng `deploy.sh` vốn build lại mỗi lần chạy nên đổi tên miền chỉ là "sửa `.env.prod`, deploy".

**Build thiếu biến thì hỏng, không rơi về localhost** — lỗi này không làm trang nào hỏng, chỉ crawler và ứng dụng chat thấy, nên mặc định im lặng chính là thứ đã giấu nó từ Phase 2. Kiểm đặt trước `next build` để hỏng sau 0,2 s. CI build image frontend qua chính compose prod thay vì `docker build` trần — bước cũ vốn build một image khác image chạy thật.

## Khoảng ân hạn cho refresh token (05/10/2026)

Task nợ của Phase 6. Bằng chứng: `docs/report/assets/phase-6/refresh-leeway.txt`.

**Cấp cho tab đến muộn một phiên riêng, không trả lại token kế nhiệm** — DB chỉ giữ hash nên không có gì để trả lại, và không được thu hồi token kế nhiệm vì trình duyệt giữ câu trả lời nào tới sau cùng làm cookie, mà thứ tự đó không ai quyết định được: cả hai token phải tiếp tục chạy. Một phương án khác là trả "đã bị thay, thử lại" để frontend gửi lại bằng cookie mới. Cách đó an toàn hơn một chút (bản sao dùng trong lúc ân hạn không lấy được gì), nhưng không cứu được trường hợp mất câu trả lời: cookie vẫn còn T0, lần thử lại vẫn mang T0, và khi khoảng ân hạn hết thì người dùng bị đăng xuất.

**Chỉ token bị *xoay* mới được ân hạn, và chỉ khi token kế nhiệm còn sống** — vì thế cần cột `replaced_by_id`, chứ một mình `revoked_at` không phân biệt được "bị xoay" với "đã đăng xuất" hay "bị thu hồi cùng mọi phiên khác". Nếu không có điều kiện token kế nhiệm còn sống, trong 30 giây sau khi đổi mật khẩu thì token cũ lại mở được phiên.

**Khóa dòng khi xoay** — trước khi sửa, hai request đồng thời cùng xoay một token (đo được 10/10 lần). Hậu quả chưa lớn, nhưng ghi chép bị lệch: `revoked_at` là lần xoay sau, và `replaced_by_id` trỏ tới bên nào ghi sau cùng. Test với hai kết nối thật đỏ 5/5 lần khi bỏ khóa.

**30 giây, chỉnh được qua biến môi trường** — đủ cho độ lệch giữa hai tab và cho một lần retry, và là mặc định của Okta cho cùng loại khoảng ân hạn này.

## Storage cho production (05/10/2026)

Task nợ của Phase 6. Bằng chứng: `docs/report/assets/phase-6/storage-decision.txt`.

**Tự host media, backup ra ngoài máy** — R2 đòi thẻ, mà kế hoạch giữ hạ tầng 0đ. Hai thứ có yêu cầu ngược nhau. Media cần phát video với egress không giới hạn chặt: VPS đáp ứng được (Azure miễn phí 100 GB/tháng, Oracle 10 TB), còn B2 chỉ miễn phí egress tới 3 lần dung lượng lưu. Backup thì phải nằm *ngoài* máy chủ: B2 đủ (10 GB không cần thẻ, chỉ cần chứa vài MB × 14 bản).

**Chọn server bằng code của chính app** — 20 kiểm chạy bằng `R2Storage` + boto3 đúng bản đã khóa, qua nginx có TLS. boto3 ≥ 1.36 từng làm hỏng nhiều server S3 tương thích ở phần checksum, và thứ đó không đọc ra được từ tài liệu. RustFS và SeaweedFS đều 20/20. Chọn RustFS vì nó cấu hình bằng biến môi trường + bucket policy, đúng mô hình MinIO mà stack dev đang dùng, và nhanh hơn 6 lần khi tải video. SeaweedFS giữ làm dự phòng đã chứng minh.

**Cùng origin thay vì subdomain** — trình duyệt PUT cùng origin nên không có preflight CORS, không cần thêm DNS hay chứng chỉ, và server S3 không mở cổng nào ra ngoài. Đổi lại, nginx phải chuyển nguyên `Host`: đối chứng cho thấy thiếu dòng đó thì mọi URL ký sẵn bị 403.

## RustFS vào compose (05/10/2026)

Thực hiện quyết định storage cùng ngày. Bằng chứng: `docs/report/assets/phase-6/rustfs-compose.txt`.

**API và worker gọi bucket qua chính URL công khai, nhờ alias `${DOMAIN}` của nginx trong mạng compose** — URL ký sẵn chỉ hợp lệ cho đúng host đã ký, nên phía app phải ký cho `https://<DOMAIN>`. Gọi thẳng `storage:9000` thì phải tách hai endpoint trong code, còn đi qua IP công khai thì tùy vào NAT của nhà cung cấp. Alias không cần sửa code, và là cùng mẹo `minio.localhost` mà stack dev dùng từ 18/09. Cái giá: diễn tập không được dùng `DOMAIN=localhost`.

**`sandbox` + `nosniff` trên mọi phản hồi media** — bucket công khai giờ nằm cùng origin với app, nên một tệp bị mở như một trang sẽ chạy với tư cách của site. Loại tệp đã bị giới hạn khi ký, nhưng hai header này không tốn gì và không ảnh hưởng `<img>`/`<video>`/hls.js.

**Một service init thay vì để app tự tạo bucket** — cấu hình bucket là việc của hạ tầng, chạy ở mỗi lần `up`, gọi thẳng server trong mạng compose, nên không phụ thuộc chứng chỉ hay nginx. App vẫn chỉ biết giao thức S3, và đổi sang R2 vẫn chỉ là đổi biến môi trường.

**Dev giữ tên `minio.localhost`** — URL công khai đã nằm trong `users.avatar_url`; đổi tên host thì phải viết migration dữ liệu, mà không được gì.


## Bộ ảnh giao diện cho chương 4 (05/10/2026)

Task thêm từ lượt rà kho bằng chứng. Bằng chứng: `docs/report/assets/phase-6/ui-screenshots.txt`.

**Một script chụp lưu trong repo, không chụp tay.** Gate cuối phase còn đòi chụp lại trên tên miền thật, nên lần chụp thứ hai phải là một lệnh chứ không phải một buổi chiều. Mỗi vai đăng nhập một lần bằng form thật, rồi thu hồi phiên. Cái giá: phải chờ trang dev hydrate xong và chịu cooldown nộp bài, nên script có vài bước chờ.

**Dữ liệu cho các màn trống được nạp qua service, giống mọi script seed khác** (`seed_community`). Ghi thẳng bảng sẽ dựng được trạng thái mà API từ chối tạo. Thứ duy nhất ghi thẳng là đồng hồ, để một tuần hỏi đáp không hiện "vừa xong" ở mọi dòng.

**Những gì chỉ có thể làm thật thì làm thật ngay lúc chụp:** quiz, nộp code, sinh quiz bằng Gemini, gửi duyệt. Phần ghi của học viên đi theo tài khoản seed khi gỡ dữ liệu demo; khóa tạm thuộc một giảng viên `@e2e` nên `purge_e2e` dọn. Quiz seed không tính giờ, nên giới hạn giờ được đặt tạm rồi trả về giá trị cũ, thay vì sửa hẳn dữ liệu của khóa thật.

## Chốt phạm vi trước khi đóng băng (05/10/2026)

User chốt hai câu hỏi mà lượt rà kho bằng chứng còn để ngỏ (`docs/report/assets/README.md` mục 3.4 và 5).

**Phụ đề video bị cắt** (mục cắt giảm số 2 của kế hoạch) — đề cương §5.1 mục 3 có hứa phụ đề, nhưng player chỉ có tiến độ và tốc độ phát. Tệp `.srt`/`.txt` giảng viên tải lên vẫn được lưu cạnh video và vẫn nuôi trợ giảng AI. Thứ bị cắt chỉ là hiển thị nó thành `<track>` trên player. Cái giá: học viên không bật được phụ đề. Chương 6 ghi vào phần hạn chế; nếu làm tiếp thì chỉ cần đổi SRT sang WebVTT và thêm `<track>`.

**Chứng chỉ giữ kiểu Udemy: bài nào cũng tự đánh dấu hoàn thành được, kể cả quiz và bài code** — chứng chỉ xác nhận học viên đã đi hết khóa, không xác nhận đã đạt từng bài kiểm tra. Đã ghi nhận ở lượt `/security-review` 01/10 (`phase-6/security-review-codebase.txt` §5) là mức dưới ngưỡng, chờ chốt. Cái giá: lấy được chứng chỉ mà không cần qua quiz hay được AC, trong khi trang xác thực `/cert/{code}` là công khai. Báo cáo phải nói rõ chứng chỉ chứng nhận điều gì. Tự đánh dấu cũng được +10 XP của bài học và được tính một ngày vào chuỗi, như mọi bài khác. Còn phần thưởng thêm cho quiz đạt (+20) và bài code AC (+30) thì chỉ đến từ làm bài thật.

## Font tự host thay cho next/font/google (06/10/2026)

E2E trên `main` đỏ sau khi merge PR #88, dù chính nội dung đó đã xanh ở CI của PR. Bằng chứng: `docs/report/assets/phase-6/self-hosted-fonts.txt`.

**Tự host 14 tệp font thay vì chờ Next sửa** — `next/font/google` tải từ Google ở mỗi lần build. Khoảng 1/60 lần Google trả URL `/l/font?kit=…&skey=…` mà Next không phân tích được (vercel/next.js#99114, Turbopack chưa có bản sửa). Build production của `deploy.sh` cũng gặp lỗi này. Tự host thì build không cần mạng, và kiểm được bằng một build `--network none`. Cái giá: cập nhật phiên bản font giờ làm tay (công thức ở `frontend/public/fonts/README.md`), và repo nặng thêm 385 KB.

**`@font-face` thuần, không dùng `next/font/local`** — `next/font/local` không gắn được `unicode-range` cho từng tệp. Muốn giữ cách chia subset của Google (trình duyệt chỉ tải subset trang dùng) thì phải viết CSS tay. Phần next/font còn làm hộ được viết lại bằng tay: mặt Fallback chép nguyên số đo, preload bằng thẻ `<link>`.

## Ký tự NUL ở mọi route (17/10/2026)

Task tách từ `phase-6/nul-byte-verdict.txt` mục 6. Bằng chứng: `docs/report/assets/phase-6/nul-everywhere.txt`.

**Chặn ở cửa vào, không dựng exception handler cho lỗi CSDL** — đo trên code cũ: 7 request ra 500, 3 trong số đó chỉ là `SELECT` (tìm khóa học, slug trên URL, mã đơn trong IPN). Riêng trợ giảng AI trả **200**: câu hỏi có NUL vẫn được nhúng, Gemini vẫn viết câu trả lời và stream về trong ~5 s, rồi mới hỏng lúc lưu và kết thúc bằng sự kiện `CHAT_NOT_SAVED`. Một handler đổi `CharacterNotInRepertoireError` thành 422 không sửa được ca này: status đã gửi đi, lỗi đã được service bắt, tiền Gemini đã trả. Handler đó còn phải biết thêm một lỗi nữa (jsonb báo `UntranslatableCharacterError`, SQLSTATE `22P05`, không phải `22021`). Nó cũng không phân biệt được NUL do client gửi với NUL đến từ chỗ khác (hồ sơ Google, câu trả lời của Gemini); gọi những ca đó là 422 là sai. Vì thế không kết hợp hai cách: ở những chỗ đó, 500 kèm log mới là câu trả lời thật. Chặn ở cửa vào thì luật chạy trước mọi thứ, nên request bị từ chối không tốn gì: không ghi dòng nào, không tính lượt rate limit, không gọi model. Sau khi sửa đo được 0 lỗi asyncpg và 0 lượt tìm vector.

**Dependency cấp app (`FastAPI(dependencies=...)`), không phải middleware** — FastAPI parse body trước khi chạy dependency và Starlette giữ lại kết quả, nên luật đọc đúng object mà route sẽ validate, không parse lần hai. Lỗi đi qua handler `RequestValidationError` sẵn có, nên ra đúng envelope 422 `VALIDATION_ERROR`, kèm `loc` (`body.full_name`, `query.q`, `path.slug`). FastAPI ghép dependency cấp app vào **đầu** danh sách của mọi route, kể cả route thêm sau này. Middleware ASGI thì phải tự đệm và parse body, tự dựng response, và đứng ngoài các exception handler. Cái giá: luật chạy trước xác thực, nên request chưa đăng nhập mà có NUL nhận 422 thay vì 401. Body JSON sai cú pháp vốn cũng được trả lời trước xác thực như vậy, và câu trả lời này không lộ gì.

**Xét path, query string và body JSON; không xét header và cookie** — uvicorn trả 400 cho header có NUL trước khi request tới app (đo bằng socket thô). Về cookie, API chỉ đọc hai cái: refresh token (băm trước khi truy vấn) và state OAuth (chỉ đem so). Cookie do trang khác trên cùng tên miền đặt thì client không chọn được, chặn theo nó là làm hỏng request vô cớ. Body chỉ được xét khi route có đọc body và FastAPI đã parse nó là JSON: route không đọc body thì NUL trong đó không tới đâu cả. Chuỗi JSON `"\\u0000"` (một gạch chéo thật và năm ký tự) là văn bản hợp lệ và được lưu nguyên, đã kiểm cả trong test lẫn qua HTTP.

**Duyệt bằng vòng lặp, không đệ quy** — module `json` của Python parse được tài liệu lồng sâu hơn mức đệ quy Python đi được, nên walker đệ quy sẽ biến một body lồng sâu thành một kiểu 500 mới. Chi phí đo được: 1,2 µs cho bài nộp 64 KB, 232 µs cho transcript ~1 MB (15 % thời gian `json.loads` của chính body đó).

**IPN của VNPay cũng theo luật chung** — route này trả HTTP 200 cho mọi kết quả và ghi `payment_events` cả với callback sai chữ ký. Query có NUL giờ nhận 422 và không được ghi. Trước đây nó cũng không ghi được (500 ngay ở câu `SELECT` đơn hàng), còn VNPay thì không bao giờ gửi NUL: tham số của nó là số, mã và chữ đã mã hóa URL.

**Không gỡ validator `NoNul` của phân hệ chấm bài (PR #95)** — hai lớp không xung đột: luật chung trả lời trước, cùng mã 422. Gỡ đi thì PR này phải sửa file của một PR đang chờ merge, mà không được thêm gì.

## Cách đo mốc trước/sau của Phase 7 (20/10/2026)

Task "Đo và chụp *trước*" của Phase 7. Bằng chứng: `docs/report/assets/phase-7/before.md`.

**Đo trên stack production của máy dev, qua nginx nội bộ, không qua Cloudflare** — cùng bản build, nginx, TLS, HTTP/2 và tên miền thật với người dùng, nhưng Chrome và Node trỏ `devpath-01.me` vào `127.0.0.1` (`phase-7/stack.cjs`). Mật khẩu tài khoản seed không rời máy; độ trễ Internet và tunnel (đổi theo giờ) không lẫn vào phép so trước/sau; beacon RUM do edge Cloudflare chèn không bị tính là JS của DevPath. Cái giá: số đo không gồm chặng Internet, nên đây là phép so hai giao diện, không phải trải nghiệm của một người dùng cụ thể.

**Lighthouse tự mở Chrome mỗi lượt, 3 lượt, lấy lượt giữa** — gắn Lighthouse vào Chrome mà Playwright đang điều khiển thì tab đứng im (Playwright tự gắn vào mọi tab mới); nối rồi ngắt Playwright thì ra `NO_NAVSTART`. Chrome riêng còn cho cache trống mỗi lượt, đúng cách đo chuẩn. Trang học cần đăng nhập nhận cookie phiên qua `--extra-headers`, mỗi lượt một phiên mới vì refresh token xoay vòng. Một lượt trên ba có thể lệch xa (CLS trang chủ 0,178 so với 0,001), nên bảng giữ cả khoảng min–max.

**Script chụp ảnh tự dựng dữ liệu bằng tài khoản dùng một lần, không dựa vào seed cộng đồng** — tài khoản hocvien07/25 của `seed_interactions` + `seed_community` đã gỡ khỏi CSDL từ 06/10, và quiz khóa Python chỉ có trên CSDL dev. Giờ `capture.cjs` dựng học viên, câu hỏi, ghi chú, phiên trợ giảng, giỏ hàng và một khóa có quiz qua đúng API của UI, rồi `purge_e2e` ở cuối; chạy được trên mọi stack có bốn khóa thật, kể cả lúc chụp bộ "sau" cho chương 4. Đổi lại, mỗi lượt tốn 5 lần gọi Gemini (4 câu trợ giảng, 1 lần sinh quiz).

## Design system: ngọc + nghệ, sinh bằng script (21/10/2026)

Task đầu của Phase 7, "Tạo artifact Design System DevPath". Bằng chứng: `docs/ui-ux/design-system/` (artifact + `palette.py` + `contrast.txt`), ảnh ở `docs/report/assets/phase-7/design-system/`.

**Màu do một script sinh ra và tự kiểm, không chọn tay từng mã hex.** `palette.py` chọn từng bậc màu trong OKLCH: cùng một bước L thì trông sáng tối như nhau ở mọi hue. Màu nằm ngoài sRGB thì chỉ giảm chroma, giữ L và hue. Script viết `tokens.json` rồi đo 130 cặp đã hứa trong ghi chú token (chữ ≥ 4.5:1; viền control, focus, icon, cột biểu đồ ≥ 3:1), thoát 1 nếu một cặp dưới sàn. Lần chạy đầu bắt được 6 cặp: vàng sáng trên trắng chỉ 2,3:1 (sao, huy chương, vòng quiz 100%), bạc 2,6:1. Cả sáu chuyển sang bậc đậm hơn. Đổi màu sau này cũng đi qua đúng phép kiểm đó.

**Ngọc (hue 178) làm màu thương hiệu, nghệ (hue 84) chỉ cho phần thưởng.** Ngọc ngả lam đủ xa xanh lá Duolingo (hue ~135), là màu dành cho thân nhân vật, và hợp nền code. Nghệ có một nghĩa duy nhất: bạn vừa được thưởng (XP, sao, quiz 100%, huy chương). Cảnh báo dùng hổ phách riêng. Bộ gợi ý của `ui-ux-pro-max` cho "e-learning" (chàm + cam, claymorphism, Baloo 2 / Comic Neue) bị bác: người dùng là sinh viên, và chàm–tím là kiểu giao diện AI chung chung mà tài liệu thiết kế tránh.

**7 màu verdict và 4 mức quiz, màu không bao giờ đứng một mình.** Code hôm nay chỉ có 3 tông verdict (đúng/sai/lỗi hệ thống). Design system tách 7. SE màu xám vì đó là lỗi hệ thống, không phải lỗi của học viên. Mức quiz thấp nhất là tím dịu "an ủi", không phải đỏ. Mỗi verdict luôn có mã + nhãn + icon, nên người mù màu và trình đọc màn hình không phụ thuộc vào màu.

**Giữ tên token của shadcn cho lớp ngữ nghĩa.** `background`, `primary`, `muted`, `accent`, `border`, `input`, `ring`… giữ nguyên tên, chỉ đổi giá trị; token mới (`verdict-*`, `quiz-*`, `reward*`…) thêm cạnh đó. Như vậy task "Nền" thay `globals.css` mà không phải sửa class trong `components/ui/*`, và E2E (dựa vào role/name, không dựa vào màu) không bị ảnh hưởng.

**Preview trong artifact là bản tĩnh** (HTML + `bundle.css` đọc token), không build bundle React của frontend. Preview đủ để duyệt màu và kích thước. Component thật đổi ở task "Nền", và lúc đó `globals.css` thắng nếu lệch artifact. Trình duyệt tích hợp chưa đăng nhập claude.ai, nên preview được kiểm trên máy bằng cách dựng lại `tokens.css` theo quy tắc của loại artifact rồi chụp bằng Playwright (`check/`): 11 preview × 2 bề rộng, 0 tràn ngang, 0 lỗi console.

User duyệt bảng màu ngày 21/10/2026.

## Lexend thay Geist làm font chữ chính (21/10/2026)

Task "Chọn font có subset vietnamese" của Phase 7. Số đo và cách chạy lại: `docs/ui-ux/design-system/fonts.md`; ảnh: `docs/report/assets/phase-7/font/`.

**Chọn bằng số đo trong Chrome thật, không bằng ấn tượng.** Bảy ứng viên có subset `vietnamese` trên Google Fonts, tải đúng tệp woff2 sẽ tự host, đo bốn thứ:
- dấu chồng có trồi khỏi hộp dòng ở từng cỡ của thang chữ không;
- "₫" so với chữ số;
- bề rộng một câu tiếng Việt;
- header khách ở 360px.

Rồi chụp chữ khó ("ẩ ẫ ấ ầ ậ", "Ỗ Ữ Ẫ", "ỵ") ở 12/14px với DPR 1 của laptop thường.

**Lexend, vì dấu đọc được ở cỡ nhỏ mà không bị cắt.**
- Geist (đang dùng) và Manrope làm nhòe dấu chồng ở 12–14px; Geist còn vẽ "₫" chỉ bằng 0,73 chữ số.
- Be Vietnam Pro có dấu rõ nhất nhưng trồi 1,7px khỏi dòng ở cỡ 14–16px: `truncate` cắt mất dấu ngã, "Ỗ" đọc thành "Ô". `line-clamp` còn để lộ dấu của dòng bị ẩn ở mép dưới khung, và không cách cắt nào trong 6 cách đã thử chặn được. Dùng font này sẽ phải tăng line-height toàn site hoặc chấp nhận lỗi đổi chữ.
- Plus Jakarta Sans đặt dấu nặng của "ỵ" lệch sang phải.
- Nunito gần dáng chữ tròn của Duolingo.
- Lexend giữ mọi dấu trong dòng từ cỡ `title` trở xuống, và là một tệp variable 52 KB cho mọi độ đậm, thay vì 132 KB bốn tệp tĩnh.

**Cái giá là bề rộng: Lexend rộng hơn Geist 6%.** Header khách ở 360px tràn 3,3px. Giữ nguyên bố cục, chỉ hạ cỡ chữ dưới `sm` (logo 19px, link 14px, nút 12px, khoảng 8px) để về đúng 345,0px như Geist. 8 trang công khai × 3 bề rộng không tràn, chạy vào `next dev` trên máy với dữ liệu thật của stack demo; trang cần đăng nhập để task "Nền" đo lại. Metric font dự phòng lấy bằng chính hàm `calculateSizeAdjustValues` của Next, hàm này tính lại đúng số Geist đang có, nên không phải bật lại `next/font/google` như cách lấy font cũ.

## Ba hướng linh vật, kiểm Duo bằng số đo (21/10/2026)

Task "Phác ba hướng nhân vật" của Phase 7. Nguồn: `docs/ui-ux/mascot/` (12 SVG, canvas, script kiểm), artifact Design "Linh vật DevPath", ảnh ở `docs/report/assets/phase-7/mascot-directions/`.

**So cho công bằng: chung bảng màu, chung nét, chung bốn trạng thái.** Cả ba hướng dùng bảng màu dành sẵn cho nhân vật trong design system, cùng nét viền `jade-900`, cùng vẽ `rest`, `celebrate` (AC), `partial` (WA), `lost` (404). Mỗi hướng có một artboard riêng: hình bóng, cỡ 24–64px, nhân vật đặt trong giao diện thật (dòng verdict AC, trang 404), điểm mạnh và rủi ro. Như vậy người chọn so ý tưởng, không so tay nghề của từng bản vẽ.

**"Không giống Duo" được kiểm bằng số, không bằng mắt.** Mã màu của Duo lấy từ trang thương hiệu chính thức của Duolingo, đo ΔE trong OKLab. Thân `jade-500` cách thân Duo 0,22, cách mọi màu xanh của Duo ít nhất 0,19 (mức vừa thấy khác là ≈ 0,02). Nhưng phép đo bắt được một điều mắt không để ý: `turmeric-300`, màu nhấn đã dành cho nhân vật, cách mỏ của Duo chỉ 0,028. Từ đó có luật: **màu nghệ không tô mỏ, chân hay bàn chân của nhân vật.** Chim Lạc vì thế có thân `jade-100` và mỏ `jade-700`. Đây là hướng duy nhất lệch bảng màu dành sẵn, và vẫn là chim.

**Claude đề xuất hướng A (tắc kè), user chọn A và đặt tên Naomi (21/10/2026).** Ẩn dụ "bắt bug" biến AC và WA thành hai cảnh của cùng một chuyện (bắt được con bọ / con bọ bay mất), gắn nhân vật vào đúng điểm nhấn số 1 của khóa luận. Robot đọc rõ nhất ở cỡ nhỏ nhưng ít bản sắc. Chim Lạc có bản sắc Việt nhưng gần Duo nhất về loài. Tên Naomi không nằm trong ba tên Claude gợi ý (Kè, Sùng, Bít).

**Artboard được kiểm trên máy, không qua trình duyệt đăng nhập claude.ai.** `check/boards.cjs` mở từng `.dc.html` bằng Chrome, trả ảnh `/_blob/<id>` bằng chính tệp SVG trong repo và font bằng Lexend tự host. Lượt đầu bắt được ba artboard dài hơn khung 4–46px và một hàng ảnh tràn ngang 16px. Đã sửa, cả năm artboard khít khung.

## Hoạt ảnh Naomi bằng motion/react-mini (21/10/2026)

Task "Spike công nghệ hoạt ảnh" của Phase 7. Số đo, ảnh và cách chạy lại: `docs/report/assets/phase-7/animation-spike.md` + `animation-spike/` (`run.cjs`, `results.json`, `frames/contact-sheet.png`).

**User chốt không làm Rive (21/10/2026)**, nên spike so ba cách chạy cùng một phản ứng `celebrate` trên cùng một SVG thay vì so Motion với Rive: CSS `@keyframes`, `motion/react-mini` (WAAPI) và `motion/react` đầy đủ. Cả ba đọc một tệp biên đạo duy nhất, và được đo trên bản build production của chính frontend: Chrome thật, chuỗi CSP production gắn vào từng trang, so với một bản SVG tĩnh trong cùng khung. Thư mục spike bị xóa khỏi app sau khi đo.

**Chọn `motion/react-mini` cho component `<Mascot />`; `motion/react` đầy đủ chưa vào dự án.**
- **Motion đầy đủ:** +25,6 KB gzip (một nửa ngân sách 50 KB của phase), +51 % CPU so với CSS cho mỗi phản ứng (173 so với 114,5 ms ở 1×).
  - Transform của phần tử SVG chạy bằng JS, ghi style từng khung, chứ không lên WAAPI.
  - Nó còn tự ghi `transform-box: fill-box`, làm sai mọi điểm xoay viết bằng toạ độ bản vẽ. Lượt đầu, vai Naomi trôi 17 px.
- **`mini`:** +5,3 KB, +11 % CPU so với CSS, không bẫy nào. Đổi lại, component điều khiển được lúc chạy: dừng phản ứng cũ khi sự kiện mới tới, chờ `.finished`, lấy khung hình từ prop (`grading` theo "test k/n"), giữ biên đạo trong TypeScript.
- **CSS thuần:** 0 KB JS. Vẫn là đường lui nếu ngân sách cạn: cùng dữ liệu biên đạo sinh được `@keyframes`.

Ba cách đều 0 vi phạm CSP, đứng yên đúng nghĩa khi `prefers-reduced-motion: reduce`, và không rớt khung ở 1× lẫn 4×. Phần lớn chi phí là Chrome vẽ lại SVG trên luồng chính: transform của phần tử con trong SVG không lên compositor, nên cách nào cũng phải trả phần đó. Vì thế phản ứng phải ngắn, và hình lặp (`thinking`, `grading`) nên nhẹ.

Bốn điều component phải làm theo, từ spike:
- Transform của CSS **thay** thuộc tính `transform` của SVG, nên `build.cjs` phải sinh `<g>` bọc ngoài cho lớp nào có transform đặt chỗ.
- Điểm xoay dùng `transform-box: view-box` + toạ độ bản vẽ.
- `<svg>` cần `overflow: visible`, vì cú nhảy vượt `viewBox`.
- Lớp gọi bằng `data-layer` thay cho `id`, vì hai bản vẽ trên một trang thì trùng id.

## Component Naomi: Web Animations trực tiếp, giữ dáng sau phản ứng (21/10/2026)

Task "Component `components/mascot/`" của Phase 7. Số đo, ảnh và cách chạy lại: `docs/report/assets/phase-7/mascot.md` + `mascot/` (`capture.cjs`, `results.json`, `frames/`).

**Gọi thẳng Web Animations API, không thêm gói `motion`.** Spike chọn `motion/react-mini`, nhưng `mini` chỉ là một lớp mỏng trên chính API này. Mọi lý do spike nêu để chọn nó (dừng phản ứng cũ, chờ `.finished`, khung hình theo prop, biên đạo trong TypeScript) đều có sẵn trong API gốc: đường cong cho từng đoạn (`easing` trong keyframe), `finished`, `cancel()`, và `translate`/`rotate`/`scale` tách riêng mà trình duyệt áp cho SVG. Vì vậy component chạy đúng cơ chế spike đã đo CPU, mà không thêm 5,3 KB và không thêm dependency. Gọi trực tiếp còn cho chọn `fill` cho từng track. Track bắt đầu khác bản vẽ (ngôi sao từ scale 0) thì giữ khung đầu trong lúc chờ (`backwards`). Track bắt đầu từ bản vẽ thì không giữ, vì nếu giữ nó sẽ che track trước trên cùng thuộc tính. Lần thử đầu đã gặp đúng chuyện này với hai cú nhảy nối nhau. Đổi lại phải tự làm phần `mini` vốn làm hộ: đọc `--ease-*` từ `globals.css` (WAAPI không nhận `var()` trong `easing`) và đặt `transform-box`/`transform-origin` trước khi chạy.

**Hết phản ứng, Naomi giữ dáng của mood. Chỉ `wave` về `rest`.** Spike và `naomi.json` từng cho mọi phản ứng mờ chéo về `rest`. Ảnh khung hình cho thấy làm vậy xóa mất bối cảnh: `levelup` mất cái bục và Naomi to vọt từ 0,78 lên 1, `sad` mất ngọn nến, `graduate` mất mũ. Thêm hai lý do:
- người bật giảm chuyển động chỉ thấy tư thế tĩnh của mood, nên nếu người khác thấy hình cuối là `rest` thì hình cuối phụ thuộc vào việc có xem hoạt ảnh hay không;
- tài liệu thiết kế (mục 5) cho trang mở lại kết quả cũ hiện "tư thế tĩnh tương ứng", tức đúng hình mà người vừa nhận verdict thấy sau phản ứng.

"Về tư thế nghỉ" trong plan được hiểu là đứng yên sau ≤ 2,4 s. `wave` là cử chỉ chào, không phải trạng thái, và được vẽ cùng cỡ, cùng chỗ với `rest`, nên mờ chéo không giật. Test khóa danh sách này.

**Màu là `var(--color-<token>)`, khai ở khối `[data-mascot]` trong `globals.css`.** Bảng màu design system chưa vào `@theme` (task "Nền"). Khai ở `:root` thì các tên `slate-100`, `red-500`, `green-600` sẽ đè màu mặc định của Tailwind trên cả site trước khi task đó đổi component. Khối này phải xóa khi bảng màu vào `@theme`. Test so khối đó với `tokens.json`.

**Tư thế tĩnh do máy chủ render, mỗi mood một chunk.**
- Trình duyệt đọc bản vẽ bằng `use()` từ một `import()` có cache. Promise tự ghi `status`/`value`, nên hình đã tải render đồng bộ.
- Máy chủ đọc đồng bộ từ `art/server.ts`, nằm sau `typeof window === "undefined"` (Next thay bằng hằng lúc build). Nhờ vậy không lần render nào phải chờ chunk, kể cả request đầu sau khi khởi động. Phép đo xác nhận bundle trình duyệt không chứa module đó.
- `useDeferredValue` giữ hình cũ tới khi hình mới tải xong, nên đổi mood (grading → verdict) không chớp trống.
- Phản ứng chỉ chạy khi Naomi đã lên màn hình (IntersectionObserver). Đó là phần "tải lười".
- Một chunk hình lỗi chỉ làm Naomi biến mất, không làm sập trang (error boundary riêng).
- Hẹn giờ dự phòng (`endsAt + 1 s`) đưa Naomi về tư thế tĩnh nếu animation bị dừng hay hủy từ bên ngoài. Chrome không báo `finished` cho animation đang dừng bị tua quá điểm cuối; lúc chụp khung hình, component từng kẹt ở "đang phản ứng" vì chuyện này.

Giới hạn còn lại: React tách một boundary đã xong ra cuối luồng HTML khi phần HTML trước nó vượt 12.800 byte (`progressiveChunkSize`). Hình khi đó hiện bằng một script inline trước hydrate, nên trình duyệt tắt JS không thấy nó. Trang đo có một Naomi sau một đoạn HTML ngắn, và hình nằm ngay trong HTML. Trang `/dev/naomi` có 32 hình, và cả 32 bị tách ra cuối. Khi gắn Naomi vào trang thật (404, empty state), đo lại trên trang đó.

## Bài đọc: Markdown có xem trước, ảnh chỉ từ kho nhà (23/10/2026)

Task ngoài kế hoạch Phase 7, user yêu cầu sau khi tự soạn thử một khóa. Bằng chứng: `docs/report/assets/phase-7/article-editor.md` + `article-editor/`.

**Giữ Markdown, không chuyển sang trình soạn WYSIWYG (Tiptap, Lexical…).**
- `lessons.article_content` là Markdown. Ingest RAG cắt đoạn trên chính văn bản đó, và trang học vẽ nó bằng `<Markdown>`.
- WYSIWYG kéo theo một trong hai cái giá. Lưu HTML/JSON thì phải đổi định dạng lưu, viết lại ingest và có một đường render thứ hai, dễ lệch với trang học. Lưu Markdown qua bộ chuyển đổi thì có những định dạng soạn được mà không lưu được.
- Ô soạn có xem trước dùng **đúng component của trang học** nên thấy gì được nấy, thêm 0 KB cho trình soạn và không đổi một dòng dữ liệu nào.
- Thanh công cụ chỉ viết cú pháp, qua `execCommand("insertText")` để Ctrl+Z còn hoạt động. API này bị đánh dấu cũ, nhưng là cách duy nhất chèn chữ vào `<textarea>` mà giữ được lịch sử hoàn tác. Trình duyệt không có thì rơi về cập nhật state, chỉ mất phần hoàn tác.

**Không có bảng ảnh.** Avatar và banner có một cột trỏ tới ảnh. Ảnh của bài đọc thì nằm giữa văn bản, và một ảnh có thể được chép sang bài khác. Bảng `lesson_images` sẽ phải đồng bộ với văn bản mỗi lần lưu, và sẽ sai ngay khi giảng viên dán một dòng ảnh từ bài này sang bài kia. Thay vào đó, job dọn mồ côi coi **văn bản là nguồn sự thật**: key nào còn xuất hiện trong một bài đọc thì còn được dùng. Cái giá là một câu `LIKE '%lesson-images/%'` mỗi đêm trên bảng `lessons`, nhỏ so với việc liệt kê cả bucket.

**Một thư mục cho mỗi khóa, không phải mỗi bài.** Chuyển một đoạn có ảnh sang bài khác cùng khóa là việc thường gặp, và ảnh không nên vì thế mà "ở sai chỗ". Đuôi tệp lấy theo kiểu, không theo tên: ảnh dán từ clipboard luôn tên `image.png`.

**Ảnh chỉ được vẽ khi nằm trên kho media của DevPath; nơi khác thành liên kết.**
- Markdown cho tác giả trỏ ảnh tới bất kỳ đâu, và trình duyệt vẽ ảnh là đã báo cho chủ địa chỉ đó ai đang đọc, từ IP nào, lúc nào.
- Ở đây tác giả và người đọc là hai người khác nhau: giảng viên viết cho cả lớp, học viên hỏi giảng viên trong Hỏi đáp.
- Trang chính sách bảo mật hứa "không gắn công cụ theo dõi của bên thứ ba". Một ảnh 1 px trong bài đọc sẽ phá lời hứa đó mà DevPath không hay biết.
- CSP `img-src … https:` vẫn để mở (avatar Google cần), nên chặn phải nằm ở trình hiển thị.
- Cái giá: ảnh minh họa từ trang khác phải tải lại lên DevPath mới hiện được.

**GIF được nhận, SVG thì không.** Vài giây quay màn hình là kiểu ảnh hay gặp nhất trong bài lập trình. SVG có thể chứa script, mà bucket trả object về đúng kiểu nó được gửi lên. Đây cùng lý do với avatar.

## Nộp bài code: Naomi chỉ cho lần nộp thật, toàn màn hình không dựng lại Monaco (24/10/2026)

Nhóm màn 3 của Phase 7. Bằng chứng: `docs/report/assets/phase-7/code-submission.md` + `code-submission/`.

**Chạy thử không có Naomi.** Bản đồ phản ứng gắn nhân vật vào verdict, và chạy thử cũng ra verdict. Nhưng chạy thử là diễn tập: chỉ test mẫu, không vào lịch sử, có thể bấm hàng chục lần. Nếu Naomi nhảy mừng cả khi chạy thử đúng 2/2 test mẫu, thì cú nhảy khi nộp bài đúng hết mọi test mất ý nghĩa. Vì vậy chạy thử có dải kết quả gọn, nói số test mẫu đúng và nhắc nộp để chấm với test ẩn.

**Naomi phản ứng theo id bài nộp trang vừa gửi, không theo việc kết quả có trên màn hình.** `reactTo` chỉ khác null khi bài đang hiện chính là bài trang này vừa gửi và đang theo dõi qua WebSocket. Mở lại một bài từ lịch sử thì `reactTo` null, nên Naomi đứng yên ở mood của verdict, đúng "tư thế tĩnh tương ứng" của thiết kế mục 5. Component `<Mascot>` đã phản ứng một lần cho mỗi cặp (mood, event): `grading` rồi verdict là hai phản ứng của cùng một bài nộp.

**Toàn màn hình là cùng một cây React, đổi lớp, không phải một dialog.** Dời Monaco sang một cây khác (portal, dialog) là dựng lại editor, mất con trỏ và lịch sử hoàn tác giữa lúc học viên đang sửa bài. Ở chế độ thường, hai lớp bọc dùng `display: contents` nên không tạo hộp. Ở chế độ toàn màn hình, chúng thành hai cột flex. React giữ nguyên mọi phần tử vì chỉ `className` đổi. Script kiểm so đúng phần tử `.monaco-editor` trước và sau. Nút chỉ hiện từ 1024 px: dưới đó hai cột không vừa.

**Màu Monaco đọc từ biến CSS lúc chạy, không viết trong component.** Monaco tự vẽ và chỉ nhận mã hex. Component đọc `--color-*` của `@theme static` khi Monaco khởi tạo. Nhờ vậy `globals.css` vẫn là nơi duy nhất viết màu. Thiếu một biến thì theme vẫn được khai báo, chỉ là bản `vs` trơn: editor không bao giờ hỏng vì màu.

**Mã verdict lạ được vẽ như SE.** Grader thêm mã mới trước khi frontend biết thì dải kết quả màu xám, câu "không phải lỗi của bạn". Đó là cách đọc trung thực nhất của "trang này không biết mã đó nghĩa là gì".

**Với bài code, "Đánh dấu hoàn thành" thành nút viền.** Bài code tự hoàn thành khi bài nộp được AC, trong cùng transaction với verdict. Nếu nút này vẫn là nút chính, màn có hai nút chính cạnh "Nộp bài". Nút vẫn bấm được (user chốt 05/10: chứng chỉ giữ kiểu Udemy).


## Trang học: mục lục gập theo chương, Naomi là gương mặt của trợ giảng (25/10/2026)

Nhóm màn 4 của Phase 7. Bằng chứng: `docs/report/assets/phase-7/learn-page.md` + `learn-page/`. Backend không đổi.

**"x/y bài" chỉ viết một lần trên trang.** Số này nằm ở thanh khóa học trên cùng. Mục lục ghi "4 chương · 18 bài", mỗi chương ghi "3/3". Lý do thứ nhất là người đọc chỉ cần một con số tiến độ. Lý do thứ hai là E2E luồng vàng tìm đúng chữ "1/2 bài", nên hai chỗ cùng chữ là lỗi "strict mode" của Playwright. Script kiểm bắt được một lỗi như vậy lúc làm: phần chữ ẩn cho trình đọc màn hình của từng chương từng ghi "3/3 bài đã xong", tức là có 5 chỗ khớp "x/y bài". Giờ chữ ẩn là "Đã xong 3/3".

**Mục lục mở chương đang học, gập các chương khác.** Khóa 18 bài liệt kê hết thì bài đang học bị đẩy khỏi cột dính bên phải, và trên điện thoại mọi thứ dưới bài học bị đẩy xuống rất xa. Học viên mở thêm chương nào thì chương đó giữ nguyên. Đi sang bài thuộc chương đang gập (bằng "Bài tiếp theo") thì chương đó tự mở. Việc này được điều chỉnh ngay trong lúc render khi bài đổi, không dùng effect, nên không có khung hình nào mà dòng đang học bị ẩn.

**"Bài trước" / "Bài tiếp theo" là link, tính từ mục lục đã có trên trang.** Không cần request mới. Vì là link nên nút back của trình duyệt đi lùi từng bài, và bấm vào thì trang cuộn lên đầu bài mới. Bấm trong mục lục thì vẫn giữ vị trí cuộn như cũ: đó là chọn bài trong khi đang nhìn mục lục.

**Mỗi màn một nút chính, và nút chính đổi theo việc học.** Bài video và bài đọc chưa xong thì nút chính là "Đánh dấu hoàn thành". Xong rồi thì "Bài tiếp theo" thành nút chính, vì đó là việc tiếp theo. Bài code và quiz tự hoàn thành (AC, hoặc làm đạt) và có nút chính riêng ("Nộp bài"). Với hai loại này, đánh dấu tay là nút viền và "Bài tiếp theo" giữ màu phụ. Quiz trước đây vẫn có nút "Đánh dấu hoàn thành" màu chính cạnh nút nộp, tức là hai nút chính trên một màn.

**Naomi là gương mặt của trợ giảng, đứng ở đầu khung chat.** Naomi `thinking` khi đang tra cứu và soạn câu trả lời, `answer` (cầm sách mở) khi câu trả lời trích được nguồn trong khóa, `rest` khi chưa hỏi gì, câu hỏi ngoài phạm vi, hoặc câu trả lời bị dừng/lỗi. Mỗi câu hỏi là một sự kiện cho `thinking`, mỗi câu trả lời là một sự kiện cho `answer`. Mở lại cuộc trò chuyện từ lịch sử thì Naomi đứng yên. Vì Naomi đã ở đầu khung, phần trống của khung chat không vẽ thêm Naomi và câu trả lời không có avatar riêng. Câu từ chối nhận ra bằng đúng luật của backend (`chat.is_refusal`: cụm "ngoài phạm vi tài liệu" trong câu đầu), có test đối chiếu với `chat.py`.

**Lúc đang trả lời, trang hiện ba bước: tra cứu tài liệu khóa học → đọc N bài liên quan → soạn câu trả lời.** Trước đây chỉ có spinner và một dòng liệt kê sáu tên bài. Ba bước này đi theo đúng các sự kiện SSE có sẵn (`sources` rồi `delta`). Chúng cho người xem thấy phần truy xuất của RAG (điểm nhấn ⭐) đang làm gì, ngay trong lúc nó làm.

**Naomi `graduate` chỉ phản ứng khi khóa vừa xong trong phiên đó.** Trang phải đã thấy khóa chưa xong trước. Mở lại một khóa đã xong thì Naomi đứng yên trong banner, cạnh nút "Xem chứng chỉ". Banner dùng màu phần thưởng (nghệ nhạt) vì chứng chỉ là phần thưởng. Khóa từng xong rồi bị bỏ tick một bài thì chứng chỉ vẫn còn, và link "Xem chứng chỉ" chuyển về thanh khóa học. Không bao giờ có hai link cùng lúc.

**Hộp thư Hỏi đáp của giảng viên đổi theo.** `QaThreadView` dùng chung cho trang học và `/giang-day/hoi-dap`. Trên trang học, nút "Gửi câu trả lời" là nút phụ vì việc chính của màn là bài học. Trong hộp thư của giảng viên, trả lời là việc chính nên vẫn là nút chính.
