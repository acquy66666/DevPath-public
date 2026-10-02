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

**Transcript thì ngược lại: đi qua backend.** `components/curriculum/transcript-upload.tsx` đọc tệp `.srt`/`.txt` bằng `file.text()` rồi gửi chữ trong body JSON tới `PUT /lessons/{id}/transcript`. Transcript chỉ vài chục KB, và backend cần đọc nó trước khi giữ. Tệp không phải UTF-8 khi `file.text()` giải mã sẽ ra `U+FFFD`, và backend nhận ra điều đó. Câu lỗi 422 của backend (vì sao đọc không được, sửa thế nào) được hiện nguyên văn, vì `TRANSCRIPT_UNREADABLE` cố ý không có câu chung trong `error-messages.ts`. Upload xong, khối này báo số ký tự lời giảng đã nhận, và cho biết khi nào trợ giảng AI đọc được: ngay nếu khóa đang xuất bản, còn không thì khi xuất bản.

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

Component là `components/ui/markdown.tsx`, dùng chung với bài học dạng **bài viết** trong `learn-view.tsx` để hai chỗ không lệch kiểu nhau — đề bài truyền `className="text-sm"`, bài viết để cỡ chữ thân bài; code tính bằng `em` nên đi theo cả hai. Nó bỏ prop `node` (cây hast) mà react-markdown truyền cho mọi component tùy biến: rải thẳng xuống thẻ DOM thì thành `node="[object Object]"`.

### Xem bài đang được chấm

`lib/api/submissions.ts` là kiểu riêng ấy: `SubmissionResult.stdout_trunc` khai là `string | null` vì với case ẩn nó **luôn** null, và một kiểu nói "luôn có" là một giả định sai được viết thành code.

`watchSubmission()` mở WebSocket `/api/v1/submissions/{id}/events` với access token đi trong subprotocol (`["bearer", token]`) — không đi trong query string, vì query string nằm trong log của nginx. Nếu socket không mở được, hoặc đóng trước khi chấm xong, nó **chuyển sang polling** `GET /submissions/{id}` mỗi 2 giây. Ngoại lệ duy nhất là mã đóng 4404: hỏi lại không làm một bài nộp không tồn tại hiện ra.

Cả hai đường phát ra cùng một kiểu `GradingEvent`, nên component chỉ vẽ một thứ và không bao giờ biết dữ liệu đến bằng đường nào. Đó cũng là lý do `SubmissionDetail` mang `total_cases`: thiếu nó, đường polling đếm được số case đã xong nhưng không biết đang tiến tới con số nào.

Hàm trả về một `stop()` — gọi khi component unmount. Nó gỡ `onclose` **trước** khi đóng socket, nếu không thì chính thao tác dọn dẹp sẽ khởi động vòng polling mà nó đang cố dừng.

## Quiz (Phase 4)

- **Giảng viên soạn:** `components/quiz/quiz-editor.tsx` + `question-form.tsx`, nằm trong lesson editor của mục lục cho bài học loại `quiz`. Client ở `lib/api/quiz-authoring.ts`, dùng kiểu của giảng viên (có đáp án đúng).
- **Học viên làm bài:** `components/quiz/quiz-workspace.tsx`, nhánh `quiz` của `learn-view.tsx`. Client ở `lib/api/quiz.ts`, dùng kiểu **không có đáp án** cho tới khi nộp; giải thích chỉ về sau khi chấm.

**Đồng hồ trên trang chỉ là hiển thị hạn chót, không phải hạn chót.** Nó khởi đầu từ `seconds_remaining` do server tính theo đồng hồ của server. Về 0 thì trang tự nộp bài, nhưng quyền quyết định vẫn ở backend: tab bị treo hay bị bóp CPU thì server vẫn từ chối bài nộp trễ quá 10 giây ân hạn. Hết giờ mà chưa nộp là 0 điểm, vì đáp án dở dang không được lưu (lý do ở `docs/report/assets/decisions.md`).

### Sinh câu hỏi bằng AI

`components/quiz/quiz-generator.tsx`, hiện trong trình soạn quiz khi quiz còn là bản nháp. Giảng viên chọn một bài viết hoặc video của khóa (mặc định là bài đọc được gần nhất đứng **trước** quiz, tức bài mà quiz đặt ở cuối nó nhiều khả năng kiểm tra), chọn số câu (1–10), và câu nháp được nối vào danh sách với nhãn "AI soạn · chờ duyệt".

