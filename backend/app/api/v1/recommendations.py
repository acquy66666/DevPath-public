"""`GET /recommendations` -- the "Gợi ý cho bạn" block.

Reads the cache the nightly batch wrote and nothing else: no model is fitted
on a page load. What the request does pay for is the re-check the service
makes, which is one query for the candidate courses and one for the reader's
enrolments -- the price of never recommending a course somebody enrolled in
this morning.

Sign-in required, and deliberately so: a recommendation is derived from one
person's history, so there is no anonymous version of this page. The public
equivalent -- popular courses by category -- belongs to the catalogue.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.categories import CategoryOut
from app.schemas.courses import CourseCardBase, CourseInstructorOut
from app.schemas.recommendations import (
    ReasonOut,
    RecommendationsOut,
    RecommendedCourseOut,
)
from app.services import recommendations as recommendations_service
from app.services.recommendations import (
    RecommendationCache,
    get_recommendation_cache,
)

router = APIRouter(tags=["recommendations"])

#: Redis-backed, and overridden in tests.
Cache = Annotated[RecommendationCache, Depends(get_recommendation_cache)]

#: How many a page may ask for. The cache holds 20 per user, and asking for
#: more than that would quietly return fewer and look like a bug.
MAX_LIMIT = recommendations_service.DEFAULT_TOP_N
DEFAULT_LIMIT = 8


@router.get("/recommendations", response_model=RecommendationsOut)
async def list_recommendations(
    current_user: CurrentUser,
    session: DbSession,
    cache: Cache,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> RecommendationsOut:
    """Courses suggested for you, newest batch first.

    An empty list with a `generated_at` means the model ran and had nothing to
    suggest; an empty list with `generated_at: null` means nothing has been
    computed for you yet -- a new account, or the nightly job has not run.
    """
    served = await recommendations_service.for_user(
        session, user_id=current_user.id, limit=limit, cache=cache
    )

    return RecommendationsOut(
        generated_at=served.generated_at,
        items=[
            RecommendedCourseOut(
                **CourseCardBase.model_validate(item.course).model_dump(),
                instructor=CourseInstructorOut.model_validate(item.instructor),
                category=CategoryOut.model_validate(item.category),
                score=item.score,
                because=(
                    ReasonOut.model_validate(item.because) if item.because else None
                ),
            )
            for item in served.items
        ],
    )
