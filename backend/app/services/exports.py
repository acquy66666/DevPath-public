"""Workbooks for every statistics page: what each sheet holds, in what order.

Each builder takes the *same* objects the page's endpoint returns -- the
service results -- so an export never computes a figure of its own. The
instructor's builders are given instructor service results, which carry no
money; the admin's are given finance results. `services/excel.py` does the
writing.

Layout, every workbook (docs/thiet-ke-cap-bac-va-tai-chinh.md, section 7): the
first sheet is the summary -- report name, period, time of export, who it is
for -- then detail sheets, then for money workbooks a "Định nghĩa" sheet that
says what each figure means, so a file forwarded on its own still reads right.
"""

from collections.abc import Sequence
from datetime import date, datetime

from app.models import User
from app.services import finance, payouts, platform_stats, profit, rankings
from app.services import instructor_stats as stats
from app.services import instructor_tiers as tiers
from app.services.excel import (
    Cell,
    Column,
    Sheet,
    build,
    day_range_line,
    exported_at_line,
    money_cell,
    rate_cell,
)

LESSON_TYPES = {"video": "Video", "article": "Bài đọc", "quiz": "Quiz", "code_exercise": "Bài code"}
COURSE_STATUSES = {
    "draft": "Nháp",
    "pending_review": "Chờ duyệt",
    "published": "Đang bán",
    "rejected": "Bị từ chối",
}
GRANULARITY_LABELS = finance.GRANULARITY_LABELS


def _text(label: str) -> Column:
    return Column(label)


# --- Instructor ----------------------------------------------------------------


