"""Your XP and your streak.

Only ever the caller's own: neither route takes a user id, so there is no
somebody-else to ask about. What other people have earned is the
leaderboard's business.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.gamification import (
    GamificationSummaryOut,
    XpCourseOut,
    XpEventOut,
    XpLessonOut,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import gamification as gamification_service

router = APIRouter(prefix="/users/me", tags=["gamification"])


@router.get("/gamification", response_model=GamificationSummaryOut)
async def get_my_gamification(
    current_user: CurrentUser, session: DbSession
) -> GamificationSummaryOut:
    """XP so far and the streak as it stands today (a day is a day in Vietnam)."""
    summary = await gamification_service.get_summary(session, current_user.id)
    return GamificationSummaryOut(
        xp_total=summary.xp_total,
        current_streak=summary.current_streak,
        longest_streak=summary.longest_streak,
        last_active_date=summary.last_active_date,
        active_today=summary.active_today,
    )


@router.get("/xp-events", response_model=Page[XpEventOut])
async def list_my_xp_events(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[XpEventOut]:
    """Every award, newest first, with the lesson it was for."""
    items, total = await gamification_service.list_events(
        session, current_user.id, page=page, page_size=page_size
    )
    return Page[XpEventOut](
        items=[
            XpEventOut(
                id=item.event.id,
                amount=item.event.amount,
                reason=item.event.reason,
                created_at=item.event.created_at,
                lesson=(
                    XpLessonOut(id=item.lesson.id, title=item.lesson.title) if item.lesson else None
                ),
                course=(
                    XpCourseOut(id=item.course.id, title=item.course.title, slug=item.course.slug)
                    if item.course
                    else None
                ),
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
