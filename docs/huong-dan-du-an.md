# Hướng dẫn dự án DevPath — vận hành, cấu trúc, và cách sửa

Tài liệu này dành cho người phải **giải thích và sửa được** hệ thống này tại chỗ. Mỗi đường dẫn file đều kèm số dòng đã kiểm chứng tại thời điểm viết; nếu bạn sửa code thì số dòng lệch đi, nhưng tên hàm và tên hằng thì vẫn tìm được bằng `Ctrl+Shift+F`.

---

## 0. Kiểm tra trước khi có người xem

Làm theo thứ tự này, đừng bỏ bước nào:

- [ ] **Docker chạy được.** Khởi động bằng `start-docker.ps1`, không bấm icon — xem mục 3.2, đây là rủi ro lớn nhất.
- [ ] **Stack lên đủ.** `docker compose -f infra/docker-compose.yml up -d` rồi mở http://localhost:3000.
- [ ] **Có dữ liệu.** Trang `/khoa-hoc` phải hiện 4 khóa học. Chưa có thì chạy seed (mục 3.5).
- [ ] **Đăng nhập được** bằng tài khoản seed, vào được một khóa học, video chạy.
- [ ] **Sửa thử một chỗ** theo mục 5 rồi hoàn tác (`git checkout -- <file>`), để chắc chắn hot reload hoạt động trên máy bạn.
- [ ] **Biết mình đang ở đâu trong kế hoạch:** đọc lại `docs/plan/phase-2-core-platform.md`, các checkbox là trạng thái thật.

---

## 1. Hệ thống này là gì

Nền tảng học lập trình trực tuyến kiểu Udemy. Ba điểm nhấn kỹ thuật của khóa luận là **chấm code tự động trong sandbox Docker**, **hệ gợi ý khóa học**, và **chatbot RAG trợ giảng** — cả ba nằm ở Phase 3–4, chưa làm. Phần đã chạy được hiện nay là nền tảng: tài khoản, khóa học, học và theo dõi tiến độ.

Đã hoàn thành (Phase 1 và gần hết Phase 2):

| Nhóm | Nội dung |
|---|---|
| Tài khoản | Đăng ký/đăng nhập email + mật khẩu, đăng nhập Google, 3 vai trò `student`/`instructor`/`admin`, hồ sơ, đổi mật khẩu, ảnh đại diện |
| Khóa học | CRUD, trình dựng mục lục kéo-thả, upload video lên R2 + worker chuyển mã HLS, trang chi tiết công khai có SEO |
| Học viên | Tìm kiếm toàn văn tiếng Việt, lọc, ghi danh khóa miễn phí, trình phát HLS nhớ vị trí, ghi chú theo mốc thời gian, đánh dấu bài, đánh giá & xếp hạng |
| Hạ tầng | Docker Compose cho máy dev và cho VPS, nginx + HTTPS, CI 4 job |

Chưa làm: chấm code, quiz, AI, thanh toán, gamification, trang quản trị.

---

## 2. Bản đồ repo

```
E-learning/
├── backend/          FastAPI + Celery worker
│   ├── app/
│   │   ├── api/v1/       Router — khai báo endpoint, KHÔNG chứa logic nghiệp vụ
│   │   ├── services/     Logic nghiệp vụ, ranh giới transaction
│   │   ├── models/       Bảng SQLAlchemy
│   │   ├── schemas/      Pydantic — hình dạng dữ liệu vào/ra
│   │   ├── core/         Cấu hình, kết nối DB, bảo mật, dependency dùng chung
│   │   └── workers/      Tác vụ Celery (chuyển mã video)
│   ├── alembic/versions/ Migration — mọi thay đổi schema đều đi qua đây
│   ├── scripts/          seed.py, seed_courses.py
│   └── tests/            pytest
├── frontend/         Next.js App Router
│   ├── app/              Route. Thư mục trong ngoặc là "route group", không xuất hiện trên URL
│   │   ├── (marketing)/  Trang công khai: chủ, danh sách, chi tiết khóa học
│   │   ├── (auth)/       Đăng nhập, đăng ký
│   │   ├── (learn)/      Màn hình học: player, ghi chú
│   │   └── (dashboard)/  Khu giảng viên
│   ├── components/       Component theo miền + components/ui là shadcn
│   └── lib/api/          Gọi backend, mỗi domain một file
├── infra/            Docker Compose, nginx, script deploy
├── docs/             Thiết kế + kế hoạch 14 tuần
└── grader/           Sandbox chấm bài — Phase 3, hiện còn trống
```

