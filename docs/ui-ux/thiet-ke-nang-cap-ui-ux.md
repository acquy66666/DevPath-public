# Nâng cấp UI/UX toàn diện — tài liệu thiết kế

> Viết 16/10/2026 từ ý tưởng thô của user. Kế hoạch có checkbox nằm ở [`docs/plan/phase-7-ui-ux-upgrade.md`](../plan/phase-7-ui-ux-upgrade.md). Tài liệu này trả lời *làm gì và vì sao*; plan trả lời *làm theo thứ tự nào*.
>
> Mọi chỗ ghi **(giả định)** là Claude tự quyết khi chưa hỏi được. Mọi chỗ ghi **(user chốt)** là lời của user. Phần cần user quyết nằm ở mục 10.

## 1. Ý định — vì sao làm

User chốt 16/10: *sau khi hoàn thiện tính năng và deploy 0đ cho buổi trình bày với GVHD*, nâng cấp toàn bộ giao diện. Ba mong muốn:

1. **Một bộ thiết kế riêng** cho DevPath, từ màu sắc trở đi, làm bằng **Claude Design**.
2. **Một nhân vật linh vật riêng**, theo kiểu con cú xanh Duo của Duolingo.
3. **Bộ hoạt ảnh riêng** cho nhân vật, phản ứng theo việc học: điểm cao điểm thấp phản ứng khác nhau, trang 404 có nhân vật, v.v.

Lý do đằng sau **(giả định)**: giao diện hiện tại là shadcn/ui gần như mặc định (font Geist, bảng màu neutral, `not-found.tsx` chỉ có chữ). Nó dùng được và đã đo kỹ (0/94 tràn ngang, `ux-polish.txt`), nhưng không có bản sắc. Trước hội đồng, phần nhìn là ấn tượng đầu tiên. Khóa luận có 3 điểm nhấn kỹ thuật (sandbox, recommender, RAG); một sản phẩm *trông như sản phẩm thật* làm cả ba dễ được nhìn thấy hơn. Duolingo được chọn làm hình mẫu vì đã chứng minh một nhân vật phản ứng theo kết quả học có thể giữ người học quay lại. DevPath đã có sẵn đúng những sự kiện để nhân vật phản ứng: verdict chấm code realtime, điểm quiz, chuỗi ngày học, XP, chứng chỉ.

## 2. Mục tiêu, phi mục tiêu, phản mục tiêu

**Mục tiêu**

- Một **design system** duy nhất: token màu (sáng + tối), type scale, khoảng cách, bo góc, đổ bóng, **token chuyển động**. Nó vừa là artifact Claude Design, vừa là `frontend/app/globals.css` (`@theme`). Code chỉ đọc token, không có mã màu rời.
- Một **nhân vật linh vật gốc**: model sheet, bộ biểu cảm, và một component `<Mascot>` dùng được ở mọi nơi.
- **Bản đồ phản ứng** (mục 5) gắn nhân vật vào các sự kiện thật của app.
- Thiết kế lại **mọi nhóm màn hình** (mục 6) theo design system, mỗi nhóm có ảnh trước/sau.
- Giữ nguyên chất lượng đã đo: E2E luồng vàng xanh, 0 tràn ngang ở 360/375/1440 px, loading/empty state đủ. Thêm **a11y** (0 lỗi nghiêm trọng theo axe) và **hiệu năng** (ngân sách LCP/CLS, xem mục 8).

**Phi mục tiêu** (không làm trong đợt này)

- Không đổi nghiệp vụ, không đổi API, không migration. Backend đứng yên. Ngoại lệ duy nhất là sửa lỗi nếu lộ ra.
- Không làm app di động.
- Không âm thanh **(giả định)**: thêm âm là thêm cài đặt bật/tắt, thêm tệp, và dễ gây khó chịu trong phòng bảo vệ.
- Không đa ngôn ngữ. UI vẫn ưu tiên tiếng Việt như CLAUDE.md.

**Phản mục tiêu** (chạy được mà vẫn coi là hỏng)

