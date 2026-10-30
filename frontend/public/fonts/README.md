# Font tự host

Các file `.woff2` ở đây là chính các file Google Fonts trả về, mỗi file một subset. `app/fonts.css` khai báo chúng với `unicode-range` của Google, nên trình duyệt vẫn chỉ tải subset mà trang thật sự dùng. Hai chỗ khác Google (Phase 7 — hiệu năng, 30/10/2026, số đo ở `docs/report/assets/phase-7/performance.md`):

- **Dải `latin-ext` bỏ phần chồng với `vietnamese`** (ă đ ĩ ũ ơ ư ỳ–ỹ ₫): Google khai các ký tự đó ở cả hai subset nên trang tiếng Việt nào cũng tải thêm `latin-ext` (34 KB với Lexend) dù tệp `vietnamese` đã có. Dải mới chỉ bỏ đúng các ký tự mà tệp `vietnamese` của từng font thật sự vẽ (đã đối chiếu bảng `cmap`; Geist Mono `vietnamese` không có ₫ nên `latin-ext` của nó giữ ₫). Lấy lại font thì làm lại phép trừ này.
- **Geist Mono `latin` tách đôi** bằng `frontend/scripts/split-mono-ascii.py` (fontTools): `geist-mono-ascii.woff2` (U+20–7E, 14 KB — được preload ở trang có code ngay màn đầu) và `geist-mono-latin-rest.woff2` (12 KB). Tệp `geist-mono-latin.woff2` của Google giữ lại làm nguồn, CSS không dùng nó.

| Font | Lấy ngày | Subset | Dùng ở |
|---|---|---|---|
| Lexend (variable, 400–700) | 21/10/2026 (`lexend/v26`) | vietnamese, latin-ext, latin | Toàn site (`--font-lexend`). Thay Geist ngày 21/10: lý do ở [`docs/ui-ux/design-system/fonts.md`](../../../docs/ui-ux/design-system/fonts.md) |
| Geist Mono 1.701 | 06/10/2026 | cyrillic-ext, cyrillic, symbols, vietnamese, latin-ext, latin (tách thành `ascii` + `latin-rest`) | Code (`--font-geist-mono`) |
| Noto Serif 2.015 (600–700) | 06/10/2026 | vietnamese, latin-ext, latin | Tiêu đề + tên trên trang chứng chỉ (`.font-certificate`) |

Giấy phép: SIL Open Font License 1.1, xem [OFL.txt](OFL.txt).

## Vì sao không dùng `next/font/google`

`next/font/google` tải CSS và file font từ Google **mỗi lần** `next build` hoặc `next dev` chạy. Khoảng 1/60 lần, Google trả URL dạng `fonts.gstatic.com/l/font?kit=…&skey=…&v=…`. Next không phân tích được URL này: Turbopack báo `next/font/google queries have exactly one entry`, còn webpack báo `TypeError`. Lỗi đã được báo ở [vercel/next.js#99114](https://github.com/vercel/next.js/issues/99114), nhưng tới 06/10/2026 Turbopack vẫn chưa có bản sửa.

Hậu quả là build production hỏng ngẫu nhiên: `deploy.sh` build lại image ở mỗi lần deploy. Còn với `next dev`, chỉ một lần tải hỏng là mọi trang trả 500. E2E trên `main` sau PR #88 đã đỏ vì đúng lỗi này.

Giờ build không gọi ra mạng nữa. Kiểm bằng lệnh sau (đứng ở thư mục gốc repo, stack dev đang chạy):

```bash
docker run --rm --network none --volumes-from devpath-frontend-1 devpath-frontend:dev sh /app/scripts/build-offline.sh
```

Khi stack dev đang tắt (ví dụ stack demo đang chạy), dùng image dev với một volume ẩn danh cho `node_modules`. Docker sẽ chép `node_modules` Linux của image vào volume đó, nên không dùng bản Windows trên máy. Trong Git Bash cần `MSYS_NO_PATHCONV=1` để đường dẫn `/app/...` không bị đổi:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network none -v "$PWD/frontend:/app" -v /app/node_modules devpath-frontend:dev sh /app/scripts/build-offline.sh
```

`npm run lint` chặn mọi import `next/font/google`.

## Lấy lại / đổi font

Không cần bật lại `next/font/google` (cách làm ngày 06/10). Cách làm từ 21/10:

1. Hỏi CSS của Google Fonts bằng User-Agent của Chrome, ví dụ `https://fonts.googleapis.com/css2?family=Lexend:wght@400..700&display=swap`. Mỗi khối `@font-face` có comment tên subset, `unicode-range` và URL woff2. `docs/ui-ux/design-system/font-eval/fetch.mjs` làm đúng việc này và kiểm chữ ký `wOF2` của từng tệp.
2. Tải từng tệp về thư mục này, đặt tên `<font>-<subset>.woff2`. Chép khối `@font-face` sang `app/fonts.css`, đổi `src` thành `/fonts/<tên>`.
3. Mặt `… Fallback` lấy đúng số `next/font` sẽ sinh: `node -e "console.log(require('next/dist/server/font-utils').calculateSizeAdjustValues('Lexend'))"` (chạy trong `frontend/`) → `ascent-override`, `descent-override`, `line-gap-override`, `size-adjust`. Với Geist, lệnh này ra đúng số đang có trước đây, tức là cùng nguồn.
4. Thêm dòng bản quyền của font vào `OFL.txt`, sửa `PRELOADED_FONTS` trong `app/layout.tsx` nếu đổi font chữ chính. Cuối cùng chạy lệnh build không mạng ở trên và E2E luồng vàng để kiểm.
