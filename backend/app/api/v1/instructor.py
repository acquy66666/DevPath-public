"""The instructor's dashboard: how their courses sell, and who finishes them.

Read-only, and about the caller alone -- no instructor id in any path, so there
is no other instructor's dashboard to ask for. The role check is the whole of
the authorization: every number is already scoped to `instructor.id` inside the
service's queries.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, require_role
from app.models import User
from app.schemas.instructor_stats import (
    CourseStatsOut,
    InstructorOverviewOut,
    StatsCourseOut,
    StatsPeriod,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import instructor_stats as stats_service

router = APIRouter(prefix="/instructor", tags=["instructor"])

Instructor = Annotated[User, Depends(require_role("instructor"))]


@router.get("/stats/overview", response_model=InstructorOverviewOut)
async def get_overview(
    instructor: Instructor,
    session: DbSession,
    period: StatsPeriod = "30d",
) -> InstructorOverviewOut:
    """Revenue and new students for the period, bucket by bucket, against the
    period just before it -- plus the all-time figures."""
    overview = await stats_service.overview(session, instructor.id, period)
    return InstructorOverviewOut.model_validate(overview)


@router.get("/stats/courses", response_model=Page[CourseStatsOut])
async def list_course_stats(
    instructor: Instructor,
    session: DbSession,
    period: StatsPeriod = "30d",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[CourseStatsOut]:
    """Each course's students, completion and revenue, best seller first."""
    items, total = await stats_service.course_stats(
        session, instructor.id, period, page=page, page_size=page_size
    )
    return Page[CourseStatsOut](
        items=[
            CourseStatsOut(
                course=StatsCourseOut(
                    id=row.course.id,
                    title=row.course.title,
                    slug=row.course.slug,
                    status=row.course.status,
                    price=row.course.price,
                    thumbnail_url=row.course.thumbnail_url,
                    is_deleted=row.course.deleted_at is not None,
                ),
                students=row.students,
                completed=row.completed,
                lessons_count=row.lessons_count,
                completion_rate=row.completion_rate,
                avg_progress=row.avg_progress,
                new_enrollments=row.new_enrollments,
                sales=row.sales,
                revenue=row.revenue,
                revenue_all_time=row.revenue_all_time,
            )
            for row in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