def instructor_dashboard(
    instructor: User,
    overview: stats.Overview,
    insights: stats.Insights,
    courses: Sequence[stats.CourseStats],
) -> bytes:
    caption = [
        "Thống kê giảng dạy — DevPath",
        f"Giảng viên: {instructor.full_name}",
        day_range_line(overview.start, overview.end),
        exported_at_line(),
    ]
    cur, prev = overview.current, overview.previous
    summary = Sheet(
        "Tổng quan",
        [Column("Chỉ số", width=40), Column("Kỳ này", "number"), Column("Kỳ trước", "number")],
        [
            ("Lượt ghi danh mới", cur.enrollments, prev.enrollments),
            ("Học viên mới", cur.new_students, prev.new_students),
            ("Học viên hoạt động", cur.active_learners, prev.active_learners),
            ("Bài học hoàn thành", cur.lessons_completed, prev.lessons_completed),
            ("Lượt hoàn thành khóa", cur.completions, prev.completions),
            ("Đánh giá mới", cur.reviews, prev.reviews),
            ("Điểm đánh giá mới (trung bình)", cur.review_avg, prev.review_avg),
            ("Câu hỏi mới", cur.questions, prev.questions),
            ("Lượt thêm vào yêu thích", cur.wishlist_adds, prev.wishlist_adds),
        ],
        caption=caption,
    )
    all_time = Sheet(
        "Từ trước tới nay",
        [Column("Chỉ số", width=40), Column("Giá trị", "number")],
        [
            ("Tổng học viên", overview.students_total),
            ("Tổng lượt ghi danh", overview.enrollments_total),
            ("Khóa đang bán", overview.courses_published),
            ("Tổng số khóa", overview.courses_total),
            ("Chứng chỉ đã cấp", overview.certificates_total),
            ("Điểm đánh giá trung bình", overview.rating_avg),
            ("Số đánh giá", overview.rating_count),
            ("Câu hỏi chưa trả lời", overview.open_questions),
            ("Số ngày trung vị để hoàn thành", overview.median_days_to_complete),
        ],
        caption=["Từ trước tới nay", exported_at_line()],
    )
    rates = Sheet(
        "Tỉ lệ",
        [Column("Chỉ số", width=46), Column("Giá trị", "rate")],
        [
            ("Tỉ lệ bắt đầu học", overview.started_rate),
            ("Tỉ lệ hoàn thành", overview.completion_rate),
            ("Tiến độ trung bình", overview.avg_progress),
            ("Tỉ lệ bỏ dở (30 ngày không học)", insights.learning.idle_rate),
            ("Quiz: đạt ngay lần đầu (kỳ này)", insights.quiz.first_try_pass_rate),
            ("Quiz: hết giờ (kỳ này)", insights.quiz.expired_rate),
            ("Bài code: tỉ lệ giải được (kỳ này)", insights.code.solve_rate),
            ("Hỏi đáp: có giảng viên trả lời (kỳ này)", insights.qa.answered_rate),
            ("Hỏi đáp: trả lời trong 24 giờ (kỳ này)", insights.qa.answered_within_24h_rate),
            ("Hỏi đáp: đã giải quyết (kỳ này)", insights.qa.resolved_rate),
            ("Đánh giá có nhận xét", insights.reviews.commented_rate),
            ("Yêu thích → ghi danh", insights.interest.wishlist_conversion_rate),
        ],
        caption=["Tỉ lệ", day_range_line(insights.start, insights.end)],
    )
    series = Sheet(
        "Theo thời gian",
        [
            Column("Mốc", "date"),
            Column("Ghi danh", "int"),
            Column("Học viên mới", "int"),
            Column("Học viên hoạt động", "int"),
            Column("Bài hoàn thành", "int"),
            Column("Hoàn thành khóa", "int"),
            Column("Đánh giá", "int"),
            Column("Câu hỏi", "int"),
            Column("Yêu thích", "int"),
        ],
        [
            (
                p.bucket,
                p.enrollments,
                p.new_students,
                p.active_learners,
                p.lessons_completed,
                p.completions,
                p.reviews,
                p.questions,
                p.wishlist_adds,
            )
            for p in overview.series
        ],
        caption=["Theo " + ("ngày" if overview.granularity == "day" else "tháng")],
    )
    outcomes = Sheet(
        "Kết quả học tập",
        [Column("Chỉ số", width=46), Column("Giá trị", "number")],
        [
            ("Quiz: lượt nộp", insights.quiz.attempts),
            ("Quiz: số người làm", insights.quiz.learners),
            ("Quiz: điểm trung vị", insights.quiz.median_score),
            ("Bài code: lượt nộp chấm thật", insights.code.submissions),
            ("Bài code: số người nộp", insights.code.learners),
            ("Bài code: số lần nộp trung vị tới AC", insights.code.median_attempts_to_ac),
            *((f"Verdict {verdict}", count) for verdict, count in insights.code.verdicts.items()),
            ("Hỏi đáp: câu hỏi mới", insights.qa.questions),
            ("Hỏi đáp: giờ phản hồi trung vị", insights.qa.median_first_response_hours),
            ("Hỏi đáp: tồn đọng", insights.qa.backlog),
            *((f"Đánh giá {stars} sao", n) for stars, n in insights.reviews.distribution.items()),
            ("Đang nằm trong giỏ hàng", insights.interest.in_carts_now),
            ("Đang trong danh sách yêu thích", insights.interest.wishlisted_now),
            ("Số ngày trung vị tới bài đầu tiên", insights.learning.median_days_to_first_lesson),
        ],
        caption=[
            "Kết quả học tập, đánh giá, hỏi đáp",
            day_range_line(insights.start, insights.end),
        ],
    )
    course_sheet = Sheet(
        "Theo khóa học",
        [
            Column("Khóa học", width=40),
            Column("Trạng thái", width=14),
            Column("Học viên", "int"),
            Column("Ghi danh mới (kỳ)", "int"),
            Column("Đã hoàn thành", "int"),
            Column("Số bài", "int"),
            Column("Bắt đầu học", "rate"),
            Column("Hoàn thành", "rate"),
            Column("Tiến độ TB", "rate"),
            Column("Điểm đánh giá", "decimal"),
            Column("Số đánh giá", "int"),
            Column("Câu hỏi chờ", "int"),
            Column("Yêu thích", "int"),
            Column("Quiz đạt lần đầu", "rate"),
            Column("Code giải được", "rate"),
        ],
        [
            (
                row.course.title,
                "Đã gỡ" if row.course.deleted_at else COURSE_STATUSES.get(row.course.status),
                row.students,
                row.new_enrollments,
                row.completed,
                row.lessons_count,
                row.started_rate,
                row.completion_rate,
                row.avg_progress,
                row.rating_avg,
                row.rating_count,
                row.open_questions,
                row.wishlisted,
                row.quiz_first_try_pass_rate,
                row.code_solve_rate,
            )
            for row in courses
        ],
        caption=["Theo khóa học", day_range_line(overview.start, overview.end)],
    )
    return build([summary, all_time, rates, series, outcomes, course_sheet])


