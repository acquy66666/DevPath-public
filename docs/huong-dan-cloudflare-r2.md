# Hướng dẫn tạo bucket Cloudflare R2 + access key

Cần cho task **upload video** (Phase 2) và dùng lại cho avatar, phụ đề, ảnh thumbnail. R2 là object storage tương thích S3, **không tính phí egress** — đó là lý do đề cương chọn nó thay vì S3 cho một hệ thống phát video.

Toàn bộ phần này bạn phải tự làm: nó liên quan tới tài khoản và khóa bí mật, tôi không tạo hộ được. Xong bước 6 thì dán giá trị vào `infra/.env` (bước 7) là chạy được — code phía server đã xong và đã kiểm thử.

> **Cập nhật 18/09/2026 — máy dev không cần R2 nữa.** Stack dev có sẵn MinIO: để trống mọi `R2_*` là upload chạy được ngay, xem mục "Object storage trên máy dev" trong [infra/README.md](../infra/README.md). Hướng dẫn này giờ dành cho production (Phase 6), hoặc khi muốn thử R2 thật từ stack dev. Trường hợp sau thì phải điền **cả** `R2_ENDPOINT_URL=https://<account id>.r2.cloudflarestorage.com`, vì để trống thì nó rơi về MinIO.

---

## 1. Kích hoạt R2

1. Đăng nhập [dash.cloudflare.com](https://dash.cloudflare.com) (chưa có thì đăng ký, miễn phí, không cần domain).
2. Menu trái → **R2 Object Storage**.
3. Bấm **Purchase R2** / **Enable R2**. Cloudflare **bắt thêm phương thức thanh toán** dù bạn ở hạn mức miễn phí — đây là bước khó chịu nhất, không né được.

Hạn mức miễn phí mỗi tháng: **10 GB lưu trữ**, 1 triệu thao tác ghi (Class A), 10 triệu thao tác đọc (Class B), **băng thông ra miễn phí không giới hạn**. Vài khóa học demo không chạm tới đâu — cứ kiểm tra lại trên trang giá của Cloudflare cho chắc.

---

## 2. Tạo bucket

**R2 → Create bucket**

| Trường | Giá trị |
|---|---|
| Bucket name | `devpath-media` |
| Location | **Automatic**, hoặc chọn hint **Asia-Pacific (APAC)** |
| Storage class | Standard |

Đặt đúng tên `devpath-media` thì khỏi sửa gì; tên khác cũng được, chỉ cần nhớ để điền vào `R2_BUCKET`.

---

## 3. Lấy Account ID

Ngay trang **R2 Overview**, cột phải có mục **Account details → Account ID** — một chuỗi hex 32 ký tự. Copy lại.

Endpoint S3 của bạn sẽ là `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` — backend tự ghép, bạn chỉ cần cái ID.

---

## 4. Tạo API token (access key)

**R2 → Manage R2 API Tokens → Create API token**

| Trường | Giá trị |
|---|---|
| Token name | `devpath-backend` |
| Permissions | **Object Read & Write** |
| Specify bucket(s) | **Apply to specific buckets** → chọn `devpath-media` |
| TTL | Forever (hoặc đặt hạn nếu bạn muốn) |

Bấm **Create API Token**. Màn hình kế hiện ra:

- **Access Key ID**
- **Secret Access Key** ← **chỉ hiện đúng một lần**, rời trang là mất, phải tạo token mới

Copy cả hai ngay.

> Chọn *Object Read & Write* chứ không phải *Admin Read & Write*: token này chỉ cần đọc/ghi file trong đúng một bucket, không cần quyền tạo hay xóa bucket. Nếu nó lộ ra ngoài, thiệt hại dừng ở đó.

---

## 5. Mở CORS cho bucket

Trình duyệt **upload thẳng lên R2** (backend chỉ ký URL rồi đứng ngoài), nên bucket phải cho phép origin của frontend gọi `PUT`. Thiếu bước này thì upload chết ngay ở preflight với lỗi CORS.

**Bucket `devpath-media` → Settings → CORS Policy → Edit → Add CORS policy**, dán:

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:3000"
    ],
    "AllowedMethods": [
      "PUT",
      "GET",
      "HEAD"
    ],
    "AllowedHeaders": [
      "content-type"
    ],
    "ExposeHeaders": [
      "etag"
    ],
    "MaxAgeSeconds": 3600
  }
]
```

Khi deploy lên VPS thì thêm domain thật vào `AllowedOrigins` (thêm phần tử mới, giữ nguyên `localhost` để còn dev được).

---

## 6. Bật đường dẫn công khai để phát video

Trình duyệt phải tải được file `.m3u8` và các mảnh `.ts` thì mới phát HLS.

**Bucket → Settings → Public access → R2.dev subdomain → Allow Access**

Cloudflare trả về một URL dạng `https://pub-<chuỗi hex>.r2.dev`. Copy lại.