- **Nhân vật giống Duo.** Duolingo là hình mẫu về *cách dùng*, không phải về *hình dáng*. Một con cú xanh lá là vấn đề nhãn hiệu, và là thứ hội đồng nhìn ra ngay. Nhân vật phải gốc: khác loài, khác màu chủ đạo, khác dáng.
- **Nhân vật làm phiền.** Chặn thao tác, che nội dung, phát lại mỗi lần render, hoặc làm chậm trang. Hoạt ảnh phản ứng phải ngắn (≤ 2–3 s), không chặn click, và tắt được bằng `prefers-reduced-motion`.
- **Trẻ con hóa khu làm việc.** Ở khu giảng viên/admin (soạn khóa, thống kê, duyệt, báo cáo), nhân vật chỉ xuất hiện ở empty state và lời chào, không nhảy múa trên bảng số liệu.
- **Đẹp mà mất tiếng Việt.** Font mới vỡ dấu hai tầng ("Luồng", "Người", "Tiếng Việt" — lỗi đã gặp ở trang chứng chỉ 02/10) là hỏng.
- **Phá E2E/CI.** Đổi chữ trên nút hoặc vai trò ARIA mà spec dựa vào, không sửa spec cùng commit.

## 3. Ràng buộc đã biết (từ repo)

| Ràng buộc | Nguồn | Hệ quả cho đợt này |
|---|---|---|
| Next.js 16.3 (App Router), React 19.2, Tailwind v4 (`@theme inline`), shadcn/ui + Radix, `tw-animate-css`, lucide | `frontend/package.json`, `app/globals.css` | Token đi vào `@theme`. Component mới viết như `components/ui/*` hiện có. **Next bản này khác kiến thức cũ**: đọc `node_modules/next/dist/docs/` trước khi viết (frontend/AGENTS.md) |
| Font **tự host**, ESLint chặn `next/font/google` | CLAUDE.md, `frontend/public/fonts/README.md` | Font mới phải có woff2 subset `vietnamese`, đi qua `app/fonts.css`, kiểm bằng `frontend/scripts/build-offline.sh` |
| `.dark` variant đã khai báo nhưng **chưa có nút đổi theme** | `app/globals.css` dòng 5 | Dark mode là việc mới. Xem mục 10 |
| E2E luồng vàng dựa vào role/name trên UI thật, kể cả khung WebSocket chấm bài | `frontend/e2e/golden-flow.spec.ts` | Mỗi đổi chữ/vai trò phải sửa spec cùng commit; E2E chạy sau mỗi nhóm màn |
| Script chụp 42 ảnh cho chương 4 | `docs/report/assets/phase-6/ui/capture.cjs` | Chạy *trước* (ảnh "trước") và *sau* (ảnh mới cho báo cáo) |
| Media cùng origin, CSP sandbox cho tệp tải lên | `infra/nginx/snippets/media.conf` | Asset nhân vật nằm trong `frontend/public` (bundle), **không** đi qua bucket |
| CSP đã enforce (18/10, task Phase 6) | `infra/nginx/snippets/security-headers.conf` | Thư viện hoạt ảnh không được cần `unsafe-eval`. Rive dùng WASM → kiểm `script-src`/`wasm-unsafe-eval` trước khi chọn. Trước khi merge một nhóm màn đổi thứ được tải (thư viện, font, hình): chạy `docs/report/assets/phase-6/csp-enforce/csp-probe.cjs` + E2E vào stack production — vi phạm nào cũng là đỏ |
| Chứng chỉ PDF vẽ bằng WeasyPrint | `backend/app/services/certificates.py` | Nếu đưa nhân vật/màu mới vào PDF thì đó là đổi backend; để ngoài đợt này **(giả định)** |

## 4. Nhân vật linh vật

### 4.1 Ba hướng đề xuất

Claude nghĩ nhiều hướng rồi bỏ những hướng đụng phản mục tiêu (cú, chim xanh lá, chim nói chung quá gần Duo). Còn ba:

| Hướng | Ý tưởng | Vì sao hợp DevPath | Rủi ro |
|---|---|---|---|
| **A. Tắc kè "bắt bug"** (đề xuất) | Tắc kè nhỏ, mắt to, đuôi cuộn hình dấu `{`. Lưỡi bắt "con bug" khi bài AC | Tắc kè ăn côn trùng = bắt bug, ẩn dụ của lập trình ai cũng hiểu. Quen thuộc với người Việt. Không trùng linh vật nền tảng học nào phổ biến | Vẽ bò sát cho dễ thương cần tay. Tránh xanh lá đúng tông Duolingo (chọn ngọc/lam-lục hoặc cam) |
| B. Chim Lạc "đường bay" | Chim Lạc trên trống đồng, cách điệu tối giản, bay theo một "path" | Gắn tên DevPath (con đường) với nét văn hóa Việt, khác biệt trước hội đồng | Vẫn là chim, dễ bị so với Duo. Hình tượng văn hóa cần vẽ trang trọng, khó làm hài hước |
| C. Robot màn hình "Pi" | Robot nhỏ, mặt là màn hình, biểu cảm bằng mắt pixel | Dễ vẽ, dễ hoạt ảnh nhất (đổi mắt là đổi cảm xúc), hợp chủ đề code | Phổ biến, ít ấm áp, ít bản sắc |

