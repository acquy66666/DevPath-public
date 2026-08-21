"""HTTP plumbing shared by the routers that hand out sessions.

Two routers issue refresh tokens now -- `auth` on sign-in, `users` after a
password change -- and a refresh cookie written with different flags in two
places is a bug waiting for the one browser that notices. The rules live here
once.

Not business logic: these functions only translate between HTTP and what the
service layer already decided.
"""

from fastapi import Request, Response

from app.core.config import get_settings
from app.schemas.auth import TokenOut, UserOut
from app.services.auth import ClientInfo, IssuedTokens

# The cookie is scoped to the endpoints that read it. A cookie that is not sent
# anywhere else cannot be used for CSRF against anything else.
REFRESH_COOKIE_PATH = "/api/v1/auth"

# refresh_tokens.user_agent is VARCHAR(255); browsers send longer strings.
MAX_USER_AGENT_LENGTH = 255


def client_info(request: Request) -> ClientInfo:
    """Device details for the "signed-in devices" list. Informational only."""
    user_agent = request.headers.get("user-agent")
    return ClientInfo(
        user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
        ip_address=request.client.host if request.client else None,
    )


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        # Off on localhost only: a Secure cookie is never sent over plain http,
        # which would break the whole flow in development.
        secure=settings.cookie_secure,
        # lax, not strict: arriving from a Google search result must not look
        # like a signed-out user. Not none either -- that invites CSRF.
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().refresh_cookie_name, path=REFRESH_COOKIE_PATH)


def token_response(response: Response, tokens: IssuedTokens) -> TokenOut:
    """Body for the client, cookie for the browser."""
    set_refresh_cookie(response, tokens.refresh_token)
    return TokenOut(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(tokens.user),
    )
