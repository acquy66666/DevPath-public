# Phase 7 — Nhóm màn 2: Trang công khai (22–23/10/2026)

Nhóm màn đầu tiên của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): trang chủ, danh sách + tìm kiếm, chi tiết khóa học, trang "Trở thành giảng viên". Nhánh `feature/phase7-public-pages`. Backend không đổi.

"Trang giảng viên" trong plan được hiểu là `/tro-thanh-giang-vien`. Sàn không có trang hồ sơ giảng viên công khai, và backend không có API cho nó. Backend đứng yên suốt Phase 7, nên làm trang hồ sơ là việc của sau.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 2: Trang công khai"**: <https://claude.ai/artifact/JEVpC3YxF8tst9t27965UK>. Bản trong repo: [`docs/ui-ux/public-pages/canvas/`](../../../ui-ux/public-pages/canvas/project/canvas.json).

- **12 artboard:** 4 trang × (1440 + 375 px), cộng bảng "Thẻ khóa học + ảnh bìa" và 3 thành phần dùng chung (header, footer, thẻ khóa học).
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Màu ghi bằng mã hex của token, như canvas linh vật.
- **Naomi:** hai hình `celebrate` và `wave` chép từ canvas linh vật.
- **Khớp với code:** sau khi code, canvas được sửa theo code ở bản 12 (code thắng): ký hiệu bìa không còn dấu cách, và chân thẻ chỉ còn đánh giá + giá.

Mockup vẽ đúng dữ liệu thật của CSDL dev: 4 khóa, cây danh mục, mục lục khóa giải thuật. Không có số liệu bịa. Ví dụ "Khóa có đánh giá 4,6 (12)" ghi rõ trong ngoặc vuông là trạng thái mẫu.

## 2. Đổi gì

| Trang | Trước | Sau |
|---|---|---|
| **Thẻ khóa học** (mọi lưới khóa, cả "Khóa học của tôi", yêu thích) | Bìa gradient chàm/cam/hồng viết tay + mũ tốt nghiệp; hai badge; số liệu và giá chen nhau | Bìa "vài dòng code + cặp ngoặc" theo 6 dải màu minh họa của design system, không dùng nghệ (`lib/courses/cover.ts`); một dòng nhãn "Danh mục · Trình độ"; giảng viên có avatar; dòng "n học viên · thời lượng"; chân thẻ là đánh giá (sao `reward-mark`) và giá, "Miễn phí" là badge `success`. Rê chuột nhấc 2 px + `shadow-md` trong `duration-fast`, giảm chuyển động thì không nhấc |
| **Trang chủ** | Banner gradient tím chiếm màn đầu; hero chỉ có chữ; đã đăng nhập vẫn mời "Tạo tài khoản miễn phí"; hàng "Gợi ý cho bạn" 1 thẻ trống 3/4 hàng | Hero hai cột: lời hứa + minh họa một bài nộp AC 100/100 (code Python, 3 test, Naomi `celebrate` tĩnh) vẽ bằng chữ và token, không phải ảnh. Nút thứ hai đổi thành "Khóa học của tôi" khi đã đăng nhập (cùng cỡ nên không xê dịch). Banner xuống dưới hero, mũi tên + "1 / 3" gom vào góc. Thêm "Duyệt theo chủ đề" (mỗi danh mục một link lọc sẵn). Khối gợi ý chỉ có 1–2 khóa thì vẽ thẻ nằm ngang (`CourseRowCard`), hai cột |
| **Danh sách + tìm kiếm** | Một hộp lọc 6 ô + nút "Lọc" | Đầu trang trên nền `card`: tiêu đề, ô tìm kiếm 48 px + nút "Tìm", hàng chip chủ đề (giữ từ khóa khi đổi chủ đề). Giá / đánh giá / sắp xếp nằm cạnh số kết quả, đổi là gửi ngay; trên điện thoại gom sau nút "Bộ lọc · n". Vẫn là form GET: mọi chế độ lọc là một URL, tắt JavaScript vẫn lọc được (ô chọn nối vào form bằng thuộc tính `form`) |
| **Chi tiết khóa học** | Đầu trang trên nền trang, thẻ giá có bảng "Trình độ/Ngôn ngữ/…" lặp lại phần đầu | Đầu trang là một dải `card` chạy hết bề ngang (bóng trải + `clip-path`, nên thẻ giá vẫn đè lên dải và dính khi cuộn). Đường dẫn "Khóa học / Danh mục" đều là link. Ngày xuất bản lên dòng thông tin. Thẻ giá có "Khóa học gồm" đếm từ mục lục thật: n video · thời lượng, bài đọc, quiz, bài tập code chấm tự động (loại nào không có thì không hiện), trợ giảng AI, chứng chỉ. Mục lục: chữ loại bài ("Video", "Bài đọc"…) cạnh icon, mũi tên xoay khi mở chương |
| **Trở thành giảng viên** | Một thẻ giữa trang; giảng viên được bảo "Trang quản lý khóa học đang được xây dựng" (câu cũ từ Phase 2) | Trang hai cột: "Bạn có những gì" (4 công cụ thật của khu giảng viên), "Từ tài khoản tới khóa học trên sàn" (nâng cấp → nháp → gửi duyệt → lên sàn). Thẻ hành động: học viên có Naomi `wave` + "Chào <tên>"; giảng viên được dẫn "Vào khu giảng dạy"; khách đăng nhập rồi quay lại đúng trang (`?next=`). Footer có thêm link tới trang này, trước đây khách không có lối vào |

