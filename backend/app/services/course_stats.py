"""The numbers `courses` keeps about itself, and how each is put back.

    students_count     how many enrolments the course has
    rating_avg         the average of its reviews, 2 decimals, 0 with none
    rating_count       how many reviews
    duration_total_s   the total length of its *ready* videos

They are stored rather than computed per request so the catalogue can sort on
them with an index (docs/database-design.md, "Số liệu khóa học"). The price is
that every write to the rows they summarise has to move them too. This module
holds the one definition of each, so the paths that move them and the script
that repairs them (`scripts.rebuild_course_stats`) cannot disagree about what
right means.

The rules every path here follows:

* **recount, never adjust.** A total moves in both directions -- a video is
  replaced, a lesson deleted, a review edited -- and arithmetic on a stale
  value is how a counter wanders away from its rows. (`students_count` is the
  one exception, in `services/enrollments.py`: enrolling only ever adds, so
  `+ 1` in SQL is exact there.)
* **lock the course row first.** Two videos of one course finishing at once
  would otherwise each sum a snapshot taken before the other was ready, and the
  later write would drop the earlier video from the total. `SELECT ... FOR
  UPDATE` makes them queue, and the recount after the lock is a new statement,
  so under READ COMMITTED it sees what the other one committed.
* **`updated_at` is pinned.** The instructor's dashboard reads it as "when did
  I last change this course"; a worker finishing or a stranger's review is not
  that.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import ColumnElement, Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseSection, Enrollment, Lesson, Review, VideoAsset

CourseRef = uuid.UUID | ColumnElement[uuid.UUID]


# --- One definition per column ---------------------------------------------
#
# Each takes the course it is about. A UUID gives a query for that one course;
# `Course.id` gives a correlated subquery, which is how rebuild() asks about
# every course in one statement.


def _students(course_id: CourseRef) -> Select:
    return select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course_id)


def _rating_avg(course_id: CourseRef) -> Select:
    return select(func.coalesce(func.round(func.avg(Review.rating), 2), 0)).where(
        Review.course_id == course_id
    )


def _rating_count(course_id: CourseRef) -> Select:
    return select(func.count()).select_from(Review).where(Review.course_id == course_id)


def _duration(course_id: CourseRef) -> Select:
    """Only `ready` videos. One still transcoding has no length yet, and one
    that failed will never play -- neither is time a student can spend."""
    return (
        select(func.coalesce(func.sum(VideoAsset.duration_s), 0))
        .select_from(Lesson)
        .join(CourseSection, Lesson.section_id == CourseSection.id)
        .join(VideoAsset, Lesson.video_asset_id == VideoAsset.id)
        .where(CourseSection.course_id == course_id, VideoAsset.status == "ready")
    )


_SOURCES = {
    "students_count": _students,
    "rating_avg": _rating_avg,
    "rating_count": _rating_count,
    "duration_total_s": _duration,
}


# --- Recounting one course, from the paths that change it ------------------


async def lock_course(session: AsyncSession, course_id: uuid.UUID) -> None:
    """Serialise everyone rewriting this course's numbers, and only them."""
    await session.execute(select(Course.id).where(Course.id == course_id).with_for_update())


async def _write(session: AsyncSession, course_id: uuid.UUID, **values: object) -> None:
    # Literal values rather than the subqueries themselves, so SQLAlchemy can
    # update a Course already loaded in this session in place. With a SQL
    # expression it would expire the attribute instead, and the next read of it
    # in an async session is a MissingGreenlet.
    await session.execute(
        update(Course)
        .where(Course.id == course_id)
        .values(**values, updated_at=Course.updated_at)
    )


async def recount_rating(session: AsyncSession, course_id: uuid.UUID) -> None:
    """Rewrite the rating summary from the reviews the course now has.

    Call while holding `lock_course`, after the review itself is flushed, and
    before the commit -- the summary and the row it summarises land together.
    """
    await _write(
        session,
        course_id,
        rating_avg=await session.scalar(_rating_avg(course_id)),
        rating_count=await session.scalar(_rating_count(course_id)),
    )


async def course_of_video(session: AsyncSession, video_asset_id: uuid.UUID) -> uuid.UUID | None:
    """The course a video counts towards, or None once nothing points at it --
    an asset replaced while it was still transcoding belongs to nobody."""
    return await session.scalar(
        select(CourseSection.course_id)
        .join(Lesson, Lesson.section_id == CourseSection.id)
        .where(Lesson.video_asset_id == video_asset_id)
    )


async def recount_duration(session: AsyncSession, course_id: uuid.UUID) -> None:
    """Rewrite the course's total video length from its ready videos.

    Flushes first, so the change that prompted the recount -- a video now
    ready, a lesson deleted -- is part of what gets counted. Call before the
    commit that ends the write.
    """
    await session.flush()
    await lock_course(session, course_id)
    await _write(
        session, course_id, duration_total_s=await session.scalar(_duration(course_id))
    )


# --- Rebuilding from scratch -----------------------------------------------


@dataclass(frozen=True, slots=True)
class Drift:
    """One stored number that disagreed with its rows."""

    course_id: uuid.UUID
    slug: str
    column: str
    stored: int | Decimal
    actual: int | Decimal


async def rebuild(
    session: AsyncSession,
    course_ids: list[uuid.UUID] | None = None,
    *,
    dry_run: bool = False,
) -> list[Drift]:
    """Recompute every stored number from its rows; report and fix what drifted.

    Every course when `course_ids` is None, soft-deleted ones included -- their
    rows still exist, and a restore should not bring back a wrong number. Does
    not commit: the caller decides, and `dry_run` writes nothing at all.

    The rows are locked before they are read, for the reason in the module
    docstring: a review or a transcode landing mid-rebuild waits, then recounts
    on top of what this wrote, instead of this overwriting its recount.
    """
    scope = [] if course_ids is None else [Course.id.in_(course_ids)]

    if not dry_run:
        await session.execute(
            select(Course.id).where(*scope).order_by(Course.id).with_for_update()
        )

    rows = await session.execute(
        select(
            Course.id,
            Course.slug,
            *(getattr(Course, column).label(f"stored_{column}") for column in _SOURCES),
            *(
                source(Course.id).scalar_subquery().label(f"actual_{column}")
                for column, source in _SOURCES.items()
            ),
        )
        .where(*scope)
        .order_by(Course.slug)
    )

    drifts: list[Drift] = []
    corrections: dict[uuid.UUID, dict[str, object]] = {}

    for row in rows.mappings():
        for column in _SOURCES:
            stored, actual = row[f"stored_{column}"], row[f"actual_{column}"]
            if stored != actual:
                drifts.append(Drift(row["id"], row["slug"], column, stored, actual))
                corrections.setdefault(row["id"], {})[column] = actual

    if not dry_run:
        for course_id, values in corrections.items():
            await _write(session, course_id, **values)

    return drifts
