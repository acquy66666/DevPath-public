"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, WebSocket
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


async def user_for_access_token(session: AsyncSession, token: str) -> User | None:
    """The account an access token stands for, or None if it stands for none.

    Answers with None rather than raising because not every transport has an
    error envelope to raise into -- a WebSocket handshake has a close code and
    nothing else. The HTTP dependency below turns None into the 401.
    """
    try:
        payload = decode_access_token(token)
    except TokenError:
        return None

    user = await session.get(User, payload.user_id)
    if user is None or user.locked_at is not None:
        # The token may still be within its 15 minutes; the account is not.
        return None

    return user


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

    user = await user_for_access_token(session, credentials.credentials)
    if user is None:
        raise NotAuthenticatedError("Phiên đăng nhập không hợp lệ")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    """The signed-in user, or None -- for endpoints that serve both.

    A published course is public, but its own instructor sees it before anyone
    else does, so the route has to know who is asking without demanding it. A
    broken or expired token reads as "nobody" rather than an error: the page
    behind it is public either way.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(session, credentials)
    except NotAuthenticatedError:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


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


#: How a token reaches a WebSocket.
#:
#: The browser's WebSocket API cannot set an `Authorization` header, so the
#: credential has to travel some other way. The usual answer -- a query string
#: -- writes a live access token into nginx's access log, into any error
#: report that includes the URL, and into whatever proxy is between the two.
#: The handshake's subprotocol list is a header (`Sec-WebSocket-Protocol`), it
#: is the one header the browser API does let a page set, and it is not logged
#: as part of the request line. So the client offers `["bearer", "<token>"]`
#: and the server accepts with `bearer`.
WEBSOCKET_BEARER = "bearer"


def websocket_token(websocket: WebSocket) -> str | None:
    """Pull the access token out of the handshake, or None if it is not there.

    Exactly two protocols, ours first: a longer list is not a client that
    happens to also want something else, it is a client this server does not
    understand, and guessing which entry is a credential is how a credential
    gets read out of the wrong field.
    """
    offered = websocket.scope.get("subprotocols") or []
    if len(offered) == 2 and offered[0] == WEBSOCKET_BEARER:
        return offered[1]
    return None


async def get_websocket_user(
    session: AsyncSession, websocket: WebSocket
) -> User | None:
    """The user behind a WebSocket handshake, or None for anyone unproven."""
    token = websocket_token(websocket)
    if token is None:
        return None
    return await user_for_access_token(session, token)


__all__ = [
    "WEBSOCKET_BEARER",
    "CurrentUser",
    "DbSession",
    "OptionalUser",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "get_websocket_user",
    "require_role",
    "user_for_access_token",
    "websocket_token",
]
