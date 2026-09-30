# Phase 5 — Commerce, Gamification & Admin (tuần 11–12, 02/11 → 15/11)

**Mục tiêu:** khép kín vòng thương mại (giỏ hàng → thanh toán → sở hữu khóa học), gamification, và bộ công cụ quản trị.

## Tuần 11 — Thanh toán & thương mại

- [x] Giỏ hàng + wishlist (API + UI)
- [x] Coupon: validate (hạn, lượt dùng, phạm vi), áp vào order
  - Phần **"áp vào order" nằm ở task VNPay ngay bên dưới**: `orders` chưa tồn tại khi làm task này, và một cột trỏ vào bảng chưa có là thứ không ai kiểm được. Đã xong: bảng `coupons`/`coupon_courses` (migration `d23158098a8c`), toàn bộ luật validate, `POST /cart/coupon` (thử mã lên giỏ hiện tại, trả số tiền giảm), ô nhập mã ở `/gio-hang`, và `coupons_service.consume` — chỗ trừ lượt bằng `UPDATE … WHERE used_count < max_uses`, để task thanh toán chỉ còn gọi (23/09/2026)
- [x] VNPay sandbox: tạo payment URL → redirect → IPN handler (verify chữ ký HMAC, idempotent theo `provider_txn_id`) → order `paid` → tự động enroll các khóa trong order
  - Migration `99c7ba304d8d` (`orders`, `order_items`, `payment_events`), `services/vnpay.py` + `services/orders.py`, `POST /orders` · `POST /orders/{code}/payment-url` · `GET /payments/vnpay/ipn` (24/09/2026)
  - Merchant sandbox đã đăng ký 24/09/2026 (`VNPAY_TMN_CODE`, `VNPAY_HASH_SECRET` ở `infra/.env`); VNPay đã nhận URL thanh toán mình ký (TmnCode hợp lệ, chữ ký khớp). **Còn thiếu đúng một thứ từ bên ngoài: VNPay khai IPN URL** — cổng merchant không có ô tự khai, đã gửi mail cho kỹ thuật VNPay xin khai `<ngrok cố định>/api/v1/payments/vnpay/ipn` (Quick Tunnel đổi URL mỗi lần chạy nên không dùng được). Trống credentials thì `/payment-url` trả 503 `PAYMENT_NOT_CONFIGURED`
- [x] `payment_events` append-only log mọi IPN; trang kết quả thanh toán (thành công/thất bại/đang xử lý)
  - Ghi **trước khi phán xét**, kể cả callback sai chữ ký; `order_id` nullable để giữ được callback không khớp đơn nào. Trang `/thanh-toan/ket-qua` chỉ lấy mã đơn từ URL rồi hỏi `GET /orders/{code}` — đơn còn `pending` thì hỏi lại mỗi 3 giây trong 90 giây
- [x] Test: giả lập IPN hợp lệ/sai chữ ký/trùng lặp — cả 3 case phải đúng
  - 26 test ở `tests/api/test_orders.py` + 20 test ký/kiểm chữ ký ở `tests/test_vnpay.py` (chuỗi canonical ghim **viết tay từ đặc tả**). Chạy tay được bằng `python -m scripts.simulate_vnpay_ipn <mã đơn> [--fail]`, ký bằng đúng secret backend dùng để kiểm
- [ ] MoMo sandbox (nếu còn thời gian — mục cắt giảm số 1)
- [x] Dashboard doanh thu instructor: doanh thu theo thời gian, học viên mới, tỉ lệ hoàn thành per khóa học
  - `GET /instructor/stats/overview?period=7d|30d|90d|12m` + `GET /instructor/stats/courses`, trang `/giang-day/thong-ke` (24/09/2026). Migration `3f7c33c23e64`: `order_items.discount` — phần giảm của từng dòng, chia lúc tạo đơn, để coupon giới hạn một khóa không bị trừ vào doanh thu khóa khác cùng đơn. Ngày gom theo giờ Việt Nam. Dữ liệu demo: `python -m scripts.seed_sales` (77 đơn trải 12 tháng, qua đúng giỏ → đơn → IPN). Đã xem trên Chrome thật: cả 4 kỳ, tooltip bằng chuột và bàn phím, bề ngang 374px không cuộn ngang trang. Ảnh cho gate chưa chụp — thuộc mục thu bằng chứng cuối phase

