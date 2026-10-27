# Phase 7 — Nhóm màn 8: Thương mại (27/10/2026)

Nhóm màn 8 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): giỏ hàng, danh sách yêu thích, kết quả thanh toán với Naomi `paid`/`oops`. Nhánh `feature/phase7-commerce`, chồng lên `feature/phase7-account` (PR #127 chưa merge). Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 8: Thương mại"**: <https://claude.ai/artifact/6XuLZJDYZMZztiJfmbRWJB>. Bản trong repo: [`docs/ui-ux/commerce/canvas/`](../../../ui-ux/commerce/canvas/project/canvas.json).

- **9 artboard:** giỏ hàng 1440 (CHAOMUNG50, một khóa đã có) và 375; trạng thái giỏ (trống có gợi ý từ yêu thích, khách, mã bị từ chối, đang chuyển sang VNPay / VNPay chưa sẵn sàng); yêu thích 1440 và 375; thanh toán thành công 1440 và 375; không thành công (mã 24); đang chờ ngân hàng xác nhận và quá 90 giây.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 4 hình `paid`, `oops`, `empty-cart`, `empty-courses` chép từ canvas linh vật.
- **Dữ liệu thật** trên CSDL dev: các khóa có phí của Trần Minh Khoa và Nguyễn Mai Anh, giá thật, mã CHAOMUNG50 / HETHAN thật. Mã đơn và mã giao dịch trên mockup là mẫu.
- **Duyệt:** chưa có lời duyệt của user khi code; làm theo mockup, giả định ghi ở đây và ở `decisions.md`.
- **Khác mockup:** trạng thái "đang chờ" không có thanh tiến độ (luật của dự án: hiệu ứng nhấp nháy chỉ ở skeleton) mà đổi biểu tượng đồng hồ ở dòng nhỏ trên tiêu đề thành vòng xoay.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Dòng giỏ hàng** | Ảnh, tên, giảng viên, giá, nút "Bỏ" | Thêm cấp độ + thời lượng. Hai nút **"Để dành sau"** (lưu vào yêu thích rồi bỏ khỏi giỏ) và "Bỏ". Khóa đã có: nền xám, ảnh mờ, chip "Bạn đã có khóa này", "Vào học", "Bỏ khỏi giỏ", giá gạch |
| **Tóm tắt đơn** | "Tổng cộng" + số lớn; Tạm tính/Giảm giá chỉ hiện khi có mã | Thẻ "Tóm tắt đơn hàng": "Tạm tính · N khóa học" luôn hiện, "Giảm giá · MÃ" màu xanh, "Tổng cộng" cỡ `h1`. Nút chính 44 px **ghi số tiền**: "Thanh toán 598.500 ₫ qua VNPay" (0đ: "Nhận khóa học"). Dòng có ổ khóa nói tiền trả ở đâu, khi nào khóa học vào tài khoản |
| **Mã giảm giá** | Ô không nhãn; lỗi là một Alert đỏ dưới ô | Nhãn "Mã giảm giá" hiện; mã bị từ chối thì ô viền đỏ (`aria-invalid`), lỗi ngay dưới ô và gắn với ô (`aria-describedby`), chữ đã gõ giữ nguyên. Mã đã áp: khối nền ngọc nhạt, "Giảm 50% · hết hạn 05/11/2026", nút X |
| **Điện thoại** | Thẻ tổng ở cuối trang, phải cuộn qua cả danh sách mới thấy nút | Thanh dính đáy màn hình: tổng tiền + "Thanh toán qua VNPay". Nút trong thẻ tóm tắt chỉ hiện từ `lg`, nên lúc nào cũng chỉ một nút |
| **Từ danh sách yêu thích** | — | Dưới giỏ (và trong giỏ trống): "Trong danh sách yêu thích của bạn", tối đa 2 khóa có phí chưa ở trong giỏ và **chưa mua**, nút "Thêm vào giỏ", liên kết "Xem cả danh sách" |
| **Giỏ trống / khách** | EmptyState / thẻ chữ | EmptyState `empty-cart` + gợi ý từ yêu thích; khách: Naomi `empty-cart` đứng yên, "Đăng nhập" (quay lại giỏ) + "Đăng ký miễn phí" |
| **Yêu thích** | Thẻ khóa + hàng "Lưu ngày · Bỏ lưu · Thêm vào giỏ" (nút viền) | Dòng đếm "N khóa học bạn để dành · M khóa đã ở trong giỏ" + "Xem giỏ hàng". **Nút tim** trên ảnh bìa để bỏ lưu (44 px, `aria-pressed`). Dưới thẻ: "Lưu ngày …" + một nút: "Thêm vào giỏ" (chính), "Đã ở trong giỏ", **"Đã có · Vào học"** (khóa đã mua) hoặc "Học miễn phí". Phân trang dùng `Pager` chung |
| **Kết quả: thành công** | Thẻ có icon tích, mã đơn, "Vào học ngay"; thẻ "Chi tiết đơn hàng" | Hai cột từ `lg`. Khối nền xanh nhạt: Naomi `paid` 200 px, "ĐÃ THANH TOÁN", "Thanh toán thành công" cỡ `display`, "3 khóa học đã vào tài khoản của bạn…", "Vào học ngay" (mở khóa đầu tiên) + "Khóa học của tôi". "**Khóa học vừa mua**": mỗi khóa một nút "Bắt đầu học". Thẻ **Biên nhận**: mã đơn, mã giao dịch VNPay, giờ trả, các dòng, giảm giá, "Đã trả" |
| **Kết quả: không thành công** | Icon X, lý do mã VNPay, "Quay lại giỏ hàng" | Naomi `oops`, "Thanh toán không thành công", lý do bằng chữ ("Bạn đã hủy giao dịch trên trang của VNPay."), "Chưa có khoản nào bị trừ, và giỏ hàng của bạn vẫn còn nguyên." Thẻ "Đơn hàng" có mã từ chối |
| **Kết quả: đang chờ** | Icon đồng hồ; "Quá lâu chưa có kết quả?…" khi đang không tải | Không Naomi. "Đang chờ ngân hàng xác nhận" + vòng xoay; sau 90 giây đổi thành "Ngân hàng chưa báo kết quả" kèm câu trấn an (tiền đã trừ thì khóa vào khi VNPay báo, không cần trả lại) và nút **"Kiểm tra lại"** (hỏi lại thêm 90 giây). IPN tới trong lúc chờ thì trang tự đổi sang thành công và Naomi phản ứng |
| **Skeleton** | Khung giỏ cũ; kết quả là một khối 256 px | Dựng lại theo khung mới: dòng tóm tắt, một dòng giỏ, thẻ tóm tắt; kết quả: khối tiêu đề + thẻ biên nhận |

**Naomi** (bản đồ phản ứng, thiết kế mục 5), mỗi màn tối đa một Naomi:

| Màn | Mood | Phản ứng khi | Đứng yên khi |
|---|---|---|---|
| Kết quả, đã thanh toán | `paid` | lần đầu trình duyệt này thấy đơn ở trạng thái `paid`, đơn đặt trong vòng 1 giờ | tải lại; mở lại biên nhận cũ; giảm chuyển động |
| Kết quả, không thành công / đã hủy | `oops` | `failed`: như trên. `cancelled`: không bao giờ | như trên |
| Kết quả, đang chờ | — | — | — |
| Giỏ trống, khách ở giỏ | `empty-cart` | — | luôn |
| Yêu thích trống, khách ở yêu thích | `empty-courses` | — | luôn |

## 3. Lỗi tìm ra khi làm

- **Khóa vừa mua vẫn được mời "Thêm vào giỏ".** API giữ khóa trong danh sách yêu thích sau khi mua, nên ảnh "giỏ trống" đầu tiên mời mua lại đúng khóa vừa trả tiền (bấm thì API trả 409). Giờ giỏ và trang yêu thích hỏi khóa nào đã ghi danh (`components/commerce/use-owned-courses.ts`, cùng khóa cache `["enrollment", id]` với trang khóa học, nên thanh toán xong là làm mới), gợi ý bỏ khóa đã có, và nút ở trang yêu thích thành "Đã có · Vào học". Bản cũ cũng có lỗi này ở trang yêu thích (nút "Thêm vào giỏ" cho khóa đã mua).
- **Nút thanh toán ở thanh đáy 375 px bị cắt chữ** khi nhãn có số tiền ("…anh toán 598.500 ₫ qua VNPay"). Thanh đáy đã có số tiền bên trái, nên nút ở đó chỉ ghi "Thanh toán qua VNPay".
- **Hai liên kết "Đã có · Vào học" cùng tên** khi hai khóa đã mua: `check.cjs` bắt được (strict mode). Liên kết giờ có tên đầy đủ "Đã có · Vào học <tên khóa>", "<tên khóa>: đã ở trong giỏ".
- **"Vào học ngay" ở đơn nhiều khóa trùng đích với "Khóa học của tôi".** Giờ mở khóa đầu tiên của đơn.
- Lỗi của chính script, ghi lại cho lần sau: danh sách yêu thích trả khóa **lưu mới nhất trước**, nên sau "Để dành sau" khóa vừa để dành đứng đầu gợi ý.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **133/133** (7 test mới ở `lib/commerce/commerce-view.test.ts`: dòng tóm tắt giỏ, nhãn nút theo số tiền, gợi ý yêu thích bỏ khóa trong giỏ/đã có/miễn phí, tiêu đề đơn thành công (đơn 0đ, một khóa), thất bại có lý do bằng chữ và không lộ mã lạ, đang chờ không Naomi, Naomi phản ứng một lần cho mỗi kết quả và chỉ khi đơn còn mới) |
| `tsc --noEmit`, `npm run lint` | sạch |
| Hành vi trên Chrome thật ([`commerce/check.cjs`](commerce/check.cjs), stack dev, cho phép chuyển động) | **33/33** ([`results.json`](commerce/results.json)): khách quay lại giỏ; dòng tóm tắt; khóa đã có; nút ghi 898.000 ₫ (không tính khóa đã có); mã HETHAN: lỗi dưới ô + `aria-invalid` + `aria-describedby` + giữ chữ; CHAOMUNG50 ra 449.000 ₫ và nút đổi theo; "Để dành sau" rời giỏ vào yêu thích; thêm từ gợi ý; tim bỏ lưu; VNPay nhận đúng `vnp_Amount` + chữ ký; `paid` phản ứng, tải lại đứng yên, một Naomi, mỗi khóa có "Bắt đầu học"; khóa vừa mua không được mời lại, ở yêu thích thành "Đã có · Vào học"; thất bại: `oops`, lý do bằng chữ, nút về giỏ; đang chờ không Naomi rồi tự đổi sang thành công khi IPN tới; axe 0 critical/serious ở giỏ, yêu thích, thành công, thất bại; 360 px 0 tràn; điện thoại chỉ một nút thanh toán, dính đáy; giảm chuyển động thì 0 animation |
| Tràn ngang (`foundation/overflow.cjs`, 46 route × 360/375/1440 × 4 vai) | **0/138** ([`commerce/overflow.json`](commerce/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (18,9 s). Spec sửa cùng commit: nút thanh toán tìm theo mẫu `/^Thanh toán .+ qua VNPay$/` vì tên giờ có số tiền; `csp-probe.cjs` đổi theo |
| `next build` không mạng | xanh (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải gì từ origin mới (hình Naomi là chunk cùng origin) |

## 5. Ảnh — `commerce/before/` và `commerce/after/`

[`commerce/capture.cjs`](commerce/capture.cjs) dựng một học viên dùng một lần (`purge_e2e` ở cuối, kèm 3 đơn hàng), không tiêu lượt mã giảm giá nào (CHAOMUNG50 áp cho ảnh giỏ rồi bỏ trước khi trả). Cả hai bộ chụp ngày 27/10 trên cùng dữ liệu: `PHASE=before` với `frontend/` của `feature/phase7-account` @ `49dddc4`, `PHASE=after` trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-gio-hang-khach-1440` | Khách mở giỏ |
| `2-gio-hang-{1440,375}` | 4 khóa, 1 đã có, CHAOMUNG50 |
| `3-gio-hang-ma-het-han-1440` | Gõ HETHAN |
| `4-yeu-thich-{1440,375}` | 3 khóa, 1 đã ở trong giỏ |
| `5-thanh-toan-thanh-cong-{1440,375}` | Đơn 3 khóa, IPN `00` |
| `6-gio-hang-trong-1440` | Sau khi trả, bỏ khóa đã có: giỏ trống + gợi ý từ yêu thích |
| `7-thanh-toan-that-bai-{1440,375}` | IPN `--fail` (mã 24) |
| `8-thanh-toan-dang-cho-1440` | Đơn chưa có IPN |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh. Trên ảnh chụp cả trang 375 px, thanh thanh toán dính đáy hiện ở giữa ảnh (chỗ đáy khung nhìn 812 px).

```bash
# stack dev đang chạy
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/commerce/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/commerce/check.cjs
```

## 6. Để lại

- **Danh sách yêu thích không tự bỏ khóa đã mua.** Đó là hành vi của API; giao diện xử lý bằng cách hỏi ghi danh từng khóa (một request nhỏ mỗi khóa trên trang, tối đa một trang yêu thích). Bỏ khóa khỏi yêu thích lúc IPN là việc của backend, ngoài Phase 7.
- **"Để dành sau" là hai lệnh API** (lưu rồi bỏ khỏi giỏ), không phải một giao dịch. Lỗi giữa chừng thì khóa vẫn ở giỏ và đã ở yêu thích: không mất gì.
- **Mã giảm giá không nhớ qua lần tải lại** (như trước): mã được kiểm lại lúc tạo đơn.
- **Thanh toán thật qua VNPay** vẫn ngoài phạm vi (user chốt 16/10): ảnh và kiểm đều dừng ở URL đã ký + IPN giả lập.
