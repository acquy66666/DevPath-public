"""The instructor's dashboard: who learns, how far, and what they think.

Read-only, and about the caller alone -- no instructor id in any path, so there
is no other instructor's dashboard to ask for. The role check is the whole of
the authorization: every number is already scoped to `instructor.id` inside the
service's queries, and the one path with a course id 404s on a course that is
not the caller's.

**No money** comes out of here (`services/instructor_stats.py`); the tier's
share rate is the exception, and money-shaped tier criteria come back as met /
not met only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import DbSession, require_role
from app.models import Course, User
from app.schemas.instructor_stats import (
    CourseFunnelOut,
    CourseStatsOut,
    CriterionOut,
    InstructorInsightsOut,
    InstructorOverviewOut,
    LessonStatsOut,
    MyTierOut,
    StatsCourseOut,
    StatsPeriod,
    TierHistoryOut,
    TierOut,
    TierProgressOut,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import excel, exports
from app.services import instructor_stats as stats_service
from app.services import instructor_tiers as tiers_service

router = APIRouter(prefix="/instructor", tags=["instructor"])

Instructor = Annotated[User, Depends(require_role("instructor"))]

#: Enough for every course an instructor could have, in one export.
EXPORT_PAGE_SIZE = 10_000


def _course_out(course: Course) -> StatsCourseOut:
    return StatsCourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        status=course.status,
        thumbnail_url=course.thumbnail_url,
        is_deleted=course.deleted_at is not None,
    )


def _course_row(row: stats_service.CourseStats) -> CourseStatsOut:
    return CourseStatsOut(
        course=_course_out(row.course),
        students=row.students,
        new_enrollments=row.new_enrollments,
        completed=row.completed,
        lessons_count=row.lessons_count,
        started_rate=row.started_rate,
        completion_rate=row.completion_rate,
        avg_progress=row.avg_progress,
        rating_avg=row.rating_avg,
        rating_count=row.rating_count,
        open_questions=row.open_questions,
        wishlisted=row.wishlisted,
        quiz_first_try_pass_rate=row.quiz_first_try_pass_rate,
        code_solve_rate=row.code_solve_rate,
    )


@router.get("/stats/overview", response_model=InstructorOverviewOut)
async def get_overview(
    instructor: Instructor,
    session: DbSession,
    period: StatsPeriod = "30d",
) -> InstructorOverviewOut:
    """Learners and learning for the period, bucket by bucket, against the
    period just before it -- plus the all-time figures."""
    overview = await stats_service.overview(session, instructor.id, period)
    return InstructorOverviewOut.model_validate(overview)


@router.get("/stats/insights", response_model=InstructorInsightsOut)
async def get_insights(
    instructor: Instructor,
    session: DbSession,
    period: StatsPeriod = "30d",
) -> InstructorInsightsOut:
    """Outcomes, satisfaction, Q&A and interest: the figures behind the tiles."""
    insights = await stats_service.insights(session, instructor.id, period)
    return InstructorInsightsOut.model_validate(insights)


@router.get("/stats/courses", response_model=Page[CourseStatsOut])
async def list_course_stats(
    instructor: Instructor,
    session: DbSession,
    period: StatsPeriod = "30d",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[CourseStatsOut]:
    """Each course's learners, progress and satisfaction, most students first."""
    items, total = await stats_service.course_stats(
        session, instructor.id, period, page=page, page_size=page_size
    )
    return Page[CourseStatsOut](
        items=[_course_row(row) for row in items], total=total, page=page, page_size=page_size
    )


@router.get("/stats/courses/{course_id}/lessons", response_model=CourseFunnelOut)
async def get_course_funnel(
    course_id: uuid.UUID, instructor: Instructor, session: DbSession
) -> CourseFunnelOut:
    """Lesson by lesson: where the learners of one course stop."""
    funnel = await stats_service.course_funnel(session, instructor.id, course_id)
    return CourseFunnelOut(
        course=_course_out(funnel.course),
        enrollments=funnel.enrollments,
        lessons=[LessonStatsOut.model_validate(lesson) for lesson in funnel.lessons],
    )


@router.get("/stats/export.xlsx", response_class=Response)
async def export_stats(
    instructor: Instructor, session: DbSession, period: StatsPeriod = "30d"
) -> Response:
    """The dashboard as an Excel workbook -- the same figures, no money."""
    overview = await stats_service.overview(session, instructor.id, period)
    insights = await stats_service.insights(session, instructor.id, period)
    courses, _ = await stats_service.course_stats(
        session, instructor.id, period, page=1, page_size=EXPORT_PAGE_SIZE
    )
    content = exports.instructor_dashboard(instructor, overview, insights, courses)
    return excel.response(
        content, f"devpath_thong-ke-giang-day_{overview.start:%Y%m%d}_{overview.end:%Y%m%d}.xlsx"
    )


@router.get("/stats/courses/{course_id}/lessons/export.xlsx", response_class=Response)
async def export_course_funnel(
    course_id: uuid.UUID, instructor: Instructor, session: DbSession
) -> Response:
    funnel = await stats_service.course_funnel(session, instructor.id, course_id)
    content = exports.course_funnel(funnel)
    return excel.response(content, f"devpath_bai-hoc_{funnel.course.slug}.xlsx")


# --- Tier ---------------------------------------------------------------------


def _criterion(criterion: tiers_service.Criterion) -> CriterionOut:
    hidden = criterion.admin_only
    return CriterionOut(
        key=criterion.key,
        label=criterion.label,
        met=criterion.met,
        value=None if hidden else criterion.value,
        threshold=None if hidden else criterion.threshold,
    )


@router.get("/tier", response_model=MyTierOut)
async def get_my_tier(instructor: Instructor, session: DbSession) -> MyTierOut:
    """The caller's tier, the ladder, and how far the next step is."""
    evaluation = await tiers_service.evaluate(session, instructor.id)
    tiers = await tiers_service.list_tiers(session)
    upcoming = evaluation.next_check
    history = await tiers_service.history(session, instructor.id)
    return MyTierOut(
        current=TierOut.model_validate(evaluation.current),
        ladder=[TierOut.model_validate(tier) for tier in tiers],
        next=(
            TierProgressOut(
                tier=TierOut.model_validate(upcoming.tier),
                met=upcoming.met,
                criteria=[_criterion(c) for c in upcoming.criteria],
            )
            if upcoming is not None
            else None
        ),
        eligible="eligible" in evaluation.flags,
        history=[
            TierHistoryOut(
                from_tier=from_tier.name if from_tier else None,
                to_tier=to_tier.name,
                to_rank=to_tier.rank,
                note=change.note,
                created_at=change.created_at,
            )
            for change, from_tier, to_tier, _ in history
        ],
    )