**Không có nút "duyệt tất cả", và đó là cố ý.** Duyệt mười câu bằng một cú bấm là chưa duyệt câu nào. Mỗi câu nháp có nút **Duyệt** riêng, và **lời giải thích hiện ngay dưới phương án** để người duyệt so đáp án với lý do của chính model. Sửa rồi lưu cũng tính là duyệt. Khi `key_warning` bật (lời giải thích nói về một phương án khác với đáp án), câu hiện cảnh báo vàng. Nút xuất bản khóa lại, kèm dòng "Còn N câu AI soạn chưa duyệt", và backend cũng từ chối bằng 409 `QUIZ_NEEDS_REVIEW`.

Nút sinh chỉ gọi một request và chờ khoảng 3 giây, không stream, vì nửa câu hỏi không dùng được. Kết quả báo số câu bị loại (`dropped`) và bài có bị cắt vì quá dài hay không (`truncated`), để giảng viên biết mình đang nhìn thấy bao nhiêu phần của những gì AI đã viết.

**Cạm bẫy đã gặp khi thử:** một `next dev` chạy thẳng trên máy host (từ một worktree khác) có thể chiếm cổng 3000 trong khi container frontend vẫn báo healthy. Trình duyệt khi đó nói chuyện với code của nhánh khác, trông y hệt "bundle cũ". Trước khi nghi cache, kiểm tra xem tiến trình nào đang giữ cổng (`netstat -ano | findstr :3000`).

## Trợ giảng AI (Phase 4)

Tab **Trợ giảng AI** cạnh mục lục trong trang học (`/hoc/[slug]`). Code ở `components/chat/`, client ở `lib/api/chat.ts`, API ở mục "Trợ giảng AI" của [backend/README.md](../backend/README.md).

**Khung chat nằm cạnh bài học, không nằm trên nó.** Bấm vào một nguồn thì bài học bên trái đổi (`?bai=`), còn cuộc trò chuyện vẫn nguyên chỗ, kể cả khi câu trả lời đang chạy. Tab được dựng lần đầu khi mở, sau đó giữ nguyên (`forceMount`) để quay lại mục lục không cắt ngang câu trả lời. Ai không mở tab thì trang không tốn request nào cho chat.

**Luồng trả lời đọc bằng `fetch`, không bằng `EventSource`**, vì hỏi là `POST` có body và header `Authorization`. `lib/chat/sse.ts` tự tách khung: chỉ giao một sự kiện khi đã nhận đủ dòng trống kết thúc nó, và giải mã UTF-8 với `stream: true`, nên một chữ tiếng Việt bị cắt đôi giữa hai gói mạng không vỡ. Luồng dừng mà không có `done`/`error` (mất mạng, proxy bỏ ngang) thì `askAssistant` tự phát một `error`, để trang luôn biết câu trả lời đã kết thúc.

**Câu hỏi chỉ thật sự tồn tại khi đã có câu trả lời.** Backend lưu câu hỏi cùng câu trả lời hoàn chỉnh, không lưu trước. Vì thế lượt đang hỏi là state riêng (`LiveTurn`), và chỉ khi nhận `done` mới được ghi vào cache của TanStack Query thay cho state đó. Hỏng giữa chừng, hoặc học viên bấm **Dừng**, thì lượt ấy hiện rõ là *chưa được lưu*, kèm nút "Hỏi lại". Query tin nhắn đặt `staleTime: Infinity`, vì mọi thay đổi đều đi qua panel này. Nếu để một lần refetch chạy đua với câu trả lời vừa xong, nó có thể về sau và xóa câu trả lời khỏi màn hình. Trong lúc đang trả lời, nút đổi cuộc trò chuyện bị tắt chứ không lặng lẽ dừng câu trả lời.

**`[n]` thành nút mở bài học** nhờ một plugin remark nhỏ (`lib/chat/citations.ts`). Plugin chạy trên cây markdown chứ không trên chuỗi, vì cây đã tách sẵn code: `[1, 3]` trong khối code là list Python, không phải nguồn. Quy tắc bám theo regex `_CITATION` của backend. Chữ cái hoặc chữ số đứng ngay trước dấu ngoặc (`a[1]`, `trị[1]`) là chỉ số, không phải nguồn. Dùng `\p{L}` vì `\w` của Python hiểu Unicode, còn của JS thì không. Chỉ số nào có trong danh sách nguồn mới thành link; `[2021]` vẫn giữ nguyên chữ. Lúc đang stream, số lấy từ sự kiện `sources`. Với tin nhắn cũ, số lấy từ `citations` của backend, còn tên bài lấy từ mục lục đang có trên trang. Bài đã bị gỡ thì hiện nút mờ "không còn trong khóa".

