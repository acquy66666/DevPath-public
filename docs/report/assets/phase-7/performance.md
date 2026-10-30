# Phase 7 — Hiệu năng (Lighthouse mobile) "sau" (30/10/2026)

Task "Hiệu năng" của [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): Lighthouse mobile ba trang của bước "trước" — LCP ≤ 2,5 s, CLS ≤ 0,1, không tệ hơn số "trước"; nhân vật + chuyển động thêm ≤ 50 KB gzip ở màn đầu. Cột "trước" và cách đo ở [`before.md`](before.md); cột "sau" đi **đúng đường đó** (§7 của `before.md`): stack demo `devpath-demo` deploy từ nhánh `feature/phase7-performance`, dữ liệu `seed_study`/`seed_sales` nạp lại ngay trước, Chrome trỏ `devpath-01.me` vào nginx 127.0.0.1 (0/9 lượt có beacon Cloudflare), Lighthouse 13.5.0 mobile `simulate`, 3 lượt mỗi trang, bảng lấy lượt giữa. Dữ liệu thô ở [`after/`](after/).

## 1. Kết quả

| Trang | LCP trước | **LCP sau** | 3 lượt sau | CLS sau (max) | TBT sau | Hiệu năng trước → sau |
|---|---:|---:|---|---:|---:|---|
| Trang chủ | 2,56 s | **2,26 s** | 2,263 / 2,265 / 2,266 | 0,001 | 102 ms | 96 → 98 |
| Chi tiết khóa học | 2,56 s | **2,40 s** | 2,418 / 2,402 / 2,416 | 0,001 | 152 ms | 95 → 96 |
| Trang học | 3,31 s | **2,41 s** | 2,406 / 2,113 / 2,407 | 0,000 | 70 ms | 91 → 97 |

- **Cả ba đạt LCP ≤ 2,5 s và CLS ≤ 0,1, không trang nào tệ hơn "trước".** Lượt CLS 0,178 của trang chủ ở cột "trước" không còn (banner đã xuống dưới hero từ nhóm 2).
- Truy cập 96/100/95 → **100/100/100**. Best practices giữ 96/96/100 (lỗi console `401 /auth/refresh` của khách — như thiết kế, `before.md` §3). SEO trang học 60 vì `noindex` có chủ đích.
- **axe 12 trang: 3 vi phạm → 0** (`after/axe.json`; hai lỗi critical đã sửa ở nhóm 6 và nhóm 9).
- Máy: Windows 11, 8 CPU, stack dev dừng, **không chạy ứng dụng nặng**. LCP quan sát thật (chưa giả lập) ở 9 lượt "sau" là 141–308 ms, cùng cỡ cột "trước" (101–467 ms), nên hai cột so được.

### First Load JS (gzip mức 9, `after/bundle-stats.json`)

| Route | Trước | Sau | Δ |
|---|---:|---:|---:|
| `/` | 208,9 KB | **177,6 KB** | −31,3 |
| `/khoa-hoc` | 205,6 | 178,6 | −27,0 |
| `/khoa-hoc/[slug]` | 214,5 | 188,6 | −25,9 |
| `/hoc/[slug]` | 273,8 | 211,8 | −62,0 |
| nhỏ nhất (`/chinh-sach-bao-mat`) | 204,6 | 175,4 | −29,2 |

Ngân sách "nhân vật + chuyển động thêm ≤ 50 KB ở màn đầu" thành **âm 31 KB**: Phase 7 thêm Naomi, toast, ô soạn, trình chiếu kết quả… mà màn đầu trang chủ vẫn nhẹ hơn trước. Trước khi sửa (build `main` @ `4355381`, cuối Phase 7) màn đầu trang chủ là 239,8 KB (+30,9 KB so với "trước") — tức là ngân sách đang dùng 62 % thì task này đưa về âm.

**JS tải trong 1,5 s sau `load`** (`after/js.json`, cả chunk tải lười): 215,5 → 275,9 KB. Phần tăng là những thứ **cố ý hoãn tới sau khi trang đã tải xong và rảnh**: menu Radix của header, Toast, bản vẽ Naomi, và các route mà `<Link>` của Next tự tải trước khi rảnh (`/khoa-hoc`, `/dang-ky`, `/dang-nhap`). Chúng không nằm trên đường tới LCP và không làm TBT tăng (TBT 70–188 ms, như trước).

## 2. Lighthouse tính LCP thế nào — điều quyết định cách sửa

Với `simulate`, Lighthouse đo trang một lần không giới hạn, rồi **mô phỏng lại** quá trình tải trên mạng 1,6 Mbps / RTT 150 ms và CPU chậm 4×. Mô phỏng đó tính **mọi request đã bắt đầu trước thời điểm LCP quan sát được**, kể cả JS `async` mà trang không cần để vẽ chữ. Hai hệ quả, đo được:

