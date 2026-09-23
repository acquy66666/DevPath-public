"""Signing up for a course, and the list of what you signed up for.

Phase 2 only knows how to give away free courses. A paid one is refused here
rather than quietly enrolled, because the row this module writes is exactly the
row a payment would have to produce -- and writing it without the payment is
how a course ends up owned by somebody who never bought it.
"""

import uuid
from decimal import Decimal

from fastapi import status
from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Category, Course, Enrollment, User
from app.services import courses as courses_service


class CourseNotFreeError(DomainError):
    """A paid course is bought, not enrolled in: the row this module writes is
    the one a payment produces, and writing it without the payment is how a
    course ends up owned by somebody who never bought it."""

    status_code = status.HTTP_409_CONFLICT
    code = "COURSE_NOT_FREE"


class OwnCourseEnrollmentError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_ENROL_OWN_COURSE"


class EnrollmentNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "ENROLLMENT_NOT_FOUND"


async def find_for_course(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Enrollment | None:
    """The caller's enrolment in one course, or None.

    Shared with the curriculum service, which uses it to decide whether a
    locked lesson opens, and with the progress service, which cannot record
    anything without one.
    """
    return await session.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user.id, Enrollment.course_id == course_id
        )
    )


async def grant(
    session: AsyncSession, course_id: uuid.UUID, user_id: uuid.UUID, *, source: str
) -> bool:
    """Write the enrolment and move the course's counter. Returns "it is new".

    No rules and no commit: the rules differ by how the enrolment was earned --
    free enrolment refuses a paid course, a purchase has already been paid for
    -- but the two rows are identical, and so is the counter that has to move
    with them. Keeping that in one place is what stops `students_count` from
    being maintained two slightly different ways.

    Takes a user id rather than a `User` because the paid path runs inside a
    callback from the payment gateway, where nobody is signed in.
    """
    created = await session.scalar(
        # ON CONFLICT rather than "look, then insert": two clicks that arrive
        # together would both pass the lookup and one would die on the unique
        # constraint. Here the loser simply writes nothing, and `returning` is
        # what tells the two apart -- which also keeps the counter honest.
        insert(Enrollment)
        .values(user_id=user_id, course_id=course_id, source=source)
        .on_conflict_do_nothing(constraint="uq_enrollments_user_course")
        .returning(Enrollment.id)
    )

    if created is not None:
        # Read-modify-write in Python would lose an increment whenever two
        # people enrol at once; the database can add one to whatever it finds.
        #
        # `updated_at` is pinned to itself so SQLAlchemy's `onupdate` leaves it
        # alone: the instructor's dashboard reads that column as "when this
        # course last changed", and somebody else signing up did not change it.
        await session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(
                students_count=Course.students_count + 1,
                updated_at=Course.updated_at,
            )
        )

    return created is not None


async def enrol_free(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> tuple[Enrollment, bool]:
    """Enrol the caller in a free course. Returns the row and whether it is new.

    Asking twice is not an error -- two tabs, or a double click, describe the
    same fact -- so the second call returns the first call's row. The caller
    turns that flag into 201 or 200.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, user)

    if course.status != "published":
        # The owner and an admin can *see* a draft; nobody can enrol in one.
        # 404 rather than 409, to match what everyone else is told about it.
        raise courses_service.CourseNotFoundError("Không tìm thấy khóa học")

    if course.instructor_id == user.id:
        raise OwnCourseEnrollmentError(
            "Bạn là giảng viên của khóa học này nên không cần đăng ký"
        )

    if course.price > Decimal("0"):
        raise CourseNotFreeError(
            "Khóa học này có phí. Thêm vào giỏ hàng rồi thanh toán để vào học."
        )

    created = await grant(session, course.id, user.id, source="free")

    await session.commit()

    enrollment = await find_for_course(session, course.id, user)
    if enrollment is None:
        # Only reachable if the row vanished between the insert and this read,
        # which nothing in the system does.
        raise EnrollmentNotFoundError("Không tìm thấy đăng ký")

    return enrollment, created


async def get_for_course(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Enrollment:
    """The caller's enrolment in one course, for a page that asks "am I in?"."""
    enrollment = await find_for_course(session, course_id, user)
    if enrollment is None:
        raise EnrollmentNotFoundError("Bạn chưa đăng ký khóa học này")
    return enrollment


async def list_for_user(
    session: AsyncSession, user: User, *, page: int, page_size: int
) -> tuple[list[tuple[Enrollment, Course, User, Category]], int]:
    """Everything this account is enrolled in, most recent first.

    A soft-deleted course stays on this list on purpose: taking a course off
    sale must not take it away from the people already studying it. That is why
    the course foreign key is RESTRICT and why there is no `deleted_at` filter
    here -- the one place in the codebase where its absence is deliberate.
    """
    mine = Enrollment.user_id == user.id

    total = await session.scalar(
        select(func.count()).select_from(Enrollment).where(mine)
    )

    listing: Select[tuple[Enrollment, Course, User, Category]] = (
        select(Enrollment, Course, User, Category)
        .join(Course, Course.id == Enrollment.course_id)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(mine)
        # The id breaks ties. `created_at` defaults to `now()`, which in
        # Postgres is the transaction's start time, so two rows written
        # together carry the same instant -- and an ORDER BY that ties has no
        # fixed answer, which is how a row shows up on two pages or on none.
        .order_by(Enrollment.created_at.desc(), Enrollment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(listing)).all()
    return [tuple(row) for row in rows], total or 0
