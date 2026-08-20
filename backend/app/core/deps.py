"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import NotAuthenticatedError
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

__all__ = ["CurrentUser", "DbSession", "get_current_user", "get_db"]
