# Font tự host

Các file `.woff2` ở đây là chính các file Google Fonts trả cho `next/font/google` (đo ngày 06/10/2026), mỗi file một subset. `app/fonts.css` khai báo chúng với đúng `unicode-range` Next đã sinh, nên trình duyệt vẫn chỉ tải subset mà trang thật sự dùng.

| Font | Phiên bản | Subset | Dùng ở |
|---|---|---|---|
| Geist | 1.800 | cyrillic-ext, cyrillic, vietnamese, latin-ext, latin | Toàn site (`--font-geist-sans`) |
| Geist Mono | 1.701 | cyrillic-ext, cyrillic, symbols, vietnamese, latin-ext, latin | Code (`--font-geist-mono`) |
| Noto Serif (600–700) | 2.015 | vietnamese, latin-ext, latin | Tiêu đề + tên trên trang chứng chỉ (`.font-certificate`) |

Giấy phép: SIL Open Font License 1.1, xem [OFL.txt](OFL.txt).

## Vì sao không dùng `next/font/google`

`next/font/google` tải CSS và file font từ Google **mỗi lần** `next build` hoặc `next dev` chạy. Khoảng 1/60 lần, Google trả URL dạng `fonts.gstatic.com/l/font?kit=…&skey=…&v=…`. Next không phân tích được URL này: Turbopack báo `next/font/google queries have exactly one entry`, còn webpack báo `TypeError`. Lỗi đã được báo ở [vercel/next.js#99114](https://github.com/vercel/next.js/issues/99114), nhưng tới 06/10/2026 Turbopack vẫn chưa có bản sửa.

Hậu quả là build production hỏng ngẫu nhiên: `deploy.sh` build lại image ở mỗi lần deploy. Còn với `next dev`, chỉ một lần tải hỏng là mọi trang trả 500. E2E trên `main` sau PR #88 đã đỏ vì đúng lỗi này.

Giờ build không gọi ra mạng nữa. Kiểm bằng lệnh sau (đứng ở thư mục gốc repo, stack dev đang chạy):

```bash
docker run --rm --network none --volumes-from devpath-frontend-1 devpath-frontend:dev sh /app/scripts/build-offline.sh
```

`npm run lint` chặn mọi import `next/font/google`.

## Lấy lại / đổi font

1. Tạm dùng lại `next/font/google` trong `app/layout.tsx` với font và subset mới, rồi chạy `next dev`.
2. Mở trang, lấy file CSS font trong `/_next/static/chunks/…css`. Từ đó chép từng khối `@font-face`, gồm `unicode-range` và các mặt `… Fallback` với `size-adjust`/`ascent-override`, sang `app/fonts.css`.
3. Tải từng file `/_next/static/media/*.woff2` mà khối đó trỏ tới về thư mục này, đặt tên theo dạng `<font>-<subset>.woff2`.
4. Gỡ lại `next/font/google`. Cuối cùng chạy lệnh build không mạng ở trên và E2E luồng vàng để kiểm.