**Gợi ý câu hỏi ghi rõ tên bài đang xem.** Backend không biết học viên đang mở bài nào, nên hỏi "bài này" thì bước tìm kiếm không có gì để bám.

Phím Enter gửi, Shift+Enter xuống dòng. Enter dùng để xác nhận chữ trong bộ gõ (`isComposing`) thì không gửi, nếu không một câu tiếng Việt gõ dở sẽ bị gửi đi. `CHAT_RATE_LIMITED` cố ý không có câu chung trong `error-messages.ts`, vì câu của backend nói rõ phải đợi bao lâu.

## Giỏ hàng, mã giảm giá & thanh toán (Phase 5)

`/gio-hang` và `/yeu-thich`, cộng cái chuông giỏ hàng trên header và hai nút trên trang khóa học (`components/commerce/`). Khóa học có phí giờ vào giỏ thay vì đứng sau một nút "Mua khóa học" bị khóa — thanh toán là task kế tiếp, nhưng ý định mua thì thu ở giỏ từ bây giờ.

**Một query `["cart"]` cho cả trang.** Chuông trên header, nút "Thêm vào giỏ hàng" ở trang khóa học và trang giỏ hàng đều đọc chung một entry cache, nên thành phần thứ hai và thứ ba không tốn thêm request nào. Mọi thao tác giỏ hàng trả về cả cái giỏ, và `setQueryData(["cart"], …)` ghi thẳng câu trả lời ấy vào cache — con số trên chuông nhảy trong cùng cú bấm, không cần refetch. Danh sách yêu thích trả 204 nên hai mutation của nó `invalidateQueries` thay vì ghi đè.

**Trái tim đọc `["wishlist-ids"]`**, một mảng id, chứ không hỏi "khóa này đã lưu chưa?" cho từng khóa: một response nhỏ, dùng chung được cho mọi thẻ trên trang, và không đẻ ra một endpoint chỉ để trả lời một chữ có/không.

Khách chưa đăng nhập không thấy chuông lẫn trái tim — cả hai đều cần tài khoản, mà header đã có sẵn nút "Đăng nhập" cách đó hai ô. Hai trang thì chặn ở client như mọi trang cần đăng nhập khác (`?next=` quay lại đúng chỗ), chốt chặn thật vẫn là 401 của backend.

**Nút "Thanh toán qua VNPay" gọi hai request, có chủ ý**: tạo đơn (`POST /orders`) rồi xin URL đã ký (`POST /orders/{code}/payment-url`), sau đó `window.location.href` sang VNPay — chuyển trang thật vì đích đến không thuộc app này. Đơn hàng là bản ghi sống lâu, URL thanh toán là chuỗi ký sống 15 phút; tách ra thì một máy chủ chưa cấu hình VNPay vẫn trả lời được "đơn đã tạo, xem ở đây" thay vì làm mất nó sau một câu lỗi.

**Trang `/thanh-toan/ket-qua` không đọc kết quả từ URL.** VNPay chuyển trình duyệt về kèm nguyên câu trả lời trong query string, nhưng trang chỉ lấy `vnp_TxnRef` (mã đơn) rồi hỏi `GET /orders/{code}` — query string đi qua trình duyệt, mà trình duyệt là thứ chủ nó sửa được, tin vào nó nghĩa là ai gõ được `vnp_ResponseCode=00` cũng tự ghi danh được. Callback của VNPay có thể tới **sau** cú chuyển trang vài giây, nên đơn còn `pending` thì trang tự hỏi lại mỗi 3 giây trong 90 giây rồi dừng và chỉ cho người dùng mã đơn để hỏi lại — chứ không tuyên bố là thất bại.

