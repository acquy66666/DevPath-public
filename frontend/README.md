# Frontend — Next.js

Giao diện web: trang public (SSR cho SEO), trải nghiệm học, dashboard giảng viên và admin.

Next.js 16 (App Router) · React 19 · TypeScript · Tailwind v4 · shadcn/ui (preset `radix-nova`, icon Lucide) · TanStack Query · dnd-kit (kéo-thả mục lục).

## Chạy local

```bash
npm install
```

```bash
npm run dev
```

Mở `http://localhost:3000`. Trang chủ hiển thị thẻ trạng thái backend — muốn thấy "Hoạt động" thì chạy backend trước (xem [backend/README.md](../backend/README.md)), nếu không nó hiện "Không kết nối được" mà trang vẫn sống.

Địa chỉ backend đọc từ `NEXT_PUBLIC_API_BASE_URL`, mặc định `http://localhost:8000` — copy [.env.example](.env.example) thành `.env.local` nếu cần đổi. Phải là `localhost` chứ không phải `127.0.0.1`: trình duyệt coi hai tên đó là hai site khác nhau, mà cookie refresh đặt `SameSite=lax` nên sẽ bị bỏ im lặng — biểu hiện là đăng nhập xong F5 phát là mất phiên.

Kiểm tra trước khi commit:

```bash
npm run lint
```

```bash
npm run build
```

## Auth (Phase 2)

| Đường dẫn | Nội dung |
|---|---|
| `/dang-ky` | Form tạo tài khoản (họ tên, email, mật khẩu) |
| `/dang-nhap` | Form đăng nhập; đọc `?loi=<CODE>` do callback Google chuyển về |
| `/tro-thanh-giang-vien` | Tự nâng cấp tài khoản lên giảng viên |
| `/ho-so` | Hồ sơ: sửa họ tên, đổi mật khẩu |

- `lib/api/auth.ts` — client typed khớp `backend/app/schemas/auth.py`.
- `lib/auth/auth-provider.tsx` — `AuthProvider` + hook `useAuth()`: `user`, `accessToken`, `status`, `signIn`, `signUp`, `signOut`, `refreshSession`. Đổi vai trò xong thì gọi `refreshSession()` chứ không vá state tại chỗ — giao diện không bao giờ được nói khác hàng trong DB.
- `lib/auth/validation.ts` — bản sao quy tắc validate của backend (mật khẩu ≥ 8 ký tự và ≤ 72 **byte**), chỉ để báo lỗi ngay cạnh ô nhập; backend vẫn là nơi quyết định.
- `lib/api/error-messages.ts` — ánh xạ `code` của backend sang câu tiếng Việt cho **toàn** ứng dụng (auth, hồ sơ, khóa học, mục lục). Không bao giờ switch theo `message`.
- `components/auth/google-button.tsx` — link thường (không phải `fetch`: OAuth là điều hướng cả trang), chỉ hiện khi `NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED=true` để không mời người dùng bấm vào thứ chắc chắn lỗi 503.

**Access token nằm trong bộ nhớ, không ở `localStorage` cũng không ở cookie JS đọc được.** Refresh token là cookie `HttpOnly` của backend, nên F5 xong `AuthProvider` gọi `/auth/refresh` để dựng lại phiên — đó là lúc header hiện ô xám chờ (`status === "loading"`). Đánh đổi: `middleware.ts` của Next không đọc được cookie đó nên guard route phải làm ở client. Trang học (`/hoc/...`) và các trang cần đăng nhập đều chặn ở client: chưa đăng nhập thì hiện lời mời kèm `?next=` quay lại đúng trang, ví dụ trong `components/learn/learn-view.tsx`. Chốt chặn thật vẫn là backend (401/403).

**Cạm bẫy đã gặp: refresh gọi hai lần là mất phiên.** Backend xoay vòng refresh token và coi token đã thu hồi quay lại là bị đánh cắp (thu hồi sạch phiên). React StrictMode chạy effect hai lượt trong dev ⇒ hai request refresh song song ⇒ tự đăng xuất chính mình. `lib/api/auth.ts` vì thế gom mọi lời gọi refresh đang bay vào **một** promise duy nhất. Hệ quả còn lại: mở hai tab cùng lúc sau khi để lâu vẫn có thể chạm vào tình huống này. Việc thêm khoảng ân hạn (leeway) phía backend đã được ghi thành checkbox của [Phase 6](../docs/plan/phase-6-hardening-deploy.md).

## Khu vực giảng viên (Phase 2)

