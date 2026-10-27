# Phase 7 — Nhóm màn 7: Tài khoản (27/10/2026)

Nhóm màn 7 của mục "Thiết kế lại theo nhóm màn" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): đăng nhập, đăng ký (giữ điều kiện "form chỉ gửi sau hydrate"), hồ sơ, màn chào mừng sau đăng ký với Naomi `wave`. Nhánh `feature/phase7-account`, từ `main` sau PR #126. Backend không đổi.

## 1. Mockup

Artifact Design **"DevPath — Nhóm 7: Tài khoản"**: <https://claude.ai/artifact/EMciYF4e8wDtYhT81XUKTu>. Bản trong repo: [`docs/ui-ux/account/canvas/`](../../../ui-ux/account/canvas/project/canvas.json).

- **9 artboard:** đăng nhập 1440 và 375; trạng thái form (lỗi từng ô, sai mật khẩu, email đã có tài khoản, quá số lần thử, đang gửi, mật khẩu đang hiện); đăng ký 1440 (đến từ trang khóa học, mật khẩu đạt) và 375 (email đã có, mật khẩu còn thiếu); màn chào mừng 1440 và 375; hồ sơ 1440 (Người mua 08, vừa đổi mật khẩu) và 375 (tài khoản Google).
- **Design system:** cài bản DevPath (`project/ds/devpath/tokens.json`). Naomi là hình `wave` chép từ canvas linh vật.
- **Dữ liệu thật** trên CSDL dev: Người mua 08 (chuỗi 7 ngày, 350 XP), 8 danh mục, 3 khóa miễn phí, khóa "Python cơ bản cho người mới bắt đầu". "Lê Thu Hà" là tên mẫu gõ vào form.
- **Duyệt:** chưa có lời duyệt của user khi code; làm theo mockup với giả định ghi ở đây và ở `decisions.md`. User đổi hướng thì sửa theo.

## 2. Đổi gì

| Phần | Trước | Sau |
|---|---|---|
| **Khung đăng nhập/đăng ký** | Logo + một thẻ hẹp giữa trang, không có gì nói vì sao nên ở đây | Từ `lg`: thẻ hai cột 1040 px. Bên trái nền ngọc nhạt: logo, Naomi `wave` 176 px (đứng yên), tiêu đề, một câu, ba điểm. Bên phải: form. Dưới `lg`: form một cột, Naomi 72 px cạnh tiêu đề. Dưới thẻ: "Chính sách bảo mật" |
| **Đăng nhập** | Hai ô, nút, "Đăng ký" | "Chào mừng trở lại / Tiến độ, bài đã nộp, ghi chú và chuỗi ngày học của bạn vẫn ở đây." Nút Google cao bằng nút chính, "hoặc dùng email". Ô mật khẩu có nút **Hiện/Ẩn**. "Đăng ký miễn phí" giữ `next` |
| **Đăng ký** | "Tối thiểu 8 ký tự" là dòng chữ xám cố định | Đến từ trang khóa học thì "Xong là bạn quay lại *Python cơ bản cho người mới bắt đầu*." **Dòng luật mật khẩu đếm ngược** ("Tối thiểu 8 ký tự · còn 5") rồi thành dấu tích xanh; quá 72 byte thì đỏ ngay khi gõ. Câu đồng ý chính sách bảo mật. "Đăng nhập" giữ `next` |
| **Lỗi form** | Lỗi nằm yên ở ô cho tới lần gửi sau; con trỏ không di chuyển | Gửi khi sai → **con trỏ về ô sai đầu tiên**. Gõ lại vào ô nào thì lỗi của ô đó biến mất. Sai mật khẩu → ô mật khẩu trống và nhận con trỏ, email giữ nguyên. Email đã có tài khoản → liên kết **"Đăng nhập với email này"** (mang email và `next`; trang đăng nhập điền sẵn email, con trỏ ở ô mật khẩu) |
| **Sau đăng ký** | Về trang chủ, không chào | **`/chao-mung`**: khối ngọc với Naomi `wave` 220 px, "Chào Hà, mình là Naomi!", một câu Naomi tự giới thiệu, nút chính "Quay lại “Python cơ bản…”" (hoặc "Khám phá khóa học" nếu không đến từ đâu) + nút phụ. Rồi "Học trên DevPath thế nào" (3 bước), "Bắt đầu với một chủ đề" (danh mục), "Khóa miễn phí để bắt đầu" (3 khóa) |
| **Hồ sơ** | Ba thẻ chồng nhau: ảnh đại diện, thông tin, mật khẩu | **Thẻ tài khoản**: ảnh + nút "Tải ảnh lên" ngay dưới ảnh, tên, email, chip vai trò + ngày tham gia, luật ảnh; hai ô "Chuỗi ngày" (nền nghệ khi đang giữ chuỗi) và "Tổng XP" dẫn sang "Khóa học của tôi" / bảng xếp hạng. Rồi hai **mục cài đặt** hai cột (tên + câu giải thích bên trái, form bên phải): "Thông tin cá nhân" (email chỉ đọc trong ô xám, "Chưa có gì thay đổi" / "Đã lưu thay đổi." cạnh nút), "Đổi mật khẩu" (hai ô có Hiện/Ẩn, dòng luật đếm ngược, Alert thành công màu xanh) |
| **Tài khoản Google** | "Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu. Đặt mật khẩu riêng là tính năng sẽ bổ sung sau." | Mục "Mật khẩu" với chữ G của Google: "… chưa có mật khẩu riêng. Bạn vào DevPath bằng nút “Đăng nhập bằng Google”." (bỏ lời hứa tính năng chưa có) |
| **Khách mở `/ho-so`** | Thẻ "Đăng nhập để xem hồ sơ" + nút | Khung như cổng trang học: Naomi `wave` đứng yên, câu nói trang này có gì, nút "Đăng nhập" quay lại `/ho-so` |
| **Skeleton** | Thẻ đăng nhập 338 px; hồ sơ ba thẻ đo 22/10 | Đo lại 27/10: thẻ 1040 × 558 (1440) / 446 px (375); hồ sơ 194 + 301 + 301 / 348 + 419 + 375 px |

