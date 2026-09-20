"""The two recommender blocks a page can ask for.

`GET /recommendations` -- "Gợi ý cho bạn" -- reads the cache the nightly batch
wrote and nothing else: no model is fitted on a page load. What the request
does pay for is the re-check the service makes, which is one query for the
candidate courses and one for the reader's enrolments -- the price of never
recommending a course somebody enrolled in this morning. Sign-in is required,
and deliberately so: a recommendation is derived from one person's history, so
there is no anonymous version of it.

`GET /courses/{course_id}/similar` -- "Khóa học tương tự" -- is the opposite in
every respect: derived from the course being viewed rather than from who is
viewing it, so it needs no sign-in, and computed from `course_embeddings` on
each request rather than read from a cache. It lives here rather than in
`api/v1/courses.py` because it is the content-based half of the recommender and
belongs beside the collaborative half; `courses.py` is about managing courses.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.categories import CategoryOut
from app.schemas.courses import CourseCardBase, CourseInstructorOut
from app.schemas.recommendations import (
    ReasonOut,
    RecommendationsOut,
    RecommendedCourseOut,
    SimilarCourseOut,
    SimilarCoursesOut,
)
from app.services import content_based as content_based_service
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
                sources=list(item.sources),
            )
            for item in served.items
        ],
    )


#: How many neighbours a course page may ask for. Six fills one row of cards
#: on a wide screen; the ceiling is there so a crawler cannot turn the block
#: into a full-catalogue scan.
MAX_SIMILAR = 12
DEFAULT_SIMILAR = 6


@router.get("/courses/{course_id}/similar", response_model=SimilarCoursesOut)
async def list_similar_courses(
    course_id: uuid.UUID,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_SIMILAR)] = DEFAULT_SIMILAR,
) -> SimilarCoursesOut:
    """Courses closest to this one by what they are about, nearest first.

    Public on purpose: this is a block on the public course page, and the
    course it describes is already readable by anyone. A course the public
    cannot see answers 404 rather than an empty list -- the second would be a
    claim that nothing resembles it.

    An empty `items` means the course has no embedding yet: published since
    the last batch, or the key was out of quota when it ran.
    """
    found = await content_based_service.similar_to(
        session, course_id=course_id, limit=limit
    )

    return SimilarCoursesOut(
        items=[
            SimilarCourseOut(
                **CourseCardBase.model_validate(item.course).model_dump(),
                instructor=CourseInstructorOut.model_validate(item.instructor),
                category=CategoryOut.model_validate(item.category),
                score=item.score,
            )
            for item in found
        ]
    )