**Quy tắc phân lớp backend, hỏi là phải trả lời được:** router → service → model. Router nhận request, gọi service, trả response. Service quyết định *chuyện gì xảy ra* và ném lỗi nghiệp vụ. Model chỉ mô tả bảng.

Lý do: chỉ tầng service đáng kiểm thử, và nó là tầng duy nhất không cần biết HTTP. Logic nằm trong router thì muốn test phải dựng request giả; nằm trong service thì chỉ cần gọi một hàm Python với một session. Xem [`backend/app/services/reviews.py`](../backend/app/services/reviews.py) làm ví dụ mẫu.

---

## 3. Khởi chạy

### 3.1 Cách chính — Docker

```bash
cp infra/.env.example infra/.env
```

```bash
docker compose -f infra/docker-compose.yml up -d
```

Lần đầu mất vài phút để build. Sau đó:

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:3000 | Giao diện |
| http://localhost:8000/docs | Tài liệu API tự sinh (Swagger) — **mở cái này cho giáo viên xem, nó gây ấn tượng tốt** |
| localhost:5432 | Postgres |

### 3.2 Máy dev này: chạy Docker bằng script, đừng bấm icon

Máy này có một lỗi ở tầng hệ thống file Windows: **file socket AF_UNIX Docker tạo ra thì sau đó không xóa được nữa** (lỗi 1920). Mỗi lần máy ngủ, Docker bị giết và để lại socket; lần bật sau nó phải xóa socket cũ trước khi bind lại, xóa không được nên backend crash ngay.

Vì vậy hãy khởi động Docker bằng:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Admin\start-docker.ps1
```

Script dọn socket cũ rồi mới bật Docker và chờ daemon sẵn sàng. **Sau mỗi lần máy ngủ hoặc khởi động lại đều phải chạy nó** — bấm icon Docker Desktop sẽ ra màn hình lỗi đỏ.

Chữa tận gốc cần quyền Administrator và một lần khởi động lại: mở PowerShell as administrator, chạy `chkdsk C: /f`, gõ `Y` để hẹn lịch, rồi khởi động lại máy và để nó chạy xong. **Nên làm việc này trước ngày bảo vệ**, đừng để phụ thuộc vào script.

### 3.3 Không có Docker thì sao

Đường vòng nếu Docker vẫn không lên: cài PostgreSQL 16 trực tiếp lên Windows kèm extension `pgvector` (migration đầu tiên tạo `vector`, `unaccent`, `pg_trgm`; hai cái sau có sẵn trong bản cài chuẩn). Tạo database `devpath`, user `devpath`, mật khẩu `devpath`, rồi chạy backend và frontend trực tiếp:

```bash
cd backend && .venv\Scripts\python.exe -m alembic upgrade head
```

```bash
cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```bash
cd frontend && npm run dev
```

Redis chỉ cần cho Celery (chuyển mã video). Không có Redis thì mọi thứ khác vẫn chạy, chỉ upload video mới hỏng.

### 3.4 Chạy test

```bash
cd backend && .venv\Scripts\python.exe -m pytest -q
```

Với stack đang chạy, kết quả là **471 passed, 2 skipped**. Không có Postgres thì các test chạm database sẽ **skip** chứ không fail — đó là chủ ý, xem `backend/tests/conftest.py`. Trên CI thì ngược lại: không kết nối được là fail, để một service container hỏng không bao giờ hiện ra thành build xanh.

### 3.5 Nạp dữ liệu mẫu

```bash
cd backend && .venv\Scripts\python.exe -m scripts.seed
```

Chạy lại bao nhiêu lần cũng được, lần thứ hai trở đi không tạo thêm gì. Tài khoản tạo ra:

| Email | Mật khẩu | Vai trò |
|---|---|---|
| `admin@devpath.local` | `devpath-admin` | admin |
| `khoa.tran@devpath.local` | `devpath-instructor` | instructor |
| `mai.anh@devpath.local` | `devpath-instructor` | instructor |

Học viên thì tự đăng ký một tài khoản mới khi demo — nó cũng chính là màn trình diễn luồng đăng ký.

