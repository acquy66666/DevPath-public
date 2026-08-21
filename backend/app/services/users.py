"""User account changes people make to themselves."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import User


class RoleChangeNotAllowedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ROLE_CHANGE_NOT_ALLOWED"


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