1. **LCP nhảy theo bậc 150 ms (một RTT)**: 2.557 → 2.709 → 2.860 ms. Mỗi bậc ≈ 25–30 KB tải trước LCP. Bớt 10 KB có thể không đổi gì; bớt đúng chỗ thì xuống hẳn một bậc. Trang chủ ở bước cuối đổi bậc chỉ vì HTML giảm 21,1 → 16,7 KB: HTML + CSS (~43 KB) đã nằm sát ngưỡng một vòng TCP.
2. **Trang càng nhanh trên máy thật, chunk "tải lười" càng dễ bị tính**: chunk tải ngay sau hydrate bắt đầu ở ~205 ms, trước LCP quan sát ~240 ms, nên vẫn bị mô phỏng tính vào (trang chủ dao động 2,71 ↔ 3,16 s giữa các lượt). Vì vậy menu/toast phải hoãn tới sau `load` + lúc rảnh, không chỉ "sau hydrate".

Cũng vì nhân CPU quan sát lên 4 lần, **số đo vô nghĩa khi máy bận**: lượt đầu trên `main` khi một trò chơi đang chạy ra LCP 3,4 / 3,0 / 5,1 s, TBT 1–2,6 s (LCP quan sát thật chậm 3–5× lượt "trước"). Mọi số trong tài liệu này đo khi máy yên.

## 3. Tìm và sửa

Công cụ: `measure.cjs` (3 lượt × 3 trang), [`performance/probe.cjs`](performance/probe.cjs) (một lượt Lighthouse với `--blocked-url-patterns` — chặn một nhóm tệp để xem LCP đổi bao nhiêu), và `next experimental-analyze --output` (bộ phân tích bundle của Turbopack, chạy trong container không mạng).

| # | Phát hiện | Sửa | Đo |
|---|---|---|---|
| 1 | **Trang học** chỉ vẽ tiêu đề bài (phần tử LCP) sau chuỗi 3 request nối nhau: làm mới phiên → khóa theo slug → tiến độ/mục lục | Máy chủ tải sẵn khóa + mục lục (công khai, như nhau với khách và học viên; cookie phiên chỉ gửi tới `/api/v1/auth` nên phần riêng của học viên vẫn ở trình duyệt). Khung chờ vẽ **tiêu đề bài thật** từ mục lục; tiến độ hỏi ngay sau làm mới phiên | LCP quan sát = FCP; 3,31 → 2,26–2,56 s |
| 2 | Lượt đầu sau sửa 1: **CLS 0,214** ở trang học — tiến độ giờ có thể về trước bài học, trang vẽ với ô giữ chỗ nhỏ rồi dài ra, đẩy mục lục (dưới bài trên điện thoại) | Lần mở đầu giữ khung chờ tới khi bài học cũng về; đổi bài sau đó như cũ | CLS 0,000 ở 3/3 lượt |
| 3 | **Phông `latin-ext` tải ở mọi trang tiếng Việt** (Lexend 34 KB): dải `latin-ext` của Google chồng dải `vietnamese` (ă đ ĩ ũ ơ ư ỳ–ỹ ₫) | Bỏ khỏi `latin-ext` đúng các ký tự tệp `vietnamese` của từng font có (đối chiếu `cmap`; Geist Mono thiếu ₫ nên giữ). Quét HTML 3 trang: 0 ký tự còn cần `latin-ext` | −34 KB trước LCP ở mọi trang |
| 4 | Khung chung có Radix Menu + floating-ui (~23 KB) cho menu điện thoại/chuông/tài khoản, Radix Toast | Nút vẽ ngay (giữ chỗ đúng từng pixel, `header-buttons.tsx`); menu điện thoại + Toaster tải sau `load` + lúc rảnh (`useAfterLoad`), chạm/focus sớm thì tải ngay và mở/nhận focus; chuông + menu tài khoản chỉ tải khi đã đăng nhập | Khung chung 232,9 → 175,4 KB (cùng sửa 5–8) |
| 5 | Trang học tải sẵn trình soạn code, quiz, Hỏi đáp, trợ giảng AI, bộ Markdown, "Học tiếp theo" dù bài video không cần | Mỗi phần một chunk (`learn/lazy-parts.tsx`) với khung chờ của chính nó; Markdown bắt đầu tải ngay khi mục lục cho biết bài là bài đọc | `/hoc/[slug]` 330,0 → 211,8 KB |
| 6 | Hộp thoại "Báo cáo" (Radix Dialog + form, ~26 KB) nằm trong màn đầu trang chi tiết | Nút vẽ ngay, hộp thoại tải ở lần bấm đầu (`report-dialog.tsx`) | — |
| 7 | **Turbopack đóng gói lặp component Naomi có hoạt ảnh vào 3 chunk** cùng tải ở trang chủ (`error.tsx` gốc, khối minh họa, `not-found`), ~6 KB mỗi bản — trong khi ở cả ba chỗ Naomi đứng yên | `<LazyNaomiStill>`: Naomi tĩnh không có mã hoạt ảnh, mã tải lười; HTML máy chủ vẫn có hình. Dùng ở StatePanel, EmptyState, khối minh họa. Thử bản server component trước: SVG ~8 KB đi hai lần (HTML + payload RSC), trang chi tiết lên một bậc → bỏ | Trang chủ 2,71 → 2,57 s |
| 8 | Geist Mono không preload, chỉ được phát hiện sau khi CSS về → thêm một tầng chờ ở trang có code trong màn đầu; tệp `latin` 23 KB mà khối code và bìa khóa học chỉ dùng ASCII | Preload ở trang chủ, danh sách, chi tiết; tách `geist-mono-latin` thành `ascii` (14 KB, được preload) + `latin-rest` (12 KB) bằng `frontend/scripts/split-mono-ascii.py` | Chặn thử Geist Mono: −1 bậc ở cả hai trang |
| 9 | 3 ảnh banner PNG (63 KB) tải trước LCP dù banner nằm dưới hero; `loading="lazy"` không đủ (ngưỡng của Chrome trên điện thoại 1.250–2.500 px) | Chỉ gắn `src` khi carousel cách màn hình ≤ 200 px (IntersectionObserver) | −63 KB trước LCP ở trang chủ |
| 10 | `favicon.ico` 26 KB, ưu tiên High, ở mọi trang — **logo mặc định của create-next-app** chưa từng đổi | `app/icon.svg` 254 byte (ô màu `primary`, chữ "D" trắng — giả định thiết kế, DevPath chưa có logo dạng hình) | −26 KB |
| 11 | HTML trang chủ chứa **hai bản** "Khóa học mới" + "Duyệt theo chủ đề": skeleton chờ của Suspense và bản thật stream ngay sau (API trả trong vài ms, skeleton không bao giờ hiện) | Bỏ hai Suspense đó; trang chủ chờ API như trang chi tiết (hai khối vẫn tự ẩn khi API lỗi) | HTML 21,1 → 16,7 KB; trang chủ 2,56 → 2,26 s |
| 12 | nginx nén ở mức mặc định 1 | `gzip_comp_level 5` | ~−15 KB văn bản ở lượt tải đầu trang chủ |

