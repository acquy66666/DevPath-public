# Phase 7 — Nhóm màn 9: Khu giảng viên (27/10/2026)

Nhóm màn 9 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): tổng quan, tạo khóa, soạn khóa (mục lục kéo-thả, bài tập code, sinh quiz AI), thông tin khóa, thống kê, cấp bậc, Hỏi đáp. Nhánh `feature/phase7-instructor`, từ `main` sau PR #128. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 9: Giảng viên"**: <https://claude.ai/artifact/2iru9SgcxvnJi3qzSAEYZU>. Bản trong repo: [`docs/ui-ux/instructor/canvas/`](../../../ui-ux/instructor/canvas/project/canvas.json).

- **7 artboard:** tổng quan 1440 (lời chào + việc đang chờ + danh sách có lọc) và 375; tạo khóa + ba trạng thái trống (chưa có khóa, mục lục trống, hộp thư trống); soạn khóa tab Nội dung với bài tập code đang mở; tab Thông tin của khóa bị từ chối với gợi ý trước khi gửi duyệt; bài trắc nghiệm có dải sinh câu hỏi AI và 2 câu chờ duyệt; hộp thư Hỏi đáp.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 4 hình `wave`, `empty`, `empty-courses`, `empty-notes` chép từ canvas linh vật.
- **Dữ liệu thật** trên CSDL dev: khóa, mục lục và câu quiz của Trần Minh Khoa ("Python cơ bản cho người mới bắt đầu", "Kiểm tra: ép kiểu"). Trạng thái "bị từ chối"/"bản nháp" của hai khóa và ba câu hỏi Hỏi đáp trên mockup là minh họa (CSDL dev không có câu hỏi nào).
- **Duyệt:** chưa có lời duyệt của user khi code; làm theo mockup, giả định ghi ở đây và ở `decisions.md`.
- **Khác mockup:** loại bài trong dòng mục lục là biểu tượng chứ không phải chữ viết tắt; nút trong dòng giữ 36 px (mockup vẽ 32 px); thống kê và cấp bậc không có artboard riêng — chỉ đổi đầu trang và màu.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Điều hướng** | Mỗi trang một liên kết "← …"; trang danh sách mang 4 nút Hỏi đáp/Thống kê/Cấp bậc/Tạo khóa học | Thanh "Giảng dạy" dưới header: Khóa học · Hỏi đáp (huy hiệu số câu chờ) · Thống kê · Cấp bậc, `aria-current`, + "Tạo khóa học" (nút chính ở tổng quan, viền ở trang khác, ẩn ở trang tạo khóa). Điện thoại: thanh cuộn ngang, nút vào trang |
| **Tổng quan** | Tiêu đề "Khóa học của tôi" + danh sách thẻ chữ | Lời chào "Chào <tên>" với Naomi `wave` đứng yên, dòng đếm khóa/học viên/việc. Thẻ **"Việc đang chờ"**: câu hỏi chưa trả lời → khóa bị từ chối ("Xem lý do" mở thẳng tab Thông tin) → bản nháp ("Soạn tiếp"). "Khóa học của bạn" có chip lọc theo trạng thái (kèm số, chỉ trạng thái có khóa); mỗi dòng có ảnh bìa, giá · học viên · thời lượng · ngày cập nhật, badge trạng thái theo màu nghĩa |
| **Tạo khóa** | Form trong thẻ | Breadcrumb, form + cột "Sau bước này" (3 bước tới khi lên trang công khai) |
| **Soạn khóa** | Một trang dọc: mục lục → thông tin → trạng thái (cuộn qua mục lục mới tới nút gửi duyệt) | Breadcrumb, tiêu đề + badge + "Xem trang công khai". Hai tab **Nội dung / Thông tin khóa học** (ở URL `?tab=thong-tin`, cả hai luôn gắn nên bài sửa dở không mất). Cột phải dính: thẻ **Trạng thái** (biểu tượng + câu theo trạng thái, lý do từ chối, nút "Gửi duyệt"/"Gửi duyệt lại"/"Gỡ khỏi trang công khai", và với bản nháp/bị từ chối: **"Trước khi gửi duyệt" — gợi ý, không bắt buộc, x/4**) + thẻ **Mục lục** (đếm chương, video, bài đọc, bài tập code, trắc nghiệm, bài học thử). "Xóa khóa học" xuống cuối tab Thông tin |
| **Mục lục** | Thẻ "Nội dung khóa học"; chương ghi "N bài học"; thêm bài bằng ô chọn loại | Chương: "CHƯƠNG N" + tên + tóm tắt "6 bài · 4 video · 1 bài tập code · 1 trắc nghiệm". Dòng bài: ô biểu tượng loại, bài đang mở viền ngọc + nền nhạt + "· đang sửa" + nút thu gọn. Thêm bài: **4 nút chọn loại** (radio) + tên + "Thêm bài". Thêm chương: khung viền đứt |
| **Khung sửa bài** | Thông báo "Đã lưu" đẩy cả khung xuống; nút Lưu/Đóng ở cuối | Thanh cuối: "Cho học thử" bên trái; "Đã lưu bài học." (vùng `role="status"`) + Đóng + Lưu bên phải. Bài tập code: nhóm "Đề bài và code mở đầu" và "Test case" có tiêu đề |
| **Soạn quiz** | Badge hổ phách viết tay, đáp án đúng `emerald` | "Sinh câu hỏi bằng AI" là dải nền `info-soft`. "Câu hỏi · 4 câu · 2 chờ duyệt"; câu chờ duyệt nền `warning-soft`, badge `warning`; đáp án đúng đậm `success-text` có dấu tích + chữ ẩn "Đáp án đúng"; phương án xếp 2 cột; dải xuất bản nói còn bao nhiêu câu chưa duyệt |
| **Hỏi đáp** | Liên kết quay lại, ô tích "Chỉ câu chưa trả lời" | Tab **"Chờ trả lời · N" / "Tất cả"**, ô chọn khóa bên phải; trống: Naomi `empty` + "Xem tất cả câu hỏi" |
| **Thống kê, Cấp bậc** | Liên kết quay lại; màu `emerald`/`red`/`amber` viết tay | Bỏ liên kết (thanh điều hướng thay), tiêu đề theo thang chữ, màu theo token (`success-text`, `destructive-text`, `warning*`) |
| **Skeleton** | Khung cũ; `giang-day/loading.tsx` luôn vẽ skeleton danh sách cho mọi route con | Dựng lại theo khung mới (thanh điều hướng, lời chào + việc chờ + dòng có ảnh bìa, tab + cột phải). `loading.tsx` chọn skeleton theo đường dẫn |