| Đường dẫn | Nội dung |
|---|---|
| `/giang-day` | Danh sách khóa học của giảng viên, có phân trang |
| `/giang-day/moi` | Tạo khóa học: chỉ tên + danh mục, xong là vào thẳng trình soạn |
| `/giang-day/[courseId]` | Mục lục (kéo-thả), thông tin khóa học, trạng thái/xuất bản/xóa |

- `components/instructor/instructor-gate.tsx` chặn ở client cho gọn mắt, **không phải để bảo vệ**: quyền thật nằm ở `require_role("instructor")` trên từng endpoint. Cổng này loại cả tài khoản admin — `require_role` khớp chính xác nên admin vào đây sẽ ăn 403 ở mọi request.
- `components/curriculum/` — trình soạn mục lục. `lib/curriculum/tree.ts` giữ toàn bộ phép biến đổi cây dưới dạng hàm thuần, nhờ vậy các handler kéo-thả đủ ngắn để đọc.

**Kéo-thả gửi cả danh sách, không gửi lệnh di chuyển.** Thả xong, client biết thứ tự cuối cùng nên gửi nguyên trạng thái đó (`PUT .../order`). Kéo bài học sang chương khác cũng dùng đúng endpoint của chương đích — backend nhận nuôi bài đó và đánh số lại chương cũ, nên **một** request là đủ và không có khoảnh khắc nào bài học thuộc về hai chương.

**Tải video lên đi thẳng từ trình duyệt tới bucket.** `components/curriculum/video-upload.tsx` xin URL đã ký từ backend, rồi `PUT` file lên R2 **không kèm cookie, không kèm token** — chữ ký trong URL là toàn bộ quyền, và gửi thông tin đăng nhập sang origin khác là cách làm rò rỉ chúng. Dùng `XMLHttpRequest` chứ không phải `fetch` vì tới giờ `fetch` vẫn không báo được tiến độ upload, mà một file 400 MB không có thanh tiến độ trông y hệt trang bị treo.

Sau khi tải xong, màn hình hỏi lại trạng thái mỗi 4 giây trong lúc `processing`. TanStack Query **tạm dừng hỏi khi tab bị ẩn** và hỏi lại ngay lúc tab được focus — đúng thứ ta muốn: giảng viên chuyển tab đi làm việc khác trong lúc chờ chuyển mã, quay lại là thấy kết quả, không có ai hỏi vòng vo suốt mấy phút vào một tab không ai nhìn.

**Bàn phím dùng được:** chọn tay nắm → phím cách → phím mũi tên → phím cách để thả, kèm thông báo tiếng Việt cho screen reader (dnd-kit chỉ có sẵn tiếng Anh và đọc ra UUID). Trong lúc kéo *chương*, mọi bài học bị tắt vai trò điểm thả (`disabled: { droppable: true }`) — nếu không, mũi tên xuống sẽ dừng ở từng bài học nằm trong chính chương đang kéo.

**Cạm bẫy dnd-kit:** khi trang còn cuộn được và đích đến nằm dưới điểm giữa màn hình, mũi tên **cuộn trang** trước rồi mới di chuyển phần tử — đó là hành vi có sẵn của `KeyboardSensor`, không phải lỗi. Test tự động vì thế phải đặt viewport đủ cao để trang hết cuộn.

## Soạn bài tập code (Phase 3)

Nằm trong chính trình soạn mục lục: thêm bài học loại **Bài tập code** rồi bấm sửa. `components/exercise/` lo phần còn lại — đề bài Markdown, code mở đầu, giới hạn thời gian/bộ nhớ, và danh sách test case.

**Bài tập sống ở bảng khác nên nó tự lưu.** Nút “Lưu bài học” ghi tên và cờ học thử; nút “Lưu bài tập” ghi đề bài và giới hạn. Gộp chung một nút sẽ phải ghi hai lần vào hai nhóm bảng trong một thao tác, và nửa chừng hỏng thì không có trạng thái nào đúng để quay về.

**404 là câu trả lời, không phải lỗi.** Bài học vừa tạo thì `GET /lessons/{id}/code-exercise` trả 404 — đó là trạng thái rỗng, nên query tắt retry cho riêng mã này và render form tạo thay vì banner đỏ.

**Hai giá trị mặc định được chọn theo hướng an toàn:** test case mặc định **ẩn**, và ô đó tự về ẩn sau mỗi lần thêm. Quên nó một lần là đáp án nằm trên trang học viên.

**Giao diện cảnh báo ba trạng thái mà API vẫn cho phép:** không có test case (bài nộp sẽ bị từ chối — `EXERCISE_NOT_READY`), toàn case ẩn (học viên không có gì để thử), toàn case hiện (in đáp án mẫu là qua bài). Cả ba đều hợp lệ với cơ sở dữ liệu và đều sai về mặt sư phạm.

