"""Applying to teach: a learner asks, an admin decides.

Until November 2026 `POST /users/me/instructor` turned any account into an
instructor on the spot. Now a learner sends an application (with an optional
introduction) and an admin approves or rejects it; **`users.role` changes only
on approval**, in the same transaction that records the decision and tells the
learner (`notifications.add`), so a decision nobody hears about cannot happen.

* Only a student may apply. An instructor already has what they would ask for
  (409 `ALREADY_INSTRUCTOR`); an admin would *lose* rights, so that is refused
  as `ROLE_CHANGE_NOT_ALLOWED`, the same code the old route used.
* One pending application at a time (409 `INSTRUCTOR_APPLICATION_PENDING`);
  after a rejection the learner may apply again.
* A rejection needs a reason the learner reads, like a rejected course.

The application row is locked (`FOR UPDATE`) before its status is read: two
admins deciding the same application must not both succeed, and the second is
told it has already been decided.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import DomainError
from app.models import (
    NOTIFICATION_INSTRUCTOR_APPLICATION_APPROVED,
    NOTIFICATION_INSTRUCTOR_APPLICATION_REJECTED,
    Enrollment,
    InstructorApplication,
    User,
)
from app.schemas.instructor_applications import ApplicationStatusFilter
from app.services import notifications as notifications_service
from app.services.users import RoleChangeNotAllowedError


class AlreadyInstructorError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ALREADY_INSTRUCTOR"


class ApplicationPendingError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "INSTRUCTOR_APPLICATION_PENDING"


class ApplicationNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "INSTRUCTOR_APPLICATION_NOT_FOUND"


class ApplicationDecidedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "INSTRUCTOR_APPLICATION_DECIDED"


# --- The learner's side ----------------------------------------------------


async def latest_for(session: AsyncSession, user: User) -> InstructorApplication | None:
    """The caller's most recent application, whatever became of it.

    A pending one is the latest by definition (only one waits at a time, and
    it is always the newest); putting it first also keeps the answer right
    when two rows share a `created_at` -- `now()` is the transaction's clock.
    """
    return await session.scalar(
        select(InstructorApplication)
        .where(InstructorApplication.user_id == user.id)
        .order_by(
            (InstructorApplication.status == "pending").desc(),
            InstructorApplication.created_at.desc(),
            InstructorApplication.id.desc(),
        )
        .limit(1)
    )


async def apply(
    session: AsyncSession, user: User, *, motivation: str | None
) -> InstructorApplication:
    """Send an application. Changes no role."""
    if user.role == "instructor":
        raise AlreadyInstructorError("Tài khoản của bạn đã là giảng viên")
    if user.role != "student":
        raise RoleChangeNotAllowedError(
            "Chỉ tài khoản học viên mới gửi yêu cầu trở thành giảng viên được"
        )

    pending = await session.scalar(
        select(InstructorApplication.id).where(
            InstructorApplication.user_id == user.id,
            InstructorApplication.status == "pending",
        )
    )
    if pending is not None:
        raise ApplicationPendingError("Yêu cầu trước của bạn đang chờ quản trị viên duyệt")

    application = InstructorApplication(user_id=user.id, motivation=motivation)
    session.add(application)
    try:
        await session.commit()
    except IntegrityError as error:
        # Two tabs at once: the partial unique index let one through.
        await session.rollback()
        if "uq_instructor_applications_pending" in str(error.orig):
            raise ApplicationPendingError(
                "Yêu cầu trước của bạn đang chờ quản trị viên duyệt"
            ) from error
        raise
    await session.refresh(application)
    return application


# --- The admin's side ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdminApplication:
    application: InstructorApplication
    applicant: User
    enrollments_count: int
    earlier_rejections: int


def _listing() -> Select:
    enrollments_count = (
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.user_id == InstructorApplication.user_id)
        .scalar_subquery()
    )
    earlier = aliased(InstructorApplication)
    earlier_rejections = (
        select(func.count())
        .select_from(earlier)
        .where(
            earlier.user_id == InstructorApplication.user_id,
            earlier.status == "rejected",
            earlier.id != InstructorApplication.id,
            earlier.created_at <= InstructorApplication.created_at,
        )
        .scalar_subquery()
    )
    return select(InstructorApplication, User, enrollments_count, earlier_rejections).join(
        User, User.id == InstructorApplication.user_id
    )


def _view(row) -> AdminApplication:
    application, applicant, enrollments_count, earlier_rejections = row
    return AdminApplication(
        application=application,
        applicant=applicant,
        enrollments_count=enrollments_count or 0,
        earlier_rejections=earlier_rejections or 0,
    )


async def pending_count(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(InstructorApplication)
            .where(InstructorApplication.status == "pending")
        )
        or 0
    )


async def list_applications(
    session: AsyncSession,
    *,
    status: ApplicationStatusFilter,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AdminApplication], int]:
    """The queue by default, oldest first; decided ones most recent first."""
    listing = _listing()
    if status != "all":
        listing = listing.where(InstructorApplication.status == status)
    if q:
        listing = listing.where(
            or_(
                User.full_name.icontains(q, autoescape=True),
                User.email.icontains(q, autoescape=True),
            )
        )

    total = await session.scalar(select(func.count()).select_from(listing.subquery()))

    if status == "pending":
        listing = listing.order_by(InstructorApplication.created_at.asc(), InstructorApplication.id)
    else:
        listing = listing.order_by(
            func.coalesce(
                InstructorApplication.decided_at, InstructorApplication.created_at
            ).desc(),
            InstructorApplication.id,
        )

    rows = await session.execute(listing.offset((page - 1) * page_size).limit(page_size))
    return [_view(row) for row in rows], total or 0


async def get_application(session: AsyncSession, application_id: uuid.UUID) -> AdminApplication:
    row = (
        await session.execute(
            _listing()
            .where(InstructorApplication.id == application_id)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise ApplicationNotFoundError("Không tìm thấy yêu cầu")
    return _view(row)


async def _locked_pending(
    session: AsyncSession, application_id: uuid.UUID
) -> InstructorApplication:
    application = await session.scalar(
        select(InstructorApplication)
        .where(InstructorApplication.id == application_id)
        .with_for_update()
    )
    if application is None:
        raise ApplicationNotFoundError("Không tìm thấy yêu cầu")
    if application.status != "pending":
        raise ApplicationDecidedError("Yêu cầu này đã được quyết định trước đó")
    return application


async def approve(
    session: AsyncSession, application_id: uuid.UUID, admin: User
) -> AdminApplication:
    """pending -> approved, and the applicant becomes an instructor."""
    application = await _locked_pending(session, application_id)
    applicant = await session.scalar(
        select(User).where(User.id == application.user_id).with_for_update()
    )
    if applicant.role != "student":
        # Not reachable through the API today (only an approval makes an
        # instructor), but a role changed by hand must not be overwritten.
        raise RoleChangeNotAllowedError(
            f"Tài khoản này đang là '{applicant.role}', không duyệt thành giảng viên được"
        )

    application.status = "approved"
    application.decided_by = admin.id
    application.decided_at = datetime.now(tz=UTC)
    # NULL instructor_tier_id is the first tier (models/instructor_tier.py).
    applicant.role = "instructor"

    notifications_service.add(
        session,
        user_id=applicant.id,
        type=NOTIFICATION_INSTRUCTOR_APPLICATION_APPROVED,
        payload={"application_id": str(application.id)},
    )
    await session.commit()
    return await get_application(session, application.id)


async def reject(
    session: AsyncSession, application_id: uuid.UUID, admin: User, reason: str
) -> AdminApplication:
    """pending -> rejected, with the reason. The learner may apply again."""
    application = await _locked_pending(session, application_id)

    application.status = "rejected"
    application.decided_by = admin.id
    application.decided_at = datetime.now(tz=UTC)
    application.rejection_reason = reason

    notifications_service.add(
        session,
        user_id=application.user_id,
        type=NOTIFICATION_INSTRUCTOR_APPLICATION_REJECTED,
        payload={"application_id": str(application.id), "reason": reason},
    )
    await session.commit()
    return await get_application(session, application.id)
