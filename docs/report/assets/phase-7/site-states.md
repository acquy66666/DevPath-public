# Phase 7 — Trạng thái toàn site: 404, lỗi, đang tải, rỗng (22/10/2026)

Task thứ hai của mục "Nền" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): 404 và trang lỗi có Naomi theo bản đồ phản ứng ([thiết kế](../../../ui-ux/thiet-ke-nang-cap-ui-ux.md), mục 5), skeleton theo design system, mọi empty state có Naomi kèm đạo cụ. Nhánh `feature/phase7-site-states`.

## 1. Kiểm kê trước khi sửa

| Loại | Số | Ở đâu |
|---|---:|---|
| `not-found.tsx` | 3 | `app/` (đường dẫn không có), `khoa-hoc/[slug]/`, `cert/[code]/` |
| `error.tsx` | 8 | `app/`, `(learn)/`, `(auth)/`, `khoa-hoc/`, `khoa-hoc/[slug]/`, `cert/[code]/`, `giang-day/`, `quan-tri/` |
| `global-error.tsx` | 0 | lỗi ở root layout rơi về trang có sẵn của Next, tiếng Anh |
| `loading.tsx` | 6 | `(auth)/`, `khoa-hoc/(danh-sach)/`, `giang-day/`, `giang-day/hoi-dap/`, `giang-day/thong-ke/`, `quan-tri/` |
| Skeleton tự vẽ (`animate-pulse`) | 76 chỗ / 42 tệp | phần lớn `h-64 bg-muted/40` có viền, không theo kích thước nội dung |
| Empty state | 28 chỗ | khung nét đứt + icon lucide (một nửa), hoặc chỉ một dòng chữ |

## 2. Ba component mới trong `components/ui/`

| Component | Dùng cho | Ghi chú |
|---|---|---|
| `StatePanel` | 404, lỗi | Naomi 200 px cạnh chữ khi khung rộng ≥ 576 px, 128 px phía trên khi hẹp hơn (container query: thẻ đăng nhập luôn hẹp). `code` ("404") đặt chữ mono. `detail` cho mã lỗi. `mood={null}` ở khu giảng viên/admin |
| `EmptyState` | rỗng | "Chưa có … nào" + cách tạo cái đầu tiên. Cỡ `lg` (trang học viên, Naomi 128 px), `md` (tab, thẻ, khu làm việc, 80 px), `sm` (dropdown, 64 px). Cạnh chữ khi khung ≥ 448 px |
| `Skeleton`, `SkeletonText`, `SkeletonInline`, `SkeletonRegion` | đang tải | Nền `muted`, bo góc của vật nó thay. `SkeletonText` cao đúng line-height của kiểu chữ trong thang. Chỉ nhấp nháy khi không giảm chuyển động (`motion-safe:`). Một thông báo "Đang tải…" mỗi vùng cho trình đọc màn hình |

Naomi ở cả ba chỗ đều **tĩnh** (không truyền `event`): trang 404 hay danh sách rỗng không phải sự kiện vừa xảy ra. Là hình trang trí (`aria-hidden`): tiêu đề đã nói hết.

## 3. Naomi ở đâu

| Chỗ | Mood |
|---|---|
| 3 trang 404 | `lost` (cầm bản đồ ngược) |
| 6 trang lỗi phía học viên + `global-error.tsx` mới | `sorry` (cầm biển "đang sửa") |
| 2 trang lỗi khu giảng viên/admin | không có (thiết kế, mục 2: ở khu làm việc chỉ có ở empty state và lời chào) |
| Giỏ hàng | `empty-cart` |
| Khóa học của tôi, yêu thích, danh sách khóa học khi sàn chưa có khóa nào, danh sách khóa của giảng viên, hàng đợi duyệt, khóa hot (dashboard admin), bảng thống kê từng khóa | `empty-courses` |
| Trang thông báo, chuông | `empty-notifications` |
| Ghi chú, lịch sử nộp bài, mục lục khóa chưa có chương | `empty-notes` |
| Tìm không ra (danh sách khóa học, người dùng, mã giảm giá, cấp giảng viên, hàng đợi khi có từ khóa) | `empty-search` |
| Hỏi đáp, đánh giá, bảng xếp hạng, trợ giảng AI (mở đầu + lịch sử), hộp thư hỏi đáp giảng viên, thống kê giảng viên, banner, danh mục, mã giảm giá, báo cáo, bảng kê, khoản chi | `empty` |

Hai luật rút ra khi làm:

- **Mỗi màn một Naomi.** Tài khoản mới mở `/khoa-hoc-cua-toi` thấy hai chỗ rỗng (khối "XP gần đây" và danh sách khóa). Naomi ở danh sách, khối XP giữ một dòng chữ.
- Dòng "chưa có …" nằm **trong** một thẻ có dữ liệu khác (từng ô của trang xếp hạng tài chính, danh mục con, bảng con của bảng kê, ghi chú dưới biểu đồ) giữ chữ: đó là một ô trống của một bảng, không phải một trang rỗng.

Khu giảng viên/admin: `lib/design/site-states.test.ts` đỏ nếu `components/admin|instructor` gọi thẳng `<Mascot>`; Naomi chỉ tới đó qua `EmptyState`.

## 4. Lỗi tìm ra

1. **"Thử lại" không chữa được lỗi từ máy chủ.** Next 16.3 đưa cho `error.tsx` prop `retry` (tải lại segment rồi render); 8 trang lỗi dùng `reset` cũ, chỉ render lại phần đã có ở trình duyệt. Thử thật bằng [`site-states/retry.cjs`](site-states/retry.cjs): dừng container backend, mở trang khóa học (ra trang lỗi), bật backend, bấm "Thử lại".
   - Với `retry`: trang khóa học hiện lại ngay, cùng tài liệu (không tải lại cả trang).
   - Đối chứng, tạm đổi về `reset`: backend đã sống lại mà trang vẫn kẹt ở trang lỗi suốt 60 s.

   Cả 8 tệp giờ dùng `retry`; test đỏ nếu có tệp quay lại `reset`.
2. **Không có `global-error.tsx`**: lỗi ở root layout (providers) cho người xem trang lỗi có sẵn của Next, tiếng Anh. Giờ có, với Naomi `sorry`, tự nạp `globals.css` + `fonts.css` vì nó thay cả tài liệu.
3. **Skeleton sai kích thước** (mục 5): 31/46 lượt xem có CLS ≥ 0,01, lớn nhất 0,449. Ba nguyên nhân đáng kể ngoài chiều cao sai:
   - khối thành tích trả `null` khi phiên đăng nhập còn đang khôi phục, rồi mới chèn vào, đẩy danh sách khóa học xuống;
   - dòng cấp giảng viên trên trang thống kê cũng trả `null` khi đang tải;
   - carousel banner trang chủ stream với `fallback={null}`, tới sau thì đẩy hero xuống 476 px.
4. **Giọng văn**: trang lỗi đăng nhập "Thử lại giúp mình nhé" (hệ thống tự xưng — design system cấm); trang lỗi không nói lỗi là của ai. Giờ mọi trang lỗi nói "Lỗi phía hệ thống, không phải do bạn", có mã lỗi (mono) khi Next gửi `digest`.
5. README frontend còn ví dụ `<Mascot mood="lost" event />` cho 404 (trái với "tĩnh") và nhắc khối `[data-mascot]` đã xóa ở task Nền. Đã sửa.

## 5. Skeleton đúng kích thước nội dung thật

**Cách làm:** dựng lại khung thật (thẻ, padding, số dòng, chiều cao dòng theo thang chữ), không đặt khối xám ước lượng. Ví dụ `CourseCardSkeleton` có đúng ảnh bìa 16:9, hai badge 22 px, tiêu đề, hai dòng mô tả, giảng viên, dòng số liệu, giá. Chỗ nào có nhãn tĩnh thì nhãn hiện thật, chỉ số liệu là thanh xám (`SkeletonInline` trong khối thành tích). Khu giảng viên có một skeleton mỗi màn (`components/instructor/instructor-skeletons.tsx`). Nó được dùng ở ba chỗ: `loading.tsx`, cổng đăng nhập (chọn theo đường dẫn) và chính trang khi chờ truy vấn đầu. Nhờ vậy ba bước chuyển không lệch nhau.

**Cách đo:** [`site-states/shift.cjs`](site-states/shift.cjs) giữ mọi response API lại 1,2 s để skeleton kịp lên màn hình. Sau đó nó đọc Cumulative Layout Shift khi dữ liệu thay chỗ skeleton. Mỗi route được mở một lượt trước để `next dev` biên dịch xong. Phép đo chạy trên stack dev với tài khoản seed (trang có dữ liệu thật): 23 route × 2 bề rộng = 46 lượt xem, đủ 4 vai. Skeleton đúng kích thước thì không có gì xê dịch: CLS 0.

| | Lượt CLS ≥ 0,01 | Lượt CLS ≥ 0,1 ("kém" theo Web Vitals) | Tổng CLS | Lớn nhất |
|---|---:|---:|---:|---:|
| Trước | 31/46 | 17 | 4,397 | 0,449 |
| Sau vòng 1 (khung thật + mọi danh sách khu làm việc chừa một màn hình) | 20/46 | 4 | 1,198 | 0,111 |
| Sau vòng 2 (bỏ chừa màn hình) | 24/46 | 6 | 1,608 | 0,207 |
| **Sau vòng 3 (chừa màn hình chỉ cho danh sách thường dài)** | **16/46** | **2** | **0,802** | **0,111** |

