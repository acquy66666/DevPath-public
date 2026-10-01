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

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.v1._transport import (
    REFRESH_COOKIE_PATH,
    clear_refresh_cookie,
    client_info,
    set_refresh_cookie,
    token_response,
)
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import DomainError
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service
from app.services.google_oauth import (
    GoogleAuthError,
    GoogleOAuthClient,
    get_google_oauth_client,
)
from app.services.rate_limit import RateLimiter, get_rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Half of the OAuth CSRF check: the other half rides in the URL Google sends
# the browser back with, and the two have to match.
STATE_COOKIE_NAME = "devpath_oauth_state"
STATE_TTL_SECONDS = 10 * 60

RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    session: DbSession,
    limiter: RateLimit,
) -> TokenOut:
    """Create a student account and sign it in. Public by design.

    Instructor and admin accounts are never created here: the role is set by
    the service, so `"role": "admin"` in the body is simply ignored. 429
    AUTH_RATE_LIMITED when one client creates too many accounts in an hour.
    """
    tokens = await auth_service.register_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        limiter=limiter,
        client=client_info(request),
    )
    return token_response(response, tokens)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: DbSession,
    limiter: RateLimit,
) -> TokenOut:
    """Sign in with email and password. Public by design.

    Other devices stay signed in -- each sign-in opens its own session row.
    429 AUTH_RATE_LIMITED after too many attempts at one address, or from one
    client, in fifteen minutes -- right password or not.
    """
    tokens = await auth_service.authenticate_user(
        session,
        email=payload.email,
        password=payload.password,
        limiter=limiter,
        client=client_info(request),
    )
    return token_response(response, tokens)


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
            session, raw_token=raw_token, client=client_info(request)
        )
    except auth_service.DomainError:
        # The cookie is spent either way; leaving it in the browser only means
        # the next call fails the same way.
        clear_refresh_cookie(response)
        raise

    return token_response(response, tokens)


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
    clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """The signed-in user's own profile."""
    return UserOut.model_validate(current_user)


# --- Google sign-in --------------------------------------------------------


def _frontend_error_redirect(code: str) -> RedirectResponse:
    """Send the browser back to the sign-in page with something to show.

    The callback is a top-level navigation, so an error here has to be a page
    the user can read and act on -- a JSON envelope would be a dead end. The
    frontend turns `loi` into a sentence using the same code table as every
    other error.
    """
    settings = get_settings()
    response = RedirectResponse(f"{settings.frontend_url}/dang-nhap?loi={code}")
    response.delete_cookie(STATE_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return response


@router.get("/google/authorize")
async def google_authorize(
    google: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
) -> RedirectResponse:
    """Start the Google flow. Public by design -- it is the way in.

    Answers 503 GOOGLE_OAUTH_NOT_CONFIGURED when no OAuth client has been set
    up for this deployment, which is the state of a fresh checkout.
    """
    state = secrets.token_urlsafe(32)

    response = RedirectResponse(google.authorization_url(state=state))
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=get_settings().cookie_secure,
        # Must survive Google's cross-site redirect back here, which lax allows
        # for a top-level GET navigation -- exactly what this is.
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: DbSession,
    google: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Where Google returns the browser. Public by design.

    Nothing here trusts the query string on its own: the state has to match the
    cookie this backend set, and the code is only worth anything to whoever
    also holds the client secret.
    """
    if error is not None:
        # The user pressed Cancel on the consent screen.
        return _frontend_error_redirect("GOOGLE_ACCESS_DENIED")

    expected_state = request.cookies.get(STATE_COOKIE_NAME)
    if not expected_state or not state or not secrets.compare_digest(state, expected_state):
        # No cookie, no state, or a state we never issued: this callback did not
        # start here.
        return _frontend_error_redirect("GOOGLE_STATE_INVALID")

    if not code:
        return _frontend_error_redirect(GoogleAuthError.code)

    try:
        identity = await google.exchange_code(code=code)
        tokens = await auth_service.sign_in_with_google(
            session, identity=identity, client=client_info(request)
        )
    except DomainError as exc:
        return _frontend_error_redirect(exc.code)

    settings = get_settings()
    response = RedirectResponse(settings.frontend_url)
    set_refresh_cookie(response, tokens.refresh_token)
    # One state, one use.
    response.delete_cookie(STATE_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return response