Naomi ở nhóm này luôn **tĩnh**: trang chủ và trang giảng viên không có sự kiện nào vừa xảy ra để phản ứng (bản đồ phản ứng, mục 5). Mỗi màn chỉ một Naomi.

## 3. Lỗi tìm ra khi làm

- **Thẻ khóa học làm trang 360 px tràn 13 px.** Dòng nhãn và tên giảng viên dùng `truncate` (`white-space: nowrap`). Phần tử của lưới một cột có `min-width: auto`, nên vẫn tính độ rộng của cả dòng không xuống hàng. Lần đo đầu ra 2/132 lượt xem tràn (danh sách, "Khóa học của tôi" của học viên). Đổi sang `line-clamp-1`, cũng cắt một dòng nhưng độ rộng tối thiểu chỉ là từ dài nhất: 0/132.
- **Skeleton của "Học tiếp theo" thiếu dòng mô tả** mà khối thật có, nên trang nhảy một dòng khi khối tới. Giờ `CourseBlockSkeleton` tách `described` (dòng dưới tiêu đề) khỏi `notes` (dòng lý do trên thẻ). Trước đó một cờ làm cả hai, nên "Khóa học mới" không dùng được.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **35/35** (4 test mới ở `lib/courses/cover.test.ts`: một khóa một bìa; 400 khóa dùng đủ 6 màu và 6 ký hiệu; mọi lớp màu của bìa là bậc có trong `globals.css` và không phải nghệ; đếm mục lục theo loại, đúng thứ tự, bỏ loại vắng) |
| `tsc --noEmit`, `eslint app components lib` | sạch |
| Tràn ngang (`foundation/overflow.cjs`, 44 route × 360/375/1440 × 4 vai, stack dev) | lần đầu 2/132, sau khi sửa **0/132** (`public-pages/overflow.json`) |
| E2E luồng vàng (stack dev) | **1 passed** (23,1 s), không sửa spec: chữ và vai trò mà spec dựa vào ("Thêm vào giỏ hàng", tiêu đề h1 của khóa) giữ nguyên |

## 5. Ảnh — `public-pages/before/` và `public-pages/after/`

[`public-pages/capture.cjs`](public-pages/capture.cjs) chụp 18 ảnh toàn trang cho `PHASE=before` (code của `main` @ `47850b1`) và `PHASE=after`, trên stack dev, ở 1440 và 375 px:

| Ảnh | Ai xem |
|---|---|
| `trang-chu-khach`, `danh-sach`, `tim-python`, `chi-tiet-tra-phi`, `chi-tiet-mien-phi`, `giang-vien-khach` | khách |
| `trang-chu-hoc-vien` (có "Gợi ý cho bạn"), `chi-tiet-da-ghi-danh`, `giang-vien-hoc-vien` | `nguoimua08@sales.devpath.example` (chỉ đọc, đăng xuất ở cuối) |

Banner trong ảnh vẫn là gradient tím: đó là ảnh do `scripts.seed_banners` sinh ra (dữ liệu, không phải giao diện). Đổi bảng màu của script đó là một việc riêng, đã ghi ở mục 6.

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/public-pages/capture.cjs
```

## 6. Để lại

- **Ảnh banner mẫu** (`backend/scripts/seed_banners.py`) vẽ gradient tím–lam, đúng thứ design system ghi ở mục "Không làm". Sinh lại bằng màu ngọc/nghệ là việc của dữ liệu demo, làm trước khi chụp bộ ảnh chương 4 ở gate.
- **Trang hồ sơ giảng viên công khai** cần một endpoint mới, nên để sau Phase 7.
- **Ô chọn ở thanh lọc admin cắt dấu** (ghi từ task trạng thái toàn site) vẫn là việc của nhóm 10. `NativeSelect` ở trang danh sách giữ chiều cao 40 px nên không bị.
