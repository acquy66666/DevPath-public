# Phase 7 — Nền: token vào code, `components/ui`, header/footer (22/10/2026)

Task đầu của mục "Nền" trong [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md): đưa design system ([`docs/ui-ux/design-system/`](../../../ui-ux/design-system/README.md)) vào `frontend/app/globals.css`, cập nhật toàn bộ `components/ui/*`, làm lại header, footer và menu điện thoại, rồi đo lại tràn ngang ở 360/375/1440 px. Nhánh `feature/phase7-foundation`.

## 1. Token vào code

| | Số lượng | Ở đâu trong `globals.css` |
|---|---:|---|
| Bậc màu gốc (`slate-0…950`, `jade`, `turmeric`, 7 họ trạng thái) | 82 | `@theme static`: luôn phát ra, vì bản vẽ của Naomi đọc `var(--color-*)` từ script |
| Token ngữ nghĩa (`primary`, `border`, `verdict-ac-soft`, `quiz-party`…) | 82 | biến trong `:root`, tiện ích trong `@theme inline`: theme tối sau này chỉ cần một khối định nghĩa lại `:root` |
| Kiểu chữ (`text-display` … `text-eyebrow`, `text-code`, `text-numeral`, `text-cert-title`) | 14 | `@theme`: cỡ + line-height + độ đậm + giãn chữ, đơn vị rem |
| Bo góc (`xs` 4 · `sm` 6 · `md` 10 · `lg` 14 · `xl` 20 px) | 5 | `@theme` |
| Đổ bóng (`xs`, `sm`, `md`, `lg`) | 4 | `@theme` |
| Thời lượng (`duration-instant` … `duration-mascot`) + đường cong (`ease-*`) | 6 + 4 | `@theme static`; `transition` trơn của cả site mặc định `duration-fast` + `ease-standard` |

- Khối `[data-mascot]` (bảng màu tạm của Naomi) **đã xóa**. Test màu của Naomi giờ đọc palette chung.
- Theme tối cũ của shadcn (`.dark`, xám thuần) và biến `sidebar-*` không ai dùng đã bỏ. Theme vẫn chỉ có sáng (tài liệu thiết kế, mục 10).
- Focus: một luật nền `:focus-visible { outline: 2px solid ring; outline-offset: 2px }` cho mọi thứ bàn phím tới được. Component không tự vẽ vòng focus riêng nữa.
- **Thang bo góc đổi giá trị** (lg 10 → 14 px, xl 14 → 20 px để đúng tên token). 184 class `rounded-lg/xl/2xl` trong 81 tệp màn hình được đổi tên lùi một bậc, nên số pixel trên các màn chưa thiết kế lại giữ nguyên.

**Test giữ code và design system khớp nhau:** `frontend/lib/design/tokens.test.ts` (trong `npm test`):

1. 82 bậc màu của `globals.css` bằng đúng `tokens.json`, hai chiều.
2. 82 token ngữ nghĩa có biến `:root` trỏ đúng bậc, có tiện ích trong `@theme inline`, và `:root` không có biến nào ngoài `tokens.json`.
3. Thang chữ, bo góc, bóng, thời lượng, đường cong bằng `tokens.json`.
4. `cn()` hiểu tên mới (mục 2).
5. Không tệp nào trong `components/ui/` gọi thẳng bậc màu gốc (`bg-emerald-600`), mã hex (trừ trong `url()` data), `black`/`white`, hay `leading-none`/`leading-tight` (đẩy dấu chồng tiếng Việt ra khỏi dòng).

## 2. Lỗi tìm ra: `cn()` nuốt cỡ chữ mới

`cn()` dùng `tailwind-merge` 3.6.0. Thư viện chưa biết `text-body-sm`, coi nó là **màu chữ**, nên `cn("text-body-sm", "text-muted-foreground")` trả về `text-muted-foreground` (cỡ chữ biến mất), còn `cn("text-h1", "text-sm")` giữ cả hai. Tương tự với `ease-standard`, `duration-fast`: hai cái cùng loại không gộp. Đo trên chính thư viện, trước và sau khi khai báo:

| Đầu vào | `twMerge` trơn | `cn()` mới |
|---|---|---|
| `text-body-sm text-muted-foreground` | `text-muted-foreground` | giữ cả hai |
| `text-h1 text-sm` | giữ cả hai | `text-sm` |
| `ease-standard ease-enter` | giữ cả hai | `ease-enter` |
| `duration-fast duration-base` | giữ cả hai | `duration-base` |

