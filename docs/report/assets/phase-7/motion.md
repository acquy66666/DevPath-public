# Micro-interaction theo token chuyển động (29/10/2026)

Task đầu của mục "Chuyển động và chất lượng" ([plan](../../../plan/phase-7-ui-ux-upgrade.md)). Luật lấy từ [design system, Motion](../../../ui-ux/design-system/project/components/Motion/README.md): thời lượng và đường cong chỉ lấy từ token, chỉ động `transform` và `opacity`, không hoạt ảnh nào chặn thao tác, và với `prefers-reduced-motion: reduce` thì chỉ còn đổi màu và mờ dần.

Nhánh `feature/phase7-micro-interactions`. Backend không đổi.

## 1. Hiện trạng trước task

Rà `app/` + `components/`:

| Hạng mục | Trước | Sau |
|---|---|---|
| Hover/press | Nút lún 1px khi nhấn (đã có từ task "Nền"); hover đổi màu theo `duration-fast`. 3 dòng có hover mà không có transition (mã giảm giá, danh sách bài trang duyệt) | Đủ cả 3 dòng; nút giữ nguyên |
| Toast | **Không có**. Bỏ một khóa khỏi giỏ/yêu thích thì dòng biến mất, không một chữ nào xác nhận | `components/ui/toast.tsx` (Radix Toast) + "Hoàn tác" |
| Thanh tiến độ | Trang học động `width` (luật chỉ cho `transform`); ô tải video `transition-[width] duration-200` (không phải token) | `components/ui/progress.tsx`: `translateX`, `duration-progress`, giảm chuyển động thì nhảy thẳng |
| Chuyển tab | Chỉ đổi màu; vạch dưới tab `line` bật/tắt tức thì | Vạch giãn từ giữa tab (`scale-x`, `duration-base`); panel vừa chuyển tới mờ vào và nhích 4px. Panel đầu **không** chạy khi tải trang (không làm chậm lần vẽ đầu) |
| Mũi tên gập/mở | 3 chỗ xoay `rotate-180` mà không tắt khi giảm chuyển động | Đủ `motion-reduce:transition-none` |
| Token | Carousel banner `duration-500 ease-out` | `duration-slow ease-standard` |
| Lưới an toàn | Không có: mọi `animate-*` (vòng xoay tải, mờ vào của dialog) vẫn chạy khi giảm chuyển động | `globals.css` có khối `@media (prefers-reduced-motion: reduce)`: mọi CSS animation xong trong 1 ms, lặp 1 lần, không cuộn mượt |

## 2. Toast

- **Dùng khi:** một thứ vừa rời màn hình vì một cú bấm. Hiện có 3 chỗ: bỏ khỏi giỏ (kèm "Hoàn tác" = thêm lại), để dành sang yêu thích, bỏ khỏi yêu thích (kèm "Hoàn tác" = lưu lại). **Không** dùng cho lỗi (Alert cạnh chỗ hỏng) và không thay "Đã lưu thay đổi." cạnh form (các script kiểm cũ còn tìm câu đó, và nó đúng chỗ hơn).
- **Vị trí:** góc phải trên, ngay dưới header. Ở đáy màn hình điện thoại, toast sẽ đè thanh "Thanh toán qua VNPay" dính đáy của giỏ hàng (luật "không che nút hành động").
- **Chuyển động:** vào trượt 1rem từ phải, `duration-slow` + `ease-enter`; ra ~70 % (`duration-base`) + `ease-exit`; vuốt sang phải để đóng. Giảm chuyển động: chỉ còn mờ, và lưới an toàn làm nó xong ngay.
- **Thời gian:** 6 s, dừng khi con trỏ hoặc focus ở trên (Radix); F8 nhảy tới vùng toast; tối đa 3 cái, cái cũ nhất đóng trước. Logic danh sách ở `lib/design/toast-store.ts` (không import, `npm test` chạy được).
- **Lỗi của Radix Toast 1.2.23 tìm ra khi kiểm:** Radix chỉ nghe "con trỏ/focus rời đi" khi đang có toast. Bấm "Hoàn tác" làm toast đóng trong lúc con trỏ còn trên nó, nên cờ "tạm dừng" kẹt lại: **toast sau đó không bao giờ tự đóng** (đo: vẫn mở sau 10 s, 10/10 lượt nhìn). `Toaster` giờ báo cho Radix "con trỏ đã rời" mỗi khi có toast mới mà con trỏ không nằm trên vùng toast; focus còn trong vùng toast thì Radix vẫn giữ dừng như thiết kế. Sau khi sửa: toast kế tiếp đóng sau 6 s.

## 3. Kiểm trên Chrome thật — `motion/check.cjs`