**Naomi** (thiết kế mục 4: ở khu làm việc chỉ ở empty state và lời chào), mỗi màn tối đa một Naomi, luôn đứng yên:

| Màn | Mood |
|---|---|
| Tổng quan — lời chào | `wave` |
| Chưa có khóa học | `empty-courses` |
| Mục lục trống | `empty-notes` |
| Hộp thư Hỏi đáp trống | `empty` |

## 3. Lỗi tìm ra khi làm

- **Thanh tỉ lệ ở thống kê là `role="meter"` không có giá trị** khi khóa chưa có học viên (tỉ lệ `null`): axe báo `aria-required-attr` (serious). Có từ Phase 6.5, chỉ lộ ở trang thống kê của giảng viên mới. Giờ chưa có số thì thanh là trang trí, chữ "—" bên cạnh nói đủ (`course-stats-table.tsx`, `course-funnel.tsx`).
- **`giang-day/loading.tsx` vẽ skeleton danh sách khóa cho mọi route con** (soạn khóa, tạo khóa, cấp bậc), nên mở một khóa thì thấy khung danh sách rồi mới đổi. Giờ chọn theo đường dẫn.
- **Dev server trong container giữ bản cũ sau khi đổi nhánh** (trang chủ 500 vì `GoogleMark` "không tồn tại"; sau đó axe vẫn thấy thanh `meter` đã sửa) — khởi động lại container frontend là hết. Đã có trong ghi nhớ dự án, ghi lại vì lặp lại hai lần trong nhóm này.
- Lỗi của chính script, ghi lại cho lần sau: radio ẩn (`sr-only`) trong nhãn thì Playwright không `check()` được — bấm vào nhãn; tóm tắt chương có hai bản (điện thoại/màn rộng), tìm phải lọc `visible=true`.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **139/139** (6 test mới ở `lib/instructor/teaching-view.test.ts`: chip lọc chỉ cho trạng thái có khóa, thứ tự việc đang chờ và đích của từng việc, dòng chào, tóm tắt chương, đếm mục lục, gợi ý trước khi gửi duyệt; `site-states.test.ts` cho đúng một Naomi ở lời chào và chỉ đứng yên) |
| `tsc --noEmit`, `npm run lint` | lint sạch; tsc trên máy chỉ báo một lỗi ở `app/(marketing)/chao-mung/page.tsx` (kiểu route `"/chao-mung"`), do `.next/types` trên máy cũ từ 03:16 — container dev giữ `.next` ở volume riêng. Không thuộc nhóm này; `next build` (có kiểm kiểu) xanh |
| Hành vi trên Chrome thật ([`instructor/check.cjs`](instructor/check.cjs), stack dev, cho phép chuyển động) | **35/35** ([`results.json`](instructor/results.json)): thanh điều hướng đúng trang hiện tại + huy hiệu 1 câu; lời chào gọi tên, một Naomi, 0 hoạt ảnh; việc đang chờ đúng thứ tự; chip lọc chỉ trạng thái có khóa, lọc "Bản nháp" ra 2 dòng; "Xem lý do" mở tab Thông tin có lý do; gợi ý 1/4 và nút "Gửi duyệt lại" vẫn bấm được; đổi tab chỉ đổi địa chỉ, bài sửa dở còn nguyên khi quay lại; thêm bài bằng nút "Trắc nghiệm"; quiz có 2 nút Duyệt, chưa xuất bản được; Hỏi đáp mở ở "Chờ trả lời · 1"; trang tạo khóa không có nút tạo trên thanh; axe 0 critical/serious ở tổng quan, thông tin khóa, soạn bài code, soạn quiz, Hỏi đáp, tạo khóa, thống kê, cấp bậc; 360 px 0 tràn ở tổng quan, soạn khóa, Hỏi đáp, tạo khóa; giảm chuyển động thì 0 hoạt ảnh |
| Tràn ngang (`foundation/overflow.cjs`, 46 route × 360/375/1440 × 4 vai) | **0/138** ([`instructor/overflow.json`](instructor/overflow.json)) |
| Nhảy bố cục khi giữ API 1,2 s (`site-states/shift.cjs`) | mọi trang giảng viên **CLS < 0,1**. Soạn khóa giảm từ 0,111 (1440) / 0,101 (375) xuống **0,040 / 0,041** (skeleton mới có tab + cột phải). Tổng quan 0,008 / 0,0005, thống kê 0,0006 / 0,020, cấp bậc 0,0006 / 0,0004. Hỏi đáp 0,027 / 0,042 (trước 0,0009 / 0,024): tài khoản đo (Trần Minh Khoa) không có câu hỏi nào nên thật ra là trạng thái trống, ngắn hơn ba dòng skeleton — chân trang nhích lên. Số "trước" ở `site-states/shift-after.json` (22/10) ([`instructor/shift.json`](instructor/shift.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (19,5 s). Spec không đổi: giảng viên trong E2E soạn khóa qua API |
| `next build` không mạng | xanh (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải gì từ origin mới |

## 5. Ảnh — `instructor/before/` và `instructor/after/`

[`instructor/capture.cjs`](instructor/capture.cjs) (dữ liệu dựng ở [`instructor/stage.cjs`](instructor/stage.cjs), dùng chung với `check.cjs`) dựng một giảng viên "Lê Thu Hà" dùng một lần với bốn khóa (một xuất bản — trạng thái đặt thẳng CSDL để không tốn quota Gemini cho ingest, một nháp, một bị quản trị viên seed trả lại kèm lý do, một trống), bài video/bài đọc/bài tập code 3 test/quiz 4 câu (2 câu cuối đánh dấu AI soạn chưa duyệt ngay trong CSDL — không gọi Gemini), và một học viên đặt một câu hỏi; `purge_e2e` gỡ hết ở cuối. Thống kê và cấp bậc chụp trên Trần Minh Khoa (số thật), phiên đăng xuất sau đó. Cả hai bộ chụp ngày 27/10 trên cùng dữ liệu: `PHASE=before` với `frontend/` của `main` @ `73161ca`, `PHASE=after` trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-chua-co-khoa-1440` | Giảng viên mới, chưa có khóa |
| `2-tao-khoa-1440` | `/giang-day/moi` |
| `3-hoi-dap-trong-1440` | Hộp thư chưa có câu hỏi |
| `4-tong-quan-{1440,375}` | 4 khóa (1 xuất bản, 2 nháp, 1 bị từ chối), 1 câu hỏi chờ |
| `5-muc-luc-trong-1440` | Khóa chưa có chương |
| `6-soan-bai-code-{1440,375}` | Khóa đã xuất bản, bài tập code đang mở |
| `7-soan-quiz-1440` | Bài trắc nghiệm đang mở, 2 câu chờ duyệt |
| `8-thong-tin-bi-tu-choi-1440` | Khóa bị từ chối, tab Thông tin (bản "trước": cả trang) |
| `9-hoi-dap-{1440,375}` | Một câu hỏi chờ trả lời |
| `10-thong-ke-1440`, `11-cap-bac-1440` | Trần Minh Khoa |

Ảnh chụp với `prefers-reduced-motion: reduce`.

```bash
# stack dev đang chạy
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/instructor/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/instructor/check.cjs
```
