# Phase 7 — Nhóm màn 10: Khu quản trị (29/10/2026)

Nhóm màn 10 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md), cũng là nhóm cuối. Nhóm gồm tổng quan, duyệt khóa học, báo cáo vi phạm, người dùng, danh mục, mã giảm giá, banner, và năm trang tài chính thêm từ Phase 6.5. Nhánh `feature/phase7-admin`, từ `main` sau PR #129. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 10: Quản trị"**: <https://claude.ai/artifact/XvGnpgHB1uBCCvuGjgkv67>. Bản trong repo: [`docs/ui-ux/admin/canvas/`](../../../ui-ux/admin/canvas/project/canvas.json).

- **8 artboard + 1 component.** Artboard: tổng quan 1440 (thanh bên 4 nhóm + "Cần xử lý") và 375 (menu đang mở); bốn trạng thái trống; hàng đợi duyệt; trang duyệt một khóa (kiểm tra nhanh + quyết định, đang viết lý do từ chối); báo cáo vi phạm (một báo cáo đang mở); người dùng (hộp thoại khóa); mã giảm giá. Component là thanh bên, dùng chung bằng `dc-import`.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 4 hình `empty`, `empty-search`, `empty-courses`, `empty-notifications`.
- **Duyệt:** user duyệt ngày 29/10 ("Duyệt, code đi").
- **Khác mockup:**
  - Badge "Chờ duyệt" giữ màu `info` của badge dùng chung; mockup vẽ cam.
  - "Kiểm tra nhanh" không có dòng video chuyển mã thất bại, vì mục lục không mang trạng thái video.
  - Thẻ báo cáo ở tổng quan ghi luật đóng báo cáo, không ghi lý do của báo cáo mới nhất.
  - Mã giảm giá là thẻ, không phải bảng.
  - Người dùng là bảng từ `md` và thẻ dưới `md`.
  - Lý do của từng điểm ở `decisions.md`.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Điều hướng** | Tiêu đề "Quản trị" + một đoạn mô tả, rồi hàng 12 tab ngang cuộn sang bên (tràn ở 1440 px, `before.md`) | **Thanh bên** 240 px, 4 nhóm: Tổng quan · Kiểm duyệt · Tài chính · Nội dung sàn. Mỗi mục có biểu tượng; huy hiệu số chờ ở "Duyệt khóa học" và "Báo cáo vi phạm"; mục đang mở có `aria-current`. Trang con thuộc mục cha (trang duyệt → "Duyệt khóa học", bảng kê → "Thanh toán giảng viên"). Dưới `lg` thanh bên gập thành **một nút** "Quản trị · <mục đang mở> · <tổng việc chờ>"; bấm thì mở cùng danh sách, Esc gập lại và trả focus. Khung cùng bề rộng với header, chữ của mục thẳng mép logo |
