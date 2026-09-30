"""Reports: a learner flags something, an admin decides what happens to it.

**You can only report what you can see.** Each target type is checked with the
rule that already decides who may read it: a course through
`courses.get_course_for_viewer`, a review through the course it sits on, a Q&A
thread or reply through `qa.visible_thread`. A report on something invisible
would be a way to probe for content by id. Reporting your own words is refused.

**One pending report per person per target**, held by the partial unique
index and written as `INSERT ... ON CONFLICT DO NOTHING`, so a double click
cannot slip two rows in between a check and an insert.

**A decision is about the content, not one reporter.** Resolving or dismissing
closes *every* pending report on the same target in one `UPDATE`. Resolving can
also take the content down, in the same transaction as the reports closing:

* a course is **taken down** (`published -> draft`, instructor notified) --
  never deleted, since students who bought it keep their enrolment;
* a review is deleted and the course's rating recomputed, exactly as when its
  author withdraws it;
* a Q&A thread (with its replies) or a single reply is deleted.

`content_removed` records what actually happened: content that was already
gone, or a course that was no longer on sale, leaves it `false`.

**The admin sees the content as it is now**, looked up per type for the page of
reports being read. Nothing is copied at report time; a target deleted since
reads as "no longer exists", which is itself an answer.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import DomainError
from app.models import (
    REPORT_PENDING_STATUSES,
    Course,
    CourseSection,
    Lesson,
    QaReply,
    QaThread,
    Report,
    Review,
    User,
)
from app.services import course_stats, moderation
from app.services import courses as courses_service
from app.services import qa as qa_service

ReportStatusFilter = Literal["pending", "closed"]
TargetType = Literal["course", "review", "qa_thread", "qa_reply"]

#: How much of a long body the queue shows. The admin opens the link for more.
EXCERPT_LENGTH = 300

#: What the instructor reads when a course is taken down without a note.
DEFAULT_TAKE_DOWN_REASON = "Khóa học bị gỡ sau khi quản trị viên xử lý báo cáo vi phạm."


class ReportTargetNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "REPORT_TARGET_NOT_FOUND"


class OwnContentReportError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_REPORT_OWN_CONTENT"


class AlreadyReportedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ALREADY_REPORTED"


class ReportNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "REPORT_NOT_FOUND"


class ReportClosedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "REPORT_ALREADY_CLOSED"


# --- Filing a report -------------------------------------------------------


async def _author_of_visible_target(
    session: AsyncSession, target_type: TargetType, target_id: uuid.UUID, reporter: User
) -> uuid.UUID:
    """Who wrote the target -- if the reporter can see it at all."""
    try:
        if target_type == "course":
            course = await courses_service.get_course_for_viewer(session, target_id, reporter)
            return course.instructor_id
        if target_type == "review":
            review = await session.get(Review, target_id)
            if review is None:
                raise ReportTargetNotFoundError("Không tìm thấy nội dung cần báo cáo")
            await courses_service.get_course_for_viewer(session, review.course_id, reporter)
            return review.user_id
        if target_type == "qa_thread":
            thread = await qa_service.visible_thread(session, target_id, reporter)
            return thread.user_id
        reply = await session.get(QaReply, target_id)
        if reply is None:
            raise ReportTargetNotFoundError("Không tìm thấy nội dung cần báo cáo")
        await qa_service.visible_thread(session, reply.thread_id, reporter)
        return reply.user_id
    except DomainError as exc:
        # Each type has its own "not found" code; the reporter only needs one.
        # A 403 (a Q&A thread in a course they are not in) passes through.
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise ReportTargetNotFoundError("Không tìm thấy nội dung cần báo cáo") from None
        raise


async def create(
    session: AsyncSession,
    reporter: User,
    *,
    target_type: TargetType,
    target_id: uuid.UUID,
    reason: str,
    details: str | None,
) -> Report:
    author_id = await _author_of_visible_target(session, target_type, target_id, reporter)
    if author_id == reporter.id:
        raise OwnContentReportError("Bạn không thể báo cáo nội dung của chính mình")

    report_id = await session.scalar(
        insert(Report)
        .values(
            reporter_id=reporter.id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            details=details,
        )
        .on_conflict_do_nothing(
            index_elements=["reporter_id", "target_type", "target_id"],
            index_where=Report.status.in_(REPORT_PENDING_STATUSES),
        )
        .returning(Report.id)
    )
    if report_id is None:
        raise AlreadyReportedError(
            "Bạn đã báo cáo nội dung này, quản trị viên đang xem xét"
        )

    await session.commit()
    report = await session.get(Report, report_id)
    assert report is not None
    return report


# --- What the admin reads --------------------------------------------------


@dataclass(frozen=True, slots=True)
class TargetView:
    """The reported thing as it is now, or `exists=False`."""

    exists: bool
    title: str | None = None
    excerpt: str | None = None
    rating: int | None = None
    author: User | None = None
    course: Course | None = None
    lesson_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None


MISSING = TargetView(exists=False)


@dataclass(frozen=True, slots=True)
class AdminReport:
    report: Report
    reporter: User
    resolver: User | None
    target: TargetView
    #: Pending reports on the same target, this one included when pending.
    pending_on_target: int


def _excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text if len(text) <= EXCERPT_LENGTH else text[: EXCERPT_LENGTH - 1].rstrip() + "…"


async def _targets(
    session: AsyncSession, reports: list[Report]
) -> dict[tuple[str, uuid.UUID], TargetView]:
    """Look every target of one page up, one query per type."""
    ids: dict[str, set[uuid.UUID]] = {}
    for report in reports:
        ids.setdefault(report.target_type, set()).add(report.target_id)

    found: dict[tuple[str, uuid.UUID], TargetView] = {}

    if course_ids := ids.get("course"):
        rows = await session.execute(
            select(Course, User)
            .join(User, User.id == Course.instructor_id)
            .where(Course.id.in_(course_ids), Course.deleted_at.is_(None))
        )
        for course, author in rows:
            found["course", course.id] = TargetView(
                exists=True,
                title=course.title,
                excerpt=_excerpt(course.subtitle),
                author=author,
                course=course,
            )

    if review_ids := ids.get("review"):
        rows = await session.execute(
            select(Review, User, Course)
            .join(User, User.id == Review.user_id)
            .join(Course, Course.id == Review.course_id)
            .where(Review.id.in_(review_ids))
        )
        for review, author, course in rows:
            found["review", review.id] = TargetView(
                exists=True,
                excerpt=_excerpt(review.comment),
                rating=review.rating,
                author=author,
                course=course,
            )

    if thread_ids := ids.get("qa_thread"):
        rows = await session.execute(
            select(QaThread, User, Course)
            .join(User, User.id == QaThread.user_id)
            .join(Lesson, Lesson.id == QaThread.lesson_id)
            .join(CourseSection, CourseSection.id == Lesson.section_id)
            .join(Course, Course.id == CourseSection.course_id)
            .where(QaThread.id.in_(thread_ids))
        )
        for thread, author, course in rows:
            found["qa_thread", thread.id] = TargetView(
                exists=True,
                title=thread.title,
                excerpt=_excerpt(thread.body),
                author=author,
                course=course,
                lesson_id=thread.lesson_id,
                thread_id=thread.id,
            )

    if reply_ids := ids.get("qa_reply"):
        rows = await session.execute(
            select(QaReply, User, QaThread, Course)
            .join(User, User.id == QaReply.user_id)
            .join(QaThread, QaThread.id == QaReply.thread_id)
            .join(Lesson, Lesson.id == QaThread.lesson_id)
            .join(CourseSection, CourseSection.id == Lesson.section_id)
            .join(Course, Course.id == CourseSection.course_id)
            .where(QaReply.id.in_(reply_ids))
        )
        for reply, author, thread, course in rows:
            found["qa_reply", reply.id] = TargetView(
                exists=True,
                title=thread.title,
                excerpt=_excerpt(reply.body),
                author=author,
                course=course,
                lesson_id=thread.lesson_id,
                thread_id=thread.id,
            )

    return found


async def list_for_admin(
    session: AsyncSession,
    *,
    status_filter: ReportStatusFilter,
    target_type: TargetType | None,
    page: int,
    page_size: int,
) -> tuple[list[AdminReport], int]:
    """The queue (pending, oldest first) or the history (newest decision first)."""
    reporter = aliased(User)
    resolver = aliased(User)
    same_target = aliased(Report)
    pending_on_target = (
        select(func.count())
        .select_from(same_target)
        .where(
            same_target.target_type == Report.target_type,
            same_target.target_id == Report.target_id,
            same_target.status.in_(REPORT_PENDING_STATUSES),
        )
        .scalar_subquery()
    )

    listing = (
        select(Report, reporter, resolver, pending_on_target)
        .join(reporter, reporter.id == Report.reporter_id)
        .outerjoin(resolver, resolver.id == Report.resolved_by)
    )
    if status_filter == "pending":
        listing = listing.where(Report.status.in_(REPORT_PENDING_STATUSES)).order_by(
            Report.created_at.asc(), Report.id
        )
    else:
        listing = listing.where(Report.status.not_in(REPORT_PENDING_STATUSES)).order_by(
            Report.resolved_at.desc(), Report.id
        )
    if target_type is not None:
        listing = listing.where(Report.target_type == target_type)

    total = await session.scalar(
        select(func.count()).select_from(listing.order_by(None).subquery())
    )
    rows = (
        await session.execute(
            listing.offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        )
    ).all()

    targets = await _targets(session, [row[0] for row in rows])
    return [
        AdminReport(
            report=report,
            reporter=reporter_user,
            resolver=resolver_user,
            target=targets.get((report.target_type, report.target_id), MISSING),
            pending_on_target=count,
        )
        for report, reporter_user, resolver_user, count in rows
    ], total or 0


async def get_for_admin(session: AsyncSession, report_id: uuid.UUID) -> AdminReport:
    reporter = aliased(User)
    resolver = aliased(User)
    row = (
        await session.execute(
            select(Report, reporter, resolver)
            .join(reporter, reporter.id == Report.reporter_id)
            .outerjoin(resolver, resolver.id == Report.resolved_by)
            .where(Report.id == report_id)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise ReportNotFoundError("Không tìm thấy báo cáo")
    report, reporter_user, resolver_user = row

    pending = await session.scalar(
        select(func.count())
        .select_from(Report)
        .where(
            Report.target_type == report.target_type,
            Report.target_id == report.target_id,
            Report.status.in_(REPORT_PENDING_STATUSES),
        )
    )
    targets = await _targets(session, [report])
    return AdminReport(
        report=report,
        reporter=reporter_user,
        resolver=resolver_user,
        target=targets.get((report.target_type, report.target_id), MISSING),
        pending_on_target=pending or 0,
    )


async def pending_count(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.status.in_(REPORT_PENDING_STATUSES))
        )
        or 0
    )


# --- Deciding --------------------------------------------------------------


async def _pending(session: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await session.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if report is None:
        raise ReportNotFoundError("Không tìm thấy báo cáo")
    if report.status not in REPORT_PENDING_STATUSES:
        raise ReportClosedError("Báo cáo này đã được xử lý")
    return report


async def start_review(session: AsyncSession, report_id: uuid.UUID) -> AdminReport:
    """open -> reviewing: "somebody is on it". Idempotent while pending."""
    report = await _pending(session, report_id)
    report.status = "reviewing"
    await session.commit()
    return await get_for_admin(session, report.id)


async def _remove_target(
    session: AsyncSession, target_type: str, target_id: uuid.UUID, note: str | None
) -> bool:
    """Take the reported thing down. False if there was nothing left to remove."""
    if target_type == "course":
        course = await moderation.lock_course(session, target_id)
        if course is None or course.status != "published":
            return False
        await moderation.stage_take_down(session, course, note or DEFAULT_TAKE_DOWN_REASON)
        return True

    if target_type == "review":
        review = await session.get(Review, target_id)
        if review is None:
            return False
        course_id = review.course_id
        # Same order as the author withdrawing it: lock, delete, recount.
        await course_stats.lock_course(session, course_id)
        await session.delete(review)
        await session.flush()
        await course_stats.recount_rating(session, course_id)
        return True

    model = QaThread if target_type == "qa_thread" else QaReply
    row = await session.get(model, target_id)
    if row is None:
        return False
    # A thread takes its replies and votes with it (ON DELETE CASCADE).
    await session.delete(row)
    await session.flush()
    return True


async def _close_all(
    session: AsyncSession,
    report: Report,
    admin: User,
    *,
    status_to: Literal["resolved", "dismissed"],
    note: str | None,
    content_removed: bool,
) -> None:
    await session.execute(
        update(Report)
        .where(
            Report.target_type == report.target_type,
            Report.target_id == report.target_id,
            Report.status.in_(REPORT_PENDING_STATUSES),
        )
        .values(
            status=status_to,
            resolved_by=admin.id,
            resolved_at=datetime.now(tz=UTC),
            resolution_note=note,
            content_removed=content_removed,
        )
        # The rows are re-read with populate_existing; nothing to sync here.
        .execution_options(synchronize_session=False)
    )


async def resolve(
    session: AsyncSession,
    report_id: uuid.UUID,
    admin: User,
    *,
    note: str | None,
    remove_content: bool,
) -> AdminReport:
    """The report was right. Optionally take the content down with it."""
    report = await _pending(session, report_id)
    removed = False
    if remove_content:
        removed = await _remove_target(session, report.target_type, report.target_id, note)
    await _close_all(
        session, report, admin, status_to="resolved", note=note, content_removed=removed
    )
    await session.commit()
    return await get_for_admin(session, report.id)


async def dismiss(
    session: AsyncSession, report_id: uuid.UUID, admin: User, *, note: str | None
) -> AdminReport:
    """The content stays. Every pending report on it is closed."""
    report = await _pending(session, report_id)
    await _close_all(
        session, report, admin, status_to="dismissed", note=note, content_removed=False
    )
    await session.commit()
    return await get_for_admin(session, report.id)