def course_funnel(funnel: stats.CourseFunnel) -> bytes:
    sheet = Sheet(
        "Theo bài học",
        [
            Column("Chương", width=28),
            Column("Bài học", width=36),
            Column("Loại", width=10),
            Column("Đã mở", "int"),
            Column("Đã hoàn thành", "int"),
            Column("Hoàn thành / ghi danh", "rate"),
            Column("Video: đã xem TB", "rate"),
            Column("Quiz đạt lần đầu", "rate"),
            Column("Code giải được", "rate"),
            Column("Câu hỏi", "int"),
            Column("Ghi chú", "int"),
        ],
        [
            (
                lesson.section_title,
                lesson.title,
                LESSON_TYPES.get(lesson.type, lesson.type),
                lesson.started,
                lesson.completed,
                lesson.completion_rate,
                lesson.avg_watched,
                lesson.quiz_first_try_pass_rate,
                lesson.code_solve_rate,
                lesson.questions,
                lesson.notes,
            )
            for lesson in funnel.lessons
        ],
        caption=[
            f"Học viên dừng ở đâu — {funnel.course.title}",
            f"{funnel.enrollments} lượt ghi danh",
            exported_at_line(),
        ],
    )
    return build([sheet])


# --- Admin: overview -----------------------------------------------------------


def platform_overview(
    overview: platform_stats.Overview, hot: Sequence[platform_stats.HotCourse]
) -> bytes:
    cur, prev = overview.current, overview.previous
    summary = Sheet(
        "Tổng quan",
        [Column("Chỉ số", width=40), Column("Kỳ này", "number"), Column("Kỳ trước", "number")],
        [
            (
                "Doanh thu (tiền học viên trả)",
                money_cell(cur.revenue),
                money_cell(prev.revenue),
            ),
            ("Đơn hàng", cur.orders, prev.orders),
            ("Lượt ghi danh", cur.enrollments, prev.enrollments),
            ("Người dùng mới", cur.new_users, prev.new_users),
            ("Người dùng hoạt động", cur.active_users, prev.active_users),
            ("Hoạt động trung bình mỗi ngày", cur.avg_daily_active, prev.avg_daily_active),
        ],
        caption=[
            "Tổng quan toàn sàn — DevPath",
            day_range_line(overview.start, overview.end),
            exported_at_line(),
        ],
    )
    series = Sheet(
        "Theo thời gian",
        [
            Column("Mốc", "date"),
            Column("Doanh thu", "money"),
            Column("Đơn", "int"),
            Column("Ghi danh", "int"),
            Column("Người dùng mới", "int"),
            Column("Hoạt động", "int"),
        ],
        [
            (p.bucket, p.revenue, p.orders, p.enrollments, p.new_users, p.active_users)
            for p in overview.series
        ],
    )
    hot_sheet = Sheet(
        "Khóa học hot",
        [
            Column("Khóa học", width=40),
            Column("Giảng viên", width=24),
            Column("Ghi danh mới", "int"),
            Column("Lượt bán", "int"),
            Column("Doanh thu", "money"),
        ],
        [
            (h.course.title, h.instructor.full_name, h.new_enrollments, h.sales, h.revenue)
            for h in hot
        ],
    )
    return build([summary, series, hot_sheet])


# --- Admin: revenue ------------------------------------------------------------