| **Tiêu đề màn** | Mỗi màn một `h2` cỡ chữ thường (hoặc `sr-only`) dưới `h1` chung "Quản trị" | `AdminTitle`: mỗi màn một `h1` theo thang chữ (`text-h2`/`text-h1`), một dòng mô tả, nút của màn bên phải (Tạo mã, Thêm banner, Xuất Excel) |
| **Tổng quan** | Số liệu toàn sàn ngay đầu trang | **"Cần xử lý"** đứng đầu, 3 thẻ dẫn tới màn tương ứng: khóa chờ duyệt (gọi tên khóa chờ lâu nhất + số ngày), báo cáo chờ xử lý, tài khoản đang khóa (vẽ nhạt: chỉ để biết). Khóa hot không còn ghi "★ 0.0" khi chưa ai đánh giá |
| **Duyệt khóa học** | Ô chọn trạng thái; dòng có ảnh bìa xám "không có ảnh" | Chip lọc (số ở "Chờ duyệt"); ảnh bìa dự phòng theo màu khóa; "Gửi duyệt <ngày> · **chờ N ngày**" (từ 3 ngày thì chữ cam đậm); nút "Xem và duyệt" ở dòng chờ duyệt |
| **Trang duyệt** | Liên kết "← Hàng đợi duyệt"; ảnh bìa to (nếu có); tên khóa là `h2` | Đường dẫn vị trí "Duyệt khóa học / <tên>"; đầu trang ảnh bìa nhỏ + badge trạng thái + **số ngày chờ** + danh mục + trình độ, tên khóa là `h1`. Mô tả và mục lục trong thẻ; chương có tóm tắt theo loại bài. Cột phải (từ `xl`) có **"Kiểm tra nhanh"** (4 gợi ý giống hệt bên giảng viên, chỉ để gợi ý) và "Quyết định" |
| **Báo cáo vi phạm** | Nút bật/tắt "Chờ xử lý/Đã xử lý"; mọi lý do đỏ; sao màu `amber` viết tay | Tab gạch chân "Hàng đợi · N / Đã xử lý"; badge lý do theo mức nặng (xúc phạm đỏ, spam/sai sự thật cam, còn lại xám) và badge trạng thái theo màu nghĩa; nội dung bị báo cáo hiện nguyên văn cỡ chữ đọc; phần quyết định là dải nền riêng ở cuối thẻ, có nhãn "Ghi chú xử lý (không bắt buộc)" |
| **Người dùng** | Danh sách thẻ; khóa = câu hỏi hiện ngay trong dòng | Bảng từ `md` (tài khoản, vai trò + số khóa, ngày tham gia, lần đăng nhập gần nhất, thao tác); thẻ dưới `md`. Tài khoản đang khóa nền `destructive-soft`. **Khóa hỏi lại bằng hộp thoại**; mở khóa làm luôn |
| **Mã giảm giá** | Ô chọn trạng thái, badge chung chung | Chip lọc; badge Đang chạy/Sắp chạy/Hết lượt/Đã kết thúc theo màu nghĩa; mã trong ô mono; **thanh lượt dùng** khi có trần; mã đã kết thúc nền `muted` |
| **Danh mục, Banner, 5 trang tài chính** | `h2` nhỏ; màu `emerald`/`amber`/`red` viết tay; nền `muted/40`, `destructive/5` | Tiêu đề `h1` theo thang chữ; mọi màu viết tay → token ngữ nghĩa (`success-text`, `warning-soft`, `destructive-text`…); thẻ nền `card` |
| **Ô chọn ở thanh lọc** | Ép `h-9` (36 px) → cắt dấu tiếng Việt (ghi từ nhóm "Trạng thái toàn site") | 40 px theo design system |
| **Skeleton** | Tiêu đề + mô tả + 7 tab giả | Khung thật: thanh bên 4 nhóm (từ `lg`) hoặc nút gập; tiêu đề `h1` + một dòng + thanh công cụ + dòng |

**Naomi** (thiết kế mục 4: ở khu làm việc chỉ ở empty state): không đổi chỗ, vẫn 80 px, đứng yên, mỗi màn tối đa một. Tổng quan không có Naomi.

## 3. Lỗi tìm ra khi làm

- **Ô chọn cắt dấu** ở thanh lọc admin (`NativeSelect` bị ép `h-9`), có từ trước và đã ghi lại ở nhóm "Trạng thái toàn site". Giờ cao 40 px, `check.cjs` đo.
- **Hai lỗi axe có từ trước:**
  - Dải sao của đánh giá bị báo cáo có `aria-label` gắn trên `<p>` (`aria-prohibited-attr`, serious). Giờ dải sao là `role="img"`.
  - Bảng lãi lỗ 12 tháng cuộn ngang mà bàn phím không vào được (`scrollable-region-focusable`, serious). Giờ khung cuộn là `role="region"` có tên và `tabIndex={0}`.
  - Cả hai lộ ra khi `check.cjs` chạy axe trên mọi màn admin, lần đầu từ trước tới nay.