**Thứ tự test case là dữ liệu, không phải trang trí** — “test case 3 sai” trỏ đúng dòng thứ ba. Nút lên/xuống gửi cả danh sách (`PUT .../test-cases/order`), cùng cách kéo-thả mục lục gửi.

Đáp án của case ẩn **không bao giờ xuống trình duyệt học viên**: backend trả hai model khác nhau tùy người gọi, và model của học viên không có trường nào để chứa đáp án. `lib/api/grading.ts` vì thế chỉ khai kiểu của giảng viên. Trang nộp bài có kiểu riêng ở `lib/api/submissions.ts`, không dùng lại kiểu của giảng viên.

### Trang nộp bài

`components/exercise/exercise-workspace.tsx` — đề bài, editor, hai nút, kết quả, lịch sử. Nằm trong nhánh `code_exercise` của [learn-view.tsx](components/learn/learn-view.tsx), có `key={lesson.id}` để chuyển bài là đổi editor chứ không mang code bài cũ sang.

**Monaco tự phục vụ, không qua CDN.** `@monaco-editor/react` mặc định tải editor từ jsdelivr — trang quan trọng nhất của đồ án sẽ phụ thuộc mạng của căn phòng, đúng hôm bảo vệ. `scripts/copy-monaco.mjs` chép bản dựng AMD của package vào `public/monaco` (đã .gitignore, 24 MB), và `loader.config({ paths: { vs: "/monaco/vs" } })` trỏ vào đó. Chạy ở `predev`/`prebuild` chứ không phải `postinstall`: image Docker cài dependency ở một layer chỉ có lockfile, nên postinstall sẽ đi tìm một file chưa tồn tại.

Chép chứ không bundle vì bản ESM của Monaco cần plugin webpack, mà dự án build bằng Turbopack. Bản AMD không cần bundler nào cả.

**Editor không chịu điều khiển (`defaultValue`, không phải `value`).** Monaco giữ một tài liệu có con trỏ, vùng chọn và ngăn xếp undo — mỗi phím gõ đã nằm ở đó trước. Cho state React làm nguồn nghĩa là mỗi phím đi một vòng ra rồi về, và mỗi lần render xen giữa là một cơ hội đẩy chữ cũ vào tài liệu đang sống. Chữ ở trong editor, `onChange` báo ra ngoài để nộp và để lưu nháp, đường duy nhất đi ngược vào là handle mệnh lệnh — dùng cho "khôi phục code mẫu" và "đưa code bài nộp cũ vào editor", đúng hai trường hợp mà ghi đè chính là ý định.

**Bản nháp lưu ở `localStorage`** theo từng bài tập (`devpath:code:<exerciseId>`), nên F5 không mất bài đang viết. Mọi lần đọc/ghi đều bọc try/catch: chế độ ẩn danh làm `localStorage` ném lỗi, và mất bản nháp là thiệt hại nhỏ hơn vỡ cả trang.

**Hai nút gọi hai route khác nhau**, xem [backend/README.md](../backend/README.md). Khi bị 429, trang hiện chính câu của server kèm `retry_after` — `ApiError` mang sẵn trường đó vì một 429 không nói bao giờ quay lại chỉ có thể trả lời bằng cách thử lại, tức thêm một request nữa.

**Kết quả đến từ hai nguồn và không gộp làm một.** `event` là tiến độ sống (hoặc snapshot polling — client không phân biệt được), `detail` là kết quả đọc từ REST. Cái đầu nói đang tới đâu, chỉ cái sau mang output từng test — vì kênh realtime không có trường nào để chứa output. Ô input/mong đợi/thực tế chỉ vẽ cho test **không ẩn**.

**Đề bài render bằng `react-markdown`**, không bật plugin HTML thô. Đây là chữ một người dùng viết cho người dùng khác đọc: một đề bài chứa `<script>` sẽ hiện ra đúng những ký tự đã gõ.

### Xem bài đang được chấm

`lib/api/submissions.ts` là kiểu riêng ấy: `SubmissionResult.stdout_trunc` khai là `string | null` vì với case ẩn nó **luôn** null, và một kiểu nói "luôn có" là một giả định sai được viết thành code.

`watchSubmission()` mở WebSocket `/api/v1/submissions/{id}/events` với access token đi trong subprotocol (`["bearer", token]`) — không đi trong query string, vì query string nằm trong log của nginx. Nếu socket không mở được, hoặc đóng trước khi chấm xong, nó **chuyển sang polling** `GET /submissions/{id}` mỗi 2 giây. Ngoại lệ duy nhất là mã đóng 4404: hỏi lại không làm một bài nộp không tồn tại hiện ra.

