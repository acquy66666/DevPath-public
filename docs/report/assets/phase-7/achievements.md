# Phase 7 — Nhóm màn 6: Thành tích (26/10/2026)

Nhóm màn 6 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): XP + chuỗi ngày (`fire` / `sad`), bảng xếp hạng (`levelup`), chứng chỉ (`graduate`), khối gợi ý ⭐. Nhánh `feature/phase7-achievements`, từ `main` sau PR #125. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 6: Thành tích"**: <https://claude.ai/artifact/K2jZHXjnca951AjgXWYfeo>. Bản trong repo: [`docs/ui-ux/achievements/canvas/`](../../../ui-ux/achievements/canvas/project/canvas.json).

- **8 artboard:** Khóa học của tôi 1440 và 375; khối thành tích ở 5 trạng thái (giữ được, chưa học hôm nay, vừa mất, tài khoản mới, đang tải) + 3 cách viết hạng tuần; bảng xếp hạng 1440 (tuần này, vừa lên hạng) và 375 (tháng này); khối gợi ý (trang chủ với "Cách DevPath gợi ý" mở, 4 kiểu lý do, đang tải); chứng chỉ 1440 (cộng PDF chưa xong, vừa sao chép) và 375.
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là 6 hình chép từ canvas linh vật: `fire`, `sad`, `levelup`, `graduate`, `empty`, `empty-courses`.
- **Dữ liệu thật** trên CSDL dev, sau khi nạp lại `seed_sales` + `seed_study` ngày 25/10: Người mua 08 (350 XP, chuỗi 7 ngày, hạng 1 tuần), 01 (chuỗi 2 ngày, chưa học hôm nay), 38 (chuỗi vừa đứt), 34 (3 gợi ý), chứng chỉ của Người mua 06. Ba kiểu lý do ngoài "cả hai nguồn" là trạng thái mẫu (ghi ở tên artboard).
- **User duyệt 26/10, giữ cả 5 điểm**, kể cả khối "Gợi ý cho bạn" mới ở "Khóa học của tôi".
- **Khớp với code:** canvas bản 10 sửa theo code. Dòng "XP gần đây" có hai dòng (tên bài; loại XP · thời gian). Chân thẻ khóa học luôn hai dòng (trạng thái; nút), để các thẻ cạnh nhau bằng nhau.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Bố cục "Khóa học của tôi"** | 3 ô số (chuỗi, chuỗi dài nhất, tổng XP) + thẻ "XP gần đây" rộng hết trang, rồi danh sách 3 cột | Hai cột từ `lg`: khóa học bên trái (2 cột), thành tích ở cột phải 22rem. Điện thoại: thành tích trước, danh sách sau. Dòng "3 khóa học · 2 đã hoàn thành". Khách chưa đăng nhập: không có cột phải |
| **Chuỗi ngày** | Ô "Chuỗi ngày học 7 ngày" + icon lửa | Thẻ nền nghệ nhạt có Naomi `fire`, "7 ngày" màu chuỗi, "Hôm nay đã được tính" / "Học một bài hôm nay để giữ chuỗi", dải 7 ngày của tuần (ngày trong chuỗi tô lửa, hôm nay có vòng, chưa học hôm nay thì ô viền đứt), "Chuỗi dài nhất: 9 ngày". Câu đọc cho trình đọc màn hình: "Chuỗi 7 ngày: từ thứ Hai 19/10 đến hôm nay." |
| **Chuỗi vừa đứt** | "0 ngày" + "Hoàn thành một bài để bắt đầu chuỗi mới" | Thẻ trắng, Naomi `sad`, "Chuỗi đã dừng", "Ngày học gần nhất là thứ Bảy 24/10.", "Học một bài hôm nay để bắt đầu chuỗi mới. Chuỗi dài nhất của bạn là 7 ngày." Quá 7 ngày hoặc chưa từng học: không Naomi |
| **XP** | Ô "Tổng XP" | Thẻ XP: "350 XP", "Hạng 2 tuần này" (huy chương khi trong top 3, dẫn sang bảng xếp hạng), "XP gần đây" với chip "+10 XP" màu phần thưởng, tên bài, loại XP · thời gian |
| **Thẻ khóa học** | "Hoàn thành …" chữ xám, nút "Chứng chỉ" xám | "✓ Hoàn thành …" màu thành công; nút "Chứng chỉ" màu phần thưởng |
| **Gợi ý cho bạn** | Chỉ ở trang chủ; dòng "Vì bạn đã học …" | Thêm ở "Khóa học của tôi". Mỗi thẻ: câu lý do theo nguồn + nhãn "Học viên giống bạn" / "Nội dung gần" / "Phổ biến". Nút "Cách DevPath gợi ý" mở ba nguồn bằng lời thường và giờ tính gần nhất |
| **Bảng xếp hạng** | Tab không có panel (lỗi axe critical ở mốc "trước"); thẻ "Bạn đang đứng hạng 1 / 13 người"; danh sách có huy chương nhỏ | Mỗi tab có panel. Dòng kỳ + số người. Thẻ "Bạn" có Naomi `levelup`: "Bạn đang dẫn đầu tuần này" / "Bạn đứng hạng 4 tháng này", XP + số người, "Hơn hạng 2 là 10 XP" / "Cần thêm 20 XP để lên hạng 3", "Lên N hạng từ lần trước bạn xem" khi hạng tăng. Bục 3 hạng (thứ tự 2–1–3, cao theo hạng, viền huy chương). Danh sách từ hạng 4, dòng của bạn nền ngọc |
| **Chứng chỉ** | Hộp xanh lục "Chứng chỉ hợp lệ"; khung viền kép; nút PDF | Dải "Chứng chỉ hợp lệ. DevPath cấp ngày … cho …, mã …". Giấy ngang A4 như bản PDF từ `lg` (khung kép ngọc, tiêu đề serif, tên dưới gạch, chân trang giảng viên/ngày/mã/địa chỉ xác thực, con dấu nghệ ở giữa). Khối chia sẻ: Naomi `graduate`, câu "Ai có đường dẫn này đều kiểm tra được chứng chỉ…", "Tải chứng chỉ PDF" (nút chính) + "Sao chép liên kết" (nút viền; là nút chính khi PDF chưa xong) |

