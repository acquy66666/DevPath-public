"""The admin's list of accounts, and the one thing done to them here: lock.

**What locking does.** `users.locked_at` set means the account cannot sign in
(password or Google), cannot refresh a session, and cannot use an access token
it already holds -- `auth.authenticate_user`, `auth.rotate_refresh_token`,
`auth.sign_in_with_google` and `deps.user_for_access_token` all read it. Locking
also revokes every refresh token right away, so the account's open tabs stop
at their next request instead of at their next refresh.

**What it does not do.** Nothing the account wrote is removed, and an
instructor's courses stay on sale: students who paid keep learning. Taking
content down is a separate, deliberate act (`services/moderation.py`,
`services/reports.py`).

**Admins cannot be locked** -- including by themselves. With one admin on the
platform, a mis-click would lock everybody out of this very screen, and there
is no screen above it to undo that from.

Both moves are idempotent: locking a locked account keeps the first
`locked_at`, which is the one that says when it happened.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Course, Enrollment, User
from app.services import auth as auth_service

RoleFilter = Literal["student", "instructor", "admin", "all"]
LockFilter = Literal["locked", "active", "all"]


class UserNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "USER_NOT_FOUND"


class CannotLockAdminError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_LOCK_ADMIN"


@dataclass(frozen=True, slots=True)
class AdminUser:
    user: User
    courses_count: int
    enrollments_count: int


def _listing() -> Select:
    courses_count = (
        select(func.count(Course.id))
        .where(Course.instructor_id == User.id, Course.deleted_at.is_(None))
        .scalar_subquery()
    )
    enrollments_count = (
        select(func.count(Enrollment.id)).where(Enrollment.user_id == User.id).scalar_subquery()
    )
    return select(User, courses_count, enrollments_count)


def _view(row) -> AdminUser:
    user, courses_count, enrollments_count = row
    return AdminUser(user=user, courses_count=courses_count, enrollments_count=enrollments_count)


async def list_users(
    session: AsyncSession,
    *,
    q: str | None,
    role: RoleFilter,
    lock: LockFilter,
    page: int,
    page_size: int,
) -> tuple[list[AdminUser], int]:
    """Newest accounts first; search matches name or email."""
    listing = _listing()
    if q:
        listing = listing.where(
            or_(
                User.full_name.icontains(q, autoescape=True),
                User.email.icontains(q, autoescape=True),
            )
        )
    if role != "all":
        listing = listing.where(User.role == role)
    if lock == "locked":
        listing = listing.where(User.locked_at.is_not(None))
    elif lock == "active":
        listing = listing.where(User.locked_at.is_(None))

    total = await session.scalar(select(func.count()).select_from(listing.subquery()))
    rows = await session.execute(
        listing.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [_view(row) for row in rows], total or 0


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> AdminUser:
    row = (
        await session.execute(
            _listing().where(User.id == user_id).execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise UserNotFoundError("Không tìm thấy người dùng")
    return _view(row)


async def _locked_row(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserNotFoundError("Không tìm thấy người dùng")
    return user


async def lock(session: AsyncSession, user_id: uuid.UUID) -> AdminUser:
    user = await _locked_row(session, user_id)
    if user.role == "admin":
        raise CannotLockAdminError("Không khóa được tài khoản quản trị")

    if user.locked_at is None:
        user.locked_at = datetime.now(tz=UTC)
    # Every time, not only the first: a session opened in the window between
    # two clicks would otherwise survive the second one.
    await auth_service.revoke_all_sessions(session, user.id)
    await session.commit()
    return await get_user(session, user.id)


async def unlock(session: AsyncSession, user_id: uuid.UUID) -> AdminUser:
    """Sign-in works again. Sessions revoked by the lock stay revoked."""
    user = await _locked_row(session, user_id)
    user.locked_at = None
    await session.commit()
    return await get_user(session, user.id)


async def locked_count(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(User).where(User.locked_at.is_not(None))
        )
        or 0
    )
