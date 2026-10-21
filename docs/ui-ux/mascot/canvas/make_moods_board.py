"""Writes project/NaomiMoods.dc.html (the "Naomi · bộ biểu cảm" artboard) from
../naomi/naomi.json and assets.json, so re-uploaded drawings only need a rerun.

    python docs/ui-ux/mascot/canvas/make_moods_board.py [height]

Then check with check/boards.cjs and publish the artboard (README, last section).
"""
import html, json, os, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # docs/ui-ux/mascot
assets = json.load(open(f"{root}/canvas/assets.json", encoding="utf8"))["assets"]
by_file = {v: k for k, v in assets.items()}
manifest = {m["mood"]: m for m in json.load(open(f"{root}/naomi/naomi.json", encoding="utf8"))["moods"]}

MONO = "font-family: 'Geist Mono', ui-monospace, Consolas, monospace"
CODE_C = "#066254"

# (section title, [(mood, short caption)]) ; spans must add up to 8 per row
ROWS = [
    [("Trang nộp bài · đang chấm và 7 verdict", [
        ("grading", "Đang chấm, “test k/n”"), ("celebrate", "AC 100/100"), ("partial", "WA, AC một phần"),
        ("sleepy", "TLE quá thời gian"), ("stuffed", "MLE quá bộ nhớ"), ("dizzy", "RE lỗi khi chạy"),
        ("tangled", "CE lỗi cú pháp"), ("sorry", "SE, lỗi hệ thống, 500")])],
    [("Kết quả quiz", [
        ("party", "100 %"), ("proud", "≥ 80 %"), ("cheer", "50–79 %"), ("comfort", "< 50 %"), ("startled", "Hết giờ")]),
     ("Trợ giảng AI", [("thinking", "Đang trả lời"), ("answer", "Trả lời có nguồn")]),
     ("Nghỉ", [("rest", "Về đây sau mỗi phản ứng")])],
    [("Thành tích", [
        ("fire", "Chuỗi ngày còn giữ"), ("sad", "Chuỗi ngày vừa mất"), ("levelup", "Lên hạng"), ("graduate", "Nhận chứng chỉ")]),
     ("Tài khoản, thanh toán", [("wave", "Đăng ký xong, chào lại"), ("paid", "Thanh toán xong"), ("oops", "Thanh toán lỗi")]),
     ("Trang 404", [("lost", "Không tìm thấy trang")])],
    [("Empty state · đạo cụ theo chỗ", [
        ("empty", "Tư thế chờ, chưa đạo cụ"), ("empty-cart", "Giỏ hàng trống"), ("empty-courses", "Chưa có khóa học"),
        ("empty-notifications", "Chưa có thông báo"), ("empty-notes", "Chưa có ghi chú"), ("empty-search", "Tìm không ra")]),
     ("RULES", [])],
]

def cell(mood, caption):
    m = manifest[mood]
    blob = by_file["naomi/" + m["file"]]
    return (
        f'<figure style="margin: 0; display: flex; flex-direction: column; gap: 6px; min-width: 0">'
        f'<div style="background: #f0f4f7; border-radius: 10px; height: 140px; display: flex; align-items: center; justify-content: center">'
        f'<img src="/_blob/{blob}" width="132" height="132" alt="{html.escape(m["label"])}"></div>'
        f'<figcaption style="display: flex; flex-direction: column; gap: 2px">'
        f'<code style="{MONO}; font-size: 12px; line-height: 18px; color: {CODE_C}">{mood}</code>'
        f'<span style="font-size: 13px; line-height: 18px; color: #273842">{html.escape(caption)}</span>'
        f'</figcaption></figure>'
    )

RULES = (
    '<section style="grid-column: span 2; background: #ffffff; border: 1px solid #e3eaee; border-radius: 14px; padding: 18px 20px; display: flex; flex-direction: column; gap: 8px; min-width: 0">'
    '<h3 style="margin: 0; font-size: 14px; line-height: 20px; font-weight: 600">Luật phản ứng</h3>'
    '<ul style="margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; line-height: 18px; color: #273842">'
    '<li>Một lần cho mỗi sự kiện, 2–3 giây rồi về <code style="' + MONO + '; font-size: 12px">rest</code>.</li>'
    '<li>Chỉ khi sự kiện vừa xảy ra trong phiên. Mở lại lịch sử thì hiện hình tĩnh, không ăn mừng lại.</li>'
    '<li>Không che nút, không chặn click. Bật giảm chuyển động thì chỉ còn hình tĩnh này.</li>'
    '<li>Đạo cụ mang màu của verdict hay mức quiz: TLE hổ phách, MLE hồng, RE tím, CE lam, SE xám.</li>'
    '</ul></section>'
)

out = []
for row in ROWS:
    parts = []
    for title, items in row:
        if title == "RULES":
            parts.append(RULES)
            continue
        n = len(items)
        parts.append(
            f'<section style="grid-column: span {n}; display: flex; flex-direction: column; gap: 10px; min-width: 0">'
            f'<h2 style="margin: 0; font-size: 12px; line-height: 16px; font-weight: 600; letter-spacing: 0.06em; color: #556670">{html.escape(title.upper())}</h2>'
            f'<div style="display: grid; grid-template-columns: repeat({n}, minmax(0, 1fr)); gap: 16px">'
            + "".join(cell(m, c) for m, c in items)
            + "</div></section>"
        )
    out.append('  <div style="display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 16px">\n    ' + "\n    ".join(parts) + "\n  </div>")

count = sum(len(items) for row in ROWS for t, items in row)
assert count == len(manifest), (count, len(manifest))
H = int(sys.argv[1]) if len(sys.argv) > 1 else 1300
page = f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Naomi — bộ biểu cảm</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&amp;display=swap">
<style>
body{{margin:0}}
a{{color:#066254}}a:hover{{color:#074b40}}
</style>
</helmet>
<div style="width: 1440px; height: {H}px; box-sizing: border-box; padding: 48px; background: #f8fafc; color: #102029; font-family: 'Lexend', 'Segoe UI', system-ui, sans-serif; display: flex; flex-direction: column; gap: 28px">
  <header style="display: flex; flex-direction: column; gap: 8px; max-width: 920px">
    <div style="font-size: 12px; line-height: 16px; font-weight: 600; letter-spacing: 0.06em; color: #556670">NAOMI · BỘ BIỂU CẢM</div>
    <h1 style="margin: 0; font-size: 30px; line-height: 40px; font-weight: 700; letter-spacing: -0.015em">Mỗi sự kiện một phản ứng</h1>
    <p style="margin: 0; font-size: 18px; line-height: 30px; color: #273842">24 mood của bản đồ phản ứng cộng tư thế nghỉ, và 5 đạo cụ cho empty state: 30 hình. Mỗi mood gắn với một sự kiện app đã phát ra hôm nay. Hình ở đây cũng là tư thế tĩnh khi người dùng bật giảm chuyển động.</p>
  </header>
{chr(10).join(out)}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1440,"height":{H}}}}}'>
class Component extends DCLogic {{
  renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
'''
open(f"{root}/canvas/project/NaomiMoods.dc.html", "w", encoding="utf8", newline="\n").write(page)
print("cells", count)
