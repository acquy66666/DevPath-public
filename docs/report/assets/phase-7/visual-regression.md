# Hồi quy hình ảnh — bằng chứng (29/10/2026)

Nhánh `feature/phase7-visual-regression`. Task Phase 7 "Hồi quy hình ảnh".

## Cách làm

- **10 màn × 2 khổ** (1440×900 và 375×812), chụp cả trang, cộng một ảnh logo ở header với `maxDiffPixels: 0` → **24 baseline**, 2,6 MB, ở `frontend/e2e/visual/pages.visual.spec.ts-snapshots/`.
  - Khách: trang chủ, danh sách khóa, chi tiết khóa (khóa có phí), đăng nhập, 404, bảng xếp hạng.
  - Học viên: khóa học của tôi, giỏ hàng (đúng một khóa), trang học có bài đọc.
  - Giảng viên: `/giang-day`. Quản trị: `/quan-tri`.
- **Môi trường chụp cố định:** spec chỉ chạy qua `frontend/scripts/visual.sh` (`npm run test:visual`), trong image `mcr.microsoft.com/playwright:v<bản @playwright/test>-noble`. Máy dev và CI cùng image, cùng Chromium, cùng font, nên baseline sinh trên máy dev dùng được cho CI. Container gia nhập mạng compose; `e2e/visual/forward.mjs` chuyển `localhost:3000/8000/9000` về `frontend`/`backend`/`storage`, nên URL trong trang và URL media lưu trong CSDL giữ nguyên.
- **Dữ liệu cố định:** stack chỉ chạy `scripts.seed`, giống job E2E của CI. Trên máy dev phải dựng một stack sạch bên cạnh (`docker compose -p devpath-visual`, lệnh ở đầu `visual.sh`). CSDL dev hằng ngày có `seed_sales`/`seed_study` nên không khớp baseline. Tài khoản cũng cố định: admin, giảng viên `khoa.tran` của seed, và học viên `visual-hocvien@e2e.devpath.example`, do spec tự đăng ký lần đầu rồi dùng lại (nên số đếm của admin không tăng qua các lượt; `purge_e2e` của luồng vàng xóa học viên này, lượt sau đăng ký lại).
- **Vùng động bị loại trước khi chụp, không nới ngưỡng:**
  - ngày, giờ và "N phút trước" trong chữ được viết lại thành một giá trị cố định (seed đóng dấu ngày chạy); "30 ngày trước đó" (tên kỳ so sánh) thì giữ nguyên;
  - `animations: "disabled"`, `reducedMotion: "reduce"`, caret ẩn, chỉ báo dev của Next ẩn (`screenshot.css`);
  - chờ heading, không còn `[data-slot="skeleton"]`, `networkidle`, `document.fonts.ready`.
- **Ngưỡng:** `maxDiffPixelRatio: 0.001` cho cả trang (hai phía cùng một image, nên lệch thật là đổi thật), `maxDiffPixels: 0` cho logo. Project ảnh `retries: 0`.
- Mỗi vai đăng nhập một lần cho mỗi project (giới hạn 10 lần/15 phút/email). `visual.sh` xóa bộ đếm đăng nhập của đúng ba email đó trước mỗi lượt, để chạy liền nhiều lượt trên máy dev không bị `AUTH_RATE_LIMITED`.
- **Không dùng Git LFS:** 24 ảnh tổng 2,6 MB. LFS sẽ buộc thêm `lfs: true` cho checkout CI và tốn hạn mức băng thông LFS. Nếu bộ ảnh lớn lên quá vài chục MB thì xét lại.
- `npm run test:e2e` giờ là `--project=chromium` (chỉ luồng vàng). Project ảnh bị `testIgnore` ở project luồng vàng, nên chạy trên Windows không đụng tới baseline Linux.

## CI

Job "E2E — golden flow" có thêm bước **Visual regression** (`npm run test:visual`), chạy **trước** luồng vàng, trên stack vừa seed. Luồng vàng chạy cả khi ảnh lệch (`if: !cancelled()`). Ảnh lệch (expected/actual/diff) nằm trong `frontend/test-results`, đã có sẵn trong artifact `playwright-report` khi job đỏ.

**Chưa có lượt CI thật:** GitHub Actions bị chặn vì hết phút tới 01/11/2026. Sau 01/11 chạy lại CI cho nhánh/`main` để có bằng chứng xanh.

## Kiểm trên máy (29/10, stack `devpath-visual` sạch)

| Lượt | Kết quả |
|---|---|
| Sinh baseline (`--update-snapshots`) | 24 passed (42,9 s) |
| So sánh lượt 1, lượt 2 ngay sau | 24 passed (44,4 s), 24 passed (43,9 s) |
| **Thử đỏ:** đổi "trực tuyến" → "online" ở chân trang | đỏ, ví dụ trang chủ desktop 2.210 điểm ảnh lệch (tỉ lệ 0,01), mobile 1.622; trả chữ cũ lại |
| Sau khi trả lại | 24 passed (44,4 s) |
| Luồng vàng trên cùng stack (`npm run test:e2e`) | 1 passed (28,3 s) |
| Bộ ảnh lần nữa, sau luồng vàng + `purge_e2e` | 24 passed (44,3 s) |

Ngoài ra: ESLint sạch trên `e2e/` + `playwright.config.ts`, `npm test` 156/156.

## Cập nhật baseline khi giao diện đổi có chủ đích

```bash
cd infra && docker compose stop
docker compose -p devpath-visual up -d --build --wait
docker compose -p devpath-visual exec -T backend alembic upgrade head
docker compose -p devpath-visual exec -T backend python -m scripts.seed
cd ../frontend && COMPOSE_PROJECT=devpath-visual bash scripts/visual.sh --update-snapshots
```

Mở từng PNG đổi trong PR để duyệt trước khi commit. Xong thì `docker compose -p devpath-visual down -v` rồi bật lại stack dev.