**Đề xuất của Claude: hướng A**, vì ẩn dụ "bắt bug" gắn thẳng với tính năng chấm code (điểm nhấn ⭐ số 1): AC = bắt được bug. Hướng cuối do user chọn trong buổi Claude Design đầu tiên, nơi cả ba được phác cạnh nhau. **Đã chốt 21/10/2026: hướng A, tên Naomi** (user đặt). Model sheet và bộ biểu cảm: [`docs/ui-ux/mascot/`](mascot/README.md).

### 4.2 Sản phẩm đầu ra của nhân vật

- **Model sheet**: chính diện, ¾, nghiêng; tỉ lệ; bảng màu riêng của nhân vật (lấy từ token).
- **Bộ biểu cảm**: tối thiểu 12 trạng thái, đúng danh sách `mood` ở mục 5.
- **Dạng kỹ thuật: SVG nhiều lớp đặt tên** (thân, đầu, mắt, mí, miệng, tay, đuôi, phụ kiện), để hoạt ảnh bằng code và đổi màu theo theme.
- **Component**: `<Mascot mood="celebrate" size="sm|md|lg" />`. Dùng `aria-hidden` khi chỉ trang trí, câu chữ đi kèm mới là nội dung. Có tư thế tĩnh cho `prefers-reduced-motion`. Tải lười ngoài màn hình đầu.

### 4.3 Công nghệ hoạt ảnh — quyết bằng spike, không bằng bài review

| Cách | Mạnh | Yếu với dự án này |
|---|---|---|
| **SVG + Motion** (`motion/react`, tên mới của Framer Motion) — mặc định đề xuất | Claude viết được trọn bằng code, không cần phần mềm hoạt hình. Nhẹ, đổi màu theo token, không WASM nên không đụng CSP | Hoạt ảnh phức tạp (biến dạng mềm) khó hơn |
| **Rive** (state machine + runtime `@rive-app/canvas`) | Nhân vật phản ứng theo state machine, mượt, tệp nhỏ. Đúng loại công cụ dành cho linh vật tương tác | Phải dựng trong Rive Editor (người làm tay). Runtime WASM: kiểm CSP. Thêm một công cụ ngoài repo |
| **Lottie** (After Effects → JSON) | Phổ biến nhất | Chỉ phát lại, tương tác phải tự code. Cần After Effects |

~~**(giả định)** v1 dùng **SVG + Motion**: không phụ thuộc kỹ năng hoạt hình của ai, và mọi thứ nằm trong repo nên chạy lại được. Nếu user muốn tự làm trong Rive Editor thì spike ở đầu phase so hai bản cùng một trạng thái ("celebrate"): dung lượng tải, CPU, CSP, công làm.~~

**Đã chốt 21/10/2026: SVG + `motion/react-mini`.** User chọn không làm Rive. Spike so ba cách chạy cùng phản ứng `celebrate`: CSS keyframes, `motion/react-mini` và `motion/react` đầy đủ. Kết quả:
- `mini` thêm 5,3 KB gzip và 11 % CPU so với CSS.
- Motion đầy đủ thêm 25,6 KB và 51 % CPU. Nó chạy transform của SVG bằng JS, và tự đặt `transform-box: fill-box`, làm sai điểm xoay.
- Cả ba đều 0 vi phạm CSP và đứng yên khi `reduce`.

Số đo: [`animation-spike.md`](../report/assets/phase-7/animation-spike.md).

## 5. Bản đồ phản ứng — nhân vật gắn vào sự kiện thật

Mỗi dòng là một sự kiện app **đã phát ra hôm nay** (không cần backend mới).