Phần còn lại trước LCP ở trang chủ: HTML 17 KB, CSS 22 KB (một tệp Tailwind cho cả site), Lexend 54 KB, Geist Mono ASCII 14 KB, JS ~180 KB — trong đó khung React + Next ~150 KB không bỏ được.

## 4. Đánh đổi, ghi lại

- Trang chủ không còn stream: byte đầu tiên chờ hai lời gọi API (~20–30 ms trên máy dev). Backend treo thì trang chủ treo như trang chi tiết — trước đây phần đầu trang vẫn hiện.
- Menu điện thoại và toast có trễ ~vài trăm ms sau khi trang tải xong; bấm sớm hơn thì menu mở khi mã về (không mất cú bấm, không mất focus).
- Banner bắt đầu tải khi người đọc cuộn tới gần (200 px).
- Favicon mới là giả định; đổi bằng cách thay `frontend/app/icon.svg`.

## 5. Kiểm

- `npm test` 156/156, `tsc` + ESLint sạch; `next build` production trong image (13 lần deploy).
- axe 12 trang: 0 vi phạm (`after/axe.json`).
- Hồi quy hình ảnh và E2E: §6.

## 6. Hồi quy

Trên stack sạch `devpath-visual` (chỉ `scripts.seed`, dựng lại từ `down -v`), đúng cách của [`visual-regression.md`](visual-regression.md):

- `npm run test:visual`: **24/24 passed**, không cập nhật baseline nào — header (nút giữ chỗ thay menu), Naomi tĩnh, trang chủ không còn Suspense đều ra đúng từng điểm ảnh như trước.
- `npm run test:e2e` (`COMPOSE_PROJECT_NAME=devpath-visual`): **10 passed** — axe 4 vai × 1440/375 (gồm menu điện thoại đang mở), luồng vàng, luồng vàng bằng bàn phím.

## 7. Chạy lại

Như `before.md` §7 với `LABEL=after`. `measure.cjs` giờ chạy lại một lượt Lighthouse bị lỗi trace `NO_NAVSTART` (gặp khi máy bận). Trước khi đo: không mở ứng dụng nặng, `docker run --rm alpine true` nên dưới ~0,7 s.

## 8. Tệp

| Tệp | Nội dung |
|---|---|
| `after/summary.json` | Tóm tắt: build, đường đi, First Load JS 3 route, 9 lượt Lighthouse + trung vị, axe, kết quả purge. `commit` ghi `c82e019` vì đo trên cây làm việc trước commit cuối của nhánh; code đo chính là commit cuối của nhánh |
| `after/bundle-stats.json`, `after/js.json`, `after/axe.json`, `after/lighthouse/*.json` | Như `before/` |
| `performance/probe.cjs` | Một lượt Lighthouse có chặn URL, để thử một thay đổi trước khi làm |