MONEY_DEFINITIONS = [
    ("Giá niêm yết (GMV)", "Tổng giá bán của các dòng trong đơn đã thanh toán."),
    ("Giảm giá", "Phần mã giảm giá chia vào từng dòng lúc tạo đơn."),
    ("Học viên trả", "Giá niêm yết − giảm giá; tổng các dòng của một đơn bằng tổng đơn."),
    (
        "Hoa hồng giảng viên",
        "Làm tròn xuống tới đồng của (học viên trả × tỉ lệ chia). Tỉ lệ chia được chốt "
        "theo cấp của giảng viên lúc đơn được thanh toán.",
    ),
    ("Phần sàn giữ", "Học viên trả − hoa hồng giảng viên (chưa trừ phí cổng thanh toán)."),
    ("Ngày", "Theo thời điểm thanh toán, giờ Việt Nam."),
]


def _definitions(extra: Sequence[tuple[str, str]] = ()) -> Sheet:
    return Sheet(
        "Định nghĩa",
        [Column("Số liệu", width=30), Column("Nghĩa", width=100)],
        [*MONEY_DEFINITIONS, *extra],
    )


MONEY_COLUMNS = [
    Column("Đơn", "int"),
    Column("Dòng bán", "int"),
    Column("Người mua", "int"),
    Column("Giá niêm yết", "money"),
    Column("Giảm giá", "money"),
    Column("Học viên trả", "money"),
    Column("Hoa hồng GV", "money"),
    Column("Phần sàn giữ", "money"),
]


def _money_values(item: finance.Money) -> tuple:
    return (
        item.orders,
        item.lines,
        item.buyers,
        item.list_amount,
        item.discount,
        item.paid,
        item.instructor_share,
        item.platform_share,
    )


def _bucket_label(moment: datetime, granularity: str) -> str:
    if granularity == "hour":
        return f"{moment:%d/%m/%Y %H}:00"
    if granularity == "day":
        return f"{moment:%d/%m/%Y}"
    if granularity == "week":
        return f"Tuần {moment.isocalendar().week} ({moment:%d/%m/%Y})"
    if granularity == "month":
        return f"{moment:%m/%Y}"
    if granularity == "quarter":
        return f"Quý {(moment.month - 1) // 3 + 1}/{moment:%Y}"
    return f"{moment:%Y}"


