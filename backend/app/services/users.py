"""User account changes people make to themselves."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.security import hash_password, verify_password
from app.models import User
from app.services.auth import ClientInfo, IssuedTokens, replace_all_sessions


class RoleChangeNotAllowedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ROLE_CHANGE_NOT_ALLOWED"


class PasswordNotSetError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "PASSWORD_NOT_SET"


class InvalidCurrentPasswordError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_CURRENT_PASSWORD"


class PasswordUnchangedError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "PASSWORD_UNCHANGED"


async def promote_to_instructor(session: AsyncSession, user: User) -> User:
    """Turn a student into an instructor, at their own request.

    Teaching is opt-in and self-service: this platform has no application queue
    for it, and an admin gate would only be a queue nobody drains. What keeps
    it honest is downstream -- a new instructor's courses still start as drafts
    and go through review before anyone can see them.

    Asking again once you already are one is not an error: two tabs and two
    clicks should not produce a scary message.
    """
    if user.role == "instructor":
        return user

    if user.role != "student":
        # An admin already outranks this in every check, so "promoting" them
        # would take rights away. Refuse rather than answer 200 and do nothing.
        raise RoleChangeNotAllowedError(
            "Chỉ tài khoản học viên mới có thể tự nâng cấp thành giảng viên"
        )

    user.role = "instructor"
    await session.commit()
    return user


async def update_profile(session: AsyncSession, user: User, *, full_name: str) -> User:
    """Edit the caller's own profile. Only the fields in the schema can move."""
    user.full_name = full_name
    await session.commit()
    return user


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Replace the password, then start the sessions over.

    The current password is required even though the caller is already signed
    in: an access token can be fifteen minutes old and belong to whoever sat
    down at an unlocked laptop, while the password is something only its owner
    knows.

    Returns a fresh token pair -- every other session of this user has just
    been revoked, including the refresh token this device was holding.
    """
    if user.password_hash is None:
        # A Google-only account. There is nothing to verify against, and
        # setting a first password is a different flow with its own checks.
        raise PasswordNotSetError(
            "Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu để đổi"
        )

    if not verify_password(current_password, user.password_hash):
        raise InvalidCurrentPasswordError("Mật khẩu hiện tại không đúng")

    if verify_password(new_password, user.password_hash):
        raise PasswordUnchangedError("Mật khẩu mới phải khác mật khẩu hiện tại")

    user.password_hash = hash_password(new_password)
    tokens = await replace_all_sessions(session, user, client)
    await session.commit()
    return tokens