**Ô "Mã giảm giá" (`coupon-box.tsx`) hỏi lại mỗi khi giỏ đổi.** Query key là `["cart-coupon", mã, hình-dạng-giỏ]`, trong đó hình dạng giỏ là danh sách id cộng tổng tiền: bỏ một khóa ra là một câu hỏi khác, nên câu trả lời cũ không được phép nằm lại trên màn hình, và mã không còn áp được sẽ tự nói ra điều đó ngay trong ô. `retry: false` — mã bị từ chối là một câu trả lời chứ không phải trục trặc mạng, thử lại ba lần chỉ làm câu ấy tới muộn hơn. Mã **không** được nhớ giữa các lần vào trang: dù sao thanh toán cũng kiểm lại từ đầu, nên một mã khôi phục từ storage chỉ là lời hứa trang này không giữ được. Coupon phạm vi từng khóa mới gắn nhãn "Đang được giảm giá" lên dòng — coupon toàn sàn phủ hết mọi dòng, dán nhãn khắp nơi thì không nói thêm gì mà lại chiếm chỗ của dòng "bạn đã có khóa này".

## Khu vực quản trị (Phase 5)

| Đường dẫn | Nội dung |
|---|---|
| `/quan-tri` | Tổng quan toàn sàn: doanh thu, DAU, người dùng hoạt động, tài khoản mới (so với kỳ trước), biểu đồ doanh thu + DAU, bảng khóa học hot |
| `/quan-tri/khoa-hoc` | Hàng đợi duyệt: lọc theo trạng thái (mặc định "Chờ duyệt", chờ lâu nhất đứng đầu), tìm theo tên khóa hoặc tên/email giảng viên |
| `/quan-tri/khoa-hoc/[courseId]` | Đọc khóa học như người mua sẽ thấy (mô tả, mục lục, bấm từng bài để xem trước bài đọc/video) và quyết định: duyệt, từ chối kèm lý do, gỡ khỏi sàn kèm lý do |
| `/quan-tri/bao-cao` | Báo cáo vi phạm: chờ xử lý / đã xử lý, lọc theo loại nội dung; gỡ nội dung, xác nhận vi phạm mà giữ, bỏ qua; khóa tác giả ngay trên thẻ |
| `/quan-tri/nguoi-dung` | Mọi tài khoản, mới nhất trước; khóa/mở (tài khoản admin không có nút khóa) |
| `/quan-tri/danh-muc` | Cây danh mục 2 cấp: thêm, đổi tên, chuyển cấp, lên/xuống, xóa (chỉ danh mục trống) |
| `/quan-tri/ma-giam-gia` | Chiến dịch mã giảm giá: tạo/sửa trong hộp thoại (chọn khóa học cho mã theo khóa), kết thúc sớm, xóa mã chưa dùng |
| `/quan-tri/banner` | Banner trang chủ: tải ảnh thẳng lên bucket, bật/tắt, lịch hiện/gỡ, lên/xuống, xóa |

- `(dashboard)/layout.tsx` giờ chỉ là khung header/footer; **ai được vào do từng khu tự quyết**: `giang-day/layout.tsx` bọc `InstructorGate`, `quan-tri/layout.tsx` bọc `AdminGate` + thanh tab. Hai vai trò khớp chính xác ở backend, không khu nào là tập cha của khu kia.
- Tab có số đang chờ lấy từ `GET /admin/summary`; mọi query của khu này nằm dưới key `["admin"]` nên một quyết định làm mới luôn cả con số trên tab.
- Trang duyệt đọc bài học qua đúng endpoint học viên dùng (`may_manage` đã mở mọi khóa cho admin), nên thứ admin xem trước chính là thứ sẽ được bán. Video dùng lại `components/learn/video-player.tsx`.
- **Báo cáo:** `components/reports/report-button.tsx` — nút "Báo cáo" + hộp thoại (5 lý do, "Lý do khác" bắt buộc mô tả) ở trang chi tiết khóa học, từng đánh giá, câu hỏi và câu trả lời Hỏi đáp. Nút tự ẩn trên nội dung của chính người đọc; trong Hỏi đáp nó cũng ẩn với giảng viên/admin vì họ xóa trực tiếp được. `ALREADY_REPORTED` được hiện như thành công ("Bạn đã báo cáo nội dung này"). `components/ui/dialog.tsx` viết tay theo đúng khuôn các component radix khác — `shadcn add dialog` với style `radix-nova` đòi ghi đè `button.tsx` và tự thêm một gói npm tên `cn`.
- **Tổng quan** dùng lại `ColumnChart`, `StatTile`, `PeriodPicker` và hàm định dạng của dashboard giảng viên (`components/instructor/stats/`) — hai dashboard đọc giống nhau, chỉ khác phạm vi.
- **Banner trang chủ:** `components/banners/home-banners.tsx` (Server Component, `connection()` để banner hẹn giờ không bị nướng vào HTML lúc build; lỗi thì không vẽ gì) → `banner-carousel.tsx` (client): tự chuyển 6 giây, dừng khi rê chuột/focus, **không tự chuyển** khi hệ thống bật giảm chuyển động; slide ẩn có `aria-hidden` và link của nó ra khỏi thứ tự Tab. Ảnh banner tải lên qua `uploadToStorage` — cùng hàm với video và ảnh đại diện.
- Ba loại thông báo mới cho giảng viên (`course_approved`, `course_rejected`, `course_taken_down`) có nhánh riêng trong `describe()`, link về `/giang-day/{course_id}` — nơi `course-status-card.tsx` hiện "Lý do từ chối".