**Naomi** (bản đồ phản ứng, thiết kế mục 5), mỗi màn một Naomi:

| Màn | Mood | Phản ứng khi | Đứng yên khi |
|---|---|---|---|
| `/chao-mung` | `wave` | lần đầu mở trang ngay sau khi đăng ký trong tab này | tải lại; mở lại sau; tài khoản khác; khách |
| Đăng nhập, đăng ký | `wave` | — | luôn (chưa có gì xảy ra để phản ứng) |
| `/ho-so` (khách) | `wave` | — | luôn |

## 3. Lỗi tìm ra khi làm

- **Liên kết qua lại giữa đăng nhập và đăng ký làm rơi `next`.** Người được đưa sang đăng nhập từ một khóa học, bấm "Đăng ký" vì chưa có tài khoản, thì đăng ký xong về trang chủ thay vì khóa đó. Giờ cả hai liên kết giữ `next` (`authHref`).
- **Lỗi của ô che dòng luật mật khẩu**: bấm gửi khi trống thì "Vui lòng nhập mật khẩu" nằm mãi dưới ô, kể cả khi đã gõ lại, và dòng đếm ngược không hiện. `check.cjs` bắt được; giờ gõ vào ô nào thì lỗi ô đó được gỡ.
- **Sai mật khẩu hiện tại ở hồ sơ dùng mã `INVALID_CURRENT_PASSWORD`**, không phải `INVALID_CREDENTIALS` như đăng nhập: bản đầu đặt sai mã nên ô không được xóa. Sửa trước khi `check.cjs` chạy lần đầu.
- **Stack dev không chạy được**: image backend cũ thiếu `openpyxl` (thêm ở Phase 6.5) nên backend chết lúc import. `docker compose up -d --build` dựng lại.
- Lỗi của chính script, ghi lại cho lần sau: `ck_users_credential` đòi `password_hash` hoặc `oauth_sub`; biến tài khoản dùng một lần thành tài khoản Google phải đặt cả `oauth_provider`/`oauth_sub`.

## 4. Kiểm

