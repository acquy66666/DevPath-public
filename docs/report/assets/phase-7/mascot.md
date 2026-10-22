# Component Naomi `<Mascot>` (21/10/2026)

Task "Component `components/mascot/`" của [Phase 7](../../../plan/phase-7-ui-ux-upgrade.md). Lý do của từng lựa chọn: [`decisions.md`](../decisions.md) § "Component Naomi". Cách dùng trong code: [`frontend/README.md`](../../../../frontend/README.md) § "Linh vật Naomi".

```tsx
<Mascot mood="celebrate" event={submission.id} />   // verdict vừa tới: phản ứng một lần rồi đứng yên
<Mascot mood="celebrate" />                          // mở lại kết quả cũ: tư thế tĩnh, không ăn mừng lại
<Mascot mood="grading" event={id} progress={k / n} /> // thanh laptop sáng theo số test đã chấm
<Mascot mood="lost" size="lg" event />               // trang vừa mở
```

## Đã làm

| Phần | Tệp |
|---|---|
| Component: tư thế tĩnh do máy chủ render; phản ứng bằng Web Animations, chỉ khi đã lên màn hình (IntersectionObserver) và không bật `prefers-reduced-motion`; một lần mỗi `event`; `pointer-events: none`; `aria-hidden` trừ khi có `label` | `frontend/components/mascot/mascot.tsx`, `play.ts` |
| 30 bản vẽ web, mỗi mood một chunk, sinh từ cùng bộ phận với model sheet: màu `var(--color-*)`, lớp `data-layer`, mảnh `data-part`. Các SVG trong `docs/` vẫn ra đúng từng byte cũ | `frontend/components/mascot/art/` ← `docs/ui-ux/mascot/naomi/build.cjs` |
| Biên đạo 30 mood: 14 động tác dùng chung (nhảy, nhún, nghiêng đầu, chớp mắt, vung tay, vẫy đuôi, mảnh bật ra…), toạ độ theo bản vẽ 200 × 200 | `frontend/lib/mascot/choreography.ts`, `keyframes.ts` |
| 10 test: tên lớp có trong bản vẽ, phản ứng ≤ `duration-mascot`, mọi mảnh về đúng chỗ khi hết, không hai track tranh một thuộc tính hay một điểm xoay, chỉ `wave` về `rest`, màu và đường cong khớp `tokens.json`. Thử làm hỏng 4 kiểu (quá giờ, sai tên, tranh thuộc tính, không về chỗ): cả 4 đều đỏ | `frontend/lib/mascot/mascot.test.ts` |
| Token: 4 đường cong `--ease-*` (`@theme static`), bảng màu 28 token của Naomi ở khối `[data-mascot]` (đã xóa ở task "Nền" 22/10/2026: Naomi giờ đọc palette chung trong `@theme static`) | `frontend/app/globals.css` |
| Trang xem trước mọi mood + luồng chấm bài thu nhỏ + ô thử bấm xuyên. Chỉ có ở dev, bản production trả 404 trừ khi build với `MASCOT_PREVIEW=1` | `frontend/app/(dev)/dev/naomi/` |

## Cách đo

[`mascot/capture.cjs`](mascot/capture.cjs) chạy trên bản `next build` production, không cần stack nào:

1. Chép tạm hai trang đo giống hệt nhau vào `app/(measure)/do-naomi/`. `khong` có một ô trống cùng cỡ, `co` có `<Mascot mood="lost" size="lg" event />`. Script xóa chúng khi xong, kể cả khi lỗi.
2. `next build` với `MASCOT_PREVIEW=1`, `NEXT_PUBLIC_API_BASE_URL=""`.
3. Dung lượng: First Load JS bằng chính hàm `writeRouteBundleStats` của Next, giống [`before.md`](before.md). JS tải thật đo bằng cách mở trang trong Chrome và gzip mức 9 từng tệp. Mỗi chunk tĩnh có bản vẽ phải chứa đúng một mood.
4. `next start` ở 127.0.0.1:3108, rồi Chrome 155 (Playwright, `channel: "chrome"`). Mọi tài liệu HTML được gắn đúng chuỗi CSP đọc từ `infra/nginx/snippets/security-headers.conf`. Trong Chrome kiểm: hình tĩnh trong HTML máy chủ, thời gian từng phản ứng, giảm chuyển động, tải lười, bấm xuyên, hồi phục khi animation bị hủy, và luồng chấm bài k/n → verdict.
5. Chụp khung hình chính xác: dừng mọi animation của thẻ, đặt `currentTime` = 0/200/500/900/1400/2000 ms rồi chụp, sau đó chụp thêm một khung khi đã hết phản ứng.

