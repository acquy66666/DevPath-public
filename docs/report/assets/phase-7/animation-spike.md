# Spike công nghệ hoạt ảnh — Naomi `celebrate` (21/10/2026)

Task "Spike công nghệ hoạt ảnh" của [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md). **User chốt 21/10: chỉ SVG + Motion, không làm Rive** (câu hỏi 3, mục 10 của [tài liệu thiết kế](../../../ui-ux/thiet-ke-nang-cap-ui-ux.md)). Vì vậy spike không so Motion với Rive. Nó so **ba cách chạy cùng một phản ứng trên cùng một SVG**, để chọn cách nào vào component `<Mascot />`:

| Biến thể | Cách chạy | JS riêng |
|---|---|---|
| `static` | SVG tĩnh trong cùng khung trang — **mốc để trừ** | không |
| `css` | CSS `@keyframes`, sinh từ cùng dữ liệu biên đạo | không (server component) |
| `mini` | `motion/react-mini` — `useAnimate` mỏng trên Web Animations API | có |
| `motion` | `motion/react` đầy đủ — `useAnimate` với `animate()` lai, giá trị transform độc lập (`y`, `scaleX`, `rotate`) | có |

Cả ba bản động đọc **một nguồn biên đạo** ([`animation-spike/src/choreography.json`](animation-spike/src/choreography.json)): thời lượng `duration-mascot` 2400 ms, đường cong lấy từ token `ease-*`. Naomi khom lấy đà, nhảy 30 đơn vị, tiếp đất bằng `ease-overshoot`. Bóng co lại khi nhảy, đuôi đung đưa, tay giơ con bọ vẫy ba nhịp. Ba ngôi sao bung lần lượt, cách nhau 120 ms. Hết 2400 ms thì mờ chéo 220 ms (`duration-base`) về tư thế `rest`. Bản vẽ là hai tệp sinh từ `build.cjs`: `naomi-celebrate.svg` và `naomi-rest.svg`.

## Cách đo

[`animation-spike/run.cjs`](animation-spike/run.cjs) chép `src/` vào `frontend/app/(spike)/spike-naomi/` rồi chạy các bước dưới đây. Sau khi đo, **xóa thư mục đó khỏi frontend** — spike không để lại gì trong app.

1. **Build** bằng `next build` 16.3.1 trên máy. `NEXT_PUBLIC_API_BASE_URL=""` (cùng origin, đúng như image production).
2. **Dung lượng.** First Load JS lấy bằng chính hàm `writeRouteBundleStats` của Next, giống [`before.md`](before.md). JS/CSS tải thật đo bằng cách mở trang trong Chrome rồi phát lại một lần. Gzip mức 9.
3. **CSP.** `next start` ở 127.0.0.1:3107, rồi Chrome 155 (Playwright `channel: "chrome"`). **Mọi tài liệu HTML được gắn đúng chuỗi `Content-Security-Policy` đọc từ `infra/nginx/snippets/security-headers.conf`.** Đếm sự kiện `securitypolicyviolation` và lỗi console.
4. **CPU.** Lấy thời gian CPU luồng chính (`Performance.getMetrics`, `timeDomain: threadTicks`) trong cửa sổ 3 s quanh một lần phát lại. Mỗi biến thể 7 lượt, lấy trung vị, ở mức bóp CPU 1× và 4× (4× là mức Lighthouse mobile). Song song ghi khung `requestAnimationFrame`.
5. **Giảm chuyển động.** Ở `prefers-reduced-motion: reduce`, lấy 29 mẫu trong 3 s: có animation nào chạy không, lớp nào có transform không, độ mờ của hai bản vẽ.
6. **Ảnh khung** ở ≈ 250/700/1100/1800/2900 ms và ở chế độ giảm chuyển động.

Chạy lại (không cần stack nào, ~9 phút):

```bash
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/animation-spike/run.cjs
```

`motion@14.2.0` được cài bằng `npm install --no-save`, không vào `package.json`. Bản 14.5.0 ra đúng hôm đo, còn 14.2.0 đã ra được 8 ngày.

## Kết quả

### Dung lượng tải (gzip)

| Biến thể | First Load JS | Δ JS so với `static` | Δ CSS | Tệp thêm |
|---|---|---|---|---|
| `static` | 205,0 KB | — | — | — |
| `css` | 205,0 KB | **0** | +0,6 KB | 1 tệp CSS |
| `mini` | 210,3 KB | **+5,3 KB** | 0 | 1 chunk (5,7 KB gzip, gồm cả component) |
| `motion` | 230,6 KB | **+25,6 KB** | 0 | 2 chunk (21,5 + 4,6 KB) |

