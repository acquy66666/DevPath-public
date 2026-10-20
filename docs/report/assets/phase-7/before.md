# Mốc "trước" của Phase 7 — số đo và ảnh giao diện (20/10/2026)

Cột "trước" cho chương 5 (so trước/sau nâng cấp UI/UX) và bộ ảnh giao diện cũ cho chương 4. Task: "Đo và chụp *trước*" của [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md). Ngân sách so sánh nằm ở [thiết kế UI/UX](../../../ui-ux/thiet-ke-nang-cap-ui-ux.md) mục 8.

## 1. Đo trên cái gì

| | |
|---|---|
| Code | `main` @ `59f1039` (sau PR #109 — Phase 6.5 đã merge), chưa có thay đổi nào của Phase 7 |
| Stack | Stack production chạy trên máy dev, project compose `devpath-demo`, tên miền `https://devpath-01.me`. **Deploy lại từ `main` ngay trước khi đo** (`infra/scripts/deploy.sh`, migration `79240999111f → ad80b1df78a1`), vì bản đang chạy là build 18/10, chưa có giao diện Phase 6.5. Build Next `7ye3d-tGAcSK3VP-x7zAL`, Next 16.3.1 |
| Dữ liệu | Bốn khóa thật + `seed_sales`/`seed_study` **nạp lại ngay trước khi chụp** (`seed_study --purge`, `seed_sales --purge`, `infra/scripts/seed-demo.sh`), vì dữ liệu nạp 19/10 đã già: chuỗi ngày của người mua về 0, bảng tuần thưa |
| Đường đi | Chrome và Node trỏ `devpath-01.me` → nginx `127.0.0.1:443` của máy dev (`RESOLVE_TO`, [`stack.cjs`](stack.cjs)), không vòng qua Cloudflare. Cùng bản build, cùng nginx/TLS/HTTP 2, cùng tên miền trên thanh địa chỉ. Lý do: mật khẩu tài khoản seed không rời máy, số đo không lẫn độ trễ Internet/tunnel (đổi theo giờ), không có beacon RUM mà edge Cloudflare tự chèn. Kiểm: 0/9 lượt Lighthouse có beacon `cloudflareinsights` |
| Máy | Windows 11, 8 CPU; stack dev **dừng** trong lúc đo (bật lại sau) để máy yên |
| Công cụ | Chrome 155 headless, Lighthouse 13.5.0 (mobile, `simulate`: RTT 150 ms, 1,6 Mbps, CPU chậm 4×), axe-core 4.13.0, Playwright 1.63 |

## 2. Dung lượng JavaScript

Gzip ở cả hai bảng là nén lại mức 9 để so được với nhau; "qua mạng" là số byte thật (nginx nén ở mức của nó).

**First Load JS theo bản build** (`bundle-stats.json` — hàm `writeRouteBundleStats` của chính Next, chạy trên `.next` của container frontend; Next 16.3 không in bảng này ra màn hình nữa):

| Route | Tệp | Thô | Gzip |
|---|---:|---:|---:|
| `/` (trang chủ) | 14 | 673,0 KB | **208,9 KB** |
| `/khoa-hoc/[slug]` | 16 | 691,0 KB | 214,5 KB |
| `/hoc/[slug]` (trang học, có Monaco + hls.js) | 18 | 895,8 KB | 273,8 KB |
| nhỏ nhất (`/chinh-sach-bao-mat`, `/_not-found`) | 13 | 660,9 KB | 204,6 KB |

Khung chung (layout gốc, React, TanStack Query, header) đã ~204 KB gzip. Phần riêng của trang chủ chỉ ~4 KB.

**JS trình duyệt thật sự tải ở trang chủ** (`js.json`; khách, cache trống, chờ `load` + 1,5 s): 17 tệp, 689,3 KB thô, **215,5 KB gzip**, 221,2 KB qua mạng, 0 tệp bên thứ ba. Nhiều hơn bảng trên 3 tệp chunk tải lười sau khi trang hiện.

Ngân sách Phase 7: nhân vật + Motion thêm ≤ 50 KB gzip ở màn đầu → trang chủ ≤ ~259 KB (First Load) / ~266 KB (tải thật).

## 3. Lighthouse mobile

3 lượt mỗi trang, mỗi lượt một Chrome mới (cache và hồ sơ trống). Bảng lấy lượt có điểm hiệu năng ở giữa; cột "khoảng" là min–max của 3 lượt. Trang chủ và chi tiết khóa học đo như khách lần đầu ghé; trang học (bài video "Cài đặt Python và VS Code") đo với một phiên đăng nhập mới của học viên mỗi lượt, cả 3 lượt dừng đúng ở URL bài học.

| Trang | Hiệu năng | LCP | CLS | TBT | FCP | Speed Index | Truy cập | Best practices | SEO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Trang chủ | 96 | **2,56 s** | 0,001 | 96 ms | 1,06 s | 1,06 s | 96 | 96 | 100 |
| Chi tiết khóa học | 95 | **2,56 s** | 0,002 | 177 ms | 1,21 s | 1,21 s | 100 | 96 | 100 |
| Trang học | 91 | **3,31 s** | 0,002 | 97 ms | 1,06 s | 2,98 s | 95 | 100 | 60 ¹ |

| Khoảng 3 lượt | Hiệu năng | LCP | CLS | TBT |
|---|---|---|---|---|
| Trang chủ | 85–96 | 2,56–3,01 s | 0,001–**0,178** | 96–128 ms |
| Chi tiết khóa học | 94–96 | 2,56–2,71 s | 0,002 | 119–177 ms |
| Trang học | 90–91 | 3,31–3,39 s | 0,002 | 90–114 ms |

¹ Trang học cố ý `noindex` (audit `is-crawlable`), không phải lỗi.

Điều Phase 7 phải biết (ngân sách: LCP ≤ 2,5 s, CLS ≤ 0,1, không tệ hơn cột này):

- **Cả ba trang đã vượt LCP 2,5 s ở bước "trước"**. Trang chủ: phần tử LCP là ảnh banner đầu tiên, thiếu `fetchpriority="high"` (`lcp-discovery-insight`); tải ảnh chỉ ~33 ms, phần lớn là trễ vẽ (307 ms ở lượt trung vị, 612 ms ở lượt 1). Trang học: phần tử LCP là tiêu đề bài, chỉ vẽ sau khi client làm mới phiên rồi tải bài (Speed Index 2,98 s so với FCP 1,06 s).
- **CLS 0,178 ở lượt 1 trang chủ** (2 lượt sau 0,001): khối "Học lập trình bằng cách viết code…" dưới banner bị đẩy xuống, tức khung banner chưa giữ chỗ khi ảnh về chậm. Một lượt trên ba là đủ để vượt 0,1.
- Truy cập 96 ở trang chủ: 3 chấm chuyển banner chỉ 24×8 px (`target-size`). Trang học 95: một nút không có tên (`button-name`).
- Best practices 96: lỗi console `401 /api/v1/auth/refresh` ở trang công khai — khách mở trang thì frontend hỏi phiên và nhận 401 như thiết kế, nhưng Lighthouse đếm là lỗi.

## 4. axe-core (12 trang)

`axe.json` — 10 trang của khách/học viên (trang chủ, danh sách, chi tiết khóa học, bảng xếp hạng, chứng chỉ, bài video, bài code, khóa học của tôi, giỏ hàng, hồ sơ), `/giang-day/thong-ke` của giảng viên seed, `/quan-tri` của admin seed. Ở 1440 px, chờ mạng yên + 1,2 s.

| Trang | Luật | Mức | Nút | Nguyên nhân |
|---|---|---|---:|---|
| `/bang-xep-hang` | `aria-valid-attr-value` | **critical** | 1 | Tab "Tuần này" dùng `TabsTrigger` mà không có `TabsContent`, nên `aria-controls` của Radix trỏ vào panel không tồn tại — `components/gamification/leaderboard-view.tsx` |
| `/giang-day/thong-ke` | `aria-required-attr` | **critical** | 2 | `role="meter"` bỏ `aria-valuenow` khi giá trị là null (khóa chưa có học viên) — `components/instructor/stats/course-stats-table.tsx` |
| `/khoa-hoc` | `heading-order` | moderate | 1 | Thẻ khóa học dùng `h3` ngay dưới `h1`, không có `h2` |
| 9 trang còn lại | — | — | 0 | |

Gate Phase 7 đòi 0 lỗi `critical`/`serious`: "trước" là **2 critical trên 2 trang**.

## 5. Ảnh giao diện

- [`before/ui/`](before/ui/) — **42/42 ảnh** của `phase-6/ui/capture.cjs` (khách, học viên, người mua, giảng viên, admin, khóa tạm; 1440 px và 3 ảnh 375 px), `capture-log.json`. Cùng tên tệp với bộ 05/10 ở `phase-6/ui/`, nên ảnh "sau" so được theo từng tên.
- [`before/tiers-finance/`](before/tiers-finance/) — 12 màn của Phase 6.5 (`phase-6/tiers-finance/capture.cjs`: doanh thu, xếp hạng, cấp giảng viên, thanh toán, lãi lỗ, bảng kê, thống kê + cấp bậc của giảng viên), không có lỗi console, giảng viên không thấy số tiền nào.

Tài khoản thật duy nhất trên stack demo (tài khoản Google của user, vai giảng viên) được **làm mờ trước khi chụp**: hai script đọc tên + email của mọi tài khoản không phải `*.example` từ CSDL, rồi `blurPrivate()` (`stack.cjs`) làm mờ mọi phần tử chứa chúng và mọi ảnh đại diện Google. Ảnh có che: `ui/44`, `tiers-finance/05`, `06` (tên, email, ảnh đại diện); `tiers-finance/02`, `03` che một `<option>` trong ô chọn giảng viên, không hiện trên ảnh. Quét lại mọi tệp chữ trong `phase-7/` và hai thư mục script: 0 chỗ có tên/email đó.

Thấy được trên ảnh, để dành cho nhóm màn tương ứng:

- **Thanh tab admin có 10 mục, tràn ở 1440 px** — "Báo cáo vi phạm" bị cắt, "Người dùng" khuất (`ui/42`–`47`). Lộ ra từ Phase 6.5 (5 tab tài chính mới) → nhóm 10.
- Bảng xếp hạng tuần chỉ có dữ liệu thứ Hai–thứ Ba (tuần bắt đầu 19/10).

## 6. Dữ liệu ghi trong lúc đo và đã dọn

`capture.cjs` trước đây dựa vào hocvien07/hocvien25 của `seed_interactions` + `seed_community`, đã gỡ khỏi CSDL từ 06/10, và quiz khóa Python soạn tay chỉ có trên CSDL dev. Giờ script tự dựng thứ nó cần qua đúng API của UI, đều là tài khoản dùng một lần `@e2e.devpath.example`:

- một học viên: ghi danh khóa Python, 3 ghi chú theo mốc video, một câu hỏi ở bài "Ép kiểu…" (giảng viên seed trả lời qua API → thông báo cho cả hai bên), một báo cáo khóa học, bốn câu trợ giảng AI của buổi demo 22/09 (2 câu có nguồn, 2 câu bị từ chối — 4 lượt Gemini), một khóa có phí trong giỏ + 2 khóa yêu thích, hai lần nộp bài "đếm số chẵn" (WA rồi AC);
- một giảng viên: khóa "Git cho người mới bắt đầu", quiz 5 câu sinh bằng Gemini, gửi duyệt; admin seed duyệt qua API; học viên trên làm quiz đó (80 %).

Cuối mỗi lượt: xóa thông báo `qa_question` mà câu hỏi tạm để lại cho giảng viên seed (theo `thread_id`), rồi `scripts.purge_e2e`. Kiểm sau cả ba script: 0 tài khoản `@e2e.devpath.example`, 0 `payout_statements` (bảng kê nháp của ảnh 12 đã xóa), 0 thông báo `qa_question`, 0 báo cáo. `measure.cjs` dùng một học viên dùng một lần riêng, cũng purge ở cuối.

## 7. Chạy lại (cột "sau" phải đi đúng đường này)

```bash
cd infra && ./scripts/deploy.sh                       # bản cần đo lên stack demo
docker exec devpath-demo-backend-1 python -m scripts.seed_study --purge
docker exec devpath-demo-backend-1 python -m scripts.seed_sales --purge
./scripts/seed-demo.sh && cd ..
set -a && . infra/.env.seed-demo && set +a
export npm_config_cache=D:/devpath-tmp/npm-cache TEMP=D:/devpath-tmp/temp TMP=D:/devpath-tmp/temp
BASE_URL=https://devpath-01.me API_URL=https://devpath-01.me RESOLVE_TO=127.0.0.1 COMPOSE_PROJECT=devpath-demo \
  OUT_DIR=docs/report/assets/phase-7/after/ui NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/ui/capture.cjs
BASE_URL=https://devpath-01.me API_URL=https://devpath-01.me RESOLVE_TO=127.0.0.1 \
  OUT_DIR=docs/report/assets/phase-7/after/tiers-finance NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/tiers-finance/capture.cjs
LABEL=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/measure.cjs
```

`npm_config_cache`/`TEMP` sang ổ D: vì ổ C: gần đầy từng làm Docker Desktop chết giữa lượt đo 18/10. Dừng stack dev trước khi đo. Thời gian: chụp ~6 phút, đo ~3 phút.

## 8. Hai trục trặc của công cụ đo, và cách đã chọn

- **Lighthouse gắn vào Chrome của Playwright (`--port`) thì treo**: tab Lighthouse mở ra đứng im ở `Page.navigate` 10 phút (Playwright tự gắn vào mọi tab mới). Nối Playwright vào một Chrome tự mở rồi ngắt ra trước khi chạy Lighthouse thì Lighthouse báo `NO_NAVSTART`. Lighthouse tự mở Chrome thì chạy (thử trên example.com rồi trên trang chủ). Lighthouse không nhận `--user-data-dir` qua `--chrome-flags` (chrome-launcher luôn dùng hồ sơ tạm của nó), nên trang học nhận cookie phiên qua `--extra-headers`, mỗi lượt một phiên mới (refresh token xoay vòng; dùng lại cookie cũ quá 30 s là bị coi là token bị trộm).
- Báo cáo Lighthouse bỏ ảnh chụp base64 (dải phim, ảnh cuối, ảnh cả trang) trước khi lưu: 5,3 → 2,1 MB cho 9 tệp, mọi số đo và chẩn đoán còn nguyên. Lighthouse còn chép `--extra-headers` vào `configSettings`, tức cookie refresh của phiên đo: `slim()` thay bằng `<đã xóa>` (phiên đó đã đăng xuất và tài khoản đã purge, nhưng token không vào repo).

## 9. Tệp

| Tệp | Nội dung |
|---|---|
| `before/summary.json` | Tóm tắt: commit, build, đường đi, First Load JS 3 route, 9 lượt Lighthouse + trung vị, axe theo trang, kết quả purge |
| `before/bundle-stats.json` | First Load JS của 37 route (tệp, thô, gzip) |
| `before/js.json` | Từng tệp JS trang chủ tải thật (transfer, decoded, thô, gzip) |
| `before/axe.json` | Vi phạm axe của 12 trang (luật, mức, số nút, selector mẫu) |
| `before/lighthouse/*.json` | 9 báo cáo Lighthouse (đã bỏ ảnh) |
| `before/ui/`, `before/tiers-finance/` | 42 + 12 ảnh |
| `measure.cjs`, `stack.cjs` | Script đo và helper đường đi |
| `../phase-6/ui/capture.cjs`, `../phase-6/tiers-finance/capture.cjs` | Hai script chụp (sửa 20/10 để chạy trên dữ liệu hiện tại và đường nội bộ) |