| `mood` | Sự kiện | Nơi | Phản ứng (gợi ý) |
|---|---|---|---|
| `grading` | Đang chấm, WebSocket báo "test k/n" | Trang nộp bài | Gõ laptop, thanh tiến độ theo k/n |
| `celebrate` | Verdict **AC 100/100** | Trang nộp bài | Bắt được bug, nhảy mừng, confetti nhỏ |
| `partial` | AC một phần / **WA** | Trang nộp bài | Gãi đầu, chỉ vào test đầu tiên sai |
| `sleepy` | **TLE** | Trang nộp bài | Ngáp, đồng hồ cát |
| `stuffed` | **MLE** | Trang nộp bài | Bụng phồng |
| `dizzy` | **RE** | Trang nộp bài | Choáng, sao quay |
| `tangled` | **CE** | Trang nộp bài | Rối như mì, kính mờ |
| `sorry` | **SE** / lỗi hệ thống / 500 | Trang nộp bài, `error.tsx` | Cầm biển "đang sửa", xin lỗi |
| `party` / `proud` / `cheer` / `comfort` | Quiz **100 %** / **≥ 80 %** / **50–79 %** / **< 50 %** (ngưỡng là giả định) | Kết quả quiz | Bốn mức: tiệc, tự hào, khích lệ, an ủi + nút "Ôn lại" |
| `startled` | Quiz **hết giờ** (backend chấm 0 điểm) | Kết quả quiz | Giật mình nhìn đồng hồ |
| `fire` / `sad` | Chuỗi ngày **giữ được** / **vừa mất** | Khối thành tích `/khoa-hoc-cua-toi` | Lửa cháy / buồn nhưng động viên bắt đầu lại |
| `levelup` | XP **lên hạng** trên bảng xếp hạng | `/bang-xep-hang` | Bay lên bục |
| `graduate` | **Nhận chứng chỉ** | Trang học khi hoàn thành, `/cert/[code]` | Đội mũ tốt nghiệp |
| `lost` | **404** | `app/not-found.tsx` + 2 trang 404 riêng | Lạc đường, cầm bản đồ ngược |
| `empty` (+ đạo cụ) | Giỏ trống, chưa có khóa học, chưa thông báo, chưa ghi chú, tìm không ra | Các empty state | Tư thế chờ + đạo cụ theo chỗ |
| `thinking` / `answer` | Trợ giảng AI **đang stream** / **có nguồn** / từ chối | Tab "Trợ giảng AI" | Avatar suy nghĩ khi `delta` tới; cầm sách khi có `sources` |
| `wave` | Đăng ký xong, chào trở lại | Onboarding, trang chủ khi đăng nhập | Vẫy tay |
| `paid` / `oops` | Thanh toán **thành công** / **thất bại** | `/thanh-toan/ket-qua` | Ăn mừng / ngơ ngác |

Luật chung: phản ứng **một lần** cho mỗi sự kiện (không phát lại mỗi lần render hay khi polling), ≤ 2–3 s rồi về tư thế nghỉ, không che nút hành động, tôn trọng `prefers-reduced-motion`. **Chỉ phản ứng khi sự kiện vừa xảy ra trong phiên này**: verdict tới qua WebSocket, quiz vừa nộp, chứng chỉ vừa cấp. Mở lại lịch sử nộp bài hay trang kết quả cũ thì hiện tư thế tĩnh tương ứng, không ăn mừng lại.

## 6. Phạm vi màn hình — mười nhóm

Mỗi nhóm đi đủ một vòng: mockup trong Claude Design (artifact "Design") → user duyệt → code → E2E + ảnh trước/sau. Thứ tự đề xuất theo mức "hội đồng sẽ thấy":

1. **Nền**: token, `components/ui/*`, header/footer/nav điện thoại, theme.
2. **Trang công khai**: trang chủ (banner, gợi ý, khóa mới), danh sách + tìm kiếm, chi tiết khóa học, trang giảng viên.
3. **Nộp bài code** ⭐: Monaco, kết quả từng test realtime, nhân vật theo verdict.
4. **Trang học**: video, bài đọc, mục lục, ghi chú, Hỏi đáp, **trợ giảng AI** ⭐.
5. **Quiz**: làm bài có đồng hồ, kết quả theo bốn mức.
6. **Thành tích**: XP/chuỗi ngày, bảng xếp hạng, chứng chỉ, **gợi ý** ⭐.
7. **Tài khoản**: đăng ký/đăng nhập (giữ điều kiện hydrate của form), hồ sơ, onboarding.
8. **Thương mại**: giỏ, yêu thích, kết quả thanh toán.
9. **Giảng viên**: tổng quan, soạn khóa, curriculum kéo-thả, soạn bài code, sinh quiz AI, thống kê, Hỏi đáp.
10. **Admin + trạng thái**: tổng quan, duyệt, báo cáo, người dùng, danh mục/mã/banner; 404/500/loading/empty toàn site.

## 7. Claude Design trong quy trình