Ngân sách của phase: nhân vật + Motion thêm ≤ 50 KB gzip ở màn đầu ([`before.md`](before.md)). Cả ba đều lọt, nhưng riêng `motion/react` đầy đủ đã ăn **một nửa** ngân sách trước khi có hình nào.

### CPU luồng chính mỗi lần phản ứng (ms, trung vị 7 lượt)

| Biến thể | 1×: tổng | script | style | **phần của hoạt ảnh** (trừ `static`) | 4×: tổng | **phần của hoạt ảnh** |
|---|---|---|---|---|---|---|
| `static` | 54,1 | 9,2 | 1,9 | — | 74,3 | — |
| `css` | 168,5 | 9,5 | 23,7 | **114,5** | 234,4 | **160,2** |
| `mini` | 181,2 | 11,7 | 26,5 | **127,1** (+11 %) | 252,0 | **177,8** (+11 %) |
| `motion` | 227,3 | 29,4 | 60,0 | **173,2** (+51 %) | 315,6 | **241,4** (+51 %) |

Dải 7 lượt ở 1× gần như không chồng nhau: `css` 162,7–178,6, `mini` 174,6–191,9, `motion` 220,9–240,7. Số đầy đủ, kể cả từng lượt và cửa sổ không phát, ở [`results.json`](animation-spike/results.json).

**Cái gì đang chạy giữa phản ứng** (`document.getAnimations()` ở ~800 ms):

| Biến thể | Đang chạy |
|---|---|
| `css` | 9 `CSSAnimation` |
| `mini` | 17 `Animation` WAAPI (mỗi thuộc tính của mỗi lớp một cái) |
| `motion` | Chỉ 6 `Animation` WAAPI, cho độ mờ. **Mọi transform trên SVG chạy bằng JS**: ghi `style.transform` mỗi khung, nên script tăng gấp 3 và style recalc gấp 2,5 |

**Khung hình: không biến thể nào rớt khung.** Ở 1× cả bốn đều 180/180 khung, p95 16,8 ms, 0 khung > 25 ms. Ở 4× được 177–179 khung với 1–2 khung > 25 ms, và chính bản `static` cũng có 1 khung như vậy.

Phần lớn chi phí là vẽ lại SVG, và **cách nào cũng phải trả**. Chrome không đưa transform của phần tử con trong SVG lên compositor, nên mỗi khung là một lần vẽ lại trên luồng chính (~0,7 ms/khung ở 1×). Cách chạy chỉ quyết định phần cộng thêm.

### CSP, giảm chuyển động

| | `css` | `mini` | `motion` |
|---|---|---|---|
| Vi phạm CSP (policy production, không `unsafe-eval`, không `wasm-unsafe-eval`) | 0 | 0 | 0 |
| `reduce`: animation chạy / lớp nào có transform | không / không | không / không | không / không |
| `reduce`: đứng ở tư thế `celebrate` (cả ngôi sao), không đổi sang `rest` | có | có | có |

Lỗi console duy nhất ở cả bốn trang là 401 của `/auth/refresh`: script trả lời như với khách chưa đăng nhập, vì không có backend.

### Công làm

Đếm số dòng mã, bỏ dòng trống và chú thích:

| Phần | Số dòng | Ghi chú |
|---|---|---|
| Phần chung, cách nào cũng cần | 55 | Khung hai bản vẽ chồng nhau (25), CSS điểm xoay (13), bọc lớp cho SVG (17) |
| `css` | 33 | Hàm sinh `@keyframes` từ dữ liệu. Không có JS lúc chạy |
| `mini` | 59 | Component 37 + đọc biên đạo 22 |
| `motion` | 54 | Component 32 + đọc biên đạo 22. Cộng thêm **một cái bẫy** chỉ lộ ra khi đo (bên dưới) |

Bốn điều spike tìm ra và component thật phải làm theo:

1. **Transform của CSS thay thuộc tính `transform` của SVG, chứ không cộng vào.**
   - Áp vào cách nào cũng vậy: CSS, WAAPI hay Motion.
   - `#naomi` (`translate(0 -8)`) và từng ngôi sao (mỗi cái có `translate` + `scale` đặt chỗ riêng) cần một `<g>` trống bọc ngoài để làm chuyển động.
   - Spike bọc lớp bằng script. Còn component thật thì `build.cjs` phải sinh sẵn các lớp bọc đó.
