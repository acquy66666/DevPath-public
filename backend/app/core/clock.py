"""What day it is, for the features that count in days.

A day on this platform is a day in Vietnam: a student studying at 00:30 in Hà
Nội is studying on the new day, although UTC is still on the old one. Vietnam
has had no daylight saving since 1975, so a fixed offset is the same as the
named zone and needs no tz database on the host.

SQL that groups by day spells the zone by name instead (`Asia/Ho_Chi_Minh`,
see `services/instructor_stats.py`): inside `AT TIME ZONE`, Postgres reads the
string `'+07:00'` as POSIX, west of Greenwich.
"""

from datetime import date, datetime, time, timedelta, timezone

VIETNAM = timezone(timedelta(hours=7))


def today_in_vietnam(now: datetime | None = None) -> date:
    """The calendar day it is in Vietnam at `now` (default: this instant)."""
    return (now or datetime.now(VIETNAM)).astimezone(VIETNAM).date()


def start_of_day(day: date) -> datetime:
    """Midnight at the beginning of `day` in Vietnam, as an aware datetime."""
    return datetime.combine(day, time.min, tzinfo=VIETNAM)