Tài khoản này có sẵn hai loại artifact của Claude Design: **Design System** (README thương hiệu, token theo theme, type scale, component có preview, asset) và **Design** (canvas mockup màn hình). Quy trình **(giả định)**:

1. Tạo artifact **"DevPath Design System"** từ chính codebase (token hiện có làm điểm xuất phát), rồi chỉnh màu/chữ/token chuyển động cùng user.
2. Phác **ba hướng nhân vật** cạnh nhau trên một artifact Design. User chọn, rồi làm model sheet + bộ biểu cảm.
3. Mỗi nhóm màn: một artifact Design. Khi duyệt, chuyển sang code trong repo. Token lấy từ design system, không chép mã màu từ mockup.
4. **Một nguồn chân lý**: khi code và artifact lệch nhau, `globals.css` thắng, rồi cập nhật artifact.
5. Sau phase: viết **skill dự án `devpath-ui`** (`.claude/skills/devpath-ui/`) ghi luật token, component, nhân vật, chuyển động, để mọi phiên sau tự theo. `nextjs-feature` trỏ sang nó.

Figma MCP cũng đang kết nối trong môi trường này. Đó là đường dự phòng nếu cần một file Figma, không phải đường chính.

## 8. Chất lượng và đo lường (cho chương 5)

| Thứ đo | Cách | Ngưỡng **(giả định)** |
|---|---|---|
| E2E luồng vàng | `npm run test:e2e` + job CI | "1 passed", không "flaky" |
| Tràn ngang | Script rà UX 02/10 (47 trang × 375/1440) | 0/94, thêm 360 px |
| Truy cập (a11y) | axe-core qua Playwright trên các trang chính; bàn phím | 0 lỗi `critical`/`serious` |
| Hiệu năng | Lighthouse (mobile) trang chủ, chi tiết khóa, trang học | LCP ≤ 2,5 s, CLS ≤ 0,1, không tệ hơn số "trước" |
| Dung lượng | JS tải ở trang chủ (`next build` output) | Nhân vật + Motion thêm ≤ 50 KB gzip ở màn đầu |
| Hồi quy hình ảnh | Playwright `toHaveScreenshot` cho ~10 trang khóa | Baseline commit vào repo, CI so. **Baseline sinh trên Linux** (trong job CI hoặc image Playwright), không sinh trên Windows: font render khác nhau nên baseline Windows sẽ đỏ trên CI |
| Tiếng Việt | Ảnh chụp chữ có dấu hai tầng trên mọi font mới | Không vỡ dấu |

Bằng chứng vào `docs/report/assets/phase-7/`: ảnh trước/sau từng nhóm, export design system, model sheet + bộ biểu cảm, GIF/video ngắn các phản ứng, bảng số đo trước/sau.

## 9. Skill và công cụ cho giai đoạn này (nghiên cứu 16/10)

Nguyên tắc: **ưu tiên nguồn chính chủ**. Với skill cộng đồng, **kiểm audit trước khi cài** (`https://skills.sh/api/v1/skills/audit/<owner>/<repo>/<skill>`). Skill là chỉ dẫn mà agent làm theo, nên cũng là một bề mặt tấn công. Cài từng skill (`owner/repo/skill`), không cài cả repo.

**Đã có sẵn trong môi trường, không cần cài**: superpowers (brainstorming, writing-plans, TDD, verification), Claude Design (Design System + Design), Figma MCP, trình duyệt tích hợp + Playwright, `artifact-design`, `diagram-design`, `skill-creator` (để viết `devpath-ui`).