> `r2.dev` bị Cloudflare bóp băng thông và **họ nói rõ là không dùng cho production** — đủ tốt cho demo khóa luận. Khi lên VPS có domain riêng thì gắn **Custom Domain** vào bucket, đổi mỗi biến `R2_PUBLIC_BASE_URL` là xong, không phải sửa code.

---

## 7. Dán vào `infra/.env`

Chạy bằng Docker (cách thường dùng) thì điền vào **`infra/.env`** — copy từ `infra/.env.example` nếu chưa có. Compose truyền các biến này vào container `backend` và `worker`.

> Đừng điền vào `backend/.env` khi chạy Docker: compose luôn truyền biến môi trường (rỗng nếu `infra/.env` không có), mà biến môi trường **đè** file `.env`. Kết quả là điền một nơi, đọc một nơi khác, và endpoint vẫn trả 503. `backend/.env` chỉ dùng khi chạy backend trực tiếp trên máy, không qua Docker.

```env
R2_ACCOUNT_ID=<32 ký tự hex ở bước 3>
R2_ACCESS_KEY_ID=<bước 4>
R2_SECRET_ACCESS_KEY=<bước 4>
R2_BUCKET=devpath-media
R2_PUBLIC_BASE_URL=https://pub-xxxxxxxx.r2.dev
# Chỉ bắt buộc ở stack dev (infra/docker-compose.yml), nơi để trống nghĩa là MinIO.
R2_ENDPOINT_URL=https://<32 ký tự hex ở bước 3>.r2.cloudflarestorage.com
```

Ở **production** (`infra/.env.prod`), để trống bất kỳ dòng nào trong ba dòng đầu thì các endpoint upload trả **503 `STORAGE_NOT_CONFIGURED`**. Đây là có chủ đích, giống hệt cách Google OAuth đang làm, để phần còn lại của hệ thống vẫn chạy và test vẫn xanh khi chưa có khóa. Ở **stack dev** thì khác: từ 18/09/2026, để trống là rơi về MinIO local, không ra 503.

Cả `infra/.env` lẫn `backend/.env` đều đã nằm trong `.gitignore`. **Đừng bao giờ commit Secret Access Key** — nếu lỡ đẩy lên GitHub thì vào R2 → Manage API Tokens → xóa token đó và tạo cái mới, đừng chỉ sửa file.

---

## 8. Kiểm tra

Sau khi điền `.env` và khởi động lại backend:

```bash
docker compose -f infra/docker-compose.yml restart backend worker
```

Rồi thử upload một video ngắn ở `/giang-day/<id khóa học>` → mở một bài học dạng Video. Trạng thái sẽ đi qua `uploading → processing → ready`; xong là bài học có video phát được.

Luồng này đã chạy thật trên bucket R2 của dự án: video 10 giây → `ready` sau vài giây, manifest và segment tải công khai được, và tải lên lần nữa thì toàn bộ object của video cũ bị dọn khỏi bucket.

### Ảnh đại diện dùng chung cấu hình này

Upload avatar ở `/ho-so` đi đúng luồng ký URL này, cùng bucket và cùng CORS — không phải cấu hình thêm gì. Khác nhau ở bố cục key và giới hạn:

| | Video bài giảng | Ảnh đại diện |
|---|---|---|
| Key | `videos/<video_asset_id>/…` | `avatars/<user_id>/<ngẫu nhiên>.<ext>` |
| Định dạng | MP4, MOV, MKV, WebM | JPG, PNG, WebP (**không** SVG) |
| Giới hạn | 2 GB | 5 MB |
| Sau khi báo xong | worker transcode sang HLS | ghi `users.avatar_url`, xóa ảnh cũ |

Hai chi tiết có lý do:

- **Tên file ngẫu nhiên mỗi lần đổi ảnh.** URL công khai bị CDN và trình duyệt cache; dùng lại `avatar.png` thì người dùng đổi ảnh xong vẫn nhìn thấy ảnh cũ.
- **Không nhận SVG.** SVG là tài liệu chạy được script, mà bucket trả file về đúng content-type đã ký.

Nếu hỏng, xem theo thứ tự:

| Triệu chứng | Nguyên nhân hay gặp |
|---|---|
| 503 `STORAGE_NOT_CONFIGURED` | Thiếu một trong ba biến đầu, điền nhầm vào `backend/.env` khi đang chạy Docker, hoặc chưa restart backend |
| Lỗi CORS ở bước PUT (xem tab Network) | Bước 5 chưa làm, hoặc origin không khớp từng ký tự |
| `SignatureDoesNotMatch` | Copy nhầm/thiếu ký tự Secret Access Key |
| Upload xong nhưng kẹt ở `processing` | Worker chưa chạy hoặc ffmpeg lỗi — xem `docker compose logs worker` |
| `ready` nhưng player không phát | `R2_PUBLIC_BASE_URL` sai, hoặc bước 6 chưa bật public access |
| Script Python tải `.m3u8` bị **403** nhưng trình duyệt xem được | Cloudflare chặn User-Agent mặc định của `urllib` trên `r2.dev`. Không phải lỗi phân quyền — kiểm bằng `curl` hoặc đặt User-Agent của trình duyệt |
