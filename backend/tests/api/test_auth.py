"""Email + password authentication.

Everything here goes through real HTTP against a real database inside a
transaction that is rolled back afterwards -- see tests/conftest.py.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_refresh_token, hash_password, hash_refresh_token
from app.models import RefreshToken, User
from app.services import auth as auth_service

COOKIE = get_settings().refresh_cookie_name
LEEWAY = get_settings().refresh_token_reuse_leeway_seconds

VALID = {
    "email": "hoc.vien@example.com",
    "password": "mật-khẩu-đủ-dài",
    "full_name": "Học Viên A",
}


async def register(client: AsyncClient, **overrides: str) -> Response:
    return await client.post("/api/v1/auth/register", json={**VALID, **overrides})


async def login(client: AsyncClient, **overrides: str) -> Response:
    payload = {"email": VALID["email"], "password": VALID["password"], **overrides}
    return await client.post("/api/v1/auth/login", json=payload)


def error_code(response: Response) -> str:
    return response.json()["detail"]["code"]


async def sessions_of(session: AsyncSession, user_id: str) -> list[RefreshToken]:
    rows = await session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    return list(rows)


async def live_sessions_of(session: AsyncSession, user_id: str) -> list[RefreshToken]:
    return [row for row in await sessions_of(session, user_id) if row.revoked_at is None]


async def rotated_seconds_ago(session: AsyncSession, raw: str, seconds: float) -> None:
    """Move a token's rotation into the past -- a replay that arrives long
    after the honest tabs have moved on, without a test that sleeps."""
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    )
    assert row is not None and row.revoked_at is not None
    row.revoked_at = datetime.now(tz=UTC) - timedelta(seconds=seconds)
    await session.flush()


# --- Register --------------------------------------------------------------


async def test_register_creates_a_student_and_returns_an_access_token(
    api_client: AsyncClient,
) -> None:
    response = await register(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == get_settings().access_token_ttl_minutes * 60
    assert body["user"]["email"] == VALID["email"]
    assert body["user"]["full_name"] == VALID["full_name"]
    assert body["user"]["role"] == "student"


async def test_register_never_returns_the_password_hash(api_client: AsyncClient) -> None:
    body = (await register(api_client)).json()

    # `has_password` is a boolean about the account, which is fine; the hash
    # itself and the plaintext are what must never appear.
    assert "password_hash" not in body["user"]
    assert "$2b$" not in str(body)
    assert VALID["password"] not in str(body)


async def test_register_stores_the_password_hashed(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)

    user = await db_session.scalar(select(User).where(User.email == VALID["email"]))
    assert user is not None
    assert user.password_hash != VALID["password"]
    assert user.password_hash.startswith("$2b$")


async def test_register_sets_an_httponly_refresh_cookie(api_client: AsyncClient) -> None:
    """The refresh token must be unreachable from JavaScript.

    XSS on the SPA would otherwise hand an attacker a 30-day session.
    """
    response = await register(api_client)

    raw = response.headers["set-cookie"]
    assert COOKIE in raw
    assert "HttpOnly" in raw
    assert "samesite=lax" in raw.lower()
    # Scoped to the only endpoints that read it.
    assert "Path=/api/v1/auth" in raw
    assert response.cookies[COOKIE]


async def test_register_opens_exactly_one_session_row(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    body = (await register(api_client)).json()

    rows = await sessions_of(db_session, body["user"]["id"])
    assert len(rows) == 1
    assert rows[0].revoked_at is None


async def test_stored_session_holds_only_the_hash_of_the_cookie(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client)
    raw_token = response.cookies[COOKIE]

    rows = await sessions_of(db_session, response.json()["user"]["id"])
    assert rows[0].token_hash == hash_refresh_token(raw_token)
    assert raw_token not in rows[0].token_hash


async def test_register_normalises_the_email(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client, email="  Hoc.Vien@Example.COM  ")

    assert response.json()["user"]["email"] == "hoc.vien@example.com"
    assert await db_session.scalar(
        select(User).where(User.email == "hoc.vien@example.com")
    )


async def test_register_rejects_a_duplicate_email(api_client: AsyncClient) -> None:
    await register(api_client)

    response = await register(api_client, full_name="Người khác")

    assert response.status_code == 409
    assert error_code(response) == "EMAIL_ALREADY_REGISTERED"


async def test_duplicate_check_ignores_case(api_client: AsyncClient) -> None:
    await register(api_client)

    response = await register(api_client, email="HOC.VIEN@example.com")

    assert response.status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "không-phải-email"),
        ("password", "ngắn"),
        ("full_name", "   "),
    ],
)
async def test_register_validates_its_input(
    api_client: AsyncClient, field: str, value: str
) -> None:
    response = await register(api_client, **{field: value})

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


async def test_register_rejects_a_password_bcrypt_would_truncate(
    api_client: AsyncClient,
) -> None:
    """bcrypt stops at 72 bytes.

    Accepting more would mean two different passwords opening one account.
    """
    response = await register(api_client, password="đ" * 40)  # 80 bytes in UTF-8

    assert response.status_code == 422


async def test_register_cannot_grant_itself_a_role(api_client: AsyncClient) -> None:
    """Mass assignment: the client does not get to pick its own role."""
    response = await api_client.post(
        "/api/v1/auth/register", json={**VALID, "role": "admin"}
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "student"


# --- Login -----------------------------------------------------------------


async def test_login_with_the_right_password_returns_a_token(
    api_client: AsyncClient,
) -> None:
    await register(api_client)

    response = await login(api_client)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies[COOKIE]


async def test_login_accepts_the_email_in_any_case(api_client: AsyncClient) -> None:
    await register(api_client)

    response = await login(api_client, email="HOC.VIEN@EXAMPLE.COM")

    assert response.status_code == 200


async def test_login_records_the_moment_it_happened(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)

    await login(api_client)

    user = await db_session.scalar(select(User).where(User.email == VALID["email"]))
    await db_session.refresh(user)
    assert user.last_login_at is not None


async def test_login_with_the_wrong_password_is_rejected(api_client: AsyncClient) -> None:
    await register(api_client)

    response = await login(api_client, password="sai-mật-khẩu-rồi")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_CREDENTIALS"


async def test_unknown_email_gives_the_same_error_as_a_wrong_password(
    api_client: AsyncClient,
) -> None:
    """Two different messages would turn the login form into an account oracle."""
    response = await login(api_client, email="khong-ton-tai@example.com")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_CREDENTIALS"


async def test_oauth_only_account_cannot_be_opened_with_a_password(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(
        User(
            email="google-only@example.com",
            full_name="Google Only",
            password_hash=None,
            oauth_provider="google",
            oauth_sub="google-sub-123",
        )
    )
    await db_session.flush()

    response = await login(api_client, email="google-only@example.com")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_CREDENTIALS"


async def test_locked_account_cannot_sign_in(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(
        User(
            email="bi-khoa@example.com",
            full_name="Bị Khóa",
            password_hash=hash_password(VALID["password"]),
            locked_at=datetime.now(tz=UTC),
        )
    )
    await db_session.flush()

    response = await login(api_client, email="bi-khoa@example.com")

    assert response.status_code == 403
    assert error_code(response) == "ACCOUNT_LOCKED"


async def test_login_opens_a_second_session_without_closing_the_first(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Signing in on a phone must not sign the laptop out."""
    user_id = (await register(api_client)).json()["user"]["id"]

    await login(api_client)

    rows = await sessions_of(db_session, user_id)
    assert len(rows) == 2
    assert all(row.revoked_at is None for row in rows)