Vòng 1 và 2 cho thấy cùng một mẹo vừa lợi vừa hại. Footer luôn bám đáy màn hình (`body` `min-h-full` + `main` `flex-1`). Vì thế skeleton ngắn hơn màn hình để footer hiện ra rồi bị nội dung đẩy đi. Ngược lại, skeleton chừa một màn hình mà nội dung thật ngắn thì footer lại bị kéo lên.

Luật chốt (vòng 3) theo độ dài điển hình của từng danh sách:

- **Chừa một màn hình** (`ListSkeleton fill`) cho danh sách thường dài: người dùng, dashboard, danh mục, mã giảm giá, banner, các trang tài chính, cấp giảng viên.
- **Không chừa** cho hàng đợi thường ngắn hoặc rỗng (khóa chờ duyệt, báo cáo) và danh sách của giảng viên.

Log ba vòng: `site-states/shift-rounds.log`. JSON: `shift-before.json`, `shift-after.json` (vòng 3).

| Vai | Trang | 1440 px trước → sau | 375 px trước → sau |
|---|---|---|---|
| khách | `/khoa-hoc` | 0,000 → 0,000 | 0,001 → 0,001 |
| khách | `/khoa-hoc/python-co-ban` | 0,002 → 0,000 | 0,019 → 0,001 |
| học viên | `/` | 0,161 → 0,007 | 0,096 → 0,096 |
| học viên | `/khoa-hoc-cua-toi` | 0,211 → 0,001 | 0,441 → 0,015 |
| học viên | `/gio-hang` | 0,001 → 0,001 | 0,000 → 0,045 |
| học viên | `/yeu-thich` | 0,001 → 0,002 | 0,218 → 0,064 |
| học viên | `/thong-bao` | 0,001 → 0,001 | 0,025 → 0,026 |
| học viên | `/ho-so` | 0,052 → 0,001 | 0,073 → 0,000 |
| học viên | `/bang-xep-hang` | 0,001 → 0,001 | 0,042 → 0,001 |
| học viên | `/khoa-hoc/python-co-ban` | 0,003 → 0,003 | 0,018 → 0,000 |
| học viên | `/hoc/python-co-ban?bai=…` | 0,001 → 0,001 | 0,004 → 0,004 |
| giảng viên | `/giang-day` | 0,001 → 0,001 | 0,066 → 0,024 |
| giảng viên | `/giang-day/thong-ke` | 0,069 → 0,001 | 0,449 → 0,019 |
| giảng viên | `/giang-day/hoi-dap` | 0,001 → 0,001 | 0,104 → 0,024 |
| giảng viên | `/giang-day/cap-bac` | 0,070 → 0,001 | 0,317 → 0,000 |
| giảng viên | `/giang-day/[khóa]` | 0,141 → 0,111 | 0,251 → 0,101 |
| admin | `/quan-tri` | 0,074 → 0,000 | 0,245 → 0,003 |
| admin | `/quan-tri/khoa-hoc` | 0,000 → 0,043 | 0,101 → 0,059 |
| admin | `/quan-tri/bao-cao` | 0,034 → 0,027 | 0,221 → 0,060 |
| admin | `/quan-tri/nguoi-dung` | 0,207 → 0,000 | 0,216 → 0,000 |
| admin | `/quan-tri/danh-muc` | 0,034 → 0,000 | 0,120 → 0,000 |
| admin | `/quan-tri/ma-giam-gia` | 0,056 → 0,001 | 0,136 → 0,025 |
| admin | `/quan-tri/banner` | 0,007 → 0,029 | 0,110 → 0,000 |

**Còn lại, có lý do:**

- **Trình soạn khóa học** (0,111 / 0,101; trước 0,141 / 0,251). Mục lục là danh sách chương dài bao nhiêu thì chưa biết, và nó nằm phía trên form thông tin. API khóa học không trả số chương, nên skeleton không biết trước. Sửa thật là đổi thứ tự khối hoặc API: việc của nhóm màn 9.
- **Giỏ hàng, yêu thích ở 375 px** (0,045 / 0,064). Skeleton là một dòng giỏ / một thẻ khóa, còn tài khoản đo (`nguoimua08`) có giỏ và danh sách rỗng, nên empty state ngắn hơn. Chọn khớp với danh sách có hàng, là trường hợp người dùng thật tới trang này.
- **Trang chủ 375 px** (0,096): khối "Gợi ý cho bạn" chỉ hiện sau khi biết người xem đã đăng nhập. Hiện skeleton sớm hơn thì khách (đa số người mở trang chủ) lại thấy nó biến mất.
- **Header**: chỗ giữ nút tài khoản cao 44 px, nút đăng nhập của khách 44 px, avatar người đã đăng nhập 40 px; lệch 4 px ở hầu hết lượt đo, mức 0,0004. Để nguyên.