Cả hai đường phát ra cùng một kiểu `GradingEvent`, nên component chỉ vẽ một thứ và không bao giờ biết dữ liệu đến bằng đường nào. Đó cũng là lý do `SubmissionDetail` mang `total_cases`: thiếu nó, đường polling đếm được số case đã xong nhưng không biết đang tiến tới con số nào.

Hàm trả về một `stop()` — gọi khi component unmount. Nó gỡ `onclose` **trước** khi đóng socket, nếu không thì chính thao tác dọn dẹp sẽ khởi động vòng polling mà nó đang cố dừng.

## Quiz (Phase 4)

- **Giảng viên soạn:** `components/quiz/quiz-editor.tsx` + `question-form.tsx`, nằm trong lesson editor của mục lục cho bài học loại `quiz`. Client ở `lib/api/quiz-authoring.ts`, dùng kiểu của giảng viên (có đáp án đúng).
- **Học viên làm bài:** `components/quiz/quiz-workspace.tsx`, nhánh `quiz` của `learn-view.tsx`. Client ở `lib/api/quiz.ts`, dùng kiểu **không có đáp án** cho tới khi nộp; giải thích chỉ về sau khi chấm.

**Đồng hồ trên trang chỉ là hiển thị hạn chót, không phải hạn chót.** Nó khởi đầu từ `seconds_remaining` do server tính theo đồng hồ của server. Về 0 thì trang tự nộp bài, nhưng quyền quyết định vẫn ở backend: tab bị treo hay bị bóp CPU thì server vẫn từ chối bài nộp trễ quá 10 giây ân hạn. Hết giờ mà chưa nộp là 0 điểm, vì đáp án dở dang không được lưu (lý do ở `docs/report/assets/decisions.md`).

## Cấu trúc

```
app/
├── (marketing)/     Trang public: home, danh sách + chi tiết khóa học (SSR, SEO)
├── (learn)/         Player, quiz, code editor (client-heavy) — Phase 2+
└── (dashboard)/     Khu vực giảng viên: /giang-day (+ admin ở Phase 5)
components/ui/       shadcn/ui (generated, hạn chế sửa tay) + form-field, native-select, textarea
components/layout/   site-header, site-footer
components/instructor/ danh sách khóa học, form tạo/sửa, trạng thái
components/curriculum/ trình soạn mục lục (kéo-thả)
components/exercise/   trình soạn bài tập code + test case (Phase 3)
lib/api/             API client typed, 1 file mỗi domain
lib/curriculum/      biến đổi cây mục lục (hàm thuần)
lib/grading/         giới hạn tài nguyên, chép tay từ model backend
```

## Nguyên tắc

- **Server Component mặc định**; chỉ `"use client"` khi thật sự cần state/effect/event.
- Mọi call API đi qua [lib/api/client.ts](lib/api/client.ts) — không rải `fetch` trong component. Không dùng `app/api/` của Next.js, backend là FastAPI.
- Tailwind + shadcn/ui, không thêm UI library khác.
- Mỗi route segment có `loading.tsx` và `error.tsx`; danh sách rỗng phải có empty state tử tế.

Chi tiết: skill `nextjs-feature` trong `.claude/skills/`.

## Ba cái bẫy của Next.js 16 đã gặp

**Component gọi API phải `await connection()`.** Không có nó, trang bị prerender lúc build và kết quả API bị đóng băng vào HTML tĩnh — trạng thái backend sẽ luôn hiện như lúc chạy `npm run build`. Kết hợp với `<Suspense>` để phần tĩnh của trang vẫn được prerender bình thường.

**Dev server đôi khi phục vụ bundle cũ.** Sửa file, `tsc` sạch, tải lại trang vẫn ra giao diện cũ — đã gặp hai lần, cả hai đều ở container Docker trên Windows, nơi Turbopack phải poll để thấy thay đổi. `touch` không cứu được; `docker compose restart frontend` thì được. Dấu hiệu nhận ra: đọc `outerHTML` của phần vừa sửa thấy đúng cấu trúc cũ, tức không phải lỗi logic mà là mã cũ.

**Không dựng JSX bên trong `try/catch`.** ESLint (`react-hooks/error-boundaries`) chặn, và đúng: lỗi render của component con sẽ bị `catch` nuốt nhầm. Await trong `try`, gán kết quả ra biến, rồi mới render bên ngoài.

`AGENTS.md` và `CLAUDE.md` trong thư mục này do `next dev` tự sinh và tự thêm lại — chúng chỉ tới bộ doc trong `node_modules/next/dist/docs/`, là nguồn chính xác nhất cho phiên bản đang dùng.