# --- Refresh ---------------------------------------------------------------


async def test_refresh_returns_a_new_access_token(api_client: AsyncClient) -> None:
    await register(api_client)

    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rotates_the_cookie(api_client: AsyncClient) -> None:
    old_token = (await register(api_client)).cookies[COOKIE]

    response = await api_client.post("/api/v1/auth/refresh")

    assert response.cookies[COOKIE] != old_token


async def test_refresh_revokes_the_token_it_replaces(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    old_hash = hash_refresh_token(response.cookies[COOKIE])

    await api_client.post("/api/v1/auth/refresh")

    rows = {row.token_hash: row for row in await sessions_of(db_session, user_id)}
    assert rows[old_hash].revoked_at is not None
    assert len(rows) == 2


async def test_refresh_without_a_cookie_is_rejected(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert error_code(response) == "REFRESH_TOKEN_MISSING"


async def test_refresh_with_an_unknown_token_is_rejected(api_client: AsyncClient) -> None:
    api_client.cookies.set(COOKIE, generate_refresh_token())

    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_REFRESH_TOKEN"


async def test_expired_refresh_token_is_rejected(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = (await register(api_client)).json()["user"]["id"]
    raw = generate_refresh_token()
    db_session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(tz=UTC) - timedelta(seconds=1),
        )
    )
    await db_session.flush()
    api_client.cookies.set(COOKIE, raw)

    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_REFRESH_TOKEN"


async def test_refresh_records_the_token_that_replaced_it(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """What tells a rotated token from a signed-out one, and what the leeway
    below checks is still in use."""
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    old_hash = hash_refresh_token(response.cookies[COOKIE])

    new_cookie = (await api_client.post("/api/v1/auth/refresh")).cookies[COOKIE]

    rows = {row.token_hash: row for row in await sessions_of(db_session, user_id)}
    assert rows[old_hash].replaced_by_id == rows[hash_refresh_token(new_cookie)].id
    assert rows[hash_refresh_token(new_cookie)].replaced_by_id is None


async def test_reusing_a_rotated_token_is_treated_as_theft(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Past the leeway, a rotated token only leaves the client's cookie jar by
    being stolen."""
    stolen = (await register(api_client)).cookies[COOKIE]
    await api_client.post("/api/v1/auth/refresh")
    await rotated_seconds_ago(db_session, stolen, LEEWAY + 1)

    api_client.cookies.set(COOKIE, stolen)
    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert error_code(response) == "REFRESH_TOKEN_REUSED"


async def test_reuse_closes_every_session_of_that_user(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """We cannot tell the thief's copy from the victim's, so both go."""
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    stolen = response.cookies[COOKIE]
    await api_client.post("/api/v1/auth/refresh")
    await rotated_seconds_ago(db_session, stolen, LEEWAY + 1)

    api_client.cookies.set(COOKIE, stolen)
    await api_client.post("/api/v1/auth/refresh")

    rows = await sessions_of(db_session, user_id)
    assert rows
    assert all(row.revoked_at is not None for row in rows)


# --- Refresh: two tabs, one cookie -----------------------------------------
#
# Every tab of a browser shares one refresh cookie. Two tabs that wake up
# together both refresh, and the second request can leave carrying the token
# the first has just rotated -- the honest client, not a thief. Treating that
# as theft signed the person out of everything (docs/report/assets/phase-6/
# refresh-leeway.txt). The same happens to a single tab whose answer was lost
# on the way back and that asks again.


async def test_a_token_rotated_moments_ago_still_refreshes(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    first = response.cookies[COOKIE]
    other_tab = (await api_client.post("/api/v1/auth/refresh")).cookies[COOKIE]

    api_client.cookies.set(COOKIE, first)
    late = await api_client.post("/api/v1/auth/refresh")

    assert late.status_code == 200
    assert late.json()["access_token"]
    assert late.cookies[COOKIE] not in {first, other_tab}
    # Nothing was revoked on its account: the other tab's token and the late
    # tab's new one are both live.
    live = {row.token_hash for row in await live_sessions_of(db_session, user_id)}
    assert live == {hash_refresh_token(other_tab), hash_refresh_token(late.cookies[COOKIE])}


async def test_the_other_tab_stays_signed_in(api_client: AsyncClient) -> None:
    first = (await register(api_client)).cookies[COOKIE]
    other_tab = (await api_client.post("/api/v1/auth/refresh")).cookies[COOKIE]
    api_client.cookies.set(COOKIE, first)
    await api_client.post("/api/v1/auth/refresh")

    api_client.cookies.set(COOKIE, other_tab)
    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200


async def test_the_leeway_is_counted_from_the_rotation(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    first = (await register(api_client)).cookies[COOKIE]
    await api_client.post("/api/v1/auth/refresh")
    await rotated_seconds_ago(db_session, first, LEEWAY - 2)

    api_client.cookies.set(COOKIE, first)
    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200


async def test_a_signed_out_token_gets_no_leeway(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Signing out gives a token up rather than replacing it, so it coming
    back -- however soon -- is a copy."""
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    raw = response.cookies[COOKIE]
    await api_client.post("/api/v1/auth/logout")

    api_client.cookies.set(COOKIE, raw)
    refreshed = await api_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 401
    assert error_code(refreshed) == "REFRESH_TOKEN_REUSED"
    assert await live_sessions_of(db_session, user_id) == []


async def test_no_leeway_once_the_replacement_is_signed_out(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The leeway covers a token whose replacement is still in use. Sign out
    of the replacement and the old token must not open a session again."""
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    first = response.cookies[COOKIE]
    await api_client.post("/api/v1/auth/refresh")
    await api_client.post("/api/v1/auth/logout")

    api_client.cookies.set(COOKIE, first)
    refreshed = await api_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 401
    assert error_code(refreshed) == "REFRESH_TOKEN_REUSED"
    assert await live_sessions_of(db_session, user_id) == []


async def test_no_leeway_after_every_session_was_closed(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A password change, an admin lock and theft detection all close every
    session at once; a token rotated a moment before must not reopen one."""
    response = await register(api_client)
    user_id = response.json()["user"]["id"]
    first = response.cookies[COOKIE]
    await api_client.post("/api/v1/auth/refresh")
    await auth_service.revoke_all_sessions(db_session, uuid.UUID(user_id))
    await db_session.flush()

    api_client.cookies.set(COOKIE, first)
    refreshed = await api_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 401
    assert await live_sessions_of(db_session, user_id) == []


# --- Logout ----------------------------------------------------------------


async def test_logout_revokes_the_session_and_clears_the_cookie(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client)
    user_id = response.json()["user"]["id"]

    logout = await api_client.post("/api/v1/auth/logout")

    assert logout.status_code == 204
    assert not api_client.cookies.get(COOKIE)
    rows = await sessions_of(db_session, user_id)
    assert all(row.revoked_at is not None for row in rows)


async def test_logout_without_a_session_still_succeeds(api_client: AsyncClient) -> None:
    """Signing out twice is not an error the user can do anything about."""
    response = await api_client.post("/api/v1/auth/logout")

    assert response.status_code == 204


async def test_a_revoked_token_cannot_be_refreshed(api_client: AsyncClient) -> None:
    raw = (await register(api_client)).cookies[COOKIE]
    await api_client.post("/api/v1/auth/logout")

    api_client.cookies.set(COOKIE, raw)
    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


# --- Current user ----------------------------------------------------------


async def test_access_token_identifies_the_caller(api_client: AsyncClient) -> None:
    token = (await register(api_client)).json()["access_token"]

    response = await api_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == VALID["email"]
    assert response.json()["role"] == "student"


async def test_me_without_a_token_is_unauthorised(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert error_code(response) == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(
    "header",
    ["Bearer clearly-not-a-jwt", "Basic hoc.vien@example.com:secret", "Bearer"],
)
async def test_me_rejects_a_bad_authorization_header(
    api_client: AsyncClient, header: str
) -> None:
    response = await api_client.get("/api/v1/auth/me", headers={"Authorization": header})

    assert response.status_code == 401


async def test_the_refresh_cookie_is_not_accepted_as_an_access_token(
    api_client: AsyncClient,
) -> None:
    """Different tokens, different jobs: the long-lived one must not open the API."""
    raw = (await register(api_client)).cookies[COOKIE]

    response = await api_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {raw}"}
    )

    assert response.status_code == 401