---

## 4. Một request đi qua những đâu

Đây là câu hỏi hay bị hỏi nhất. Lấy ví dụ **bấm "Đăng ký học miễn phí"**:

```
Trình duyệt
  └─ EnrollButton (Client Component)         frontend/components/courses/enroll-button.tsx
       └─ enrolInCourse()                     frontend/lib/api/enrollments.ts
            └─ apiFetch() gắn JWT vào header  frontend/lib/api/client.ts
                 │  POST /api/v1/courses/{id}/enroll
                 ▼
FastAPI
  └─ router enrol_in_course()                 backend/app/api/v1/enrollments.py:28
       └─ enrollments_service.enrol_free()    backend/app/services/enrollments.py
            ├─ kiểm tra khóa học published, không phải khóa của chính mình, giá = 0
            ├─ INSERT ... ON CONFLICT DO NOTHING vào bảng enrollments
            ├─ UPDATE courses SET students_count = students_count + 1
            └─ commit
                 │  201 (lần đầu) hoặc 200 (đã ghi danh rồi)
                 ▼
TanStack Query cập nhật cache → nút đổi thành "Vào học"
```

Ba chi tiết trong luồng này đáng nhớ vì chúng là **quyết định thiết kế**, không phải ngẫu nhiên:

1. **`ON CONFLICT DO NOTHING` thay vì "kiểm tra rồi mới ghi".** Hai cú bấm đến cùng lúc sẽ cùng vượt qua bước kiểm tra, rồi một cú chết vì ràng buộc unique. Để database quyết định thì cú thua đơn giản là không ghi gì.
2. **`students_count = students_count + 1` chứ không đọc-sửa-ghi trong Python.** Đọc-sửa-ghi làm mất một lượt khi hai người ghi danh cùng lúc.
3. **201 lần đầu, 200 lần sau.** Ghi danh hai lần là cùng một sự thật, không phải lỗi.

### Hai URL backend, và vì sao

Frontend gọi backend bằng **hai địa chỉ khác nhau**: Server Component gọi `http://backend:8000` (tên service trong mạng Docker), còn trình duyệt gọi `http://localhost:8000`. Trình duyệt không phân giải được tên `backend`. Hai biến `API_BASE_URL_INTERNAL` và `NEXT_PUBLIC_API_BASE_URL` tách đúng hai phía đó; [`frontend/lib/api/client.ts`](../frontend/lib/api/client.ts) chọn theo `typeof window`.

Trên VPS thì gộp làm một: nginx định tuyến `/api` về backend nên trình duyệt gọi cùng domain với trang.

---

## 5. Bài tập sửa tại chỗ

Làm hết 5 bài này một lượt trước ngày bảo vệ. Mỗi bài: sửa → xem kết quả → **hoàn tác bằng `git checkout -- <file>`**. Mục tiêu không phải nhớ vị trí, mà là biết *cách tìm* vị trí.

> **Mẹo tìm nhanh:** thấy chữ gì trên màn hình thì `Ctrl+Shift+F` trong VS Code, gõ đúng chữ đó. Gần như luôn ra ngay file cần sửa. Đây cũng là câu trả lời trung thực nếu giáo viên hỏi "làm sao em tìm được chỗ đó".

### Bài 1 — Đổi chữ trên trang chủ (dễ nhất)

**File:** [`frontend/app/(marketing)/page.tsx:11`](../frontend/app/(marketing)/page.tsx)

```tsx
<h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
  Học lập trình bằng cách viết code     ← sửa dòng này
</h1>
```

Lưu file, trang tự nạp lại. **Vì sao nhanh vậy:** Next.js chạy dev server có hot reload, sửa file là trình duyệt cập nhật mà không mất trạng thái.

### Bài 2 — Đổi màu chủ đạo

**File:** [`frontend/app/globals.css:58`](../frontend/app/globals.css)

```css
:root {
  --primary: oklch(0.205 0 0);   ← dòng 58, màu nút chính (đang là đen)
}
```

Đổi thành `oklch(0.55 0.2 260)` sẽ ra màu xanh dương. Nút "Đăng ký", "Đăng ký học miễn phí" đổi màu theo ngay.

**Điều phải hiểu để trả lời tiếp:**