```bash
NODE_PATH=frontend/node_modules node docs/report/assets/phase-7/mascot/capture.cjs   # ~3 phút
```

## Kết quả

### Dung lượng (gzip)

| | Số đo |
|---|---|
| First Load JS, trang có Naomi so với trang không | **+6,3 KB** (210,4 → 216,9 KB; 13 → 14 chunk) |
| JS tải thật khi mở trang (gồm chunk hình `lost`) | **+7,9 KB**, 1 chunk hình được tải |
| Một chunk hình | 1,3–2,0 KB, trung vị 1,5 KB. Mỗi chunk đúng một mood; trang chỉ tải mood nó dùng |
| Bản vẽ phía máy chủ (`art/server.ts`) trong bundle trình duyệt | 0: không chunk nào chứa hơn một hình |

Ngân sách của phase là "nhân vật + Motion thêm ≤ 50 KB gzip ở màn đầu". Component dùng 7,9 KB, tức 16 % ngân sách. Spike đo bản `mini` thêm 5,3 KB cho riêng phản ứng `celebrate`, gồm cả thư viện. Bản này không có thư viện, nhưng chở biên đạo của cả 30 mood và phần tải hình. Đây là số đo trên trang đo. Khi Naomi vào trang thật (404, empty state, trang nộp bài), cột "sau" của chương 5 đo lại trên đúng trang đó.

### Hành vi (Chrome 155, CSP production)

| Kiểm | Kết quả |
|---|---|
| Vi phạm CSP / lỗi console qua 30 phản ứng | **0 / 0** |
| Hình tĩnh trong HTML máy chủ, trang đo, request 1 và 2 | 1 hình, 0 boundary tách ra cuối HTML |
| Hình tĩnh trong HTML máy chủ, `/dev/naomi` (32 hình) | 32 hình. Cả 32 boundary bị React tách ra cuối HTML, vì HTML trước chúng vượt 12.800 byte (`progressiveChunkSize`). Chúng hiện bằng script inline trước hydrate. Không có gì phải chờ: máy chủ đọc bản vẽ đồng bộ |
| Bấm "Phát" → bắt đầu phản ứng | 64–99 ms |
| Phản ứng dài nhất | 2.246 ms (`wave`, gồm 220 ms mờ chéo về `rest`). Mood giữ dáng dài nhất 1.864 ms (`celebrate`) |
| Sau phản ứng | 0 animation còn chạy ở cả 30 mood. 29 mood giữ dáng, `wave` về `rest` |
| `prefers-reduced-motion: reduce`, bấm "Phát tất cả", lấy mẫu 3 s | 0 animation, 0 lớp bị dịch/xoay/co, mọi Naomi ở pha `still`, không mood nào đổi hình ([`reduced.png`](mascot/reduced.png)) |
| Tải lười, khung nhìn 700 px, bấm "Phát tất cả" | Mood đầu (trên màn hình): đang phản ứng. Mood cuối (ngoài màn hình): đứng yên, chỉ phản ứng sau khi cuộn tới |
| Naomi đè lên nút | `elementFromPoint` ở tâm Naomi trả về nút; bấm 2 lần thì nút đếm 2 |
| Animation bị hủy từ bên ngoài giữa `celebrate` | Về tư thế tĩnh sau 2,85 s (hẹn giờ dự phòng `endsAt + 1 s`), không kẹt |
| Luồng chấm bài: `grading` 0/5 → 5/5 → verdict AC cùng mã bài nộp | Thanh laptop 0 → 1 → 2 → 3 → 4 → 5 đoạn, rồi `celebrate`. Có `label` nên `role="img"` + `aria-label` là mô tả của mood |

### Từng mood

Thời gian đo từ lúc vào pha `playing` tới lúc ra (thời gian thực trong Chrome), kèm gzip của chunk hình.