2. **Motion đầy đủ tự ghi `transform-box: fill-box` vào phần tử SVG nó biến đổi.**
   - Điểm xoay viết bằng toạ độ bản vẽ (`transform-box: view-box`) vì thế bị hiểu thành độ lệch tính từ khung của chính lớp đó.
   - Lượt đo đầu: vai Naomi trôi 17 px, cái bóng trượt sang phải.
   - Phải truyền `transformBox: "view-box"` vào từng lần `animate()` thì mới đúng. Sau khi sửa, vai lệch ≤ 1 px giữa ba biến thể.
   - CSS và `mini` đúng ngay từ đầu.
3. **`viewBox` 200×200 xén mất đỉnh đầu khi Naomi nhảy**, ở cả ba biến thể. Cần `overflow: visible` trên `<svg>`, và khung chứa không được `overflow: hidden`.
4. **Hai bản vẽ chồng nhau thì trùng `id`** (`#tail`, `#naomi`…). Selector khi đó bắt cả lớp của bản đang ẩn. Spike đổi id của bản `rest`. Component thật nên gọi lớp bằng `data-layer` thay cho `id`: một trang có hai Naomi cũng trùng id như vậy.

Ảnh: [`frames/contact-sheet.png`](animation-spike/frames/contact-sheet.png) ghép ba hàng (một hàng một biến thể) × sáu cột, năm cột thời điểm + chế độ giảm chuyển động. Ảnh lẻ nằm cùng thư mục. Ba hàng ra cùng một chuyển động. Mốc thời gian chỉ gần đúng: lệnh chụp được gọi sau `setTimeout`, cộng thêm độ trễ của chính lần chụp.

## Quyết định

**Component `<Mascot />` chạy bằng SVG + `motion/react-mini`. `motion/react` đầy đủ chưa vào dự án.** Ghi ở [`decisions.md`](../decisions.md) § "Hoạt ảnh Naomi bằng motion/react-mini". Lý do:

- **So với Motion đầy đủ**, `mini` nhỏ hơn 5 lần (5,3 so với 25,6 KB) và tốn ít hơn 27 % CPU cho cùng một phản ứng (127 so với 173 ms). Nó chạy transform trên WAAPI thay vì ghi style từng khung bằng JS, và không có bẫy `fill-box`. Các thứ Motion đầy đủ có mà `mini` không có (`AnimatePresence`, `layout`, lò xo, motion value) thì bộ biểu cảm không cần đến.
- **So với CSS thuần**, `mini` đắt hơn 5,3 KB và 11 % CPU. Đổi lại, component điều khiển được phản ứng lúc chạy:
  - dừng phản ứng cũ khi sự kiện mới tới (`mini` tự dừng animation cũ trên cùng thuộc tính);
  - chờ `.finished` để báo React là đã về tư thế nghỉ;
  - lấy khung hình từ prop, ví dụ `grading` chạy theo "test k/n";
  - giữ biên đạo trong TypeScript có kiểm kiểu, thay vì sinh một tệp CSS cho mỗi mood.
- **Không có gì phải trả thêm về CSP hay truy cập.** Cả ba cách 0 vi phạm dưới policy production, cả ba đứng yên đúng nghĩa khi `reduce`.
- **SSR không cần Motion.** Server render sẵn tư thế tĩnh của mood. JS chỉ thêm chuyển động sau hydrate, nên trước hydrate, khi tắt JS hay khi `reduce`, người dùng vẫn thấy đúng hình. Vì vậy không cần `motion/react-client` (câu hỏi ở mục 11 của tài liệu thiết kế).

**Đường lui:** nếu ngân sách 50 KB bị nhóm màn khác ăn hết, cùng dữ liệu biên đạo sinh được `@keyframes` (hàm `keyframesCss()` của spike) với 0 KB JS.

**Khi nào mới thêm `motion/react` đầy đủ:** chỉ khi một task sau thật sự cần exit animation, `layout` hoặc lò xo. Khi đó tải lười theo route và đo lại theo ngân sách: cộng ~21,5 KB gzip, phần lõi dùng chung.

Rive không được đo: user chốt không dùng. Nên spike này không kết luận gì về Rive.