- Đây là **design token**, không phải màu của một nút cụ thể. Toàn bộ giao diện tham chiếu tới `--primary` chứ không viết mã màu trực tiếp, nên đổi một chỗ là đổi cả hệ thống. Đó là điểm mạnh, nói ra được thì rất tốt.
- Dòng 93 là `--primary` trong khối `.dark` — **giao diện tối dùng giá trị riêng**. Đổi mỗi dòng 58 thì chế độ tối không đổi.
- `oklch(L C H)` = độ sáng / độ bão hòa / góc màu. Dùng thay `#rrggbb` vì đổi độ sáng không làm lệch tông màu. Nếu thấy khó nhớ, cứ nói thật: "đây là hệ màu shadcn/ui dùng mặc định".

### Bài 3 — Đổi nhãn hiển thị

**File:** [`frontend/lib/courses/labels.ts:5`](../frontend/lib/courses/labels.ts)

```ts
export const LEVEL_LABELS: Record<CourseLevel, string> = {
  beginner: "Người mới bắt đầu",   ← đổi thành "Nhập môn"
  intermediate: "Trung cấp",
  advanced: "Nâng cao",
};
```

Đổi một chỗ, nhãn đổi ở **cả** thẻ khóa học, trang chi tiết và form của giảng viên.

**Điểm cần nêu:** trong database lưu `beginner`, không lưu "Người mới bắt đầu". Chuỗi tiếng Việt chỉ là cách hiển thị. Nhờ vậy đổi chữ không cần migration, và sau này làm đa ngôn ngữ chỉ phải thay bảng ánh xạ này.

### Bài 4 — Đổi số khóa học mỗi trang

**File:** [`frontend/app/(marketing)/khoa-hoc/page.tsx:26`](../frontend/app/(marketing)/khoa-hoc/page.tsx)

```ts
const PAGE_SIZE = 12;   ← đổi thành 2 để thấy rõ phân trang
```

Với 4 khóa học seed, để `2` sẽ thấy 2 trang.

**Câu hỏi bẫy hay đi kèm:** *"Backend có kiểm soát số này không?"* Có. Backend nhận `page_size` từ query string, mặc định 20 và **chặn trên ở 100** ([`backend/app/schemas/pagination.py`](../backend/app/schemas/pagination.py), dùng ở [`backend/app/api/v1/courses.py:57`](../backend/app/api/v1/courses.py)). Frontend xin 12 nên mặc định 20 không có tác dụng, nhưng frontend **không thể** xin 1000 — server từ chối với lỗi 422. Nguyên tắc: kiểm tra ở client là để người dùng biết ngay, kiểm tra ở server mới là để bảo vệ hệ thống.

### Bài 5 — Đổi giới hạn ở backend (chạm cả ba lớp)

**File:** [`backend/app/models/study.py:31`](../backend/app/models/study.py)

```python
NOTE_MAX_LENGTH = 2000   ← đổi thành 100
```

Vào một bài học, mở tab ghi chú, gõ hơn 100 ký tự rồi lưu → API trả lỗi 422, giao diện hiện "Thông tin chưa hợp lệ".

**Đây là bài quan trọng nhất**, vì nó cho thấy bạn hiểu hệ thống chứ không chỉ nhớ vị trí file:

- Hằng số nằm ở tầng **model**, được tầng **schema** dùng lại ([`backend/app/schemas/study.py:26`](../backend/app/schemas/study.py)). Pydantic mới là chỗ thực sự chặn.
- Backend đổi rồi nhưng ô nhập ở frontend **vẫn cho gõ 2000 ký tự**, vì con số đó đang viết cứng ở [`frontend/components/learn/notes-panel.tsx:105`](../frontend/components/learn/notes-panel.tsx). Muốn khớp thì phải sửa cả hai bên.
- Nếu bị hỏi "vì sao lại có hai chỗ": trả lời thẳng rằng đây là **giới hạn bị lặp giữa hai ngôn ngữ**, hiện đồng bộ thủ công, và cách dọn là sinh type TypeScript từ OpenAPI schema của FastAPI. Nhận ra một điểm yếu trong hệ thống của mình luôn ghi điểm cao hơn là giả vờ không có.

### Bài 6 — Đọc, không sửa: lần theo một lỗi

Giáo viên hỏi *"nếu học viên báo không đánh giá được khóa học thì em tìm ở đâu?"*. Đường đi:

1. Mở DevTools → tab Network → xem request `PUT /api/v1/courses/{id}/reviews/me` trả về gì.
2. Mã lỗi nằm trong body theo dạng `{"detail": {"code": "NOT_ENROLLED", ...}}`.
3. Tìm `NOT_ENROLLED` trong repo → ra [`backend/app/services/reviews.py`](../backend/app/services/reviews.py), thấy ngay điều kiện: phải ghi danh rồi mới được đánh giá.
4. Câu tiếng Việt hiển thị cho người dùng nằm ở [`frontend/lib/api/error-messages.ts`](../frontend/lib/api/error-messages.ts), tra theo `code`.

**Điểm thiết kế đáng nêu:** frontend luôn bắt theo `code`, **không bao giờ** đọc `message`. Đổi câu chữ thông báo không được phép làm hỏng logic.

---

## 6. Những câu hay bị hỏi, và câu trả lời nằm ở đâu trong code

### "Mật khẩu lưu thế nào?"

Băm bằng **bcrypt**, không bao giờ lưu bản rõ — `backend/app/core/security.py`. Bcrypt có tự sinh salt và cố tình chạy chậm, để dò từng mật khẩu một tốn thời gian.

### "Đăng nhập hoạt động ra sao?"

Hai token. **Access token** sống 15 phút, gửi kèm mỗi request trong header `Authorization`. **Refresh token** sống 30 ngày, nằm trong cookie `HttpOnly` nên JavaScript không đọc được.

Vì sao tách đôi: access token không thu hồi được (server chỉ kiểm chữ ký, không tra database), nên phải cho nó sống ngắn. Refresh token thì thu hồi được vì có hẳn bảng `refresh_tokens` — và hệ thống **xoay vòng** nó: mỗi lần làm mới sinh token mới, token cũ bị vô hiệu. Dùng lại token cũ bị coi là dấu hiệu bị đánh cắp và cả chuỗi bị thu hồi.

### "Điểm đánh giá trung bình tính lúc nào?"

Trong **cùng transaction** với thao tác ghi đánh giá — [`backend/app/services/reviews.py`](../backend/app/services/reviews.py). Hai chi tiết đáng nói:

- **Tính lại toàn bộ, không cộng dồn.** `students_count` cộng `+1` được vì ghi danh chỉ đi một chiều; còn điểm trung bình đổi cả hai chiều khi người dùng sửa hoặc xóa đánh giá, nên phải chạy lại `AVG` trên toàn bộ đánh giá của khóa đó.
- **Khóa dòng `courses` trước khi tính** (`SELECT ... FOR UPDATE`). Hai người đánh giá cùng lúc mà không khóa thì mỗi người tính trung bình trên một ảnh chụp chưa thấy dòng của người kia, và lượt ghi sau xóa lượt ghi trước khỏi tổng.

Đây là loại chi tiết mà hội đồng thích, vì nó cho thấy có nghĩ về đồng thời.

### "Tìm kiếm tiếng Việt làm sao?"

PostgreSQL full-text search với cột `tsvector` được một **trigger** cập nhật mỗi khi tiêu đề/mô tả đổi. Cấu hình là `to_tsvector('simple', unaccent(...))`:

- `simple` chứ không phải `english`, vì bộ stemming tiếng Anh sẽ cắt sai từ tiếng Việt.
- `unaccent` để gõ "lap trinh" vẫn ra "Lập trình".
- Phía truy vấn **bắt buộc dùng đúng cặp đó**, lệch một bên là không bao giờ khớp.

Dùng trigger thay vì generated column vì `unaccent()` là hàm STABLE chứ không IMMUTABLE, Postgres từ chối nó trong generated column. Chi tiết ở `docs/database-design.md` mục 11.

### "Video lưu ở đâu?"

Object storage **Cloudflare R2**. Trình duyệt xin backend một **presigned URL** rồi tải file thẳng lên R2 — không đi qua server ứng dụng. Sau đó một tác vụ **Celery** chuyển mã sang HLS bằng ffmpeg.

Vì sao không cho file đi qua backend: một video vài trăm MB sẽ chiếm giữ worker của API suốt thời gian tải lên. Đó cũng là lý do nginx trên VPS chỉ cần `client_max_body_size 2m`.