- **Bảng người dùng ở 375 px đẩy nút "Khóa" ra ngoài màn hình** (lần chụp "sau" đầu tiên). Dưới `md` giờ là thẻ.
- **Dev server trong container trả 404 cho mọi route động `/quan-tri/khoa-hoc/[id]`** sau khi `git stash` rồi khởi động lại; log có `watch error … .next-internal`. Xóa `/app/.next/dev` trong container rồi khởi động lại là hết. Lỗi của môi trường, không phải của code, ghi lại cho lần sau.
- **Giới hạn đăng nhập 10 lần / 15 phút mỗi email** chặn lượt `check.cjs` thứ hai, vì chụp, kiểm, E2E, CLS và tràn ngang đều đăng nhập admin. Đọc `auth:login:email:<email>` trong Redis để biết còn phải chờ bao lâu.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **144/144**. 5 test mới ở `lib/admin/admin-view.test.ts`: 12 mục trong 4 nhóm; đường dẫn thuộc mục nào (kể cả `/quan-tri/banner-cu` không thuộc "Banner"); huy hiệu chỉ ở hai hàng đợi; đếm ngày chờ nguyên ngày; thẻ "Cần xử lý" gọi tên khóa chờ lâu nhất và nói khi không có gì chờ |
| `npm run lint` | sạch |
| `tsc --noEmit` | chỉ còn lỗi có sẵn ở `app/(marketing)/chao-mung/page.tsx` (kiểu route trong `.next/types` cũ trên máy, đã ghi ở nhóm 9) |
| Hành vi trên Chrome thật ([`admin/check.cjs`](admin/check.cjs), stack dev, cho phép chuyển động) | **48/48** ([`results.json`](admin/results.json)). Thanh bên 12 mục, đúng mục hiện tại, huy hiệu, nằm cạnh nội dung ở 1440 px. "Cần xử lý" gọi tên khóa chờ 4 ngày; tổng quan không có Naomi. Chip "Chờ duyệt" đang nhấn; đổi sang "Đang bán" thì khóa chờ rời danh sách. Trang duyệt có đường dẫn vị trí + `h1` và thuộc mục "Duyệt khóa học". Kiểm tra nhanh 4/4 đạt (khóa đủ) và 4/4 chưa có (khóa thiếu), nút duyệt vẫn bấm được. Tab "Hàng đợi" đang nhấn; ô chọn cao 40 px. Khóa tài khoản mở hộp thoại; Esc đóng mà không khóa. 375 px: nút gập, mở đủ 12 mục, Esc gập lại và trả focus, nút "Khóa" nằm trong màn hình. **axe 0 lỗi critical/serious trên cả 12 màn + trang duyệt; 0 tràn ngang ở 360/375/1440 px trên cả 13 màn** |
| Tràn ngang (`foundation/overflow.cjs`, 46 route × 360/375/1440 × 4 vai) | **0/138** ([`admin/overflow.json`](admin/overflow.json)) |
| Nhảy bố cục khi giữ API 1,2 s (`site-states/shift.cjs`) | mọi trang admin **CLS < 0,1** ([`admin/shift.json`](admin/shift.json)). So với 22/10 (`site-states/shift-after.json`), 1440 px: duyệt khóa 0,043 → **0,015**, báo cáo 0,027 → **0,011**, banner 0,029 → **0,010**; 375 px: mã giảm giá 0,025 → **0,005**, báo cáo 0,060 → **0,056**, duyệt khóa 0,060 → **0,068** (hàng đợi ngắn hơn skeleton ba dòng, chân trang nhích lên). Các trang khác ≤ 0,002 như cũ |
| E2E luồng vàng (stack dev) | **1 passed** (26,3 s). Spec không đổi: admin trong E2E duyệt khóa qua API |
| `next build` không mạng | xanh (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải gì từ origin mới |

## 5. Ảnh — `admin/before/` và `admin/after/`

[`admin/capture.cjs`](admin/capture.cjs) đăng nhập quản trị viên seed bằng form và chụp hai hàng đợi lúc còn trống. Sau đó [`admin/stage.cjs`](admin/stage.cjs) dựng dữ liệu dùng một lần (dùng chung với `check.cjs`):

- một giảng viên "Nguyễn Hải Yến" với ba khóa: "Git từ số 0…" gửi duyệt và lùi 4 ngày; "SQL thực chiến…" gửi duyệt 1 ngày trước, thiếu mô tả và có chương trống; "Docker cho lập trình viên" xuất bản thẳng trong CSDL (không tốn quota Gemini);
- một học viên đánh giá khóa Docker 1 sao rồi bị khóa;
- một học viên khác báo cáo đánh giá đó (xúc phạm) và báo cáo khóa Docker (sai sự thật).

`purge_e2e` gỡ hết ở cuối, phiên admin đăng xuất. Hai bộ chụp ngày 29/10 trên cùng kịch bản: `PHASE=before` với `frontend/` của `main` @ `42c622e` (thay đổi tạm cất bằng `git stash`), `PHASE=after` trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-hang-doi-trong-1440`, `2-bao-cao-trong-1440` | Hai hàng đợi trống, Naomi |
| `3-tong-quan-{1440,375}`, `3-menu-mo-375` (chỉ "sau") | Tổng quan; menu gập đang mở |
| `4-hang-doi-{1440,375}` | 2 khóa chờ duyệt |
| `5-trang-duyet-{1440,375}`, `6-tu-choi-1440` | Khóa đủ; đang viết lý do từ chối |
| `7-trang-duyet-thieu-1440` | Khóa thiếu mô tả, chương trống |
| `8-bao-cao-{1440,375}` | 2 báo cáo chờ xử lý |
| `9-nguoi-dung-{1440,375}`, `10-hop-thoai-khoa-1440` (chỉ "sau") | Danh sách; hộp thoại khóa |
| `11-danh-muc` … `18-loi-nhuan` (1440; mã giảm giá thêm 375) | Danh mục, mã giảm giá, banner, doanh thu, xếp hạng, cấp giảng viên, thanh toán, lợi nhuận |

Ảnh chụp với `prefers-reduced-motion: reduce`.

```bash
# stack dev đang chạy; mỗi lần chạy tốn 2 lượt đăng nhập admin (giới hạn 10 / 15 phút)
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/admin/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/admin/check.cjs
```
