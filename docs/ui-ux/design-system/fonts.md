# Chọn font chữ chính (21/10/2026)

Task "Chọn font có subset `vietnamese` đầy đủ" của [Phase 7](../../plan/phase-7-ui-ux-upgrade.md). Kết quả: **Lexend** thay Geist cho mọi chữ. Geist Mono (code) và Noto Serif (chứng chỉ) giữ nguyên.

Mọi số dưới đây đo trong Chrome thật bằng các script ở [`font-eval/`](font-eval/), với chính tệp woff2 Google Fonts trả về (subset latin + vietnamese, độ đậm 400–700). Ảnh ở [`docs/report/assets/phase-7/font/`](../../report/assets/phase-7/font/).

## Ứng viên và số đo

| Font | Tải (KB) | Câu 16px | "₫" so với số 0 | Dấu chữ hoa trồi khỏi dòng ở 14/20 · 16/24 | Header khách 360px | Ghi chú |
|---|---|---|---|---|---|---|
| Geist (đang dùng) | 36,5 | 533px | **0,73** | −0,2 · −0,6 | 344,8px | "₫" nhỏ như chỉ số trên; dấu chồng nhòe ở 12–14px |
| **Lexend** | 52,3 | 566px | 1,01 | −0,3 · −0,5 | 363,3 → **345,0px** sau khi chỉnh header | Chọn |
| Be Vietnam Pro | 132,4 (4 tệp tĩnh) | 562px | 0,93 | **+1,7 · +1,7** | 361,5px | Dấu rõ nhất, nhưng `truncate` cắt dấu ngã: "Ỗ" đọc thành "Ô" |
| Manrope | 32,6 | 528px | 1,01 | +0,3 · +0,6 | 342,6px | Gọn và nhẹ nhất; dấu chồng nhòe ở 12–14px |
| Nunito | 51,0 | 519px | 1,21 | −0,1 · −0,7 | — | Nét tròn, gần dáng chữ Duolingo |
| Plus Jakarta Sans | 34,9 | 535px | 0,99 | — | — | **Loại:** dấu nặng của "ỵ" lệch hẳn sang phải, đọc như "y." |
| Bricolage Grotesque | 87,8 | 543px | 1,18 | — | — | Cá tính hợp làm chữ tiêu đề, nặng nhất trong nhóm variable |

- **Tải:** tổng woff2 subset latin + vietnamese cho độ đậm 400–700. Trang chỉ tải subset nó dùng (`unicode-range`). Lexend còn một tệp latin-ext 34,5 KB, chỉ tải khi trang có ký tự trong dải đó.
- **Câu 16px:** bề rộng câu "Chương trình chạy xong nhưng in ra khác kết quả mong đợi ở test thứ ba." Lexend rộng hơn Geist 6%.
- **Dấu trồi khỏi dòng:** khoảng cách từ đỉnh dấu cao nhất của "ẪỮỖỜỢẰẲẴẶ…" tới mép trên hộp dòng, tính bằng px, âm là nằm trong dòng. Dương nghĩa là chữ trong khung `overflow: hidden` (`truncate`, `line-clamp`) bị cắt mất phần dấu đó. Với Be Vietnam Pro, ảnh `zoom-bvp-14-20.png` cho thấy dấu ngã trên "Ỗ" và "Ẫ" mất hẳn, thêm 2px lề thì đủ. Riêng `line-clamp` còn để lộ dấu của dòng bị ẩn ở mép dưới khung, ở cả 6 cách cắt đã thử.

## Vì sao Lexend

1. **Dấu tiếng Việt đọc được ở cỡ nhỏ.** Phóng to ảnh chụp ở DPR 1 (`small-3x.png`): ở 12 và 14px, Lexend và Be Vietnam Pro vẫn tách được "ẩ ẫ ấ ầ ậ"; Geist và Manrope nhòe phần dấu chồng. Giao diện DevPath có nhiều chữ 12–14px (bảng, thời gian, nhãn), nên đây là tiêu chí nặng nhất.
2. **Không cắt dấu.** Ở mọi cỡ từ `title` trở xuống, cả dấu của chữ hoa cũng nằm trong dòng, giống Geist trước đây. Không cần luật CSS mới cho `truncate`/`line-clamp`.
3. **"₫" đúng cỡ** cho mọi giá tiền ("499.000 ₫"); Geist vẽ nó chỉ bằng 0,73 chiều cao chữ số.
4. **Một tệp variable cho mọi độ đậm** (52 KB) thay vì bốn tệp tĩnh (132 KB) của Be Vietnam Pro. Preload vẫn đúng hai tệp (latin + vietnamese) như với Geist.
5. Lexend được thiết kế để dễ đọc; đó là mục tiêu của một nền tảng học.

Cái giá: rộng hơn Geist 6%. Header khách ở 360px tràn 3,3px với cỡ chữ cũ. Đã sửa bằng cách hạ cỡ chữ dưới `sm` (logo 19px, "Khóa học" 14px, hai nút 12px, khoảng 8px): header về 345,0px, dư 15px như trước. Tám trang công khai × 360/375/1440px: 0/24 lượt tràn ngang (`font-eval/overflow.cjs`, chạy vào `next dev` lấy dữ liệu từ stack demo). Trang cần đăng nhập chưa đo lại; việc này thuộc task "Nền" (đo lại tràn ngang 360/375/1440).

## Thang chữ theo Lexend

Ba line-height đổi trong design system để dấu chữ thường không trồi khỏi dòng: display 40/48 → **40/52**, h1 30/38 → **30/40**, caption 12/16 → **12/18**. Các cỡ khác giữ nguyên.

## Chạy lại

```bash
cd docs/ui-ux/design-system/font-eval
node fetch.mjs                                    # tải woff2 vào dl/ (đã gitignore)
NODE_PATH=../../../../frontend/node_modules node measure.cjs     # bảng trên + specimen
NODE_PATH=../../../../frontend/node_modules node closeup.cjs     # chữ khó phóng to + "₫"
NODE_PATH=../../../../frontend/node_modules node lineheight.cjs  # dấu trồi theo line-height
NODE_PATH=../../../../frontend/node_modules node small.cjs       # 12/14px ở DPR 1
NODE_PATH=../../../../frontend/node_modules node header.cjs      # header khách 360px
NODE_PATH=../../../../frontend/node_modules node clip.cjs && NODE_PATH=../../../../frontend/node_modules node zoom.cjs
```

`overflow.cjs` cần app đang chạy (`BASE`, mặc định `http://localhost:3100`).
