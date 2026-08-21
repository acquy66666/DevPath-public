"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import NotAuthenticatedError, PermissionDeniedError
from app.core.security import TokenError, decode_access_token
from app.models import User

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False: FastAPI's own 403 would bypass the shared error envelope,
# and a missing header is a 401 here, not a 403.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """The signed-in user, from the Bearer access token.

    Every failure -- no header, wrong scheme, bad signature, expired, deleted or
    locked account -- comes back as the same 401. Distinguishing them would only
    tell an attacker which part of a forged token to fix next.
    """
    if credentials is None:
        raise NotAuthenticatedError("Chưa đăng nhập")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise NotAuthenticatedError("Phiên đăng nhập không hợp lệ") from exc

    user = await session.get(User, payload.user_id)
    if user is None or user.locked_at is not None:
        # The token may still be within its 15 minutes; the account is not.
        raise NotAuthenticatedError("Phiên đăng nhập không hợp lệ")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    """Dependency factory: let only these roles through.

    Roles are matched exactly -- `require_role("instructor")` does not quietly
    admit admins. An endpoint meant for both says so: `require_role("instructor",
    "admin")`. A hierarchy where the top role silently satisfies every check is
    the kind of rule that is easy to write once and impossible to remember at
    every endpoint afterwards.

    The role comes from the database row, not from the token claim: taking a
    role away then takes effect at once instead of whenever the access token
    happens to expire.

    Authorization *rules* live here, but ownership checks ("is this your
    course?") stay in the service layer -- they need the thing being touched.
    """

    async def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError("Bạn không có quyền thực hiện thao tác này")
        return current_user

    return dependency


__all__ = ["CurrentUser", "DbSession", "get_current_user", "get_db", "require_role"]