## 6. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **31/31** (5 test mới ở `lib/design/site-states.test.ts`: 404 có `lost`, lỗi dùng `retry` và đúng nhân vật theo khu, không `<Mascot>` trong `components/admin|instructor`, không `animate-pulse` ngoài `components/ui/skeleton.tsx`, không `loading.tsx` ở `khoa-hoc/` hay `khoa-hoc/[slug]/`). Lần chạy đầu, test về trang lỗi đỏ vì chữ `reset` trong một comment giải thích; giờ test bỏ comment trước khi đọc |
| `npx tsc --noEmit`, `npm run lint` | sạch |
| `next build` không mạng (`frontend/scripts/build-offline.sh`, `--network none`, stack dev tắt) | xanh: biên dịch 11,5 s, TypeScript sạch, 35/35 trang tĩnh |
| E2E luồng vàng trên stack dev | **1 passed** (43,6 s), không sửa spec |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai) | **0/132**. Lỗi console cùng loại với lượt của task Nền (401 khách hỏi phiên, 404/422 có chủ đích), không có `pageerror`. Kết quả: `site-states/overflow.json` |
| `retry.cjs` (mục 4.1) | trang lỗi có Naomi `sorry`; "Thử lại" đưa trang về sau khi backend sống lại; đối chứng `reset` kẹt 60 s |

## 7. Ảnh — `site-states/before/` và `site-states/after/`

[`site-states/capture.cjs`](site-states/capture.cjs) chụp cùng 56 ảnh cho `PHASE=before` (code của `main` @ `461cc23`, cộng trang xem trước ở dưới, viết trước khi sửa gì) và `PHASE=after`, trên stack dev:

- **`xem-truoc-*`** (22 ảnh): `/dev/trang-thai`, trang chỉ có ở dev. Nó render đúng từng tệp `not-found.tsx`, `error.tsx` (với lỗi giả) và `loading.tsx` của site, vì trang thật chỉ hiện chúng khi có gì đó thiếu, hỏng hay chậm. 17 khung ở 1440 px, 5 khung ở 375 px.
- **`404-trang`, `404-khoa-hoc`, `404-chung-chi`, `tim-khong-ra`** ở 1440 + 375 px: trang thật, khách.
- **`khoa-hoc-cua-toi`, `gio-hang`, `yeu-thich`, `thong-bao`, `giang-day`** ở 1440 + 375 px, **`chuong-thong-bao`**, **`giang-day-thong-ke`**, **`giang-day-hoi-dap`**: tài khoản dùng một lần chưa có gì (học viên kiêm giảng viên).
- **`hoc-ghi-chu`, `hoc-hoi-dap`, `hoc-tro-giang`** ở 1440 + 375 px, **`hoc-lich-su-nop`**, **`danh-gia-khoa-hoc`**, **`giang-day-chuong-trinh`**: tài khoản dùng một lần đã ghi danh khóa Python miễn phí, có một khóa nháp chưa có chương.
- **`quan-tri-bao-cao`** ở 1440 + 375 px, **`quan-tri-loi-nhuan`**, **`quan-tri-nguoi-dung`** (tìm không ra): admin seed, chỉ đọc.
- **`after/loi-khoa-hoc-that-1440.png`**: trang lỗi thật khi backend tắt (`retry.cjs`).

Hai tài khoản dùng một lần (`@e2e.devpath.example`) bị `scripts.purge_e2e` gỡ ở cuối mỗi lượt chụp.

## 8. Để lại

- **Ô chọn ở thanh lọc admin cắt dấu** ("Mọi vai trò" hiện thành "Moi vai trò", "trạng" thành "trana"): `NativeSelect` 40 px / 16 px bị ép `h-9` ở `admin-user-list` và các thanh lọc khác. Có từ task Nền (ảnh "trước" y hệt), không thuộc task này: việc của nhóm màn 10.
- Skeleton của trang đăng ký thấp hơn form thật một ô nhập (một `loading.tsx` dùng chung cho cả hai trang).
- Design system trên Claude Design chưa có preview `EmptyState`, `StatePanel`, `Skeleton` (gate "design system khớp code").

## 9. Chạy lại

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/capture.cjs
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/shift.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/site-states/retry.cjs   # dừng backend vài giây
cd frontend && npm test && npm run lint
```