## Tuần 12 — Gamification, Q&A, Admin

- [x] XP events (hoàn thành lesson/quiz/bài code AC lần đầu) + streak theo ngày hoạt động
  - Migration `e9d78af241e6` (`xp_events` append-only + `streaks`), `services/gamification.py`, `GET /users/me/gamification` · `GET /users/me/xp-events`, khối "Chuỗi ngày học / Tổng XP / XP gần đây" đầu trang `/khoa-hoc-cua-toi` (28/09/2026). XP: bài học +10 (mọi loại), quiz đạt +20 và bài code AC +30 cộng thêm vào XP bài học. Luật "lần đầu" nằm ở unique `uq_xp_events_ref` + `ON CONFLICT DO NOTHING`, ghi trong cùng transaction với completion/verdict, chỉ cho người có ghi danh. Một ngày vào chuỗi khi học viên **nộp** một thứ gì đó (hoàn thành bài, nộp quiz kể cả trượt, nộp code không tính chạy thử), theo giờ Việt Nam; chuỗi bị cắt lúc đọc chứ không có job nửa đêm. Đã chạy thật trên stack bằng một tài khoản dùng một lần (sau đó đã xóa): 2 video + quiz 100% + bài code được **sandbox thật** chấm AC → 90 XP, chuỗi 1 ngày; chạy lại cả luồng lần hai thì vẫn 90
- [x] Leaderboard Redis sorted set (tuần/tháng/toàn thời gian) + trang leaderboard
  - `services/leaderboard.py`, `GET /leaderboard?period=week|month|all`, trang `/bang-xep-hang` (lối vào ở menu người dùng và khối thành tích). Ngày hoàn thành: 28/09/2026.
  - **Ba sorted set** là view của `xp_events`: tuần ISO và tháng tính theo giờ Việt Nam, cùng bảng toàn thời gian.
  - **`ZINCRBY` chỉ chạy sau commit:** `award()` ghi tạm vào `session.info`, rollback thì bỏ.
  - **Tự lành:** bảng được dựng lại từ ledger khi thiếu marker, mỗi đêm 03:30 bằng Celery beat, và khi chạy `scripts.rebuild_leaderboard`. Dựng lại bằng `ZADD` vào key tạm rồi `RENAME`.
  - **Đồng hạng kiểu thi đấu** (1, 2, 2, 4), dựa trên `ZCOUNT` những điểm lớn hơn hẳn. Hạng của người đọc vẫn trả về khi không nằm trên trang đang xem.
  - **Dữ liệu demo** `scripts.seed_study`: 40 người mua của `seed_sales` học 70 ngày qua service thật (chỉ lùi đồng hồ). Kết quả: 648 bài, 21 quiz đạt / 3 lần trượt, 49 lượt tham gia khóa miễn phí; bảng tuần 4 người (hôm đó là thứ Hai), tháng 27 người, mọi thời gian 40 người.
  - **Đã kiểm:** API trên Redis thật; trang bằng tài khoản người mua mẫu (cả 3 tab, trang 2, không cuộn ngang ở 375px); test adapter với Redis thật (CI có Redis).
  - Test của kế hoạch học đã bắt được một lỗi: giờ của các bài trong cùng một ngày được bốc độc lập nên lệch thứ tự.
