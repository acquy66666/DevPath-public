"""The XP leaderboard.

Signed-in only: the board is a list of learners' names, and whoever reads it
should be one of them. It shows a name, an avatar and a number -- never an
email -- and takes no user id, so there is nothing else to ask it for.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.leaderboard import (
    LeaderboardEntryOut,
    LeaderboardMeOut,
    LeaderboardOut,
    LeaderboardPeriod,
    LeaderboardUserOut,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.services import leaderboard as leaderboard_service

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardOut)
async def get_leaderboard(
    current_user: CurrentUser,
    session: DbSession,
    period: LeaderboardPeriod = "week",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> LeaderboardOut:
    """Who earned the most XP this week, this month or ever, and where you stand."""
    result = await leaderboard_service.standings(
        session, current_user, period, page=page, page_size=page_size
    )
    return LeaderboardOut(
        period=period,
        starts_on=result.period.starts_on,
        ends_on=result.period.ends_on,
        items=[
            LeaderboardEntryOut(
                rank=entry.rank,
                user=LeaderboardUserOut(
                    id=entry.user.id,
                    full_name=entry.user.full_name,
                    avatar_url=entry.user.avatar_url,
                ),
                xp=entry.xp,
                is_me=entry.user.id == current_user.id,
            )
            for entry in result.entries
        ],
        total=result.total,
        page=page,
        page_size=page_size,
        me=(
            LeaderboardMeOut(rank=result.my_rank, xp=result.my_xp)
            if result.my_rank is not None and result.my_xp is not None
            else None
        ),
    )