Sửa: `lib/design/tokens.ts` khai báo tên kiểu chữ, thời lượng, đường cong; `lib/utils.ts` dựng `cn()` bằng `extendTailwindMerge(MERGE_CONFIG)`. Test (mục 1.4) kiểm cả hai chiều: khác loại thì giữ cả hai, cùng loại thì cái sau thắng.

## 3. `components/ui/*`

| Component | Đổi |
|---|---|
| Button | 6 biến thể theo token (`primary-hover`, `secondary-hover`, outline viền `input` + `shadow-xs`, destructive nền đặc). Cỡ `sm` 32 · mặc định **36** · `lg` 44 px (trước 28/32/36). Chữ đậm 600. Hover `not-disabled:`; lún 1 px chỉ khi không giảm chuyển động |
| Badge | Cao 22 px, bo tròn, đậm 600, `tabular-nums`. Thêm `muted`, `success`, `warning`, `info`, `reward`, `streak`; `destructive` thành nền nhạt |
| Card | Viền `border` thật (trước là ring), bo `lg` 14 px, tiêu đề `text-title`, chân card nền `muted` |
| Alert | 5 biến thể (`default`, `info`, `success`, `warning`, `destructive`) nền nhạt + icon màu, không viền trái. `role`: `alert` chỉ cho `destructive`, còn lại `status` (trước: mọi Alert đều `alert`) |
| Tabs | Hai kiểu: `tray` (mặc định) và `line` (`<TabsList variant="line">`, gạch chân `primary`, hàng dài thì cuộn trong chính nó) |
| Dialog | Lớp phủ `overlay`, bo `xl`, `shadow-lg`, padding 24 px, tiêu đề `text-h3`. `size="form"` 560 px (6 dialog biểu mẫu dùng), mặc định 440 px. Vào/ra bằng `duration-slow`/`ease-enter` và `duration-base`/`ease-exit`; phóng 0,96 chỉ khi không giảm chuyển động |
| Input, Textarea, NativeSelect | Cao **40** px, chữ 16 px ở mọi bề rộng (trước 32 px, 14 px từ md), nền `card`, viền `input` (3:1), `shadow-xs`; vô hiệu: nền `muted`, viền `border-strong` |
| Label, FormField | Nhãn đậm 600, line-height 20 px (bỏ `leading-none`); nhãn/ô/lời báo cách 6 px; lỗi `destructive-text` kèm icon |
| DropdownMenu | Viền + `shadow-md`, bo `md`, mục cao ≥ 32 px, mục `destructive` theo token, vào/ra theo token |
| Pager | Hai nút `ghost sm` có chevron, số trang `tabular-nums` |
| Markdown, ExportButton | Link `link` gạch chân, code bo `xs`/`md`; lỗi xuất `destructive-text` |

## 4. Header, footer, menu điện thoại

- **Header:** nền `card`, chữ thương hiệu "Dev" mực + "Path" `primary`. Từ `md`: "Khóa học", "Bảng xếp hạng" là link có nền `secondary` khi đang ở trang đó (`aria-current="page"`). Dưới `md` hai link gom vào **nút menu** ("Mở menu điều hướng", mục cao 40 px). Từ `sm`, nút đăng nhập/đăng ký cỡ `lg` (44 px, chữ 16 px), giữ ý của commit `926266d` (header phải đọc được khi chiếu). Nút tài khoản đọc là "Tài khoản: <tên>", avatar 32 px.
- **Footer:** nền `card`, chữ thương hiệu + một câu giới thiệu, ba link (Khóa học, Bảng xếp hạng, Chính sách bảo mật: Google trỏ tới trang này), dòng công nghệ.

## 5. Tràn ngang 360/375/1440 px

Script [`foundation/overflow.cjs`](foundation/overflow.cjs) mở **44 route × 3 bề rộng = 132 lượt xem** trên stack dev, dưới 4 vai đăng nhập bằng form thật:

- khách: 13 route, gồm trang 404, mã chứng chỉ sai, tìm không ra;
- học viên `nguoimua08`: 13 route, gồm 4 kiểu bài trong trang học;
- giảng viên `khoa.tran`: 6 route, gồm trình soạn khóa;
- admin: 13 route, gồm một bảng kê.

Mỗi lượt đo `scrollWidth` so với `clientWidth`, liệt kê phần tử thò ra ngoài, gom lỗi console, rồi đăng xuất mọi phiên đã mở (trình duyệt và API).