- [x] Chứng chỉ PDF khi hoàn thành 100%: job Celery sinh PDF (weasyprint) + mã QR → trang verify công khai `/cert/{code}`
  - Migration `b6fc99d6b6af` (`certificates`), `services/certificates.py`, job `render_certificate`, `GET /certificates/{code}` + `/pdf` (công khai), trang `/cert/{code}`, nút "Chứng chỉ" ở `/khoa-hoc-cua-toi` và link trong trang học. Ngày hoàn thành: 29/09/2026.
  - **Cấp** trong cùng transaction với lúc khóa học chuyển sang hoàn thành, mỗi lượt ghi danh một lần. Bỏ tick không thu hồi. Tên người học, tựa khóa và tên giảng viên được **đóng băng** lúc cấp (thêm 3 cột so với đặc tả).
  - **Mã** 16 ký tự từ 32 ký tự không gây nhầm (80 bit), có CHECK định dạng.
  - **PDF** do Celery vẽ sau commit (qua `after_commit.run`, cùng chỗ đẩy điểm bảng xếp hạng). Endpoint tải PDF đẩy lại job khi PDF chưa có.
  - WeasyPrint cần Pango, nên image và CI cài thêm Pango/HarfBuzz và font DejaVu. Test vẽ PDF skip trên Windows, bắt buộc trên CI, và đã chạy trong container.
  - `scripts.issue_certificates` cấp bù cho các lượt đã hoàn thành trước đó: 233 chứng chỉ, 233 PDF trong 98 giây.
  - **Đã chạy thật:** hoàn thành bài cuối → chứng chỉ được cấp → worker vẽ PDF sau 3 giây → tải được. Mã QR trên PDF giải ra đúng URL xác thực. Mã sai trả 404 thật.
  - Sửa kèm: `apiUrl()` trên frontend từng ghi host nội bộ `backend:8000` vào link khi render phía server; nút Google cũng mắc lỗi tiềm ẩn này.
  - Mục gate "quét QR verify được" đã chạy được; ảnh và PDF mẫu thu ở mục bằng chứng cuối phase.
- [x] Q&A theo lesson: thread + reply + upvote; badge "giảng viên trả lời"; notification khi được trả lời
  - Migration `8f1cea268f50` (`qa_threads`, `qa_replies`, `qa_votes`, `notifications`), `services/qa.py` + `services/notifications.py`, router `qa.py`, tab "Hỏi đáp" dưới bài học và trang `/giang-day/hoi-dap`. Ngày hoàn thành: 29/09/2026.
  - **Chỉ upvote**, nên `qa_votes` bỏ cột `value` của đặc tả: một dòng là một phiếu, mỗi người một phiếu (unique). Người hỏi không vote câu của mình.
  - **Ai tham gia:** học viên đã ghi danh, giảng viên của khóa, admin; bài học thử cũng vậy (xem được bài thử không có nghĩa là vào được lớp). Người hỏi sửa câu hỏi; người hỏi hoặc giảng viên đánh dấu giải quyết và xóa.
  - **Badge:** `is_instructor_reply` quyết định lúc viết. Danh sách tính `has_instructor_reply`, số vote và số trả lời lúc đọc, không có cột đếm.
  - **Notification:** trả lời câu của người khác ghi `notifications` (`qa_reply`, payload là ảnh chụp id + tiêu đề + tên người trả lời) cùng transaction với câu trả lời. Chuông và danh sách để cho task kế tiếp.
  - **Giảng viên trả lời ở đâu:** giảng viên không ghi danh được khóa mình nên không vào trang học được; hộp thư `/giang-day/hoi-dap` mở sẵn ở "chưa trả lời" (chưa có trả lời của giảng viên và chưa giải quyết).
  - **Đã chạy thật** bằng một học viên và một giảng viên dùng một lần (đã xóa sau đó), trên stack thật và trong khung trình duyệt:
    - hỏi → hộp thư có câu đó → giảng viên trả lời trên UI → badge và thông báo xuất hiện → câu rời khỏi "chưa trả lời";
    - tự vote câu mình → 409;
    - đặt câu hỏi, đánh dấu giải quyết và xóa trên UI;
    - bề ngang 375px không cuộn ngang.
  - Sửa kèm: cột mục lục của trang học tràn 17px trên điện thoại (thiếu `min-w-0` ở grid item).