def revenue(
    report: finance.RevenueReport,
    instructors: Sequence[finance.InstructorMoney],
    courses: Sequence[finance.CourseMoney],
    lines: Sequence[finance.SoldLine],
) -> bytes:
    span = report.range
    scope = (
        f"Giảng viên: {report.instructor.full_name} ({report.instructor.email})"
        if report.instructor
        else "Toàn sàn"
    )
    summary = Sheet(
        "Tóm tắt",
        [Column("Chỉ số", width=30), Column("Kỳ này", "money"), Column("Kỳ trước", "money")],
        [
            ("Số đơn", Cell(report.totals.orders, "int"), Cell(report.previous.orders, "int")),
            ("Dòng bán", Cell(report.totals.lines, "int"), Cell(report.previous.lines, "int")),
            ("Người mua", Cell(report.totals.buyers, "int"), Cell(report.previous.buyers, "int")),
            ("Giá niêm yết", report.totals.list_amount, report.previous.list_amount),
            ("Giảm giá", report.totals.discount, report.previous.discount),
            ("Học viên trả", report.totals.paid, report.previous.paid),
            (
                "Hoa hồng giảng viên",
                report.totals.instructor_share,
                report.previous.instructor_share,
            ),
            ("Phần sàn giữ", report.totals.platform_share, report.previous.platform_share),
        ],
        caption=[
            "Doanh thu — DevPath",
            scope,
            day_range_line(span.start, span.end),
            f"Gom theo {GRANULARITY_LABELS[span.granularity]}; kỳ trước là "
            f"{span.days} ngày ngay trước đó",
            exported_at_line(),
        ],
    )
    series = Sheet(
        "Theo mốc",
        [Column("Mốc", width=22), *MONEY_COLUMNS],
        [(_bucket_label(p.bucket, span.granularity), *_money_values(p)) for p in report.series],
        totals=("Tổng", *_money_values(report.totals)),
    )
    sheets = [summary, series]
    if instructors:
        sheets.append(
            Sheet(
                "Theo giảng viên",
                [
                    Column("Giảng viên", width=26),
                    Column("Email", width=30),
                    Column("Cấp", width=14),
                    Column("Khóa đã bán", "int"),
                    *MONEY_COLUMNS,
                    Column("Tỉ trọng", "rate"),
                ],
                [
                    (
                        i.instructor.full_name if i.instructor else "",
                        i.instructor.email if i.instructor else "",
                        i.tier.name if i.tier else "",
                        i.courses_sold,
                        *_money_values(i),
                        i.share_of_paid,
                    )
                    for i in instructors
                ],
            )
        )
    sheets.append(
        Sheet(
            "Theo khóa học",
            [Column("Khóa học", width=40), Column("Giảng viên", width=26), *MONEY_COLUMNS],
            [
                (
                    c.course.title if c.course else "",
                    c.instructor.full_name if c.instructor else "",
                    *_money_values(c),
                )
                for c in courses
            ],
        )
    )
    sheets.append(
        Sheet(
            "Dòng bán",
            [
                Column("Mã đơn", width=18),
                Column("Thanh toán lúc", "datetime"),
                Column("Khóa học", width=36),
                Column("Giảng viên", width=24),
                Column("Mã giảm giá", width=14),
                Column("Cổng", width=8),
                Column("Giá niêm yết", "money"),
                Column("Giảm giá", "money"),
                Column("Học viên trả", "money"),
                Column("Tỉ lệ chia", "rate"),
                Column("Hoa hồng GV", "money"),
                Column("Phần sàn giữ", "money"),
            ],
            [
                (
                    line.order_code,
                    line.paid_at,
                    line.course_title,
                    line.instructor_name,
                    line.coupon_code,
                    line.payment_provider,
                    line.unit_price,
                    line.discount,
                    line.paid,
                    line.share_rate,
                    line.instructor_share,
                    line.platform_share,
                )
                for line in lines
            ],
        )
    )
    sheets.append(_definitions())
    return build(sheets)


# --- Admin: rankings -----------------------------------------------------------

RANK_UNITS = {
    "money": "money",
    "count": "int",
    "rating": "decimal",
    "rate": "rate",
    "hours": "decimal",
}


def leaderboards(boards: rankings.Leaderboards) -> bytes:
    span = boards.range
    c = boards.concentration
    summary = Sheet(
        "Tóm tắt",
        [Column("Bảng xếp hạng", width=44), Column("Số mục", "int"), Column("Ghi chú", width=60)],
        [(r.title, len(r.entries), r.note) for r in boards.rankings]
        + [
            ("Tỉ trọng doanh thu của giảng viên số 1", rate_cell(c.top1), None),
            ("Tỉ trọng doanh thu của 5 giảng viên đầu", rate_cell(c.top5), None),
            ("Tỉ trọng doanh thu của 10 giảng viên đầu", rate_cell(c.top10), None),
        ],
        caption=[
            "Bảng xếp hạng — DevPath",
            day_range_line(span.start, span.end),
            "Cột kỳ trước: khoảng cùng độ dài ngay trước kỳ này. "
            "Đồng hạng kiểu thi đấu (1, 2, 2, 4).",
            exported_at_line(),
        ],
    )
    sheets = [summary]
    for ranking in boards.rankings:
        unit = RANK_UNITS[ranking.unit]
        sheets.append(
            Sheet(
                ranking.title,
                [
                    Column("Hạng", "int", width=7),
                    Column("Tên", width=36),
                    Column("Chi tiết", width=30),
                    Column("Giá trị", unit),  # type: ignore[arg-type]
                    Column("Kỳ trước", unit),  # type: ignore[arg-type]
                ],
                [(e.rank, e.label, e.detail, e.value, e.previous) for e in ranking.entries],
                caption=[ranking.title, *([ranking.note] if ranking.note else [])],
            )
        )
    return build(sheets)