**Naomi** (bản đồ phản ứng, thiết kế mục 5), mỗi màn một Naomi, phản ứng một lần:

| Mood | Phản ứng khi | Đứng yên khi |
|---|---|---|
| `fire` | lần đầu mở trang sau khi ngày hôm nay vào chuỗi | mở lại cùng ngày; chuỗi còn nhưng hôm nay chưa học |
| `sad` | lần đầu thấy chuỗi vừa đứt | mở lại; đứt quá 7 ngày thì không có Naomi |
| `levelup` | hạng tốt hơn lần trước trình duyệt này xem bảng đó | lần đầu xem; hạng không đổi hay giảm; không có XP kỳ này thì không có Naomi |
| `graduate` | tab vừa xong khóa và bấm "Xem chứng chỉ" | người khác mở link; tải lại; mở từ "Khóa học của tôi" |

## 3. Lỗi tìm ra khi làm

- **Tab bảng xếp hạng thiếu panel** (axe critical, ghi ở mốc "trước"): sửa, axe 0 critical/serious.
- **Thẻ khóa học cạnh nhau lệch chiều cao** khi một thẻ có nút "Chứng chỉ" (chân thẻ xuống hai dòng, thẻ kia một dòng). Giờ chân thẻ nào cũng hai dòng.
- **Container query tự hỏi chính nó**: `@container` và `@xl:flex-row` trên cùng một phần tử thì không bao giờ khớp. Khối chia sẻ chứng chỉ giờ có một lớp bọc.
- **Dev server trong container không thấy file sửa trên Windows** (lỗi đã biết): ảnh chứng chỉ đầu tiên vẫn là bản cũ; `docker compose restart frontend` rồi chụp lại.
- Lỗi của chính script, ghi lại cho lần sau: phản ứng đầu tiên sau khi khởi động lại dev server có thể chậm (biên dịch hình), nên `check.cjs` chờ `data-phase="playing"` tối đa 4 s thay vì đọc sau 0,7 s.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **117/117** (17 test mới: `lib/gamification/streak-view.test.ts` 7 — ngày Việt Nam, 4 trạng thái, mood, câu chữ, dải tuần, câu đọc, phản ứng một lần; `lib/gamification/rank-view.test.ts` 5 — số XP, dòng kỳ, thẻ "Bạn" khi dẫn đầu/đứng sau/đồng hạng/chưa có XP, hạng tăng, bục; `lib/recommendations/reason.test.ts` 5) |
| `tsc --noEmit`, `npm run lint` | sạch |
| Hành vi trên Chrome thật ([`achievements/check.cjs`](achievements/check.cjs), stack dev, cho phép chuyển động) | **38/38** ([`results.json`](achievements/results.json)): `fire`/`sad`/`levelup`/`graduate` phản ứng đúng một lần và đứng yên khi mở lại; chuỗi chờ hôm nay thì đứng yên; lần đầu xem bảng xếp hạng không ăn mừng; dòng "Lên 2 hạng"; mỗi màn một Naomi (4 màn); tab nào cũng có panel, axe 0 critical/serious trên bảng xếp hạng; bục 3 hạng; "Cách DevPath gợi ý" mở/đóng (`aria-expanded`); nhãn nguồn; sao chép đúng địa chỉ chứng chỉ; dấu chứng chỉ dùng một lần; tài khoản mới không Naomi ở thẻ chuỗi; giảm chuyển động 0 animation; 3 trang 375 px không tràn |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai) | **0/132** ([`achievements/overflow.json`](achievements/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (17,3 s), không sửa spec (luồng vàng kết thúc ở trang chứng chỉ mới) |
| `next build` không mạng | xanh (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải thêm gì mới. Hình Naomi `fire`/`sad`/`levelup`/`graduate` là chunk cùng origin đã đo ở task component |

## 5. Ảnh — `achievements/before/` và `achievements/after/`

[`achievements/capture.cjs`](achievements/capture.cjs) đăng nhập bằng form thật vào các người mua mẫu (chỉ đọc), cộng một tài khoản dùng một lần cho "tài khoản mới" (`purge_e2e` ở cuối). Cả hai bộ chụp ngày 26/10 trên cùng dữ liệu nạp lại hôm đó: `PHASE=before` chạy trên `main` @ `6cdaeb5` (một worktree, dev server tạm ở cổng 3000), `PHASE=after` trên nhánh này. 26/10 là thứ Hai, nên bảng tuần mới có 7 người và dải tuần chỉ có ngày đầu.

| Ảnh | Trạng thái |
|---|---|
| `1-khoa-hoc-cua-toi-{1440,375}` | Người mua 08: chuỗi 7 ngày, hôm nay đã học |
| `2-chuoi-chua-hoc-1440` | Người mua 01: chuỗi còn, hôm nay chưa học |
| `3-chuoi-vua-mat-1440` | Người mua 38: chuỗi vừa đứt |
| `4-bang-xep-hang-tuan-{1440,375}` | Bảng tuần này |
| `5-bang-xep-hang-thang-1440` | Bảng tháng này |
| `6-len-hang-1440` | Chỉ có ở "sau": lần xem trước ở hạng thấp hơn 3 bậc |
| `7-chung-chi-{1440,375}` | Trang chứng chỉ (khách) |
| `8-goi-y-trang-chu-{1440,375}` | Khối "Gợi ý cho bạn" ở trang chủ, Người mua 34 |
| `9-tai-khoan-moi-1440` | Tài khoản mới: chưa chuỗi, chưa XP, chưa khóa |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh.

```bash
# stack dev đang chạy, dữ liệu bán/học nạp lại trong ngày (README "Ngày tháng tính theo lúc chạy")
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/achievements/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/achievements/check.cjs
```

## 6. Để lại

- **Bản PDF vẫn xanh navy** của WeasyPrint; trang web đã theo design system. Đổi PDF là đổi backend (thiết kế, mục 3).
- **Nhớ phản ứng theo trình duyệt**: mở trên máy khác thì Naomi phản ứng thêm một lần ở đó. Muốn chính xác hơn cần backend lưu "đã xem", ngoài phạm vi phase.
- **Dải tuần không biết ngày trước chuỗi hiện tại**: API chỉ trả chuỗi hiện tại, nên ngày ngoài chuỗi là ô trơn, không phải "bỏ lỡ".
- **"Học tiếp theo" và "Khóa học tương tự" giữ như nhóm 2/4**: tiêu đề khối đã nói lý do, thẻ không cần thêm dòng.