- [x] Thông báo in-app (chuông + danh sách)
  - `GET /notifications` (+ `unread=true`), `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`. Chuông trên header và trang `/thong-bao`. Ngày hoàn thành: 29/09/2026.
  - Migration `c7c21bbd1a9b`:
    - thêm `ix_notifications_user_created`: trang danh sách đọc cả thông báo đã đọc, mà index partial của chuông không chứa chúng;
    - thêm loại `qa_question`: học viên hỏi thì giảng viên của khóa được báo, khép vòng hỏi → báo giảng viên → trả lời → báo người hỏi.
  - **Không dùng WebSocket.** Số trên chuông hỏi mỗi 60 giây và mỗi khi cửa sổ được focus lại; danh sách trong dropdown chỉ tải khi mở.
  - **Đánh dấu đã đọc idempotent**, giữ `read_at` đầu tiên. Bấm một thông báo là đánh dấu đã đọc rồi đi tới nơi nó trỏ.
  - **Câu chữ và link do frontend dựng** từ `type` + `payload`. Loại mà trang chưa biết vẫn hiện một dòng chung.
  - **Đã chạy thật** bằng một học viên và một giảng viên dùng một lần, trên một khóa tạm (đã xóa cả ba):
    - học viên hỏi → chuông giảng viên "1 chưa đọc" → bấm vào → mở đúng câu hỏi trong hộp thư, chuông về 0;
    - giảng viên trả lời → chuông học viên báo 1 → `/thong-bao` → bấm vào → trang học mở tab Hỏi đáp đúng câu hỏi;
    - ở 375px không cuộn ngang, dropdown nằm gọn trong màn hình.
  - Sửa kèm: chuông làm header không còn đủ chỗ ở 375px ("Khóa học" rớt dòng), nên dưới `sm` khoảng cách và padding nút được thu lại. Bộ phân trang của Q&A chuyển thành `components/ui/pager.tsx` dùng chung.
- [x] Admin: duyệt/từ chối khóa học (bỏ auto-approve flag của phase 2), quản lý user (khóa/mở), xử lý reports
  - **Duyệt khóa học phải gọi `enqueue_ingest`** như `submit_for_review` đang làm khi auto-approve bật (`backend/app/services/courses.py`). Tắt auto-approve mà endpoint duyệt quên việc này thì không còn gì nạp khóa học vào kho chatbot. Viết test: duyệt → một job ingest được xếp hàng (ghi 19/09/2026, đợt dọn nợ)
  - Ngày hoàn thành: 30/09/2026. Migration `6e27fe4795b3` (`reports` + mở rộng `ck_notifications_type`), `services/moderation.py` + `services/admin_users.py` + `services/reports.py`, router `/admin/*` + `POST /reports`, khu `/quan-tri` (khóa học, báo cáo, người dùng) và nút "Báo cáo" ở trang khóa học, đánh giá, Hỏi đáp.
  - **Cờ `AUTO_APPROVE_COURSES` bị bỏ hẳn** (config, compose, `.env` mẫu). Gửi duyệt luôn dừng ở `pending_review` và không xếp job nào; **duyệt** mới xếp ingest RAG + nhúng khóa học, sau commit. `test_course_ingest.py` viết lại để ghim điều đó; test cần khóa công khai tạo qua API dùng `tests/api/publishing.py`.
  - **Quyết định của admin báo giảng viên** cùng transaction: 3 loại thông báo mới `course_approved`, `course_rejected` (kèm lý do), `course_taken_down`. Lý do từ chối hiện ở trang quản lý khóa học (`CourseOut.rejection_reason`).
  - **Khóa tài khoản** dùng cột `users.locked_at` có sẵn (các chỗ chặn đăng nhập/refresh/access token đã có từ Phase 2), thêm thu hồi mọi refresh token ngay lúc khóa. Admin không khóa được (kể cả tự khóa). Khóa không gỡ nội dung, khóa học của giảng viên bị khóa vẫn bán.
  - **Báo cáo:** 5 lý do đóng (`other` bắt buộc mô tả), chỉ báo được thứ mình xem được và không phải của mình, mỗi người một báo cáo đang chờ trên một nội dung. Quyết định **đóng mọi báo cáo đang chờ trên cùng nội dung**; "gỡ nội dung" chạy cùng transaction: khóa học → `draft` (không xóa mềm), đánh giá → xóa + tính lại rating, câu hỏi/câu trả lời → xóa.
  - **Đã chạy thật** bằng 3 tài khoản dùng một lần + khóa tạm (đã xóa): gửi duyệt → từ chối có lý do → gửi lại → duyệt trên UI → worker chạy ingest (1 chunk) + embedding; 2 báo cáo → "Gỡ khóa học khỏi sàn" đóng cả hai; khóa → `ACCOUNT_LOCKED` → mở → đăng nhập lại được; 375px không cuộn ngang. Bằng chứng: `docs/report/assets/phase-5/admin-moderation.txt`.
  - Sửa kèm: ô "Viết đánh giá" hiện với **mọi** người đã đăng nhập mà chưa ghi danh (gửi thì 403) — `getMyEnrollment` trả `null` khi chưa ghi danh còn `course-reviews.tsx` so với `undefined`. Thấy khi xem trang khóa học bằng tài khoản admin.
  - Test: 19 + 8 + 25 test mới, `test_course_ingest.py` 5. Cả bộ trong container 1487 passed, 2 failed — hai test "storage chưa cấu hình → 503" đỏ vì container tự rơi về MinIO, không liên quan.