*Lưu ý trung thực:* các khóa học seed **không** phải video tự upload — chúng trỏ vào một luồng HLS mẫu công khai, đặt qua biến `SEED_SAMPLE_HLS_URL`, để dữ liệu mẫu chạy được trên máy chưa cấu hình R2. Luồng upload thật thì demo bằng cách tự tải một video lên qua khu giảng viên.

### "Vì sao chọn Next.js chứ không phải React thuần?"

Vì trang chi tiết khóa học cần **SEO**. Với React thuần, máy tìm kiếm nhận về một trang HTML rỗng rồi mới chạy JavaScript. Next.js kết xuất phía server nên toàn bộ tiêu đề, mô tả và danh sách bài học nằm sẵn trong phản hồi đầu tiên.

Đi kèm là một chi tiết trong [`frontend/app/(marketing)/khoa-hoc/[slug]/page.tsx`](<../frontend/app/(marketing)/khoa-hoc/[slug]/page.tsx>): trang **cố tình không có** `loading.tsx`. Suspense sẽ bắt đầu stream phản hồi, mà một khi header đã gửi đi thì mã trạng thái bị chốt ở 200 — khóa học không tồn tại sẽ trả 200 kèm thẻ `noindex` thay vì 404 thật.

### "Test có bao nhiêu, chạy thế nào?"

Hơn 470 test pytest cho backend, chạy trên CI cùng với ruff (linter), migration lên–xuống–lên, seed chạy hai lần để chứng minh idempotent, và một job dựng thử image production. Test chạm database chạy trong một **transaction luôn được rollback**, nên mỗi test bắt đầu từ cùng một trạng thái và không để lại gì.

### "Deploy ra sao?"

Docker Compose trên VPS, nginx làm reverse proxy và kết thúc TLS, chứng chỉ Let's Encrypt tự gia hạn. File `infra/docker-compose.prod.yml` tách riêng khỏi file dev — vì override chỉ **thêm** được vào danh sách chứ không bỏ bớt, mà hai thứ bắt buộc phải biến mất trên production lại là cổng database publish ra ngoài và bind mount mã nguồn.

**Trạng thái thật:** cấu hình deploy đã viết và đã được CI kiểm chứng, nhưng **chưa deploy lên máy chủ thật** vì chưa có VPS và tên miền. Nói đúng như vậy — checkbox trong `docs/plan/phase-2-core-platform.md` cũng đang để trống đúng như thế.

---

## 7. Chỗ dễ vấp khi demo

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Trang trắng, console báo `Failed to fetch` | Backend chưa chạy. Kiểm tra http://localhost:8000/api/v1/health |
| Đăng nhập xong F5 là mất phiên | Đang mở bằng `127.0.0.1` thay vì `localhost`. Trình duyệt coi đây là **hai site khác nhau**, mà cookie refresh đặt `SameSite=lax` nên bị bỏ im lặng |
| `/khoa-hoc` trống trơn | Chưa chạy seed |
| Sửa file frontend mà trang không đổi | Container frontend trong Docker **không** hot reload trên Windows. Sửa nhiều thì chạy `npm run dev` trực tiếp trên host, xem `infra/README.md` |
| Video không phát | Chưa cấu hình R2, hoặc mất mạng — luồng HLS mẫu nằm trên Internet |
| Nút "Mua khóa học" bị mờ | Đúng thiết kế. Thanh toán là Phase 5; hiện chỉ ghi danh được khóa miễn phí |

**Nếu bị hỏi câu không trả lời được:** nói "chỗ này em phải mở code xem lại" rồi mở ra tìm thật. Điều đó bình thường và chuyên nghiệp hơn nhiều so với đoán bừa — không ai thuộc lòng toàn bộ một hệ thống, và việc tìm được câu trả lời trong repo của mình chính là thứ đang được đánh giá.

---

## 8. Đọc thêm theo thứ tự ưu tiên

1. [`docs/plan/phase-2-core-platform.md`](plan/phase-2-core-platform.md) — trạng thái thật của dự án
2. [`docs/database-design.md`](database-design.md) — mọi bảng, ràng buộc, và lý do
3. [`docs/architecture.md`](architecture.md) — sơ đồ tổng thể
4. [`backend/README.md`](../backend/README.md) và [`infra/README.md`](../infra/README.md) — chi tiết vận hành từng phần