# --- Admin: tiers --------------------------------------------------------------

FLAG_LABELS = {
    "eligible": "Đủ điều kiện lên cấp",
    "below_maintenance": "Dưới ngưỡng duy trì",
    "recently_changed": "Vừa đổi cấp (< 6 tháng)",
    "top_tier_skips_a_step": "Đề xuất vượt cấp lên cao nhất",
}


def tier_review(evaluations: Sequence[tiers.Evaluation], ladder: Sequence) -> bytes:
    rows = []
    for e in evaluations:
        m = e.metrics
        rows.append(
            (
                e.instructor.full_name,
                e.instructor.email,
                e.current.name,
                e.current.share_rate,
                e.suggested.name,
                ", ".join(FLAG_LABELS[f] for f in e.flags),
                m.paid_students,
                m.revenue_12m,
                m.rating,
                m.reviews,
                m.completion_rate,
                m.qa_answer_rate,
                m.qa_questions,
                m.published_courses,
                m.months_active,
                m.removed_courses_90d,
            )
        )
    review = Sheet(
        "Xét cấp",
        [
            Column("Giảng viên", width=26),
            Column("Email", width=30),
            Column("Cấp hiện tại", width=14),
            Column("Tỉ lệ chia", "rate"),
            Column("Cấp đề xuất", width=14),
            Column("Ghi chú", width=40),
            Column("HV trả phí", "int"),
            Column("Doanh thu 12 tháng", "money"),
            Column("Đánh giá (Bayes)", "decimal"),
            Column("Số đánh giá", "int"),
            Column("Hoàn thành", "rate"),
            Column("Trả lời Q&A 48h", "rate"),
            Column("Câu hỏi 90 ngày", "int"),
            Column("Khóa đang bán", "int"),
            Column("Tháng hoạt động", "int"),
            Column("Khóa bị gỡ 90 ngày", "int"),
        ],
        rows,
        caption=["Xét cấp giảng viên — DevPath", exported_at_line()],
    )
    ladder_sheet = Sheet(
        "Bậc thang",
        [
            Column("Hạng", "int", width=7),
            Column("Cấp", width=16),
            Column("Tỉ lệ chia", "rate"),
            Column("HV trả phí", "int"),
            Column("Doanh thu 12 tháng", "money"),
            Column("Đánh giá tối thiểu", "decimal"),
            Column("Số đánh giá", "int"),
            Column("Hoàn thành", "rate"),
            Column("Trả lời Q&A 48h", "rate"),
            Column("Khóa đang bán", "int"),
            Column("Tháng hoạt động", "int"),
        ],
        [
            (
                t.rank,
                t.name,
                t.share_rate,
                t.min_paid_students,
                t.min_revenue_12m,
                t.min_rating,
                t.min_reviews,
                t.min_completion_rate,
                t.min_qa_answer_rate,
                t.min_published_courses,
                t.min_months_active,
            )
            for t in ladder
        ],
    )
    return build([review, ladder_sheet])


# --- Admin: payouts ------------------------------------------------------------


