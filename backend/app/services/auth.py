"""Registration, sign-in, and refresh-token rotation.

Transaction boundary: every public function here commits its own work. The
router only translates the result into HTTP.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.services.google_oauth import GoogleIdentity
from app.services.rate_limit import RateLimiter


class EmailAlreadyRegisteredError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "EMAIL_ALREADY_REGISTERED"


class InvalidCredentialsError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"


class AccountLockedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "ACCOUNT_LOCKED"


class GoogleEmailNotVerifiedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "GOOGLE_EMAIL_NOT_VERIFIED"


class GoogleAccountConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "GOOGLE_ACCOUNT_CONFLICT"


class RefreshTokenMissingError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "REFRESH_TOKEN_MISSING"


class InvalidRefreshTokenError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_REFRESH_TOKEN"


class RefreshTokenReusedError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "REFRESH_TOKEN_REUSED"


class AuthRateLimitedError(DomainError):
    """Too many sign-ins, sign-ups or password changes, too fast.

    One code for all of them: the page answers each the same way, by showing
    the wait. The message says which door was knocked on too often.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "AUTH_RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


LOGIN_EMAIL_KEY = "auth:login:email:{email}"
LOGIN_IP_KEY = "auth:login:ip:{ip}"
REGISTER_IP_KEY = "auth:register:ip:{ip}"
PASSWORD_CHANGE_KEY = "auth:password:user:{user}"


def _minutes(seconds: int) -> int:
    """A wait as people say it: never "0 phút"."""
    return seconds // 60 + 1


async def enforce_login_limits(
    limiter: RateLimiter, *, email: str, ip_address: str | None
) -> None:
    """Count this attempt against the client and against the account.

    Every attempt counts, the successful ones too. Counting only failures
    would need a second round trip after bcrypt, and ten sign-ins to one
    account in a quarter of an hour is not something a person does.

    The account key is the address whether or not an account exists behind
    it, so a refusal here says nothing about who is a member. It does let a
    stranger hold one address's sign-in shut for a window -- the price of
    stopping guesses at it, paid in minutes, with Google sign-in still open.
    """
    settings = get_settings()
    window = settings.login_window_seconds

    if ip_address:
        wait = await limiter.count(
            LOGIN_IP_KEY.format(ip=ip_address), settings.login_attempts_per_ip, window
        )
        if wait:
            raise AuthRateLimitedError(
                "Có quá nhiều lần đăng nhập từ mạng này. "
                f"Thử lại sau khoảng {_minutes(wait)} phút.",
                retry_after=wait,
            )

    wait = await limiter.count(
        LOGIN_EMAIL_KEY.format(email=email.lower()), settings.login_attempts_per_email, window
    )
    if wait:
        raise AuthRateLimitedError(
            "Email này vừa được thử đăng nhập quá nhiều lần. "
            f"Thử lại sau khoảng {_minutes(wait)} phút.",
            retry_after=wait,
        )


async def enforce_registration_limit(limiter: RateLimiter, *, ip_address: str | None) -> None:
    """Count one sign-up against the client, against a script filling the table."""
    if not ip_address:
        return

    settings = get_settings()
    wait = await limiter.count(
        REGISTER_IP_KEY.format(ip=ip_address),
        settings.registrations_per_ip,
        settings.registration_window_seconds,
    )
    if wait:
        raise AuthRateLimitedError(
            "Có quá nhiều tài khoản vừa được tạo từ mạng này. "
            f"Thử lại sau khoảng {_minutes(wait)} phút.",
            retry_after=wait,
        )


async def enforce_password_change_limit(limiter: RateLimiter, user_id: uuid.UUID) -> None:
    """Count one attempt at the current password, against guessing it."""
    settings = get_settings()
    wait = await limiter.count(
        PASSWORD_CHANGE_KEY.format(user=user_id),
        settings.password_changes_per_user,
        settings.login_window_seconds,
    )
    if wait:
        raise AuthRateLimitedError(
            "Bạn vừa thử đổi mật khẩu quá nhiều lần. "
            f"Thử lại sau khoảng {_minutes(wait)} phút.",
            retry_after=wait,
        )


