"""Rating a course you actually took.

The rule the whole module exists to hold: **only an enrolled student may write
a review**. Not the instructor about their own course, not a visitor who read
the sales page. Everything else here follows from that one sentence.

Every write also rewrites `courses.rating_avg` and `courses.rating_count`, in
the same transaction, from this table. Two things make that safe:

* the average is **recomputed**, never adjusted. `students_count` can get away
  with `+ 1` because enrolling only ever adds; an average moves in both
  directions when a review is edited, and arithmetic on a stale value is how a
  rating drifts away from the rows it is supposed to summarise.
* the course row is locked before the recount. Two people rating the same
  course at the same moment would otherwise each average a snapshot taken
  before the other's row existed, and the loser's write would erase the winner
  from the total. `SELECT ... FOR UPDATE` makes them queue instead, which costs
  nothing: contention is per-course, and the section it guards is two
  statements long.

Both halves live in `services/course_stats.py`, next to the definition that
`scripts/rebuild_course_stats.py` recomputes every column from -- so a drift
that does happen is repairable rather than permanent.
"""

import uuid

from fastapi import status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Course, Review, User
from app.services import course_stats
from app.services import courses as courses_service
from app.services import enrollments as enrollments_service


class NotEnrolledError(DomainError):
    """You cannot review a course you never took."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "NOT_ENROLLED"


class OwnCourseReviewError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_REVIEW_OWN_COURSE"


class ReviewNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "REVIEW_NOT_FOUND"


async def _writable_course(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Course:
    """The course this person is allowed to review, or the reason they are not.

    Order matters. A course they cannot see answers 404 first, so this endpoint
    never becomes a way to discover that a draft exists.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, user)

    if course.instructor_id == user.id:
        raise OwnCourseReviewError("Bạn không thể đánh giá khóa học của chính mình")

    enrollment = await enrollments_service.find_for_course(session, course.id, user)
    if enrollment is None:
        raise NotEnrolledError("Bạn cần đăng ký khóa học trước khi đánh giá")

    return course


async def find_mine(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Review | None:
    """The caller's review of one course, or None. No enrolment needed to ask.

    An unenrolled reader simply has no review, which is not an error -- and
    answering it without the enrolment check keeps the course page from having
    to know the difference before it can draw the form.
    """
    return await session.scalar(
        select(Review).where(Review.course_id == course_id, Review.user_id == user.id)
    )


async def get_mine(session: AsyncSession, course_id: uuid.UUID, user: User) -> Review:
    review = await find_mine(session, course_id, user)
    if review is None:
        raise ReviewNotFoundError("Bạn chưa đánh giá khóa học này")
    return review


async def upsert_mine(
    session: AsyncSession,
    course_id: uuid.UUID,
    user: User,
    *,
    rating: int,
    comment: str | None,
) -> tuple[Review, bool]:
    """Write or rewrite the caller's review. Returns it and whether it is new.

    Read-then-write rather than `ON CONFLICT DO UPDATE`, unlike the enrolment
    and bookmark paths: the course row is already locked by the time this looks,
    so the race those guard against cannot happen here -- and going through the
    ORM keeps `updated_at` honest about when the person last edited.
    """
    course = await _writable_course(session, course_id, user)

    await course_stats.lock_course(session, course.id)

    review = await find_mine(session, course.id, user)
    created = review is None

    if review is None:
        review = Review(course_id=course.id, user_id=user.id)
        session.add(review)

    review.rating = rating
    review.comment = comment

    # Before the recount, so the aggregate sees this row.
    await session.flush()

    await course_stats.recount_rating(session, course.id)

    await session.commit()
    await session.refresh(review)
    return review, created


async def delete_mine(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> None:
    """Withdraw the caller's review.

    Deleting one you never wrote answers 404 rather than passing quietly: a
    button that removes something should not report success when there was
    nothing to remove.
    """
    review = await get_mine(session, course_id, user)

    await course_stats.lock_course(session, course_id)

    await session.delete(review)
    await session.flush()

    await course_stats.recount_rating(session, course_id)

    await session.commit()


async def list_for_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    viewer: User | None,
    *,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Review, User]], int, Course]:
    """One course's reviews, newest first, for anyone who may see the course.

    Public, like the course page it sits on -- reviews are what a prospective
    student came to read, and hiding them behind a login would defeat them.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, viewer)

    on_course = Review.course_id == course.id

    total = await session.scalar(
        select(func.count()).select_from(Review).where(on_course)
    )

    listing: Select[tuple[Review, User]] = (
        select(Review, User)
        .join(User, User.id == Review.user_id)
        .where(on_course)
        # The id breaks ties: `created_at` defaults to `now()`, which in
        # Postgres is the transaction's start time, so two rows written
        # together carry the same instant -- and an ORDER BY that ties has no
        # fixed answer, which is how a row shows up on two pages or on none.
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(listing)).all()
    # The course comes back too: it carries the rating summary the page shows
    # above the list, and it has already been loaded and permission-checked.
    return [(review, author) for review, author in rows], total or 0, course