Stack dev, một học viên dùng một lần (`purge_e2e` ở cuối), hai lượt: `page.emulateMedia({ reducedMotion: "no-preference" })` rồi `"reduce"`. **36/36 đạt** (`motion/results.json`).

| Kiểm | Bình thường | Giảm chuyển động |
|---|---|---|
| Nút khi đang nhấn | `translate: 0px 1px` | `none` |
| Toast vào | `enter` 0,32 s, `--tw-enter-translate-x` = 1rem | 0,001 s, dịch 0 |
| Toast không chắn chuột ngoài thẻ của nó (`pointer-events: none` ở vùng chứa) | ✔ | ✔ |
| Toast có trong cây truy cập (`role=status`), axe khi đang mở 0 critical/serious | ✔ | ✔ |
| "Hoàn tác" bấm ngay khi toast còn đang vào → khóa quay lại giỏ / yêu thích | ✔ | ✔ |
| Toast đóng xong thì rời DOM; tự đóng sau ~6 s, kể cả sau một lần "Hoàn tác" | ✔ | ✔ |
| 360 px: toast ở y 72–166, nút thanh toán ở y 704; 0 tràn ngang | ✔ | ✔ |
| Thanh tiến độ trang học | `transform` 0,6 s | `transition-property: none` |
| Panel tab đầu lúc tải trang | không animation | không animation |
| Panel tab vừa chuyển tới | `enter` 0,22 s, nhích 0,25rem | 0,001 s, dịch 0 |
| Vạch dưới tab | `scale` 1 / 0, transition 0,22 s | `scale` 1 / 0, `transition-property: none` |
| `document.getAnimations()` trên giỏ hàng + trang học: CSS animation còn dài > 1 ms hoặc lặp vô hạn | — | 0 |

**Lỗi thứ hai tìm ra khi kiểm:** lượt đầu ở chế độ giảm chuyển động, vạch dưới tab vẫn trượt 0,22 s. `motion-reduce:after:transition-none` thua độ ưu tiên của `group-data-[variant=line]/tabs-list:after:transition-transform` (bộ chọn group cụ thể hơn). Sửa bằng cách cho lớp tắt mang đúng tiền tố đó, và `motion.test.ts` thêm luật bắt đúng kiểu lỗi này (thử lại bản lỗi: test đỏ, chỉ đúng dòng của `tabs.tsx`).

Ảnh: `motion/toast-1440.png`, `motion/toast-360.png` (toast dưới header, thanh thanh toán ở đáy), `motion/tabs-line.png`.

Chạy lại:

```bash
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/motion/check.cjs
```

Script tra CSDL **trước** mọi lệnh gọi API: một lệnh `docker compose exec` đồng bộ chen giữa hai request lâu hơn keep-alive của uvicorn, rồi `fetch` dùng lại socket đã chết (`ECONNRESET`).

## 4. Chặn hồi quy — `frontend/lib/design/motion.test.ts`

Đọc mã nguồn `app/` + `components/` (bỏ bản vẽ Naomi và trang `/dev`):

1. Thời lượng/đường cong chỉ là token (`duration-<số>`, `duration-[…]`, `ease-out`… → đỏ).
2. Không transition `width/height/top/left/…`.
3. Transition có `transform/translate/scale/rotate` và `animate-pulse/bounce/ping` phải có `motion-safe:` hoặc `motion-reduce:` trong cùng chuỗi lớp.
4. Transition có tiền tố biến thể thì lớp tắt phải mang đúng tiền tố đó (lỗi ở §3).
5. Trượt/phóng của `tw-animate-css` (`slide-*`, `zoom-*`) chỉ sau `motion-safe:`.
6. `globals.css` còn khối lưới an toàn; thanh tiến độ tự viết bằng `style={{ width }}` cạnh `role="progressbar"` → đỏ, dùng `<Progress>`.

`npm test` **156/156** (11 mới: 6 luật trên + 5 của `toast-store`). Cài thử `duration-500 ease-out` vào carousel → luật 1 và 3 đỏ đúng tệp.

## 5. Kiểm khác

- `npm run lint` sạch.
- E2E luồng vàng: **1 passed** (2,1 phút, stack dev).
- `next build` không mạng (volume `node_modules` của container dev): xanh.
- Tràn ngang toàn site chưa đo lại bằng `foundation/overflow.cjs`; ba thay đổi có bề rộng (toast, thanh tiến độ, tab) đã đo ở 360 px trong §3. Đo lại cả site ở gate.
- Dung lượng: `<Toaster>` nằm trong `Providers` nên Radix Toast vào mọi trang; đo ở task "Hiệu năng" (ngân sách nhân vật + chuyển động ≤ 50 KB gzip ở màn đầu).
