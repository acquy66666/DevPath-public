"""The instructor's dashboard on the wire.

Money is `Decimal` like everywhere else -- it reaches the browser as a string,
"280000.00", and is never a float on the way. The two rates are floats because
they are ratios, not money, and rounding one to four places loses nothing a
percentage on screen could show.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.instructor_stats import GRANULARITIES, PERIODS

StatsPeriod = Literal[tuple(PERIODS)]  # type: ignore[valid-type]
Granularity = Literal[GRANULARITIES]  # type: ignore[valid-type]


class StatsTotals(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: What buyers paid for these courses, net of each line's coupon share.
    revenue: Decimal
    #: Courses sold -- order lines, not orders: one order of two courses by
    #: this instructor is two sales.
    sales: int
    enrollments: int
    #: People whose first course with this instructor began in the window.
    new_students: int


class StatsPoint(StatsTotals):
    #: The first day of the bucket, on the Vietnamese calendar: the day itself,
    #: or the first of the month.
    bucket: date


class InstructorOverviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: StatsPeriod
    granularity: Granularity
    #: Both inclusive, Vietnamese calendar.
    start: date
    end: date
    current: StatsTotals
    #: The window of the same length just before this one.
    previous: StatsTotals
    #: One point per bucket, empty buckets included, oldest first.
    series: list[StatsPoint]

    # All-time, whatever the period: these describe the instructor, not the
    # window, and a completion rate over one month's joiners would mostly
    # measure how recently they joined.
    revenue_all_time: Decimal
    students_total: int
    #: Finished enrolments over all enrolments; null with no enrolments.
    completion_rate: float | None
    #: Courses not taken down.
    courses_count: int


class StatsCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    status: str
    price: Decimal
    thumbnail_url: str | None
    #: Taken down, but still listed because people are still enrolled in it.
    is_deleted: bool


class CourseStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course: StatsCourseOut
    #: All-time.
    students: int
    completed: int
    lessons_count: int
    #: `completed / students`; null with nobody enrolled -- 0% would claim
    #: that nobody finishes.
    completion_rate: float | None
    #: Lessons done over lessons there are, across every enrolment; null with
    #: nobody enrolled or nothing to do.
    avg_progress: float | None
    #: In the period.
    new_enrollments: int
    sales: int
    revenue: Decimal
    revenue_all_time: Decimal