def payout_overview(balances: Sequence[payouts.Balance], statements: Sequence) -> bytes:
    balance_sheet = Sheet(
        "Số dư giảng viên",
        [
            Column("Giảng viên", width=26),
            Column("Email", width=30),
            Column("Hoa hồng từ trước tới nay", "money"),
            Column("Chưa lập bảng kê", "money"),
            Column("Dòng chưa lập", "int"),
            Column("Dòng cũ nhất", "datetime"),
            Column("Đang ở bảng kê nháp", "money"),
            Column("Đã chốt, chưa chi", "money"),
            Column("Đã chi trả", "money"),
            Column("Thuế đã khấu trừ", "money"),
        ],
        [
            (
                b.instructor.full_name,
                b.instructor.email,
                b.earned_all_time,
                b.unbilled,
                b.unbilled_lines,
                b.oldest_unbilled,
                b.in_draft,
                b.confirmed_unpaid,
                b.paid_out,
                b.tax_withheld,
            )
            for b in balances
        ],
        caption=["Hoa hồng & thanh toán giảng viên — DevPath", exported_at_line()],
    )
    statement_sheet = Sheet(
        "Bảng kê",
        [
            Column("Mã", width=14),
            Column("Giảng viên", width=26),
            Column("Email", width=30),
            Column("Kỳ", width=10),
            Column("Trạng thái", width=12),
            Column("Số dòng", "int"),
            Column("Học viên trả", "money"),
            Column("Hoa hồng GV", "money"),
            Column("Thuế TNCN (ước tính)", "money"),
            Column("Thực chi", "money"),
            Column("Mã chuyển khoản", width=20),
            Column("Chi lúc", "datetime"),
        ],
        [
            (
                s.code,
                s.instructor_name,
                s.instructor_email,
                f"{s.period_start:%m/%Y}",
                payouts.STATUS_LABELS[s.status],
                s.line_count,
                s.gross_amount,
                s.instructor_amount,
                s.tax_withheld,
                s.payable_amount,
                s.payment_reference,
                s.paid_at,
            )
            for s in statements
        ],
    )
    return build([balance_sheet, statement_sheet])


def statement(view: payouts.StatementView) -> bytes:
    s = view.statement
    header = Sheet(
        "Bảng kê",
        [Column("Mục", width=36), Column("Giá trị", width=40)],
        [
            ("Mã bảng kê", s.code),
            ("Giảng viên", s.instructor_name),
            ("Email", s.instructor_email),
            ("Kỳ", f"{s.period_start:%d/%m/%Y} – {s.period_end:%d/%m/%Y}"),
            ("Trạng thái", payouts.STATUS_LABELS[s.status]),
            ("Số dòng bán", Cell(s.line_count, "int")),
            ("Trong đó dòng tồn từ kỳ trước", Cell(view.carried_lines, "int")),
            ("Học viên đã trả", money_cell(s.gross_amount)),
            ("Hoa hồng giảng viên", money_cell(s.instructor_amount)),
            ("Phần sàn giữ", money_cell(s.platform_amount)),
            ("Thuế TNCN khấu trừ (ước tính)", money_cell(s.tax_withheld)),
            ("Số tiền thực chi", money_cell(s.payable_amount)),
            ("Chốt lúc", Cell(s.confirmed_at, "datetime")),
            ("Chi trả lúc", Cell(s.paid_at, "datetime")),
            ("Mã chuyển khoản", s.payment_reference),
            ("Lý do hủy", s.void_reason),
            ("Ghi chú", s.note),
        ],
        caption=[
            f"Bảng kê thanh toán {s.code} — DevPath",
            "Thuế TNCN là ước tính (10% khi một lần chi từ 5.000.000 đ, NĐ 253/2026); "
            "cần kế toán xác nhận.",
            exported_at_line(),
        ],
    )
    lines = Sheet(
        "Dòng bán",
        [
            Column("Mã đơn", width=18),
            Column("Thanh toán lúc", "datetime"),
            Column("Khóa học", width=40),
            Column("Giá niêm yết", "money"),
            Column("Giảm giá", "money"),
            Column("Học viên trả", "money"),
            Column("Tỉ lệ chia", "rate"),
            Column("Hoa hồng GV", "money"),
        ],
        [
            (
                line.order_code,
                line.paid_at,
                line.course_title,
                line.unit_price,
                line.discount,
                line.net_amount,
                line.share_rate,
                line.instructor_amount,
            )
            for line in view.lines
        ],
        totals=(
            "Tổng",
            None,
            None,
            sum((line.unit_price for line in view.lines), finance.ZERO),
            sum((line.discount for line in view.lines), finance.ZERO),
            sum((line.net_amount for line in view.lines), finance.ZERO),
            None,
            sum((line.instructor_amount for line in view.lines), finance.ZERO),
        ),
    )
    return build([header, lines, _definitions()])


# --- Admin: profit -------------------------------------------------------------


