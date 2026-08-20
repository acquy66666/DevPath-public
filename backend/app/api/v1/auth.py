"""Email + password authentication.

Two tokens, two channels, on purpose:

* the **access token** goes back in the JSON body. The SPA keeps it in memory
  and sends it as `Authorization: Bearer`. It expires in minutes, so a leak is
  short-lived;
* the **refresh token** goes back only in an HttpOnly cookie. JavaScript cannot
  read it, so an XSS bug on the frontend cannot walk off with a 30-day session.

The cookie is scoped to this router's path: no other endpoint has any use for
it, and a cookie that is not sent cannot be used for CSRF against them.
"""

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service
from app.services.auth import ClientInfo, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/api/v1/auth"

# users.user_agent is VARCHAR(255); browsers send longer strings than that.
MAX_USER_AGENT_LENGTH = 255


def _client_info(request: Request) -> ClientInfo:
    """Device details for the "signed-in devices" list. Informational only."""
    user_agent = request.headers.get("user-agent")
    return ClientInfo(
        user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
        ip_address=request.client.host if request.client else None,
    )


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
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


def _token_response(response: Response, tokens: IssuedTokens) -> TokenOut:
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenOut(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(tokens.user),
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    session: DbSession,
) -> TokenOut:
    """Create a student account and sign it in. Public by design.

    Instructor and admin accounts are never created here: the role is set by
    the service, so `"role": "admin"` in the body is simply ignored.
    """
    tokens = await auth_service.register_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        client=_client_info(request),
    )
    return _token_response(response, tokens)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: DbSession,
) -> TokenOut:
    """Sign in with email and password. Public by design.

    Other devices stay signed in -- each sign-in opens its own session row.
    """
    tokens = await auth_service.authenticate_user(
        session,
        email=payload.email,
        password=payload.password,
        client=_client_info(request),
    )
    return _token_response(response, tokens)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, session: DbSession) -> TokenOut:
    """Exchange the refresh cookie for a new access token and a new cookie.

    Public by design: the cookie *is* the credential, and an expired access
    token must not stand in the way of renewing it.
    """
    settings = get_settings()
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise auth_service.RefreshTokenMissingError("Không tìm thấy phiên đăng nhập")

    try:
        tokens = await auth_service.rotate_refresh_token(
            session, raw_token=raw_token, client=_client_info(request)
        )
    except auth_service.DomainError:
        # The cookie is spent either way; leaving it in the browser only means
        # the next call fails the same way.
        response.delete_cookie(settings.refresh_cookie_name, path=REFRESH_COOKIE_PATH)
        raise

    return _token_response(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: DbSession) -> Response:
    """Revoke this device's session. Idempotent, and never an error.

    Public by design: signing out must work even once the access token has
    expired, which is exactly when people close a shared browser.
    """
    settings = get_settings()
    await auth_service.revoke_session(
        session, raw_token=request.cookies.get(settings.refresh_cookie_name)
    )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.refresh_cookie_name, path=REFRESH_COOKIE_PATH)
    return response


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """The signed-in user's own profile."""
    return UserOut.model_validate(current_user)