## Kiểm thử (Phase 6)

```bash
npm test                                       # test đơn vị: node --test trên lib/**/*.test.ts
E2E_CHROME_CHANNEL=chrome npm run test:e2e     # E2E Playwright, chạy vào stack compose đang bật
```

- **Test đơn vị** chạy bằng `node --test` thẳng trên TypeScript (Node bỏ kiểu), không cài framework. `*.test.ts` nằm ngoài `tsconfig.json` vì Node cần import có đuôi `.ts` còn cấu hình bundler của Next từ chối.
- **E2E** (`e2e/golden-flow.spec.ts`) chạy luồng vàng trên UI thật: đăng ký → thêm giỏ → thanh toán VNPay → học bài đọc → nộp code trong Monaco, chấm trong sandbox → chứng chỉ. Cần stack dev đang chạy (`docker compose up -d` trong `infra/`, đã seed) — Playwright không tự dựng stack vì luồng này cần đủ cả API, worker chấm bài và worker vẽ chứng chỉ.
  - Phần của giảng viên và admin (soạn khóa, duyệt) đi qua API trong `e2e/support/stack.ts`; IPN của VNPay do `scripts.simulate_vnpay_ipn` ký **bên trong container backend**, nên secret không ra ngoài mà request vẫn qua đúng bước kiểm chữ ký. Trang của VNPay được thay bằng route interception.
  - Tài khoản admin: mặc định là tài khoản seed (`admin@devpath.example` / `devpath-admin`), đổi bằng `E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD`.
  - Mọi tài khoản E2E có email `@e2e.devpath.example`; sau khi chạy xong, suite gọi `python -m scripts.purge_e2e` để gỡ tài khoản, khóa học, đơn hàng, chứng chỉ của nó (`E2E_KEEP_DATA=1` để giữ lại xem). Dọn tay: `docker compose exec backend python -m scripts.purge_e2e [--dry-run]`.
  - `E2E_EVIDENCE_DIR=<thư mục>` lưu ảnh từng bước — cách đã chụp `docs/report/assets/phase-6/e2e/`.
  - Mỗi lượt đăng ký 2 tài khoản và đăng nhập admin 1 lần: chạy liên tục nhiều lần sẽ chạm giới hạn đăng ký 50/giờ/IP hoặc đăng nhập 10/15 phút/email của admin.
  - CI chạy job riêng "E2E — golden flow": dựng cả stack compose, build image sandbox, seed, cài Chromium của Playwright.

## Cấu trúc

```
app/
├── (marketing)/     Trang public: home, danh sách + chi tiết khóa học (SSR, SEO)
├── (learn)/         Player, quiz, code editor (client-heavy) — Phase 2+
└── (dashboard)/     Khu vực giảng viên /giang-day và quản trị /quan-tri (mỗi khu một gate)
components/ui/       shadcn/ui (generated, hạn chế sửa tay) + form-field, native-select, textarea, markdown
components/layout/   site-header, site-footer
components/instructor/ danh sách khóa học, form tạo/sửa, trạng thái
components/curriculum/ trình soạn mục lục (kéo-thả)
components/exercise/   trình soạn bài tập code + test case (Phase 3)
components/chat/       trợ giảng AI trong trang học (Phase 4)
components/commerce/   giỏ hàng, yêu thích, mã giảm giá, kết quả thanh toán (Phase 5)
components/admin/      khu quản trị: duyệt khóa học, báo cáo, người dùng (Phase 5)
components/reports/    nút + hộp thoại báo cáo vi phạm (Phase 5)
lib/chat/            đọc luồng SSE, biến [n] thành link (hàm thuần)
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
