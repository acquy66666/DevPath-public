"""The admin's screens: course review queue, accounts, reports.

Every route requires `role='admin'` and nothing else -- there is no ownership
to check, the admin acts on the whole platform. The rules about *what* may be
done (which status moves where, who cannot be locked, which report is still
open) live in the services.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, require_role
from app.models import User
from app.schemas.admin import (
    AdminCourseOut,
    AdminCourseStatus,
    AdminPersonOut,
    AdminReportOut,
    AdminSummaryOut,
    AdminUserOut,
    CourseDecisionIn,
    ReportCourseRef,
    ReportDismissIn,
    ReportResolveIn,
    ReportTargetOut,
)
from app.schemas.categories import CategoryOut
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.reports import ReportTargetType
from app.services import admin_users as users_service
from app.services import moderation as moderation_service
from app.services import reports as reports_service
from app.services.tasks import TaskQueue, get_task_queue

router = APIRouter(prefix="/admin", tags=["admin"])

Admin = Annotated[User, Depends(require_role("admin"))]
#: Celery, and overridden in tests.
Queue = Annotated[TaskQueue, Depends(get_task_queue)]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Search = Annotated[str | None, Query(max_length=100)]


@router.get("/summary", response_model=AdminSummaryOut)
async def get_summary(_: Admin, session: DbSession) -> AdminSummaryOut:
    """The numbers on the admin's tabs: what is waiting for a decision."""
    return AdminSummaryOut(
        pending_courses=await moderation_service.pending_count(session),
        pending_reports=await reports_service.pending_count(session),
        locked_users=await users_service.locked_count(session),
    )


# --- Courses ---------------------------------------------------------------


def _course_out(item: moderation_service.AdminCourse) -> AdminCourseOut:
    course = item.course
    return AdminCourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        subtitle=course.subtitle,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        price=course.price,
        level=course.level,
        status=course.status,
        rejection_reason=course.rejection_reason,
        published_at=course.published_at,
        created_at=course.created_at,
        updated_at=course.updated_at,
        duration_total_s=course.duration_total_s,
        lessons_count=item.lessons_count,
        students_count=course.students_count,
        instructor=AdminPersonOut.model_validate(item.instructor),
        category=CategoryOut.model_validate(item.category),
    )


