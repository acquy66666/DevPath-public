"""The admin's review queue: which courses go on sale, and which come off.

Three moves, all on `courses.status`, all by an admin:

* **approve** -- `pending_review -> published`. This is the moment a course
  becomes something students can buy, so it is also the moment the chatbot
  ingest and the course embedding are scheduled -- after the commit, because
  the worker opens its own connection and must find the course published.
  Before Phase 5 the same two jobs hung off `submit_for_review` while a flag
  published courses on submit; with the flag gone, forgetting them here would
  leave every new course unanswerable by the chatbot and invisible to the
  recommender, and nothing on any page would say so.
* **reject** -- `pending_review -> rejected`, with the reason the instructor
  reads (`ck_courses_rejection_reason` refuses a rejection without one).
* **take down** -- `published -> draft`, the spec's "gỡ khỏi sàn", for a course
  that is already on sale -- usually after a report (`services/reports.py`).

Each move tells the instructor in the same transaction (`notifications.add`),
so a decision nobody hears about cannot happen.

The course row is locked (`FOR UPDATE`) before its status is read: two admins
deciding the same course at once must not both succeed, and the second one
should be told the course has already moved on.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    NOTIFICATION_COURSE_APPROVED,
    NOTIFICATION_COURSE_REJECTED,
    NOTIFICATION_COURSE_TAKEN_DOWN,
    Category,
    Course,
    CourseSection,
    Lesson,
    User,
)
from app.services import notifications as notifications_service
from app.services.courses import CourseNotFoundError, InvalidCourseStatusError
from app.services.tasks import TaskQueue

CourseStatusFilter = Literal["pending_review", "published", "rejected", "draft", "all"]


@dataclass(frozen=True, slots=True)
class AdminCourse:
    course: Course
    instructor: User
    category: Category
    lessons_count: int


def _listing() -> Select:
    lessons_count = (
        select(func.count(Lesson.id))
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id == Course.id)
        .scalar_subquery()
    )
    return (
        select(Course, User, Category, lessons_count)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(Course.deleted_at.is_(None))
    )


def _view(row) -> AdminCourse:
    course, instructor, category, lessons_count = row
    return AdminCourse(
        course=course, instructor=instructor, category=category, lessons_count=lessons_count
    )


async def list_courses(
    session: AsyncSession,
    *,
    status: CourseStatusFilter,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AdminCourse], int]:
    """Courses as the admin sees them, in any status.

    The review queue (`pending_review`) is longest-waiting first -- the fair
    order for a queue. `updated_at` stands in for "sent for review at": a
    course cannot be edited out of `pending_review`, so its last change is the
    submission or an edit made while it waited. Every other view is most
    recently changed first.
    """
    listing = _listing()
    if status != "all":
        listing = listing.where(Course.status == status)
    if q:
        listing = listing.where(
            or_(
                Course.title.icontains(q, autoescape=True),
                User.full_name.icontains(q, autoescape=True),
                User.email.icontains(q, autoescape=True),
            )
        )

    total = await session.scalar(select(func.count()).select_from(listing.subquery()))

    if status == "pending_review":
        listing = listing.order_by(Course.updated_at.asc(), Course.id)
    else:
        listing = listing.order_by(Course.updated_at.desc(), Course.id)

    rows = await session.execute(listing.offset((page - 1) * page_size).limit(page_size))
    return [_view(row) for row in rows], total or 0


async def get_course(session: AsyncSession, course_id: uuid.UUID) -> AdminCourse:
    # populate_existing: after a decision the row is already in the session,
    # and the answer must show what was just written, not what was loaded.
    row = (
        await session.execute(
            _listing()
            .where(Course.id == course_id)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise CourseNotFoundError("Không tìm thấy khóa học")
    return _view(row)


async def _locked(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await session.scalar(
        select(Course)
        .where(Course.id == course_id, Course.deleted_at.is_(None))
        .with_for_update()
    )
    if course is None:
        raise CourseNotFoundError("Không tìm thấy khóa học")
    return course


def _require(course: Course, expected: str, verb: str) -> None:
    if course.status != expected:
        raise InvalidCourseStatusError(
            f"Khóa học đang ở trạng thái '{course.status}', không {verb} được"
        )


async def approve(
    session: AsyncSession, course_id: uuid.UUID, queue: TaskQueue
) -> AdminCourse:
    """pending_review -> published, then schedule what publishing starts."""
    course = await _locked(session, course_id)
    _require(course, "pending_review", "duyệt")

    course.status = "published"
    course.rejection_reason = None
    # The first time it went on sale. A course taken down and approved again
    # keeps its original date, as `courses.unpublish` already promises.
    if course.published_at is None:
        course.published_at = datetime.now(tz=UTC)

    notifications_service.add(
        session,
        user_id=course.instructor_id,
        type=NOTIFICATION_COURSE_APPROVED,
        payload={
            "course_id": str(course.id),
            "course_slug": course.slug,
            "course_title": course.title,
        },
    )
    await session.commit()

    # After the commit, never before: the worker would find the old status --
    # or no course at all, if the commit failed.
    queue.enqueue_ingest(course.id)
    # Separate from the ingest because they fail separately: a course with no
    # lessons still has a title to embed.
    queue.enqueue_course_embedding(course.id)

    return await get_course(session, course.id)


async def reject(session: AsyncSession, course_id: uuid.UUID, reason: str) -> AdminCourse:
    """pending_review -> rejected. The instructor edits and sends it again."""
    course = await _locked(session, course_id)
    _require(course, "pending_review", "từ chối")

    course.status = "rejected"
    course.rejection_reason = reason

    notifications_service.add(
        session,
        user_id=course.instructor_id,
        type=NOTIFICATION_COURSE_REJECTED,
        payload={
            "course_id": str(course.id),
            "course_title": course.title,
            "reason": reason,
        },
    )
    await session.commit()
    return await get_course(session, course.id)


async def stage_take_down(session: AsyncSession, course: Course, reason: str) -> None:
    """published -> draft, and tell the instructor why. Does not commit.

    Split out so resolving a report can take a course down inside the same
    transaction that closes the report.

    Draft rather than `rejected`: the spec's only way off the shelf is
    `published -> draft`, and a draft sent for review again comes back through
    this queue -- which is the point.
    """
    course.status = "draft"
    notifications_service.add(
        session,
        user_id=course.instructor_id,
        type=NOTIFICATION_COURSE_TAKEN_DOWN,
        payload={
            "course_id": str(course.id),
            "course_title": course.title,
            "reason": reason,
        },
    )


async def take_down(session: AsyncSession, course_id: uuid.UUID, reason: str) -> AdminCourse:
    course = await _locked(session, course_id)
    _require(course, "published", "gỡ")
    await stage_take_down(session, course, reason)
    await session.commit()
    return await get_course(session, course.id)


async def lock_course(session: AsyncSession, course_id: uuid.UUID) -> Course | None:
    """The course row, locked, or None if it is gone. For `services/reports.py`."""
    return await session.scalar(
        select(Course)
        .where(Course.id == course_id, Course.deleted_at.is_(None))
        .with_for_update()
    )


async def pending_count(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.status == "pending_review", Course.deleted_at.is_(None))
        )
        or 0
    )