- [x] Admin dashboard: doanh thu sàn, DAU, khóa học hot; quản lý category, coupon toàn sàn, banner trang chủ
  - Ngày hoàn thành: 30/09/2026, nhánh `feature/admin-dashboard`, 4 commit (mỗi phần một commit).
  - **Dashboard** (`services/platform_stats.py`, `GET /admin/stats/overview` + `/hot-courses`, trang `/quan-tri`): doanh thu = `orders.total` của đơn `paid` theo `paid_at`, cùng lịch ngày/tháng giờ Việt Nam và phép so kỳ trước với dashboard giảng viên (dùng lại cả `ColumnChart`/`StatTile`/`PeriodPicker`). **DAU** = số người có ít nhất một dấu vết trong ngày ở các bảng vốn đã ghi — `refresh_tokens` (đăng nhập và mỗi lần mở lại phiên), tiến độ bài, XP, quiz, nộp code, hỏi trợ giảng AI, hỏi đáp, ghi chú, đặt hàng, ghi danh — không thêm bảng, không ghi gì mỗi request. Khóa học hot = nhiều ghi danh mới nhất trong kỳ, rồi doanh thu.
  - **Danh mục** (`/admin/categories`, trang `/quan-tri/danh-muc`): 2 cấp kiểm ở mọi lần ghi, không trùng tên cùng cấp, slug sinh một lần và giữ khi đổi tên, sắp xếp gửi cả một cấp, chỉ xóa được danh mục không còn con và không còn dòng `courses` nào (kể cả khóa đã xóa mềm).
  - **Mã giảm giá toàn sàn** (`services/admin_coupons.py`, `/admin/coupons`, trang `/quan-tri/ma-giam-gia`): mã không bao giờ đổi, còn lại sửa được mà đơn cũ giữ nguyên số; giới hạn lượt không hạ dưới số đã dùng; kết thúc sớm = `valid_to = now`; mã đã dùng không xóa được. Trạng thái tính lúc đọc.
  - **Banner** (migration `5b10213a072e`, `services/banners.py`, `GET /banners` công khai, `/admin/banners`, trang `/quan-tri/banner`, carousel trang chủ): đang hiện tính lúc đọc (bật + trong khung giờ, tối đa 5); ảnh tải thẳng lên bucket dưới `banners/`, ảnh cũ bị dọn khi thay/xóa; link chỉ nhận `/…` hoặc `http(s)://`. Mục cắt giảm số 4 nhưng vẫn làm vì dự án đi trước lịch. Dữ liệu demo: `python -m scripts.seed_banners`.
  - **Đã chạy thật** bằng một admin dùng một lần (đã xóa): dashboard 30 ngày ra 7.683.800 ₫ / DAU TB 7,2 / 79 người hoạt động; thêm–thêm con–đổi thứ tự–bị chặn xóa–xóa danh mục; tạo–kết thúc–xóa mã; tải ảnh banner qua ô chọn tệp → PUT lên MinIO → tắt/đưa lên/xóa (ảnh cũ 404); 5 trang không cuộn ngang ở 375px. Bằng chứng: `docs/report/assets/phase-5/admin-dashboard.txt`.
  - Test: 7 + 10 + 15 + 17 test mới, `test_models.py` thêm đặc tả bảng `banners`.

## Gate cuối phase

- [ ] Demo end-to-end: thêm giỏ hàng → áp coupon → VNPay sandbox → thanh toán → vào học ngay
- [ ] Học viên hoàn thành khóa → nhận chứng chỉ PDF, quét QR verify được
- [ ] Admin duyệt khóa học mới trước khi hiện công khai
- [ ] Thu bằng chứng vào `docs/report/assets/phase-5/`: screenshot luồng thanh toán VNPay end-to-end, log IPN (đã che dữ liệu nhạy cảm), chứng chỉ PDF mẫu + trang verify, dashboard instructor và admin