@router.get("/courses", response_model=Page[AdminCourseOut])
async def list_courses(
    _: Admin,
    session: DbSession,
    status: AdminCourseStatus = "pending_review",
    q: Search = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminCourseOut]:
    """The review queue by default -- longest waiting first. Search matches the
    title or the instructor's name or email."""
    items, total = await moderation_service.list_courses(
        session, status=status, q=q, page=page, page_size=page_size
    )
    return Page[AdminCourseOut](
        items=[_course_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.get("/courses/{course_id}", response_model=AdminCourseOut)
async def get_course(course_id: uuid.UUID, _: Admin, session: DbSession) -> AdminCourseOut:
    """One course in any status. Its curriculum and lessons are read through the
    ordinary course endpoints, which already open everything to an admin."""
    return _course_out(await moderation_service.get_course(session, course_id))


@router.post("/courses/{course_id}/approve", response_model=AdminCourseOut)
async def approve_course(
    course_id: uuid.UUID, _: Admin, session: DbSession, queue: Queue
) -> AdminCourseOut:
    """pending_review -> published. Schedules the chatbot ingest and the course
    embedding, and tells the instructor."""
    return _course_out(await moderation_service.approve(session, course_id, queue))


@router.post("/courses/{course_id}/reject", response_model=AdminCourseOut)
async def reject_course(
    course_id: uuid.UUID, body: CourseDecisionIn, _: Admin, session: DbSession
) -> AdminCourseOut:
    """pending_review -> rejected, with the reason the instructor reads."""
    return _course_out(await moderation_service.reject(session, course_id, body.reason))


@router.post("/courses/{course_id}/take-down", response_model=AdminCourseOut)
async def take_down_course(
    course_id: uuid.UUID, body: CourseDecisionIn, _: Admin, session: DbSession
) -> AdminCourseOut:
    """published -> draft: off the platform, with the reason. Enrolments stay."""
    return _course_out(await moderation_service.take_down(session, course_id, body.reason))


# --- Users -----------------------------------------------------------------


def _user_out(item: users_service.AdminUser) -> AdminUserOut:
    user = item.user
    return AdminUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        role=user.role,
        locked_at=user.locked_at,
        oauth_provider=user.oauth_provider,
        has_password=user.has_password,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        courses_count=item.courses_count,
        enrollments_count=item.enrollments_count,
    )


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    _: Admin,
    session: DbSession,
    q: Search = None,
    role: users_service.RoleFilter = "all",
    lock: users_service.LockFilter = "all",
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminUserOut]:
    """Every account, newest first. `lock=locked` lists the locked ones."""
    items, total = await users_service.list_users(
        session, q=q, role=role, lock=lock, page=page, page_size=page_size
    )
    return Page[AdminUserOut](
        items=[_user_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.post("/users/{user_id}/lock", response_model=AdminUserOut)
async def lock_user(user_id: uuid.UUID, _: Admin, session: DbSession) -> AdminUserOut:
    """Block sign-in and end every session now. Admin accounts cannot be locked."""
    return _user_out(await users_service.lock(session, user_id))


@router.post("/users/{user_id}/unlock", response_model=AdminUserOut)
async def unlock_user(user_id: uuid.UUID, _: Admin, session: DbSession) -> AdminUserOut:
    return _user_out(await users_service.unlock(session, user_id))


# --- Reports ---------------------------------------------------------------


def _report_out(item: reports_service.AdminReport) -> AdminReportOut:
    report, target = item.report, item.target
    return AdminReportOut(
        id=report.id,
        target_type=report.target_type,
        target_id=report.target_id,
        reason=report.reason,
        details=report.details,
        status=report.status,
        created_at=report.created_at,
        reporter=AdminPersonOut.model_validate(item.reporter),
        target=ReportTargetOut(
            exists=target.exists,
            title=target.title,
            excerpt=target.excerpt,
            rating=target.rating,
            author=AdminPersonOut.model_validate(target.author) if target.author else None,
            course=ReportCourseRef.model_validate(target.course) if target.course else None,
            lesson_id=target.lesson_id,
            thread_id=target.thread_id,
        ),
        pending_on_target=item.pending_on_target,
        resolved_at=report.resolved_at,
        resolved_by=AdminPersonOut.model_validate(item.resolver) if item.resolver else None,
        resolution_note=report.resolution_note,
        content_removed=report.content_removed,
    )


@router.get("/reports", response_model=Page[AdminReportOut])
async def list_reports(
    _: Admin,
    session: DbSession,
    status: reports_service.ReportStatusFilter = "pending",
    target_type: ReportTargetType | None = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminReportOut]:
    """Pending reports oldest first, or closed ones newest decision first --
    each with the reported content as it is now."""
    items, total = await reports_service.list_for_admin(
        session, status_filter=status, target_type=target_type, page=page, page_size=page_size
    )
    return Page[AdminReportOut](
        items=[_report_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.post("/reports/{report_id}/review", response_model=AdminReportOut)
async def start_review(report_id: uuid.UUID, _: Admin, session: DbSession) -> AdminReportOut:
    """open -> reviewing: mark that somebody is looking at it."""
    return _report_out(await reports_service.start_review(session, report_id))


@router.post("/reports/{report_id}/resolve", response_model=AdminReportOut)
async def resolve_report(
    report_id: uuid.UUID, body: ReportResolveIn, admin: Admin, session: DbSession
) -> AdminReportOut:
    """The report was right. `remove_content` also takes the content down.
    Closes every pending report on the same content."""
    return _report_out(
        await reports_service.resolve(
            session, report_id, admin, note=body.note, remove_content=body.remove_content
        )
    )


@router.post("/reports/{report_id}/dismiss", response_model=AdminReportOut)
async def dismiss_report(
    report_id: uuid.UUID, body: ReportDismissIn, admin: Admin, session: DbSession
) -> AdminReportOut:
    """The content stays. Closes every pending report on it."""
    return _report_out(await reports_service.dismiss(session, report_id, admin, note=body.note))
