"""Building and rearranging a course curriculum.

`position` is a plain integer, contiguous from 0 within each parent, and every
operation that could leave a hole closes it. Contiguity is not required by the
database -- it is what makes "append" mean `len(existing)` and what keeps the
numbers the instructor never sees from drifting into nonsense.

Rearranging is always **whole-list**: the client sends the arrangement it wants
rather than a move instruction. The unique constraints on `(parent, position)`
are deferrable precisely so those rewrites can pass through states where two
rows briefly claim the same slot.
"""

import uuid

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Course, CourseSection, Lesson, User
from app.schemas.curriculum import LessonCreate, LessonUpdate
from app.services import courses as courses_service


class SectionNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "SECTION_NOT_FOUND"


class LessonNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "LESSON_NOT_FOUND"


class LessonLockedError(DomainError):
    """The lesson exists and is worth knowing about, but not readable yet."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "LESSON_LOCKED"


class InvalidOrderError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ORDER"


async def _sections_of(session: AsyncSession, course_id: uuid.UUID) -> list[CourseSection]:
    rows = await session.scalars(
        select(CourseSection)
        .where(CourseSection.course_id == course_id)
        .order_by(CourseSection.position)
    )
    return list(rows)


async def _lessons_of(session: AsyncSession, section_id: uuid.UUID) -> list[Lesson]:
    rows = await session.scalars(
        select(Lesson).where(Lesson.section_id == section_id).order_by(Lesson.position)
    )
    return list(rows)


def _renumber(rows: list) -> None:
    """Close the gaps left by a delete or a move, keeping the current order."""
    for index, row in enumerate(rows):
        row.position = index


async def _load_section(session: AsyncSession, section_id: uuid.UUID) -> CourseSection:
    section = await session.get(CourseSection, section_id)
    if section is None:
        raise SectionNotFoundError("Không tìm thấy chương")
    return section


async def _section_for_management(
    session: AsyncSession, section_id: uuid.UUID, user: User
) -> tuple[CourseSection, Course]:
    """A section the caller may edit, together with the course that owns it.

    Ownership lives on the course, so every section and lesson check walks up
    to it -- including the soft-delete filter, which is why this goes through
    the courses service rather than a join written here.
    """
    section = await _load_section(session, section_id)
    course = await courses_service.load_for_management(session, section.course_id, user)
    return section, course


async def _lesson_for_management(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> tuple[Lesson, CourseSection, Course]:
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Không tìm thấy bài học")
    section, course = await _section_for_management(session, lesson.section_id, user)
    return lesson, section, course


# --- Reading ---------------------------------------------------------------


async def get_curriculum(
    session: AsyncSession, course_id: uuid.UUID, viewer: User | None
) -> list[tuple[CourseSection, list[Lesson]]]:
    """The table of contents, if the course itself may be seen."""
    course = await courses_service.get_course_for_viewer(session, course_id, viewer)

    sections = await _sections_of(session, course.id)
    return [(section, await _lessons_of(session, section.id)) for section in sections]


async def get_lesson_for_viewer(
    session: AsyncSession, lesson_id: uuid.UUID, viewer: User | None
) -> Lesson:
    """One lesson in full.

    Three answers, and the difference matters: the owner sees anything; a
    preview lesson of a published course is open to everyone; anything else in
    a published course is locked (403 -- it exists, enrol to read it), and
    everything in a course you cannot see is simply not found.
    """
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Không tìm thấy bài học")

    section = await _load_section(session, lesson.section_id)
    course = await courses_service.get_course_for_viewer(
        session, section.course_id, viewer
    )

    if viewer is not None and courses_service.may_manage(course, viewer):
        return lesson
    if lesson.is_preview:
        return lesson

    raise LessonLockedError("Bài học này cần đăng ký khóa học mới xem được")


# --- Sections --------------------------------------------------------------


async def create_section(
    session: AsyncSession, course_id: uuid.UUID, user: User, title: str
) -> CourseSection:
    """Append a section to the end of the course."""
    course = await courses_service.load_for_management(session, course_id, user)
    existing = await _sections_of(session, course.id)

    section = CourseSection(course_id=course.id, title=title, position=len(existing))
    session.add(section)
    await session.commit()
    return section


async def update_section(
    session: AsyncSession, section_id: uuid.UUID, user: User, title: str
) -> CourseSection:
    section, _ = await _section_for_management(session, section_id, user)
    section.title = title
    await session.commit()
    await session.refresh(section)
    return section


async def delete_section(
    session: AsyncSession, section_id: uuid.UUID, user: User
) -> None:
    """Delete a section and its lessons, then close the gap it left.

    A hard delete, unlike courses: nobody bought a section, and the lessons go
    with it through ON DELETE CASCADE.
    """
    section, course = await _section_for_management(session, section_id, user)
    await session.delete(section)
    await session.flush()

    _renumber(await _sections_of(session, course.id))
    await session.commit()


async def reorder_sections(
    session: AsyncSession,
    course_id: uuid.UUID,
    user: User,
    section_ids: list[uuid.UUID],
) -> list[CourseSection]:
    """Rewrite the order of every section in one go.

    The list has to name each section exactly once. A partial list would leave
    the rows it omits sitting at stale positions, and the instructor would see
    an order nobody asked for.
    """
    course = await courses_service.load_for_management(session, course_id, user)
    sections = await _sections_of(session, course.id)

    by_id = {section.id: section for section in sections}
    if len(section_ids) != len(set(section_ids)) or set(section_ids) != set(by_id):
        raise InvalidOrderError(
            "Danh sách thứ tự phải liệt kê đúng một lần mỗi chương của khóa học"
        )

    for index, section_id in enumerate(section_ids):
        by_id[section_id].position = index

    await session.commit()
    return await _sections_of(session, course.id)


# --- Lessons ---------------------------------------------------------------


async def create_lesson(
    session: AsyncSession, section_id: uuid.UUID, user: User, data: LessonCreate
) -> Lesson:
    """Append a lesson to the end of its section.

    A video lesson starts without a video: the upload has to have something to
    attach itself to.
    """
    section, _ = await _section_for_management(session, section_id, user)
    existing = await _lessons_of(session, section.id)

    lesson = Lesson(
        section_id=section.id,
        title=data.title,
        type=data.type,
        position=len(existing),
        is_preview=data.is_preview,
        article_content=data.article_content,
    )
    session.add(lesson)
    await session.commit()
    return lesson


async def update_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, user: User, data: LessonUpdate
) -> Lesson:
    lesson, _, _ = await _lesson_for_management(session, lesson_id, user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lesson, field, value)

    await session.commit()
    await session.refresh(lesson)
    return lesson


async def delete_lesson(session: AsyncSession, lesson_id: uuid.UUID, user: User) -> None:
    lesson, section, _ = await _lesson_for_management(session, lesson_id, user)
    await session.delete(lesson)
    await session.flush()

    _renumber(await _lessons_of(session, section.id))
    await session.commit()


async def reorder_lessons(
    session: AsyncSession,
    section_id: uuid.UUID,
    user: User,
    lesson_ids: list[uuid.UUID],
) -> list[Lesson]:
    """Set the complete contents of one section, in order.

    A lesson in the list that currently belongs to another section of the same
    course is moved in -- which is what dropping it here means. The section it
    came from is renumbered so it does not keep a hole.

    A lesson currently in this section that the list leaves out is refused: it
    would end up at a stale position with nobody claiming it, and the request
    gives no clue where it was meant to go.
    """
    section, course = await _section_for_management(session, section_id, user)

    if len(lesson_ids) != len(set(lesson_ids)):
        raise InvalidOrderError("Danh sách thứ tự có bài học lặp lại")

    # Everything in the course, so a lesson from another section can be moved
    # in while a lesson from another course cannot.
    course_sections = await _sections_of(session, course.id)
    section_ids = {item.id for item in course_sections}
    candidates = list(
        await session.scalars(
            select(Lesson).where(Lesson.section_id.in_(section_ids))
        )
    )
    by_id = {lesson.id: lesson for lesson in candidates}

    unknown = set(lesson_ids) - set(by_id)
    if unknown:
        raise InvalidOrderError("Danh sách chứa bài học không thuộc khóa học này")

    current = {lesson.id for lesson in candidates if lesson.section_id == section.id}
    if not current <= set(lesson_ids):
        raise InvalidOrderError(
            "Danh sách phải chứa mọi bài học đang thuộc chương này"
        )

    sources = {
        by_id[lesson_id].section_id
        for lesson_id in lesson_ids
        if by_id[lesson_id].section_id != section.id
    }

    for index, lesson_id in enumerate(lesson_ids):
        lesson = by_id[lesson_id]
        lesson.section_id = section.id
        lesson.position = index

    await session.flush()

    # Sections that lost a lesson would otherwise keep its empty slot.
    for source_id in sources:
        _renumber(await _lessons_of(session, source_id))

    await session.commit()
    return await _lessons_of(session, section.id)
