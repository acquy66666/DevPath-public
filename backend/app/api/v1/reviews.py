"""Course reviews.

The list is public; writing one is not. Everything that decides *who* may write
lives in the service, because it needs the course and the enrolment to answer.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import Review, User
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.reviews import (
    CourseReviewsOut,
    ReviewAuthorOut,
    ReviewOut,
    ReviewUpsert,
)
from app.services import reviews as reviews_service

router = APIRouter(tags=["reviews"])


def _out(review: Review, author: User) -> ReviewOut:
    """A review row and its author, joined into the shape the page draws."""
    return ReviewOut(
        id=review.id,
        course_id=review.course_id,
        rating=review.rating,
        comment=review.comment,
        author=ReviewAuthorOut.model_validate(author),
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("/courses/{course_id}/reviews", response_model=CourseReviewsOut)
async def list_course_reviews(
    course_id: uuid.UUID,
    viewer: OptionalUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> CourseReviewsOut:
    """This course's reviews, newest first.

    Public on purpose: reviews are a large part of why somebody opens a course
    page at all, and a login wall in front of them would defeat the page. The
    optional token only matters for a course that is not published yet, where
    its own instructor is the only reader who gets past the 404.
    """
    rows, total, course = await reviews_service.list_for_course(
        session, course_id, viewer, page=page, page_size=page_size
    )

    return CourseReviewsOut(
        items=[_out(review, author) for review, author in rows],
        total=total,
        page=page,
        page_size=page_size,
        rating_avg=course.rating_avg,
        rating_count=course.rating_count,
    )


@router.get("/courses/{course_id}/reviews/me", response_model=ReviewOut)
async def get_my_review(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> ReviewOut:
    """Your review of this course. 404 `REVIEW_NOT_FOUND` if you have not written one.

    Answered without checking enrolment: somebody who is not enrolled simply
    has no review, and that is the same 404.
    """
    review = await reviews_service.get_mine(session, course_id, current_user)
    return _out(review, current_user)


@router.put(
    "/courses/{course_id}/reviews/me",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_my_review(
    course_id: uuid.UUID,
    payload: ReviewUpsert,
    response: Response,
    current_user: CurrentUser,
    session: DbSession,
) -> ReviewOut:
    """Rate this course, or change the rating you already gave it.

    PUT rather than POST: one person has at most one review of one course, so
    the address of the thing being written is known before it exists. 201 the
    first time, 200 when editing.

    403 `NOT_ENROLLED` for anyone who has not taken the course, and 409
    `CANNOT_REVIEW_OWN_COURSE` for its instructor.
    """
    review, created = await reviews_service.upsert_mine(
        session,
        course_id,
        current_user,
        rating=payload.rating,
        comment=payload.comment,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _out(review, current_user)


@router.delete(
    "/courses/{course_id}/reviews/me", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_my_review(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Withdraw your review. The course's average is recomputed without it."""
    await reviews_service.delete_mine(session, course_id, current_user)
