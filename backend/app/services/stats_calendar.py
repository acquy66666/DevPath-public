"""The calendar every dashboard counts on, and the small helpers they share.

**A day is a day in Vietnam.** Buckets are cut on the Vietnamese calendar
(UTC+7, the same clock the VNPay integration uses), so a sale or an enrolment
at 00:10 in Hà Nội is on today's bar even though it is 17:10 yesterday in UTC.
The windows are calendar-aligned too: "7 ngày" is today and the six days
before it, "12 tháng" is twelve whole months with this one filling up, and
every window is compared with the one of the same length just before it.

Moved here from `instructor_stats` when the instructor dashboard stopped
showing money and the admin finance pages started needing the same calendar:
the instructor's, the platform's and the finance numbers are cut by one clock.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, Date, cast, func, literal_column

from app.services.vnpay import VIETNAM

#: What a dashboard can be asked for: a length, and the bucket it is cut in.
PERIODS: dict[str, tuple[int, str]] = {
    "7d": (7, "day"),
    "30d": (30, "day"),
    "90d": (90, "day"),
    "12m": (12, "month"),
}
GRANULARITIES = ("day", "month")

#: The clock `VIETNAM` is, by name. Not '+07:00': Postgres reads an offset
#: string in AT TIME ZONE as a POSIX zone, where positive means *west* of
#: Greenwich, and every bucket would land fourteen hours off.
TIMEZONE = "Asia/Ho_Chi_Minh"

ZERO = Decimal("0.00")
RATE_PLACES = 4


def add_months(first_of_month: date, months: int) -> date:
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True, slots=True)
class Window:
    """A stretch of Vietnamese calendar: `start` inclusive, `stop` exclusive."""

    start: date
    stop: date
    granularity: str

    def bounds(self) -> tuple[datetime, datetime]:
        return (
            datetime.combine(self.start, time(), VIETNAM),
            datetime.combine(self.stop, time(), VIETNAM),
        )

    def buckets(self) -> list[date]:
        if self.granularity == "day":
            return [
                self.start + timedelta(days=offset)
                for offset in range((self.stop - self.start).days)
            ]
        months: list[date] = []
        month = self.start
        while month < self.stop:
            months.append(month)
            month = add_months(month, 1)
        return months


def windows(period: str, today: date) -> tuple[Window, Window]:
    """The window a period names, ending today, and the one just before it."""
    length, granularity = PERIODS[period]

    if granularity == "day":
        stop = today + timedelta(days=1)
        start = stop - timedelta(days=length)
        return (
            Window(start, stop, granularity),
            Window(start - timedelta(days=length), start, granularity),
        )

    # Whole months, this one included, so every bar is a full calendar month
    # and the last one fills up as the month goes on.
    stop = add_months(today.replace(day=1), 1)
    start = add_months(stop, -length)
    return (
        Window(start, stop, granularity),
        Window(add_months(start, -length), start, granularity),
    )


def vietnam_today(now: datetime | None) -> date:
    return (now or datetime.now(UTC)).astimezone(VIETNAM).date()


def local(column: ColumnElement[datetime]) -> ColumnElement[datetime]:
    """`column` as Vietnamese wall-clock time (a timestamp without zone)."""
    return func.timezone(literal_column(f"'{TIMEZONE}'"), column)


def bucket_start(column: ColumnElement[datetime], granularity: str) -> ColumnElement[date]:
    """The first day of the bucket `column` falls in, on the Vietnamese calendar.

    Both arguments are rendered as literals rather than bound: the expression
    appears in SELECT and again in GROUP BY, and Postgres only recognises the
    two as one expression when they are the same text -- two bind parameters
    are two expressions to it, whatever they hold.
    """
    if granularity not in GRANULARITIES:
        raise ValueError(granularity)
    return cast(func.date_trunc(literal_column(f"'{granularity}'"), local(column)), Date)


def rate(part: int | float, whole: int | float) -> float | None:
    return None if not whole else round(part / whole, RATE_PLACES)


def money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(ZERO)
