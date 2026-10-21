# Linh vật DevPath — Naomi

Nhân vật là **Naomi**, tắc kè “bắt bug” (hướng A, user chọn và đặt tên ngày 21/10/2026). Thư mục này giữ hai task Phase 7 ([plan](../../plan/phase-7-ui-ux-upgrade.md), [tài liệu thiết kế mục 4–5](../thiet-ke-nang-cap-ui-ux.md)): phác ba hướng, rồi model sheet + bộ biểu cảm của Naomi.

- **Artifact Design:** [Linh vật DevPath](https://claude.ai/artifact/LgYj69gDYUuze9geb8J7W8). 7 artboard: tổng quan, ba hướng, kiểm với Duo (hồ sơ lần chọn), rồi **Naomi · model sheet** và **Naomi · bộ biểu cảm**. Design system DevPath được cài vào canvas.
- **User chọn 21/10/2026: hướng A, tắc kè “bắt bug”, tên Naomi.** Claude đã đề xuất A. Tên Naomi là của user, không nằm trong ba tên gợi ý (Kè, Sùng, Bít).

## Naomi: model sheet và bộ biểu cảm (21/10/2026)

Mọi hình sinh từ một script, [`naomi/build.cjs`](naomi/build.cjs), ghép từ cùng một bộ bộ phận (đầu, mắt, mí, miệng, tay, chân, đuôi, đạo cụ). Sửa một bộ phận là mọi mood đổi theo, và tệp nào cũng có cùng bộ lớp. **SVG trong `naomi/` là đầu ra: sửa script, đừng sửa SVG.** Màu gọi bằng tên token và tra trong `tokens.json` của design system; tên không phải token thì build dừng.

| Tệp | Nội dung |
|---|---|
| `naomi/views/naomi-{front,three-quarter,side}.svg` | Model sheet: nhìn thẳng, ba phần tư (quay ~30° sang trái người xem), nghiêng (hướng trái) |
| `naomi/sheet/naomi-turnaround.svg` | Ba góc cạnh nhau trên 4 đường gióng: đỉnh đầu 37,5 · mắt 66 · cằm 126,5 · mặt đất 199,5 |
| `naomi/moods/naomi-<mood>.svg` | 30 hình: `rest` + 24 mood của mục 5 + 5 đạo cụ empty state (`empty-cart`, `empty-courses`, `empty-notifications`, `empty-notes`, `empty-search`) |
| `naomi/layers/naomi-partial-<lớp>.svg` | Tư thế `partial` tách từng lớp, cho hình lớp trên model sheet |
| `naomi/naomi.json` | Danh sách mood → sự kiện, nơi dùng, nhãn `aria-label`, tệp; đường gióng. Component `<Mascot>` đọc được từ đây |

**Tỉ lệ** (khung 200 × 200): Naomi cao 162, đầu 89 (55 %, khoảng 1,8 đầu), đầu rộng 127 gấp 1,7 lần thân (75). Nét viền 4,5 chỉ ở mép ngoài.

**Bảng màu của Naomi:** thân/đầu/tay/chân/đuôi `jade-500`, bụng `jade-100`, đốm `jade-700`, nét viền + con ngươi + miệng `jade-900`, mống mắt `turmeric-300`, lòng trắng mắt `slate-0`, lưỡi `rose-500`, má hồng `rose-200`, bóng `slate-100`. Đạo cụ mang màu của sự kiện: TLE hổ phách, MLE hồng, RE tím, CE lam, SE xám, quiz theo bốn mức, lửa chuỗi ngày `orange-500` (`streak`).

### Lớp

Gốc `<svg>` có `shadow` (bóng, đứng yên khi nhảy), `scene` (đạo cụ trên sàn: đồng hồ cát, bục, con bọ bay…) và `naomi`. Trong `naomi`, từ sau ra trước: `fx-back`, `tail`, `feet`, `body`, `props`, `arm-right`, `arm-left`, `head`, `eyes`, `eyelids`, `mouth`, `props-head`, `fx`. Mọi lớp luôn có mặt, rỗng thì là `<g id="…"/>`, nên component điều khiển theo tên mà không cần biết mood.

- `right`/`left` là của Naomi: tay phải của Naomi ở bên trái người xem khi nhìn thẳng.
- Lớp con có tên: `tail-spots`, `foot-right`/`foot-left`, `belly`, `body-spots`, `arm-*-limb`, `arm-*-hand`, `arm-*-held` (đồ cầm tay, đi theo tay khi làm hoạt ảnh), `head-shape`, `head-spots`, `nostrils`, `cheeks`, `eye-right`/`eye-left`, `lid-right`/`lid-left`.
- Tay đổi chỗ được mà không đổi tên: sau thân (`behind`, góc nghiêng), sau đạo cụ (`back`: laptop, sợi dây), mặc định sau đầu, hoặc trước mặt (`front`: gãi đầu, chống cằm, che miệng ngáp).
- Đầu, mắt, mí, miệng, mũ dùng chung một `transform` khi nghiêng đầu.
- Id trùng nhau giữa các tệp. Dùng bằng `<img>` thì không sao; nhúng nhiều SVG thẳng vào một trang thì component phải đổi id (task component).

### Luật đã kiểm bằng máy

[`check/naomi.cjs`](check/naomi.cjs) đọc mọi tệp trong `naomi/views` và `naomi/moods`, thoát 1 nếu một luật hỏng. Bản chạy: `docs/report/assets/phase-7/naomi/check.txt`.

1. Mọi màu là token; không `<style>`, `<text>`, `<image>`, `url(#…)` (ảnh tải lên artifact bị lọc `<style>`, và `<img>` không có font).
2. Đủ bộ lớp, id không trùng trong một tệp.
3. **Màu nghệ không tô miệng, tay, chân, đuôi, thân hay đầu.** Được ở mắt (mống mắt), đạo cụ, hiệu ứng và đồ cầm tay. Bản chạy liệt kê nghệ nằm ở đâu: `turmeric-300` ở `eyes`, `props-head`, `scene`; `turmeric-400` ở `props-head`, `scene`.
4. Mọi màu trên thân cách mọi màu của Duo ít nhất ΔE 0,10 (OKLab). Gần nhất là `jade-500` với Wing Overlay, ΔE 0,190.
5. Không vẽ ra ngoài khung 200 × 200 (vẽ lại với lề 20, đếm pixel ngoài khung).
6. **Đuôi xoắn và đốm phải lộ ra:** tô riêng lớp đó màu hồng sen, lấy số pixel còn thấy trong hình đầy đủ chia cho số pixel khi vẽ lớp đó một mình. Ngưỡng: đuôi ≥ 60 %, đốm đầu ≥ 50 %, đốm đuôi ≥ 50 % ở mọi hình; đốm thân ≥ 50 % ở ba góc (ở mood, đạo cụ được phép che bụng). Kết quả 21/10: đuôi thấp nhất 60 % (`stuffed`), đốm đầu 83 % (`three-quarter`), đốm đuôi 75 %, đốm thân ở ba góc 61 % (`side`).

Lần chạy đầu, luật 5–6 bắt được 11 lỗi thật: ngón chân góc nghiêng và ¾ tràn đáy khung, mũ tiệc tràn đỉnh, biển “đang sửa” và túi hàng che gần nửa đuôi, mũ tốt nghiệp che 92 % đốm đầu, tay ở tư thế nghỉ che 61 % đốm thân.

### Bài học khi vẽ

- Tay của Naomi ngắn (khoảng 35–45 đơn vị). Giơ tay lên cao thì bàn tay nấp sau đầu: nắm tay cổ vũ, đuốc, vẫy tay đều phải đưa ra ngang, ra ngoài bướu mắt (x > 163).
- Tay trái được vẽ bằng cách lật tay phải, và đồ cầm tay lật theo. Dấu tích, thẻ, chữ không được lật: viết thẳng tọa độ (`mirror: false`).
- Đạo cụ to (biển, túi, sách) đặt lệch sang bên không có đuôi.
- Mắt `happy` (^ ^) đọc ấm hơn mí trễ cho `comfort`; mí trễ cộng mí dưới đọc thành chán.
- Góc nghiêng: bướu của mắt xa ló sau đỉnh đầu trông như cái mũ, đã bỏ. Mắt tắc kè nằm hai bên đầu nên nhìn nghiêng vẫn thấy tròn một mắt.

### Chạy lại

```bash
node docs/ui-ux/mascot/naomi/build.cjs
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/naomi.cjs docs/report/assets/phase-7/naomi/check.txt
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/sheet.cjs --dir naomi/moods
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/boards.cjs docs/report/assets/phase-7/naomi/boards
```

`build.cjs` chạy lại ra đúng từng byte cũ. Đổi hình thì tải lại SVG lên canvas (mục "Sửa một hình rồi đăng lại" bên dưới); `canvas/assets.json` ghi id ↔ tệp, đường dẫn tính từ thư mục này.

## Ba hướng (hồ sơ lần chọn, 21/10/2026)

| | **A · Tắc kè “bắt bug” — đã chọn, tên Naomi** | B · Chim Lạc “đường bay” | C · Robot màn hình |
|---|---|---|---|
| Ý | Tắc kè ăn côn trùng = bắt bug. AC là bắt được con bọ, WA là con bọ bay mất | Chim Lạc trên trống đồng, nhìn nghiêng, vòng tròn đồng tâm trên cánh | Mặt là màn hình, cảm xúc bằng mắt pixel, đèn ăng-ten |
| Mạnh | Ẩn dụ khớp tính năng chấm code; AC/WA là hai cảnh của cùng một chuyện | Bản sắc Việt rõ nhất; tên "Lạc" chơi chữ được ở trang 404 | Đọc rõ nhất ở 24px; hoạt ảnh rẻ nhất; màn hình hiện được "test 3/10" |
| Rủi ro | Nhìn thẳng dễ thành ếch; nhiều chi tiết nhất | Vẫn là chim (gần Duo nhất); lệch bảng màu dành sẵn | Phổ biến, ít bản sắc, lạnh |
| Tên gợi ý | Kè · Sùng · Bít | Lạc · Đồng · Bay | Pi · Bo · Bin |

Bốn trạng thái vẽ cho cả ba, để so cho công bằng: `rest` (nghỉ), `celebrate` (AC 100/100), `partial` (WA), `lost` (404).

## Luật chung đã áp

- **Bảng màu dành sẵn** trong README của design system: thân `jade-500`, mảng sáng `jade-100`, nét `jade-900`, nhấn `turmeric-300`. Dùng thêm `jade-700` (đốm, mỏ chim), `jade-300` (mắt pixel), `red-500` (con bọ), `blue-200` (giọt mồ hôi), `slate-100` (bóng dưới chân). Không mã màu nào nằm ngoài `tokens.json`.
- **Một kiểu nét viền cho cả ba:** viền `jade-900` dày khoảng 4,5/200 bề ngang. Viền tách nhân vật khỏi nền trắng và khác cách vẽ mảng phẳng không viền của Duo.
- **Viền chỉ nằm ở mép ngoài:** mỗi khối ghép (đầu + hai u mắt, thân + cổ + đầu) vẽ hai lượt. Lượt đầu tô `jade-900` có nét dày 9, lượt sau tô màu nền không nét. Chi tay, đuôi vẽ bằng hai nét chồng (nét đậm rộng, nét màu hẹp).
- **SVG chỉ dùng thuộc tính trình bày,** không `<style>`, vì ảnh tải lên artifact bị lọc `<style>`. Mỗi bộ phận là một `<g id>` (`tail`, `head`, `eyes`, `arms`…), sẵn để task model sheet tách lớp làm hoạt ảnh.

## Kiểm với Duo

Mã màu của Duo lấy từ trang thương hiệu chính thức của Duolingo (design.duolingo.com › Identity › Color, đọc 21/10/2026). Khoảng cách đo bằng ΔE trong OKLab, mức 0,02 là vừa thấy khác. Kết quả ở [`check/duo_distance.py`](check/duo_distance.py), bản chạy ở `docs/report/assets/phase-7/mascot-directions/duo-distance.txt`.

- `jade-500` cách thân Duo (`#58CC02`) ΔE 0,22, cách mọi màu xanh của Duo ít nhất 0,19. Lệch 39° sắc độ, độ rực chưa bằng nửa.
- **`turmeric-300` cách mỏ trên của Duo (`#FFC200`) chỉ ΔE 0,028**, gần như trùng. Từ đây có **luật cho mọi hướng: màu nghệ không tô mỏ, chân hay bàn chân.** Nó chỉ ở những chỗ Duo không có: mống mắt (A), đèn ăng-ten (C), tia lấp lánh khi có thưởng. Vì vậy mỏ chim Lạc màu `jade-700`, chân màu `jade-900`. Thân chim Lạc màu `jade-100`, vì chim thân xanh mỏ vàng đúng là công thức của Duo.
- Canvas không vẽ lại Duo, chỉ ghi mã màu đã công bố.

## Bài học khi vẽ

- Tắc kè nhìn thẳng với mắt lồi trên đỉnh đầu đọc thành ếch, và hình bóng thành "tai chuột". Đã dời mắt xuống hai bên đầu, thêm đốm da báo `jade-700`, xòe ngón có giác bám ra ngoài thân. **Model sheet phải giữ đốm và đuôi ở mọi góc.**
- Chim Lạc giơ cánh lên lúc ăn mừng thì đụng mào, nên khi ăn mừng mào dựng đứng. Cánh "gãi đầu" dính vào cổ thành một mảng, nên đổi thành chạm cánh vào cằm. Đầu nhỏ thì kém dễ thương, nên bán kính đầu tăng từ 28 lên 31.
- Ở 24px: robot đọc rõ nhất. Tắc kè còn nhận ra nhờ đuôi xoắn nhưng mất ngón và đốm. Mào và đuôi của chim Lạc thành gai.

## Tệp

| Tệp | Nội dung |
|---|---|
| `directions/*.svg` | 12 hình (3 hướng × 4 trạng thái), viewBox 200 × 200, vẽ tay. `gecko-*.svg` là điểm xuất phát của Naomi |
| `canvas/project/` | Bản trong repo của canvas: `canvas.json` + 7 tệp `.dc.html`. `project/ds/devpath/tokens.json` do server chép thẳng từ artifact design system nên không có ở đây |
| `canvas/assets.json` | Id ảnh trên artifact (`/_blob/<id>`) ↔ tệp SVG, đường dẫn tính từ `docs/ui-ux/mascot` |
| `check/sheet.cjs` | Bảng kiểm: mỗi hình ở 200/64/32 px + hình bóng. `--dir naomi/moods` cho thư mục khác `directions/`, `SCALE=2` để soi nét |
| `check/naomi.cjs` | Sáu luật của Naomi (mục trên) |
| `check/boards.cjs` | Dựng lại 7 artboard trên máy, không cần mạng: ảnh lấy theo `canvas/assets.json`, Lexend tự host của frontend. Kiểm nội dung khít khung, không tràn ngang; thoát 1 nếu có artboard hỏng |
| `canvas/make_moods_board.py` | Sinh artboard “Naomi · bộ biểu cảm” từ `naomi/naomi.json` + `assets.json`: tải lại hình thì chạy lại, không sửa 30 id bằng tay |
| `check/duo_distance.py` | Đo ΔE OKLab giữa bảng màu nhân vật và màu Duo |

Chạy từ gốc repo:

```bash
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/sheet.cjs [gecko|lac|robot]
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/boards.cjs docs/report/assets/phase-7/mascot-directions
python -I docs/ui-ux/mascot/check/duo_distance.py
```

## Sửa một hình rồi đăng lại

1. Sửa SVG trong `directions/` (Naomi: sửa `naomi/build.cjs` rồi chạy nó), chạy `sheet.cjs` để xem (Naomi: thêm `check/naomi.cjs`).
2. Tải lại hình lên artifact (Artifact `publish` với `asset: true`). Hình mới có id mới: đổi id trong các artboard dùng nó và trong `assets.json`.
3. Chạy `boards.cjs`, rồi publish các artboard đã đổi với `root` = `docs/ui-ux/mascot/canvas`. Chỉ gửi `canvas.json` khi đổi bố cục.