| Lượt | Kết quả |
|---|---|
| Lần 1 (sau khi đổi token + component) | **2/132 tràn**: `/giang-day/thong-ke` ở 360 và 375 px, trang rộng 953 px; script không chỉ ra được phần tử |
| Lần 2 (script sửa cách tìm thủ phạm) | vẫn 2/132, giờ chỉ đúng `span.sr-only "Chi tiết"` ở x = 953. Bản sửa đã nằm trong tệp nhưng `next dev` trong container chưa biên dịch lại |
| Lần 3 (sau khi restart frontend) | **0/132 tràn**. `overflow.json` và `shots/` là của lượt này |

**Nguyên nhân:** bảng "từng khóa" (`min-w-[920px]`) đã nằm trong khung `overflow-x-auto`, nhưng ô đầu cột cuối có `<span class="sr-only">Chi tiết</span>`. `sr-only` là `position: absolute`. Khung cuộn không có `position`, nên không phải khối chứa của nó, và nhãn thoát ra ngoài ở x = 953. Lỗi có từ Phase 6.5 (20/10), không do task này gây ra. Lần rà UX 02/10 chưa thấy vì khi đó chưa có bảng này. Script lần 1 phát hiện trang tràn nhưng không chỉ ra phần tử: nó coi mọi phần tử trong khung cuộn là đã bị cắt. Giờ script tính từ khối chứa của phần tử `absolute`.

**Sửa:** thêm `relative` cho khung cuộn của bảng đó, và cho bảng chi phí ở `/quan-tri/loi-nhuan`. Bảng chi phí có cùng mẫu lỗi, chưa lộ chỉ vì CSDL dev chưa có khoản chi nào.

**Lỗi console:** mọi dòng đều là mã HTTP mà app vẫn trả từ trước: 401 khi khách mở trang (hỏi phiên bằng cookie refresh chưa có), 404 với mã chứng chỉ sai và với `GET /courses/{id}/reviews/me` khi học viên chưa viết đánh giá (có chủ đích), 422 với mã đơn giả do script tự đặt. Không có lỗi JavaScript (`pageerror`) nào.

## 6. Kiểm khác

| Kiểm | Kết quả |
|---|---|
| `npm test` | 26/26 (5 test mới ở `tokens.test.ts`) |
| `npx tsc --noEmit`, `npm run lint` | sạch |
| `next build` không mạng (`frontend/scripts/build-offline.sh`, `--network none`) | xanh: biên dịch 87 s, TypeScript sạch, 34/34 trang tĩnh |
| E2E luồng vàng trên stack dev (`E2E_CHROME_CHANNEL=chrome npm run test:e2e`) | **1 passed** ngay lượt đầu (3,0 phút; `next dev` vừa restart nên phải biên dịch lại từng trang), không sửa spec |
| Preview design system (`check/shoot.cjs`, 15 preview × 960/400 px) | 0 tràn, 0 lỗi console, Lexend tải được |

## 7. Ảnh — `foundation/shots/`

`header-khach-360`, `menu-dien-thoai-360` (menu mở), `header-khach-1440`, `header-hoc-vien-360`, `menu-tai-khoan-1440` (menu mở), `dang-nhap-375`, `footer-1440`, `footer-375` (toàn trang), `khoa-hoc-1440`, `gio-hang-1440`, `ho-so-1440`, `hoc-code-1440`, `bang-xep-hang-375`, `giang-day-1440`, `thong-ke-1440`, `quan-tri-1440`, `loi-nhuan-dialog-1440` (dialog biểu mẫu mở), `nguoi-dung-375`. Kết quả từng lượt xem: `foundation/overflow.json`.

## 8. Để lại cho các nhóm màn

- 20 tệp màn hình còn class màu viết tay (`emerald`, `amber`, `rose`, `sky`…), nhiều nhất `tier-review`, `quiz-workspace`, `quiz-editor`, `course-cover`. Họ màu trạng thái giờ đã là bậc của design system nên tông đã gần đúng. Mỗi nhóm màn chuyển chúng sang token ngữ nghĩa (`verdict-*`, `quiz-*`, Badge `success`…) khi thiết kế lại.
- Hero trang chủ dùng line-height chặt hơn thang (`display` 40/52), và banner seed là gradient tím–lam (nằm trong "Không làm"): việc của nhóm 2.
- Thanh tab admin (12 mục) vẫn là link riêng trong `components/admin/admin-nav.tsx`, đã cuộn trong chính nó; chuyển sang kiểu `line` ở nhóm 10.

## 9. Chạy lại

```bash
# stack dev đang chạy (infra/docker-compose.yml), trong thư mục gốc repo
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/foundation/overflow.cjs
cd frontend && npm test && npm run lint
```