def profit_report(report: profit.ProfitReport, expenses: Sequence[profit.ExpenseView]) -> bytes:
    columns = report.columns
    labels = [
        f"Quý {(c.start.month - 1) // 3 + 1}"
        if report.granularity == "quarter"
        else f"{c.start:%m/%Y}"
        for c in columns
    ]

    def line(label: str, pick) -> tuple:
        return (label, *(pick(c) for c in columns), pick(report.total))

    money_rows = [
        line("Giá niêm yết (GMV)", lambda c: c.list_amount),
        line("− Giảm giá", lambda c: c.discount),
        line("= Học viên trả", lambda c: c.collected),
        line("− Hoa hồng giảng viên", lambda c: c.instructor_share),
        line("= Doanh thu sàn", lambda c: c.platform_revenue),
        line("− Phí cổng thanh toán (ước tính)", lambda c: c.gateway_fee),
        *(
            line(f"− {profit.CATEGORY_LABELS[k]}", lambda c, k=k: c.expenses[k])
            for k in profit.OPERATING_CATEGORIES
        ),
        line("= Lợi nhuận trước thuế", lambda c: c.profit_before_tax),
        line("− Thuế", lambda c: c.tax),
        line("= Lợi nhuận giữ lại", lambda c: c.retained),
    ]
    pnl = Sheet(
        "Lãi lỗ",
        [
            Column("Khoản mục", width=40),
            *(Column(label, "money") for label in labels),
            Column("Cả năm", "money"),
        ],
        money_rows,
        caption=[
            f"Báo cáo lãi lỗ năm {report.year} — DevPath",
            "Ghi nhận theo ngày thanh toán của đơn, giờ Việt Nam.",
            exported_at_line(),
        ],
    )
    ratios = Sheet(
        "Tỉ suất",
        [
            Column("Tỉ suất", width=40),
            *(Column(label, "rate") for label in labels),
            Column("Cả năm", "rate"),
        ],
        [
            line("Take rate (doanh thu sàn / GMV)", lambda c: c.take_rate),
            line("Biên gộp (sau phí cổng / học viên trả)", lambda c: c.gross_margin),
            line("Biên lợi nhuận giữ lại", lambda c: c.net_margin),
        ],
    )
    expense_sheet = Sheet(
        "Chi phí",
        [
            Column("Ngày", "date"),
            Column("Nhóm", width=34),
            Column("Mô tả", width=44),
            Column("Số tiền", "money"),
            Column("Người nhập", width=24),
        ],
        [
            (
                e.expense.incurred_on,
                profit.CATEGORY_LABELS[e.expense.category],
                e.expense.description,
                e.expense.amount,
                e.created_by.full_name if e.created_by else None,
            )
            for e in expenses
        ],
    )
    assumptions = Sheet(
        "Giả định",
        [Column("Giả định", width=40), Column("Giá trị", width=100)],
        [
            ("Phí cổng thanh toán", report.fee_source),
            ("Đơn 0 đ", "Không qua cổng thanh toán nên không tính phí."),
            ("Hoa hồng giảng viên", MONEY_DEFINITIONS[3][1]),
            ("Thuế", "Do quản trị viên nhập theo chứng từ; không tự tính."),
        ],
    )
    return build([pnl, ratios, expense_sheet, assumptions])


def expenses_sheet(expenses: Sequence[profit.ExpenseView], total: object, scope: str) -> bytes:
    return build(
        [
            Sheet(
                "Chi phí",
                [
                    Column("Ngày", "date"),
                    Column("Nhóm", width=34),
                    Column("Mô tả", width=44),
                    Column("Số tiền", "money"),
                    Column("Người nhập", width=24),
                ],
                [
                    (
                        e.expense.incurred_on,
                        profit.CATEGORY_LABELS[e.expense.category],
                        e.expense.description,
                        e.expense.amount,
                        e.created_by.full_name if e.created_by else None,
                    )
                    for e in expenses
                ],
                caption=["Chi phí vận hành — DevPath", scope, exported_at_line()],
                totals=(None, None, "Tổng", total, None),
            )
        ]
    )


def file_day(day: date) -> str:
    return f"{day:%Y%m%d}"