| Kiểm | Kết quả |
|---|---|
| `npm test` | **126/126** (9 test mới: `lib/account/welcome.test.ts` 6 — tên gọi trong lời chào, đường sau đăng ký, liên kết giữ `next`, slug khóa từ `next`, nút chính của màn chào mừng, dấu "vừa đăng ký"; `lib/auth/validation.test.ts` 3 — dòng luật đếm ngược, khớp với kiểm lúc gửi ở mọi độ dài, quá số byte) |
| `tsc --noEmit`, `npm run lint` | sạch |
| Hành vi trên Chrome thật ([`account/check.cjs`](account/check.cjs), stack dev, cho phép chuyển động) | **37/37** ([`results.json`](account/results.json)): ô nhập không có `name`, đúng một form, `getByLabel("Mật khẩu")` ra một ô; Hiện/Ẩn; con trỏ về ô sai đầu tiên; sai mật khẩu xóa ô và đưa con trỏ về; liên kết giữ `next`; dòng luật đếm ngược → dấu tích; "Đăng nhập với email này" mang email + `next` và điền sẵn; sau đăng ký tới `/chao-mung?next=…`, gọi "Hà", `wave` phản ứng một lần, tải lại thì đứng yên, nút chính quay lại khóa; hồ sơ lưu tên (header đổi theo), sai mật khẩu hiện tại, hai ô chỉ số dẫn đúng trang; khách ở `/ho-so` và `/chao-mung`; axe 0 critical/serious ở cả 4 trang; một Naomi và 0 tràn ở 360 px; giảm chuyển động thì 0 animation |
| Tràn ngang (`foundation/overflow.cjs`, giờ 46 route × 360/375/1440 × 4 vai, thêm `/chao-mung` cho khách và học viên) | **0/138** ([`account/overflow.json`](account/overflow.json)) |
| E2E luồng vàng (stack dev) | **1 passed** (18,2 s). Spec sửa cùng commit: sau "Tạo tài khoản" chờ `/chao-mung` và tiêu đề "… mình là Naomi" thay vì `/` |
| `next build` không mạng | xanh (`frontend/scripts/build-offline.sh`, `--network none`, `--volumes-from devpath-frontend-1`) |
| CSP | không chạy lại `csp-probe.cjs`: nhóm này không tải thêm gì mới (hình `wave` là chunk cùng origin, đo ở task component). Script đó và `phase-7/measure.cjs` giờ nhận cả `/` lẫn `/chao-mung` sau đăng ký, để chạy được trên commit cũ và mới |

## 5. Ảnh — `account/before/` và `account/after/`

[`account/capture.cjs`](account/capture.cjs) chụp như khách, Người mua 08 (chỉ đọc) và hai tài khoản dùng một lần (`purge_e2e` ở cuối; một cái được biến thành tài khoản Google trong CSDL). Cả hai bộ chụp ngày 27/10 trên cùng dữ liệu: `PHASE=before` trên `main` @ `d50947f` (chưa đổi code, stack dev), `PHASE=after` trên nhánh này.

| Ảnh | Trạng thái |
|---|---|
| `1-dang-nhap-{1440,375}` | Khách mở trang đăng nhập |
| `2-dang-nhap-sai-1440` | Sai mật khẩu |
| `3-dang-ky-{1440,375}` | Đến từ trang khóa Python, đã điền, mật khẩu đạt |
| `4-dang-ky-email-da-co-1440` | Email đã có tài khoản |
| `5-sau-dang-ky-{1440,375}` | Ngay sau đăng ký ("trước": trang chủ; "sau": `/chao-mung`) |
| `6-ho-so-{1440,375}` | Hồ sơ Người mua 08 |
| `7-ho-so-google-{1440,375}` | Hồ sơ tài khoản chỉ đăng nhập bằng Google |
| `8-ho-so-khach-1440` | Khách mở `/ho-so` |

Ảnh chụp với `prefers-reduced-motion: reduce`, nên Naomi ở tư thế tĩnh. Nút "Đăng nhập bằng Google" không có trên ảnh: stack dev không bật `NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED` (mockup có nó).

```bash
# stack dev đang chạy
PHASE=after NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/account/capture.cjs
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/account/check.cjs
```

## 6. Để lại

- **Đăng ký bằng Google không qua `/chao-mung`**: callback Google do backend chuyển hướng, và backend đứng yên trong Phase 7. Người đăng ký bằng Google về thẳng `next`.
- **"Chào trở lại" khi đăng nhập không có phản ứng riêng**: đăng nhập xong về đúng `next` (thường là khóa đang học), chen một màn chào vào đó là chặn đường. Naomi `wave` đứng ở trang đăng nhập là đủ.
- **Quên mật khẩu, đổi email**: chưa có luồng ở backend; trang không hứa tính năng đó.
- **Dấu "vừa đăng ký" nằm trong `sessionStorage`**: đăng ký ở tab này rồi mở `/chao-mung` ở tab khác thì Naomi đứng yên. Đúng ý: phản ứng cho tab vừa làm việc đó.
