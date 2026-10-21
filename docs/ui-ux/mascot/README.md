# Linh vật DevPath — ba hướng (21/10/2026)

Task Phase 7 "Phác ba hướng nhân vật cạnh nhau trên một artifact Design" ([plan](../../plan/phase-7-ui-ux-upgrade.md), [tài liệu thiết kế mục 4–5](../thiet-ke-nang-cap-ui-ux.md)).

- **Artifact Design:** [Linh vật DevPath](https://claude.ai/artifact/LgYj69gDYUuze9geb8J7W8). Có 5 artboard: tổng quan, ba hướng, kiểm với Duo. Design system DevPath được cài vào canvas.
- **User chọn 21/10/2026: hướng A, tắc kè “bắt bug”, tên Naomi.** Claude đã đề xuất A. Tên Naomi là của user, không nằm trong ba tên gợi ý (Kè, Sùng, Bít). Canvas giữ nguyên cả ba hướng làm hồ sơ của lần chọn.

## Ba hướng

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
| `directions/*.svg` | 12 hình (3 hướng × 4 trạng thái), viewBox 200 × 200. Đây là nguồn chân lý |
| `canvas/project/` | Bản trong repo của canvas: `canvas.json` + 5 tệp `.dc.html`. `project/ds/devpath/tokens.json` do server chép thẳng từ artifact design system nên không có ở đây |
| `canvas/assets.json` | Id ảnh trên artifact (`/_blob/<id>`) ↔ tệp SVG |
| `check/sheet.cjs` | Bảng kiểm: mỗi hình ở 200/64/32 px + hình bóng. `SCALE=2` để soi nét |
| `check/boards.cjs` | Dựng lại 5 artboard trên máy, không cần mạng: ảnh lấy từ `directions/`, Lexend tự host của frontend. Kiểm nội dung khít khung, không tràn ngang; thoát 1 nếu có artboard hỏng |
| `check/duo_distance.py` | Đo ΔE OKLab giữa bảng màu nhân vật và màu Duo |

Chạy từ gốc repo:

```bash
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/sheet.cjs [gecko|lac|robot]
NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/boards.cjs docs/report/assets/phase-7/mascot-directions
python -I docs/ui-ux/mascot/check/duo_distance.py
```

## Bước sau: model sheet của Naomi

- Model sheet (chính diện, ¾, nghiêng) + đủ các `mood` ở mục 5 của tài liệu thiết kế, xuất phát từ bốn hình `gecko-*.svg`. Giữ đốm và đuôi xoắn ở mọi góc, vì nhìn thẳng mà thiếu chúng là thành ếch.
- Cập nhật mục "Nhân vật linh vật" trong README của design system (bản trong repo và artifact cùng lúc): hướng đã chọn, tên, luật màu nghệ không tô mỏ/chân/bàn chân.

## Sửa một hình rồi đăng lại

1. Sửa SVG trong `directions/`, chạy `sheet.cjs` để xem.
2. Tải lại hình lên artifact (Artifact `publish` với `asset: true`). Hình mới có id mới: đổi id trong các artboard dùng nó và trong `assets.json`.
3. Chạy `boards.cjs`, rồi publish các artboard đã đổi với `root` = `docs/ui-ux/mascot/canvas`. Chỉ gửi `canvas.json` khi đổi bố cục.
