"""The instructor's dashboard on the wire -- with no money in it.

Since 20/10/2026 nothing an instructor's endpoints return is priced: no
revenue, no sales, no price, not even enrolments split into paid and free
(`services/instructor_stats.py` says why). A test walks every field of these
responses for a money-shaped name (`test_instructor_stats.py`).

Rates are floats in 0..1, null when there is nobody to measure -- the screen
shows "—", never 0 %, for that.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.stats_calendar import GRANULARITIES, PERIODS

StatsPeriod = Literal[tuple(PERIODS)]  # type: ignore[valid-type]
Granularity = Literal[GRANULARITIES]  # type: ignore[valid-type]


class StatsTotals(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enrollments: int
    #: People whose first course with this instructor began in the window.
    new_students: int
    #: Distinct learners with a trace on these courses in the window.
    active_learners: int
    lessons_completed: int
    #: Enrolments that finished a course in the window.
    completions: int
    reviews: int
    review_avg: float | None
    questions: int
    wishlist_adds: int


class StatsPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: First day of the bucket on the Vietnamese calendar.
    bucket: date
    enrollments: int
    new_students: int
    active_learners: int
    lessons_completed: int
    completions: int
    reviews: int
    questions: int
    wishlist_adds: int


class InstructorOverviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: StatsPeriod
    granularity: Granularity
    start: date
    end: date
    current: StatsTotals
    previous: StatsTotals
    series: list[StatsPoint]
    # All-time.
    students_total: int
    enrollments_total: int
    courses_published: int
    courses_total: int
    started_rate: float | None
    completion_rate: float | None
    avg_progress: float | None
    median_days_to_complete: float | None
    rating_avg: float | None
    rating_count: int
    certificates_total: int
    open_questions: int


class LearningInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_rate: float | None
    idle_rate: float | None
    median_days_to_first_lesson: float | None
    median_days_to_complete: float | None


class QuizInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempts: int
    learners: int
    median_score: float | None
    first_try_pass_rate: float | None
    expired_rate: float | None


class CodeInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submissions: int
    learners: int
    solve_rate: float | None
    median_attempts_to_ac: float | None
    verdicts: dict[str, int]


class ReviewInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    distribution: dict[int, int]
    commented_rate: float | None
    new_reviews: int
    new_review_avg: float | None


class QaInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    questions: int
    answered_rate: float | None
    median_first_response_hours: float | None
    answered_within_24h_rate: float | None
    resolved_rate: float | None
    backlog: int


class InterestInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wishlist_adds: int
    wishlisted_now: int
    wishlist_conversion_rate: float | None
    in_carts_now: int


class InstructorInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: StatsPeriod
    start: date
    end: date
    learning: LearningInsightsOut
    quiz: QuizInsightsOut
    code: CodeInsightsOut
    reviews: ReviewInsightsOut
    qa: QaInsightsOut
    interest: InterestInsightsOut


class StatsCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    status: str
    thumbnail_url: str | None
    #: Taken down, but still listed because people are still enrolled in it.
    is_deleted: bool


class CourseStatsOut(BaseModel):
    course: StatsCourseOut
    students: int
    #: In the period.
    new_enrollments: int
    completed: int
    lessons_count: int
    started_rate: float | None
    completion_rate: float | None
    avg_progress: float | None
    rating_avg: float | None
    rating_count: int
    open_questions: int
    wishlisted: int
    quiz_first_try_pass_rate: float | None
    code_solve_rate: float | None


class LessonStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: uuid.UUID
    section_title: str
    title: str
    type: str
    started: int
    completed: int
    completion_rate: float | None
    avg_watched: float | None
    quiz_first_try_pass_rate: float | None
    code_solve_rate: float | None
    questions: int
    notes: int


class CourseFunnelOut(BaseModel):
    course: StatsCourseOut
    enrollments: int
    lessons: list[LessonStatsOut]


# --- Tier ---------------------------------------------------------------------


class TierOut(BaseModel):
    """A tier as an instructor sees it: no money thresholds."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    rank: int
    description: str | None
    share_rate: Decimal


class CriterionOut(BaseModel):
    key: str
    label: str
    met: bool
    #: Null where the criterion is money (or a count that is money in disguise):
    #: the instructor is told only whether it is met.
    value: str | None
    threshold: str | None


class TierProgressOut(BaseModel):
    tier: TierOut
    met: bool
    criteria: list[CriterionOut]


class TierHistoryOut(BaseModel):
    from_tier: str | None
    to_tier: str
    to_rank: int
    note: str
    created_at: datetime


class MyTierOut(BaseModel):
    current: TierOut
    ladder: list[TierOut]
    #: Progress to the tier above; null on the top tier.
    next: TierProgressOut | None
    #: The numbers already reach a tier above the current one: an admin will
    #: see this instructor in their review list.
    eligible: bool
    history: list[TierHistoryOut]
