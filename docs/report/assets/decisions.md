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

**CI có job migration riêng** — test backend không chạm database nên hai job lint/test không thể fail vì migration hỏng. Job thứ ba chạy upgrade → downgrade → upgrade → `alembic check` → seed hai lần, trên database trắng không có init script.