@dataclass(frozen=True)
class IssuedTokens:
    """What a successful sign-in produces.

    `refresh_token` is the raw value and exists only long enough for the router
    to put it in a cookie -- the database has its hash and nothing else.
    """

    user: User
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True)
class ClientInfo:
    """Whatever the request can tell us about the device, for the sessions list."""

    user_agent: str | None = None
    ip_address: str | None = None


@lru_cache
def _timing_decoy_hash() -> str:
    """A real bcrypt hash to check unknown emails against.

    Returning early for an address with no account would make sign-in visibly
    faster for it, which is a way to ask whether someone is a member here.
    Computed once, on first use rather than at import.
    """
    return hash_password("timing-decoy-never-a-real-password")


async def _issue_tokens(
    session: AsyncSession,
    user: User,
    client: ClientInfo,
) -> IssuedTokens:
    """Mint an access token and open a new session row. Does not commit."""
    settings = get_settings()
    raw_refresh = generate_refresh_token()

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_ttl_days),
            user_agent=client.user_agent,
            ip_address=client.ip_address,
        )
    )

    return IssuedTokens(
        user=user,
        access_token=create_access_token(user.id, user.role),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


async def revoke_all_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Sign this account out everywhere: every refresh token it holds stops working.

    Access tokens are not tracked, so they live out their 15 minutes -- which is
    why the access-token check also reads `users.locked_at`. Does not commit.
    """
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(tz=UTC))
    )


async def replace_all_sessions(
    session: AsyncSession,
    user: User,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Revoke every session this user has and open exactly one fresh one.

    What a password change should do: the reason most people change a password
    is that someone else may have it, so every other device is signed out --
    while the device doing the changing is not, which would be a strange
    punishment for doing the right thing.

    Does not commit; the caller owns the transaction.
    """
    await revoke_all_sessions(session, user.id)
    return await _issue_tokens(session, user, client or ClientInfo())


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    limiter: RateLimiter,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Create a student account and sign it in.

    Role is not a parameter on purpose: an account cannot be born an instructor
    or an admin, whatever the request body says.
    """
    client = client or ClientInfo()
    await enforce_registration_limit(limiter, ip_address=client.ip_address)

    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegisteredError("Email này đã được đăng ký")

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="student",
    )
    session.add(user)
    # Flush before issuing: the refresh token row needs user.id, and the unique
    # index on email is the last word if two requests raced to here.
    await session.flush()

    tokens = await _issue_tokens(session, user, client)
    await session.commit()
    return tokens


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    limiter: RateLimiter,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Verify a password and open a session. Existing sessions stay open.

    The limits are checked first, before the account is even looked up: a
    refused attempt costs a Redis round trip, not a bcrypt round.
    """
    client = client or ClientInfo()
    await enforce_login_limits(limiter, email=email, ip_address=client.ip_address)

    user = await session.scalar(select(User).where(User.email == email))

    if user is None or user.password_hash is None:
        # No account, or a Google-only account with no password to check. Spend
        # the same time either way, and answer with the same error.
        verify_password(password, _timing_decoy_hash())
        raise InvalidCredentialsError("Email hoặc mật khẩu không đúng")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Email hoặc mật khẩu không đúng")

    if user.locked_at is not None:
        # Checked after the password so a locked account is not a way to learn
        # that the address exists.
        raise AccountLockedError("Tài khoản đã bị khóa, liên hệ quản trị viên")

    user.last_login_at = datetime.now(tz=UTC)
    tokens = await _issue_tokens(session, user, client)
    await session.commit()
    return tokens


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    raw_token: str,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Exchange a refresh token for a new pair, revoking the one presented.

    Rotation is what makes theft detectable: the honest client always holds the
    newest token, so a *revoked* one coming back means someone kept a copy.
    """
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if row is None:
        raise InvalidRefreshTokenError("Phiên đăng nhập không hợp lệ")

    if row.revoked_at is not None:
        # Either a stolen copy or a replay. We cannot tell which side is the
        # thief, so every session of this user goes.
        await revoke_all_sessions(session, row.user_id)
        await session.commit()
        raise RefreshTokenReusedError(
            "Phiên đăng nhập đã bị thu hồi, vui lòng đăng nhập lại"
        )

    if row.expires_at <= datetime.now(tz=UTC):
        raise InvalidRefreshTokenError("Phiên đăng nhập đã hết hạn")

    user = await session.get(User, row.user_id)
    if user is None:
        raise InvalidRefreshTokenError("Phiên đăng nhập không hợp lệ")
    if user.locked_at is not None:
        raise AccountLockedError("Tài khoản đã bị khóa, liên hệ quản trị viên")

    row.revoked_at = datetime.now(tz=UTC)
    tokens = await _issue_tokens(session, user, client or ClientInfo())
    await session.commit()
    return tokens


async def revoke_session(session: AsyncSession, *, raw_token: str | None) -> None:
    """Sign out. Idempotent: an unknown or already-revoked token is not an error."""
    if not raw_token:
        return

    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if row is None or row.revoked_at is not None:
        return

    row.revoked_at = datetime.now(tz=UTC)
    await session.commit()


async def sign_in_with_google(
    session: AsyncSession,
    *,
    identity: GoogleIdentity,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Sign in whoever Google just vouched for, creating or linking as needed.

    Three cases, in this order:

    1. `sub` already known -> that account, whatever its address says today.
       Google's subject identifier is the stable one; an address can be renamed
       or, on a Workspace domain, handed to a different person entirely.
    2. address already registered -> link Google to that account, but only if
       Google has verified the address. Without that check, anyone able to put
       an unverified address on a Google account could walk into someone else's
       account here. And if this platform never proved the address either --
       registration sends no confirmation mail -- the password on the account
       was chosen by whoever typed the address first, who need not be the
       person Google just vouched for. That password goes, with every session
       it opened (pre-account takeover).
    3. neither -> a new student account with no password.
    """
    email = identity.email.strip().lower()
    now = datetime.now(tz=UTC)

    user = await session.scalar(
        select(User).where(
            User.oauth_provider == "google", User.oauth_sub == identity.sub
        )
    )

    if user is not None:
        if user.locked_at is not None:
            raise AccountLockedError("Tài khoản đã bị khóa, liên hệ quản trị viên")

        if user.email != email and identity.email_verified:
            # The Google account was renamed. Follow it, unless somebody else
            # here already holds the new address -- and only to an address
            # Google has verified, or a Google account pointed at somebody
            # else's address would take that address here.
            clash = await session.scalar(
                select(User).where(User.email == email, User.id != user.id)
            )
            if clash is not None:
                raise GoogleAccountConflictError(
                    "Email mới của tài khoản Google đã thuộc về một tài khoản khác"
                )
            user.email = email
    else:
        if not identity.email_verified:
            raise GoogleEmailNotVerifiedError(
                "Google chưa xác thực email này nên không thể dùng để đăng nhập"
            )

        existing = await session.scalar(select(User).where(User.email == email))

        if existing is not None:
            if existing.oauth_sub is not None and existing.oauth_sub != identity.sub:
                raise GoogleAccountConflictError(
                    "Email này đã liên kết với một tài khoản Google khác"
                )
            if existing.locked_at is not None:
                raise AccountLockedError("Tài khoản đã bị khóa, liên hệ quản trị viên")

            if existing.email_verified_at is None:
                # Nothing ever proved this address belonged to whoever set the
                # password. Google just proved who it belongs to, so the
                # account is theirs, and a password somebody else may have
                # chosen -- with the sessions it opened -- no longer gets in.
                existing.password_hash = None
                await revoke_all_sessions(session, existing.id)

            # Otherwise linking adds a way in. It never touches the name or an
            # avatar the user chose for themselves.
            existing.oauth_provider = "google"
            existing.oauth_sub = identity.sub
            existing.email_verified_at = existing.email_verified_at or now
            existing.avatar_url = existing.avatar_url or identity.picture
            user = existing
        else:
            user = User(
                email=email,
                password_hash=None,
                # full_name is NOT NULL and Google does not always send a name.
                full_name=identity.full_name or email.split("@")[0],
                avatar_url=identity.picture,
                role="student",
                oauth_provider="google",
                oauth_sub=identity.sub,
                # Signing in through Google is the verification.
                email_verified_at=now,
            )
            session.add(user)
            await session.flush()

    user.last_login_at = now
    tokens = await _issue_tokens(session, user, client or ClientInfo())
    await session.commit()
    return tokens