| Skill | Nguồn | Dùng ở đâu | Ghi chú |
|---|---|---|---|
| **frontend-design** | `anthropics/skills` · chính chủ | Mọi nhóm màn: tránh giao diện "AI chung chung", chọn hướng thẩm mỹ có chủ đích | Đọc LICENSE.txt của từng skill |
| **theme-factory**, **canvas-design**, **brand-guidelines** | `anthropics/skills` · chính chủ | Theme preset để so; poster/model sheet tĩnh; `brand-guidelines` là khuôn để viết `devpath-ui` | |
| **web-design-guidelines** | `vercel-labs/agent-skills` · chính chủ | Rà code UI theo ~100 luật a11y/animation/form/ảnh ở cuối mỗi nhóm màn | `npx skills add vercel-labs/agent-skills --skill web-design-guidelines` |
| **react-best-practices** | `vercel-labs/agent-skills` · chính chủ | Hiệu năng React/Next khi thêm hoạt ảnh | |
| **shadcn/ui** | `shadcn/ui` · chính chủ | Theming + CLI shadcn theo cấu hình dự án | `npx skills add shadcn/ui`. Lưu ý cũ: `shadcn add dialog` từng ghi đè `button.tsx` |
| **ui-ux-pro-max** | `nextlevelbuilder/ui-ux-pro-max-skill` · MIT | Kho tra cứu: kiểu giao diện, bảng màu, cặp font, luật UX, checklist trước bàn giao | Cài qua `uipro-cli`. Dùng để tra, không để quyết thay |
| **motion** | `pedronauck/skills` · cộng đồng | Motion: gesture, layout, `AnimatePresence`, SVG, spring | Bản dùng import `motion/react` (Motion v12+). **18/10: repo đã gỡ skill này; cài `bm629/agent-skills/motion-react` thay thế** ([README](README.md)) |
| **animation-principles** | `dylantarre/animation-principles` · cộng đồng | 12 nguyên lý hoạt hình cho bộ biểu cảm | Repo có 144 skill; 18/10 cài 3: `character-appeal`, `education-learning`, `accessible-motion` |
| **rive-web** / **rive** | `stevysmith/rive-skills`, `bowtiedswan/rive-skills` · cộng đồng | Chỉ khi chọn Rive ở spike 4.3 | |
| **visual-testing** | `petrkindlmann/qa-skills` · cộng đồng | Baseline `toHaveScreenshot`, che vùng động | **Tránh** `manutej/luxor-claude-marketplace/playwright-visual-testing`: catalog ghi audit HIGH risk |
| Skill a11y WCAG 2.2 | chọn sau audit | Rà truy cập | Hoặc tự dùng axe-core + Playwright, không cần skill |

Nguồn đã đọc: [anthropics/skills — tổng quan](https://codenote.net/en/posts/anthropic-official-skills-catalog-overview/), [ui-ux-pro-max](https://agentskill.sh/@nextlevelbuilder/ui-ux-pro-max), [vercel-labs/agent-skills](https://playbooks.com/skills/vercel-labs), [skill chính chủ của shadcn](https://ui.shadcn.com/docs/skills.md), [pedronauck/skills/motion](https://skills.sh/pedronauck/skills/motion), [rive-web](https://www.skills.sh/stevysmith/rive-skills/rive-web), [animation-principles/rive-animations](https://playbooks.com/skills/dylantarre/animation-principles/rive-animations), [qa-skills/visual-testing](https://skillselion.com/skills/petrkindlmann/qa-skills/visual-testing), [Claude Design (Anthropic)](https://www.anthropic.com/news/claude-design-anthropic-labs), [Lottie vs Rive vs CSS 2026](https://www.pkgpulse.com/guides/lottie-vs-rive-vs-css-animations-web-animation-formats-2026). Số lượt cài và số luật trên các catalog lệch nhau giữa các nguồn, nên không ghi ở đây.

## 10. Còn chờ user quyết

Theo thứ tự quan trọng:

1. **Ngày bảo vệ / hạn nộp báo cáo.** Nó quyết định Phase 7 dài 2 hay 3 tuần, và nhóm màn nào bị cắt nếu thiếu thời gian (cắt từ nhóm 10 ngược lên).
2. ~~**Hướng nhân vật và tên** (mục 4.1).~~ Đã chốt 21/10/2026: hướng A, tắc kè “bắt bug”, tên Naomi.
3. ~~**Rive hay chỉ code** (mục 4.3).~~ Đã chốt 21/10/2026: chỉ code, không Rive; spike chọn `motion/react-mini`.
4. **Dark mode**: làm trọn (mọi màn hai theme, có nút đổi) hay chỉ theme sáng. **(giả định)**: chỉ theme sáng, token tối giữ sẵn cho sau.

## 11. Để lại cho người làm

- Tên token, cấu trúc thư mục `components/mascot/`, cách chia variant Motion.
- Ngưỡng quiz chính xác (80/50) nếu dữ liệu demo cho thấy chỗ khác hợp hơn.
- Font cụ thể: chọn từ các font có subset `vietnamese` đầy đủ, ví dụ Be Vietnam Pro, Nunito, Lexend cho chữ, JetBrains Mono cho code, sau khi chụp thử chữ có dấu hai tầng.
- ~~Có cần `motion` trên server component không (dùng `motion/react-client` theo tài liệu Motion v12) hay gói mọi hoạt ảnh trong client component.~~ Không cần (spike 21/10): server render tư thế tĩnh của mood, client component thêm chuyển động bằng `useAnimate` của `motion/react-mini` sau hydrate.
