"""Build the DevPath design-system tokens and check every colour pair we promise.

Run from the repo root:

    python docs/ui-ux/design-system/palette.py

It writes `project/tokens.json` (the file the Claude Design artifact reads) and
`contrast.txt` (every text/mark pair with its ratio). It exits 1 if a pair
misses its floor, so a tweak that breaks WCAG AA cannot slip in quietly.

Colours are chosen in OKLCH, where equal steps of L look like equal steps of
lightness across hues, then converted to sRGB hex. A colour outside sRGB keeps
its L and hue and loses chroma until it fits. Usage notes are Vietnamese: they
are what people read on the artifact.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_TOKENS = HERE / "project" / "tokens.json"
OUT_REPORT = HERE / "contrast.txt"


# ---------------------------------------------------------------- colour math


def _oklch_to_linear_srgb(L: float, C: float, h: float) -> tuple[float, float, float]:
    a = C * math.cos(math.radians(h))
    b = C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )


def _in_gamut(rgb: tuple[float, float, float]) -> bool:
    return all(-1e-6 <= c <= 1 + 1e-6 for c in rgb)


def _encode(c: float) -> int:
    c = min(1.0, max(0.0, c))
    v = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return round(v * 255)


def oklch_hex(L: float, C: float, h: float) -> str:
    """Hex for an OKLCH colour, dropping chroma (never L or hue) to fit sRGB."""
    if not _in_gamut(_oklch_to_linear_srgb(L, C, h)):
        lo, hi = 0.0, C
        for _ in range(40):
            mid = (lo + hi) / 2
            if _in_gamut(_oklch_to_linear_srgb(L, mid, h)):
                lo = mid
            else:
                hi = mid
        C = lo
    return "#" + "".join(f"{_encode(c):02x}" for c in _oklch_to_linear_srgb(L, C, h))


def luminance(hex_: str) -> float:
    def lin(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ------------------------------------------------------------------- palette
# (L, C) per step. Hue per family.

FAMILIES: dict[str, dict] = {
    "slate": {
        "hue": 235,
        "note": "Trung tính ngả mực xanh: giấy, đường kẻ, chữ.",
        "steps": {
            "0": (1.0, 0.0),
            "25": (0.985, 0.003),
            "50": (0.966, 0.006),
            "100": (0.932, 0.009),
            "200": (0.885, 0.012),
            "300": (0.80, 0.016),
            "400": (0.70, 0.020),
            "500": (0.585, 0.024),
            "600": (0.50, 0.026),
            "700": (0.42, 0.028),
            "800": (0.33, 0.028),
            "900": (0.235, 0.028),
            "950": (0.18, 0.025),
        },
    },
    "jade": {
        "hue": 178,
        "note": "Thương hiệu — ngọc: nút chính, link, focus, thân nhân vật.",
        "steps": {
            "50": (0.972, 0.022),
            "100": (0.938, 0.045),
            "200": (0.885, 0.075),
            "300": (0.80, 0.10),
            "400": (0.70, 0.115),
            "500": (0.60, 0.11),
            "600": (0.515, 0.095),
            "700": (0.445, 0.08),
            "800": (0.37, 0.065),
            "900": (0.29, 0.05),
        },
    },
    "turmeric": {
        "hue": 84,
        "note": "Phần thưởng — nghệ: XP, sao, quiz 100%, huy chương vàng.",
        "steps": {
            "50": (0.978, 0.03),
            "100": (0.95, 0.07),
            "200": (0.905, 0.12),
            "300": (0.86, 0.155),
            "400": (0.81, 0.165),
            "500": (0.74, 0.155),
            "600": (0.615, 0.13),
            "700": (0.53, 0.11),
            "800": (0.43, 0.085),
            "900": (0.33, 0.06),
        },
    },
}

# Status families share one ladder: 50/100 soft grounds, 200 borders,
# 500/600 marks and solid fills, 700/800 text.
STATUS_STEPS = ("50", "100", "200", "500", "600", "700", "800")


def status(hue: float, chroma: tuple[float, ...], note: str) -> dict:
    lightness = (0.972, 0.938, 0.885, 0.62, 0.535, 0.46, 0.38)
    return {"hue": hue, "note": note, "steps": dict(zip(STATUS_STEPS, zip(lightness, chroma)))}


FAMILIES |= {
    "green": status(150, (0.03, 0.06, 0.10, 0.15, 0.13, 0.11, 0.085), "Thành công: AC, quiz ≥ 80%."),
    "red": status(25, (0.018, 0.04, 0.07, 0.19, 0.19, 0.165, 0.13), "Nguy hiểm: WA, thao tác xóa, lỗi biểu mẫu."),
    "amber": status(65, (0.028, 0.065, 0.11, 0.16, 0.15, 0.125, 0.095), "Cảnh báo và thời gian: TLE, quiz hết giờ."),
    "rose": status(350, (0.018, 0.04, 0.075, 0.18, 0.18, 0.155, 0.12), "MLE."),
    "violet": status(295, (0.02, 0.045, 0.08, 0.16, 0.17, 0.15, 0.12), "RE; quiz < 50% (an ủi)."),
    "blue": status(255, (0.018, 0.04, 0.07, 0.15, 0.16, 0.14, 0.11), "Thông tin: CE; quiz 50–79% (khích lệ); thông báo."),
    "orange": status(45, (0.022, 0.05, 0.09, 0.18, 0.17, 0.15, 0.11), "Lửa chuỗi ngày, huy chương đồng."),
}

HEX: dict[str, str] = {}
for fam, spec in FAMILIES.items():
    for step, (L, C) in spec["steps"].items():
        HEX[f"{fam}-{step}"] = oklch_hex(L, C, spec["hue"])

RAMP_USAGE = {
    "50": "Nền nhạt của chip, alert, dòng đang chọn thuộc họ màu này.",
    "100": "Hover trên nền nhạt; nền nhạt đậm hơn một bậc.",
    "200": "Viền và đường chia bên trong một khối nền nhạt của họ này.",
    "300": "Mảng màu minh họa.",
    "400": "Mảng màu minh họa; nền phần thưởng đi với chữ tối.",
    "500": "Icon, dấu hiệu (≥ 3:1 trên nền trắng).",
    "600": "Nền đặc đi với chữ trắng; icon; chuỗi biểu đồ.",
    "700": "Chữ và link trên nền trắng/nền trang (≥ 4.5:1).",
    "800": "Chữ trên nền 50/100 của chính họ này (≥ 4.5:1).",
    "900": "Chữ đậm nhất; nét viền minh họa.",
}

SLATE_USAGE = {
    "0": "Trắng: card, popover, chữ trên nền đặc.",
    "25": "Nền trang.",
    "50": "Nền trầm (muted).",
    "100": "Đường kẻ mảnh; hover trung tính.",
    "200": "Đường chia trên nền trầm.",
    "300": "Viền khi bị vô hiệu; minh họa.",
    "400": "Minh họa. Không dùng làm icon trên trắng (< 3:1).",
    "500": "Viền control, huy chương bạc (≥ 3:1).",
    "600": "Chữ phụ (≥ 4.5:1 trên 0–100).",
    "700": "Chữ verdict SE.",
    "800": "Chữ phụ đậm.",
    "900": "Chữ nội dung và tiêu đề.",
    "950": "Mực của đổ bóng; nền trình soạn code tối.",
}

# --------------------------------------------------------- semantic aliases
# name -> (alias target or literal, usage). Order is the order the artifact lists them.

SEMANTIC: list[tuple[str, str, str]] = [
    ("background", "slate-25", "Nền trang, nằm dưới mọi thứ."),
    ("foreground", "slate-900", "Chữ nội dung và tiêu đề trên `background`, `card`, `muted`."),
    ("card", "slate-0", "Card, panel, thân bảng, ô nhập."),
    ("card-foreground", "slate-900", "Chữ trên `card`."),
    ("popover", "slate-0", "Dropdown, popover, dialog."),
    ("popover-foreground", "slate-900", "Chữ trên `popover`."),
    ("primary", "jade-600", "Hành động chính duy nhất của một màn; vạch tab đang chọn; thanh tiến độ."),
    ("primary-hover", "jade-700", "`primary` khi trỏ chuột hoặc đang nhấn."),
    ("primary-foreground", "slate-0", "Chữ và icon trên `primary`, `primary-hover`."),
    ("secondary", "jade-50", "Nút thương hiệu dạng nhạt; mục đang chọn trong danh sách/menu."),
    ("secondary-hover", "jade-100", "`secondary` khi trỏ chuột."),
    ("secondary-foreground", "jade-800", "Chữ trên `secondary`, `secondary-hover`."),
    ("muted", "slate-50", "Nền trầm: đầu bảng, khối code, ô bị vô hiệu, skeleton."),
    ("muted-foreground", "slate-600", "Chữ phụ, placeholder, thời gian trên `background`, `card`, `muted`."),
    ("accent", "slate-100", "Hover và highlight bàn phím của dòng/mục menu trung tính."),
    ("accent-foreground", "slate-900", "Chữ trên `accent`."),
    ("link", "jade-700", "Link trong đoạn văn trên `background`, `card`."),
    ("border", "slate-100", "Đường kẻ mảnh: viền card, đường chia, kẻ bảng. Chỉ để trang trí."),
    ("border-strong", "slate-200", "Đường chia cần thấy được trên `muted`."),
    ("input", "slate-500", "Viền ô nhập, select, checkbox, nút outline (≥ 3:1 trên `card`, `background`)."),
    ("ring", "jade-600", "Vòng focus: 2px liền, cách 2px bằng màu nền (≥ 3:1 trên mọi bề mặt)."),
    ("overlay", "#06131b73", "Lớp phủ sau dialog (slate-950, 45%)."),
    ("destructive", "red-600", "Xóa, gỡ, hạ khóa. Nền đặc đi với `destructive-foreground`."),
    ("destructive-foreground", "slate-0", "Chữ trên `destructive`."),
    ("destructive-soft", "red-50", "Nền alert lỗi, nền lời báo của ô nhập sai."),
    ("destructive-text", "red-700", "Chữ lỗi trên `card`, `background`, `destructive-soft`."),
    ("success", "green-600", "Xong, đã trả tiền, đã xuất bản: icon và nền đặc."),
    ("success-soft", "green-50", "Nền alert thành công."),
    ("success-text", "green-800", "Chữ thành công trên `card`, `success-soft`."),
    ("warning", "amber-500", "Cần chú ý: chỉ dùng làm icon (nếu tô nền thì chữ tối)."),
    ("warning-soft", "amber-50", "Nền alert cảnh báo."),
    ("warning-text", "amber-800", "Chữ cảnh báo trên `card`, `warning-soft`."),
    ("info", "blue-600", "Thông báo trung tính: icon và nền đặc."),
    ("info-soft", "blue-50", "Nền alert thông tin."),
    ("info-text", "blue-800", "Chữ thông tin trên `card`, `info-soft`."),
    ("reward", "turmeric-400", "Chip XP, dải quiz 100%. Luôn đi với chữ `reward-foreground`."),
    ("reward-soft", "turmeric-50", "Nền khối thành tích."),
    ("reward-foreground", "turmeric-900", "Chữ trên `reward`, `reward-soft`."),
    ("reward-mark", "turmeric-600", "Sao đã tô, cúp, icon XP trên `card`."),
    ("streak", "orange-500", "Ngọn lửa chuỗi ngày khi chuỗi còn sống."),
    ("streak-text", "orange-700", "Số ngày cạnh ngọn lửa."),
    ("medal-gold", "turmeric-600", "Hạng 1 bảng xếp hạng."),
    ("medal-silver", "slate-500", "Hạng 2."),
    ("medal-bronze", "orange-600", "Hạng 3."),
]

# Seven verdicts: (code, family, label). Each gets ink (text/icon on its soft
# ground and on card), soft (chip ground) and solid (dots, progress segments).
VERDICTS = [
    ("ac", "green", "Đúng"),
    ("wa", "red", "Sai kết quả"),
    ("tle", "amber", "Quá thời gian"),
    ("mle", "rose", "Quá bộ nhớ"),
    ("re", "violet", "Lỗi khi chạy"),
    ("ce", "blue", "Lỗi cú pháp"),
    ("se", "slate", "Lỗi hệ thống"),
]

# Quiz result levels, by score: (mood, family, band).
QUIZ = [
    ("party", "turmeric", "100%"),
    ("proud", "green", "≥ 80%"),
    ("cheer", "blue", "50–79%"),
    ("comfort", "violet", "< 50%"),
]

CHART = [
    ("chart-1", "jade-600", "Chuỗi thứ nhất (doanh thu, ghi danh)."),
    ("chart-2", "turmeric-600", "Chuỗi thứ hai."),
    ("chart-3", "blue-600", "Chuỗi thứ ba."),
    ("chart-4", "rose-500", "Chuỗi thứ tư."),
    ("chart-5", "slate-500", "Kỳ trước, đường nền, 'khác'."),
]


def verdict_tokens() -> list[tuple[str, str, str]]:
    rows = []
    for code, fam, label in VERDICTS:
        soft, ink, solid = (
            ("slate-100", "slate-700", "slate-500") if fam == "slate" else (f"{fam}-50", f"{fam}-800", f"{fam}-600")
        )
        upper = code.upper()
        rows += [
            (f"verdict-{code}", ink, f"{upper} ({label}): chữ và icon trên `verdict-{code}-soft` và `card`."),
            (f"verdict-{code}-soft", soft, f"{upper}: nền chip verdict và dải kết quả."),
            (f"verdict-{code}-solid", solid, f"{upper}: chấm trong danh sách test, một đoạn của thanh tiến độ chấm."),
        ]
    return rows


def quiz_tokens() -> list[tuple[str, str, str]]:
    rows = []
    for mood, fam, band in QUIZ:
        ink = "turmeric-900" if fam == "turmeric" else f"{fam}-800"
        solid = "turmeric-600" if fam == "turmeric" else f"{fam}-500"
        rows += [
            (f"quiz-{mood}", ink, f"Quiz {band} (`{mood}`): điểm và câu tiêu đề trên `quiz-{mood}-soft` và `card`."),
            (f"quiz-{mood}-soft", f"{fam}-50", f"Quiz {band}: nền card kết quả."),
            (f"quiz-{mood}-solid", solid, f"Quiz {band}: vòng điểm và icon."),
        ]
    return rows


ALL_ALIASES = SEMANTIC + verdict_tokens() + quiz_tokens() + CHART
RESOLVE = {name: (target if target.startswith("#") else HEX[target]) for name, target, _ in ALL_ALIASES}
RESOLVE |= HEX

# ------------------------------------------------------------ the promises
# (fg, bg, floor, why). Text 4.5; marks, control borders and focus 3.

CHECKS: list[tuple[str, str, float, str]] = []
for bg in ("background", "card", "muted"):
    CHECKS += [
        ("foreground", bg, 4.5, "body text"),
        ("muted-foreground", bg, 4.5, "secondary text"),
        ("link", bg, 4.5, "link"),
        ("destructive-text", bg, 4.5, "error text"),
        ("success-text", bg, 4.5, "success text"),
        ("warning-text", bg, 4.5, "warning text"),
        ("info-text", bg, 4.5, "info text"),
        ("input", bg, 3.0, "control border"),
        ("ring", bg, 3.0, "focus ring"),
    ]
CHECKS += [
    ("primary-foreground", "primary", 4.5, "primary button"),
    ("primary-foreground", "primary-hover", 4.5, "primary button, hover"),
    ("secondary-foreground", "secondary", 4.5, "secondary button"),
    ("secondary-foreground", "secondary-hover", 4.5, "secondary button, hover"),
    ("accent-foreground", "accent", 4.5, "highlighted row"),
    ("muted-foreground", "accent", 4.5, "secondary text in a highlighted row"),
    ("destructive-foreground", "destructive", 4.5, "destructive button"),
    ("destructive-text", "destructive-soft", 4.5, "error alert"),
    ("success-text", "success-soft", 4.5, "success alert"),
    ("warning-text", "warning-soft", 4.5, "warning alert"),
    ("info-text", "info-soft", 4.5, "info alert"),
    ("reward-foreground", "reward", 4.5, "XP chip"),
    ("reward-foreground", "reward-soft", 4.5, "achievements block"),
    ("reward-mark", "card", 3.0, "star / trophy icon"),
    ("streak", "card", 3.0, "streak flame"),
    ("streak-text", "card", 4.5, "streak count"),
    ("streak-text", "reward-soft", 4.5, "streak count in the achievements block"),
    ("medal-gold", "card", 3.0, "medal icon"),
    ("medal-silver", "card", 3.0, "medal icon"),
    ("medal-bronze", "card", 3.0, "medal icon"),
    ("success", "card", 3.0, "success icon"),
    ("warning", "card", 3.0, "warning icon"),
    ("info", "card", 3.0, "info icon"),
    ("destructive", "card", 3.0, "danger icon"),
    ("ring", "primary-foreground", 3.0, "focus ring gap"),
]
for code, _fam, _label in VERDICTS:
    CHECKS += [
        (f"verdict-{code}", f"verdict-{code}-soft", 4.5, f"{code.upper()} chip"),
        (f"verdict-{code}", "card", 4.5, f"{code.upper()} text on card"),
        (f"verdict-{code}-solid", "card", 3.0, f"{code.upper()} dot"),
    ]
for mood, _fam, _band in QUIZ:
    CHECKS += [
        (f"quiz-{mood}", f"quiz-{mood}-soft", 4.5, f"quiz {mood} result"),
        (f"quiz-{mood}", "card", 4.5, f"quiz {mood} text on card"),
        (f"quiz-{mood}-solid", "card", 3.0, f"quiz {mood} ring"),
    ]
for name, _t, _u in CHART:
    CHECKS.append((name, "card", 3.0, "chart bar"))
for fam in ("jade", "green", "red", "rose", "violet", "blue"):
    CHECKS.append(("slate-0", f"{fam}-600", 4.5, f"white on {fam}-600"))
for fam in ("jade", "turmeric", "green", "red", "amber", "rose", "violet", "blue", "orange"):
    CHECKS += [
        (f"{fam}-800", f"{fam}-50", 4.5, f"{fam} text on its soft ground"),
        (f"{fam}-800", f"{fam}-100", 4.5, f"{fam} text on its hover ground"),
        (f"{fam}-700", "slate-0", 4.5, f"{fam}-700 text on white"),
    ]
    if fam not in ("turmeric", "amber"):
        CHECKS.append((f"{fam}-500", "slate-0", 3.0, f"{fam}-500 mark on white"))

# ------------------------------------------------------------- the rest

TYPE = {
    "fonts": [],
    "families": {
        "sans": '"Geist", "Segoe UI", system-ui, sans-serif',
        "mono": '"Geist Mono", ui-monospace, "Cascadia Mono", Consolas, monospace',
        "serif": '"Noto Serif", Georgia, serif',
    },
    "groups": [
        {
            "name": "Tiêu đề",
            "family": "sans",
            "note": "Tiêu đề có dấu hai tầng cần line-height ≥ 1,2.",
            "styles": [
                {"name": "display", "fontSize": "40px", "lineHeight": "48px", "fontWeight": 700, "letterSpacing": "-0.02em",
                 "sample": "Học lập trình theo lộ trình của bạn", "usage": "Mỗi trang tối đa một: hero trang chủ."},
                {"name": "h1", "fontSize": "30px", "lineHeight": "38px", "fontWeight": 700, "letterSpacing": "-0.015em",
                 "sample": "Luồng điều khiển trong Python", "usage": "Tiêu đề trang."},
                {"name": "h2", "fontSize": "24px", "lineHeight": "32px", "fontWeight": 600, "letterSpacing": "-0.01em",
                 "sample": "Người học nói gì", "usage": "Tiêu đề mục trong trang."},
                {"name": "h3", "fontSize": "20px", "lineHeight": "28px", "fontWeight": 600,
                 "sample": "Tiếng Việt có dấu hai tầng", "usage": "Tiêu đề nhóm, tiêu đề dialog."},
                {"name": "title", "fontSize": "16px", "lineHeight": "24px", "fontWeight": 600,
                 "sample": "Bài 4 · Vòng lặp for", "usage": "Tiêu đề card, mục danh sách, chữ nhấn trong bảng."},
            ],
        },
        {
            "name": "Nội dung",
            "family": "sans",
            "note": "Chữ nội dung có line-height ≥ 1,4. Cỡ chữ mặc định 16px.",
            "styles": [
                {"name": "body-lg", "fontSize": "18px", "lineHeight": "30px", "fontWeight": 400,
                 "sample": "Vòng lặp for đi qua từng phần tử của một dãy, theo đúng thứ tự.",
                 "usage": "Bài đọc và mô tả khóa học; tối đa ~70 ký tự mỗi dòng."},
                {"name": "body", "fontSize": "16px", "lineHeight": "24px", "fontWeight": 400,
                 "sample": "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.", "usage": "Chữ mặc định."},
                {"name": "body-sm", "fontSize": "14px", "lineHeight": "20px", "fontWeight": 400,
                 "sample": "Đạt từ 80% · 10 câu · 15 phút", "usage": "Giao diện dày: bảng, gợi ý dưới ô nhập, dòng thông tin."},
                {"name": "caption", "fontSize": "12px", "lineHeight": "16px", "fontWeight": 500, "letterSpacing": "0.01em",
                 "sample": "Cập nhật 20/10/2026", "usage": "Thời gian, trục biểu đồ, chữ trong badge. Không bao giờ là một câu."},
                {"name": "eyebrow", "fontSize": "12px", "lineHeight": "16px", "fontWeight": 600, "letterSpacing": "0.06em",
                 "sample": "KHÓA HỌC MỚI", "usage": "Nhãn viết hoa phía trên tiêu đề mục. Ngắn, không thành câu."},
            ],
        },
        {
            "name": "Mã và số",
            "family": "mono",
            "styles": [
                {"name": "code", "fontSize": "14px", "lineHeight": "22px", "fontWeight": 400,
                 "sample": "for i in range(n): print(i)", "usage": "Khối code, stdin/stdout, code trong dòng."},
                {"name": "code-sm", "fontSize": "12px", "lineHeight": "18px", "fontWeight": 400,
                 "sample": "test 3/10 · 0,42 s", "usage": "Dòng từng test, giới hạn, mã verdict."},
                {"name": "numeral", "fontSize": "28px", "lineHeight": "32px", "fontWeight": 600, "family": "sans",
                 "sample": "1.250 XP", "usage": "Ô thống kê, điểm quiz, XP. Chỉ số và đơn vị (tabular-nums)."},
            ],
        },
        {
            "name": "Chứng chỉ",
            "family": "serif",
            "styles": [
                {"name": "cert-title", "fontSize": "36px", "lineHeight": "46px", "fontWeight": 600,
                 "sample": "Nguyễn Thị Hường", "usage": "Tên người nhận và tên khóa trên /cert, không dùng ở đâu khác."},
            ],
        },
    ],
}

SPACING = [
    ("space-1", "4px", "Icon tới nhãn; padding badge."),
    ("space-2", "8px", "Khoảng giữa các control liên quan; padding chip."),
    ("space-3", "12px", "Padding card gọn (`Card size=sm`); khoảng giữa các trường biểu mẫu."),
    ("space-4", "16px", "Padding card; lề trang trên điện thoại."),
    ("space-5", "20px", "Khoảng giữa các card trong lưới."),
    ("space-6", "24px", "Khoảng giữa các nhóm trong một mục; lề trang từ md."),
    ("space-8", "32px", "Khoảng giữa các mục trên điện thoại."),
    ("space-10", "40px", "Nhịp chiều cao header; padding hero trên điện thoại."),
    ("space-12", "48px", "Khoảng giữa các mục trang từ md."),
    ("space-16", "64px", "Padding hero từ md."),
    ("space-24", "96px", "Đầu và cuối các trang giới thiệu."),
]

RADIUS = [
    ("radius-xs", "4px", "Code trong dòng, phím tắt, chấm từng test."),
    ("radius-sm", "6px", "Checkbox, chip nhỏ trong bảng dày."),
    ("radius-md", "10px", "Nút, ô nhập, select, tab, alert. Là gốc `--radius`."),
    ("radius-lg", "14px", "Card, panel, khung trình soạn code."),
    ("radius-xl", "20px", "Dialog, bong bóng lời của nhân vật, khối hero."),
    ("radius-full", "9999px", "Badge, chip verdict, avatar, thanh tiến độ."),
]


def ink(alpha: float) -> str:
    h = HEX["slate-950"]
    r, g, b = (int(h[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


SHADOW = [
    ("shadow-xs", f"0 1px 2px {ink(0.06)}", "Nút outline và ô nhập lúc yên."),
    ("shadow-sm", f"0 1px 3px {ink(0.08)}, 0 1px 2px {ink(0.04)}", "Tab đang chọn; card bấm được lúc yên."),
    ("shadow-md", f"0 6px 16px -4px {ink(0.12)}, 0 2px 4px -2px {ink(0.06)}", "Card khi hover, dropdown, popover, toast."),
    ("shadow-lg", f"0 20px 40px -12px {ink(0.20)}, 0 6px 12px -6px {ink(0.08)}", "Dialog."),
]

DURATION = [
    ("duration-instant", "90ms", "Phản hồi khi nhấn (nút lún 1px), dấu tick checkbox."),
    ("duration-fast", "150ms", "Đổi màu khi hover/focus, tooltip."),
    ("duration-base", "220ms", "Tab, accordion, menu mở ra, chip xuất hiện."),
    ("duration-slow", "320ms", "Dialog và toast đi vào; một mục trang hiện ra."),
    ("duration-progress", "600ms", "Thanh tiến độ chạy, XP và điểm đếm lên."),
    ("duration-mascot", "2400ms", "Giới hạn trên của một lần phản ứng của nhân vật trước khi về tư thế nghỉ."),
]

EASING = [
    ("ease-standard", "cubic-bezier(0.2, 0, 0, 1)", "Thứ di chuyển trong màn: tab, công tắc, tiến độ."),
    ("ease-enter", "cubic-bezier(0.05, 0.7, 0.1, 1)", "Thứ đi vào: dialog, toast, menu, dòng mới."),
    ("ease-exit", "cubic-bezier(0.3, 0, 0.8, 0.15)", "Thứ đi ra. Thời lượng ~70% của lúc vào."),
    ("ease-overshoot", "cubic-bezier(0.34, 1.56, 0.64, 1)", "Chỉ cho ăn mừng: AC, quiz 100%, lên hạng, nhân vật nhảy."),
]


def build_tokens() -> dict:
    color_tokens = []
    for name, target, usage in ALL_ALIASES:
        value = target if target.startswith("#") else "{" + target + "}"
        color_tokens.append({"name": name, "value": value, "usage": usage})
    for fam, spec in FAMILIES.items():
        for step in spec["steps"]:
            if fam == "slate":
                usage = SLATE_USAGE[step]
            elif step in ("500", "600"):
                usage = f"{spec['note']} {RAMP_USAGE[step]}"
            else:
                usage = RAMP_USAGE[step]
            if fam in ("turmeric", "amber") and step in ("400", "500"):
                usage += " Không làm chữ hay icon trên nền trắng."
            color_tokens.append({"name": f"{fam}-{step}", "value": HEX[f"{fam}-{step}"], "usage": usage})
    rows = lambda table: [dict(zip(("name", "value", "usage"), r)) for r in table]  # noqa: E731
    return {
        "name": "DevPath",
        "version": 1,
        "color": {
            "note": "Lớp ngữ nghĩa trước (component chỉ đọc lớp này), dải màu gốc sau. Theme tối để sau.",
            "themes": [{"id": "light", "name": "Sáng"}],
            "tokens": color_tokens,
        },
        "type": TYPE,
        "spacing": {"note": "Lưới 4px, trùng thang của Tailwind.", "tokens": rows(SPACING)},
        "radius": {"note": "Bo vừa phải: thân thiện nhưng không thành đồ chơi.", "tokens": rows(RADIUS)},
        "shadow": {"note": "Chỉ lớp nổi mới có bóng. Card lúc yên dùng viền `border`.", "tokens": rows(SHADOW)},
        "duration": {
            "note": "Khi prefers-reduced-motion: mọi chuyển động bằng 0, chỉ còn đổi màu (≤ duration-fast); nhân vật đứng tư thế tĩnh.",
            "tokens": rows(DURATION),
        },
        "easing": {"note": "Đường cong cho CSS transition và Motion. ease-overshoot chỉ dành cho ăn mừng.", "tokens": rows(EASING)},
    }


def main() -> int:
    OUT_TOKENS.parent.mkdir(parents=True, exist_ok=True)
    OUT_TOKENS.write_text(json.dumps(build_tokens(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["DevPath design system — contrast of every promised pair (WCAG 2.x)", ""]
    failures = 0
    for fg, bg, floor, why in CHECKS:
        ratio = contrast(RESOLVE[fg], RESOLVE[bg])
        ok = ratio + 1e-9 >= floor
        failures += not ok
        lines.append(
            f"{'ok  ' if ok else 'FAIL'} {ratio:5.2f}:1 (≥ {floor}) {fg} {RESOLVE[fg]} on {bg} {RESOLVE[bg]} — {why}"
        )
    summary = f"{len(CHECKS)} pairs, {failures} below floor."
    lines += ["", summary, "", "Palette (OKLCH source → hex):"]
    for fam, spec in FAMILIES.items():
        for step, (L, C) in spec["steps"].items():
            lines.append(f"  {fam}-{step:<4} oklch({L} {C} {spec['hue']}) → {HEX[f'{fam}-{step}']}")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(line for line in lines if line.startswith("FAIL")) or "all pairs pass")
    print(summary)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