| Mood | Phản ứng (ms) | Sau đó | Chunk (KB) |
|---|---|---|---|
| `rest` | 826 | giữ dáng | 1,3 |
| `grading` | 1.052 | giữ dáng | 1,6 |
| `celebrate` | 1.864 | giữ dáng | 1,6 |
| `partial` | 1.375 | giữ dáng | 1,6 |
| `sleepy` | 1.617 | giữ dáng | 1,6 |
| `stuffed` | 1.329 | giữ dáng | 1,3 |
| `dizzy` | 1.816 | giữ dáng | 2,0 |
| `tangled` | 1.248 | giữ dáng | 1,6 |
| `sorry` | 1.044 | giữ dáng | 1,6 |
| `party` | 1.316 | giữ dáng | 1,7 |
| `proud` | 1.196 | giữ dáng | 1,4 |
| `cheer` | 1.213 | giữ dáng | 1,4 |
| `comfort` | 1.617 | giữ dáng | 1,3 |
| `startled` | 816 | giữ dáng | 1,5 |
| `fire` | 1.433 | giữ dáng | 1,5 |
| `sad` | 1.828 | giữ dáng | 1,6 |
| `levelup` | 1.411 | giữ dáng | 1,5 |
| `graduate` | 1.614 | giữ dáng | 1,6 |
| `lost` | 1.816 | giữ dáng | 1,6 |
| `empty` | 866 | giữ dáng | 1,3 |
| `empty-cart` | 867 | giữ dáng | 1,5 |
| `empty-courses` | 864 | giữ dáng | 1,5 |
| `empty-notifications` | 1.315 | giữ dáng | 1,5 |
| `empty-notes` | 863 | giữ dáng | 1,5 |
| `empty-search` | 865 | giữ dáng | 1,4 |
| `thinking` | 1.216 | giữ dáng | 1,5 |
| `answer` | 1.011 | giữ dáng | 1,6 |
| `wave` | 2.246 | về `rest` | 1,4 |
| `paid` | 1.306 | giữ dáng | 1,5 |
| `oops` | 1.138 | giữ dáng | 1,4 |

`grading` còn có một nhịp gõ phím 420–480 ms mỗi khi số test đã chấm tăng.

## Điều tìm ra khi làm

1. **Về `rest` sau mọi phản ứng làm mất bối cảnh.** Bảng khung hình lượt đầu cho thấy `levelup` mất cái bục và Naomi to vọt, `sad` mất ngọn nến, `graduate` mất mũ. Đổi thành giữ dáng mood, chỉ `wave` về `rest`. Lý do đầy đủ ở `decisions.md`.
2. **`fill: backwards` che track trước trên cùng thuộc tính.** Track bắt đầu từ chính bản vẽ thì không được giữ khung đầu trong lúc chờ. Test "không hai track tranh một thuộc tính" tính cả khoảng chờ đó.
3. **`cheer` vung nắm tay vào trong thì tay nấp sau u mắt**, đúng điều README Naomi đã cảnh báo cho hình tĩnh. Đổi chiều vung ra ngoài.
4. **Chrome không báo `finished` cho animation đang dừng bị tua quá điểm cuối.** Script chụp từng làm component kẹt ở "đang phản ứng". Có thêm hẹn giờ dự phòng, kèm một bước kiểm hồi phục.
5. **`fill="var(--color-…)"` trong thuộc tính trình bày của SVG chạy được** trong Chrome. Nhờ vậy bản vẽ đổi màu theo token mà không cần `<style>` hay `style=`.

## Ảnh

- [`mascot/frames/sheet-1.png`](mascot/frames/sheet-1.png), [`sheet-2.png`](mascot/frames/sheet-2.png), [`sheet-3.png`](mascot/frames/sheet-3.png): mỗi bảng 10 mood × (0, 200, 500, 900, 1400, 2000 ms, sau phản ứng), khung chính xác theo `currentTime`.
- [`mascot/grid.png`](mascot/grid.png): 30 mood ở cỡ `lg`, tư thế tĩnh.
- [`mascot/reduced.png`](mascot/reduced.png): cùng trang khi `prefers-reduced-motion: reduce`, sau khi bấm "Phát tất cả".
- `mascot/results.json`: số đo đầy đủ. `mascot/build.log`: log `next build`.

GIF các phản ứng là mục của gate cuối phase, chưa làm ở task này.
