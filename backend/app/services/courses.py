"""Course lifecycle: create, edit, take down, and move through review.

Two rules hold everywhere in this module:

* **Ownership is checked here, not in the router.** The router has an id; only
  this layer has the row to compare it against.
* **Soft-deleted courses do not exist.** Every read goes through
  `_active_courses()` so the `deleted_at IS NULL` filter cannot be forgotten in
  one query out of eight -- which is the failure mode `docs/database-design.md`
  warns about.
"""

import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError, PermissionDeniedError
from app.models import Category, Course, User
from app.schemas.courses import CourseCreate, CourseUpdate
from app.services.slug import unique_slug


class CourseNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "COURSE_NOT_FOUND"


class CategoryNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "CATEGORY_NOT_FOUND"


class InvalidCourseStatusError(DomainError):
    """The transition asked for is not one the spec allows from here."""

    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_COURSE_STATUS"


def _active_courses() -> Select[tuple[Course]]:
    """Every query starts here, so no read can forget the soft-delete filter."""
    return select(Course).where(Course.deleted_at.is_(None))


def _may_manage(course: Course, user: User) -> bool:
    """Instructors own their courses; admins can act on any of them."""
    return course.instructor_id == user.id or user.role == "admin"


async def _load(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await session.scalar(_active_courses().where(Course.id == course_id))
    if course is None:
        raise CourseNotFoundError("Không tìm thấy khóa học")
    return course


async def _load_for_management(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Course:
    """Load a course the caller is allowed to change.

    403 rather than 404 for someone else's course: course ids are UUIDs, so
    confirming one exists tells an attacker nothing they could not already
    guess, and a plain "not yours" is far easier to act on when an instructor
    is signed in as the wrong account.
    """
    course = await _load(session, course_id)
    if not _may_manage(course, user):
        raise PermissionDeniedError("Khóa học này không thuộc về bạn")
    return course


async def create_course(
    session: AsyncSession, instructor: User, data: CourseCreate
) -> Course:
    """Start a course as a draft owned by the caller."""
    category = await session.get(Category, data.category_id)
    if category is None:
        raise CategoryNotFoundError("Không tìm thấy danh mục")

    course = Course(
        instructor_id=instructor.id,
        category_id=data.category_id,
        title=data.title,
        slug=unique_slug(data.title),
        subtitle=data.subtitle,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        price=data.price,
        level=data.level,
        language=data.language,
        status="draft",
    )
    session.add(course)
    await session.commit()
    return course


async def get_course_for_viewer(
    session: AsyncSession, course_id: uuid.UUID, viewer: User | None
) -> Course:
    """A published course is public; anything else belongs to its owner.

    Answers 404 rather than 403 for a draft: an unpublished course should not
    be confirmed to exist to someone who cannot read it.
    """
    course = await _load(session, course_id)

    if course.status == "published":
        return course
    if viewer is not None and _may_manage(course, viewer):
        return course

    raise CourseNotFoundError("Không tìm thấy khóa học")


async def list_own_courses(
    session: AsyncSession, instructor: User, *, page: int, page_size: int
) -> tuple[list[Course], int]:
    """The instructor's own courses, newest first, in every status."""
    mine = _active_courses().where(Course.instructor_id == instructor.id)

    total = await session.scalar(
        select(func.count()).select_from(mine.subquery())
    )
    rows = await session.scalars(
        mine.order_by(Course.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows), int(total or 0)


async def update_course(
    session: AsyncSession, course_id: uuid.UUID, user: User, data: CourseUpdate
) -> Course:
    """Edit the fields the schema allows. Status and ownership are not among them."""
    course = await _load_for_management(session, course_id, user)

    changes = data.model_dump(exclude_unset=True)

    if "category_id" in changes and changes["category_id"] is not None:
        if await session.get(Category, changes["category_id"]) is None:
            raise CategoryNotFoundError("Không tìm thấy danh mục")

    for field, value in changes.items():
        setattr(course, field, value)

    await session.commit()
    # updated_at is filled by Postgres, so the attribute is expired after the
    # UPDATE. Refresh here rather than let the response model trip over lazy IO.
    await session.refresh(course)
    return course


async def delete_course(session: AsyncSession, course_id: uuid.UUID, user: User) -> None:
    """Take the course off the platform without erasing it.

    Soft delete is the whole reason `courses.deleted_at` exists: students who
    already paid keep watching what they bought.
    """
    course = await _load_for_management(session, course_id, user)
    course.deleted_at = datetime.now(tz=UTC)
    await session.commit()


async def submit_for_review(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Course:
    """draft | rejected -> pending_review, and on to published while the flag is on.

    The flag stands in for the admin queue that Phase 5 builds. Turning it off
    is what a real review looks like: the course waits in `pending_review`.
    """
    course = await _load_for_management(session, course_id, user)

    if course.status not in ("draft", "rejected"):
        raise InvalidCourseStatusError(
            f"Khóa học đang ở trạng thái '{course.status}', không gửi duyệt được"
        )

    course.status = "pending_review"
    course.rejection_reason = None

    if get_settings().auto_approve_courses:
        course.status = "published"
        # The check constraint refuses a published course with no timestamp.
        course.published_at = datetime.now(tz=UTC)

    await session.commit()
    # updated_at is filled by Postgres, so the attribute is expired after the
    # UPDATE. Refresh here rather than let the response model trip over lazy IO.
    await session.refresh(course)
    return course


async def unpublish(session: AsyncSession, course_id: uuid.UUID, user: User) -> Course:
    """published -> draft: off the shelf, back on the workbench."""
    course = await _load_for_management(session, course_id, user)

    if course.status != "published":
        raise InvalidCourseStatusError(
            f"Khóa học đang ở trạng thái '{course.status}', không gỡ được"
        )

    course.status = "draft"
    # published_at stays: it records when this course first went on sale, which
    # a later republish should not rewrite.
    await session.commit()
    # updated_at is filled by Postgres, so the attribute is expired after the
    # UPDATE. Refresh here rather than let the response model trip over lazy IO.
    await session.refresh(course)
    return course
