"""`require_role`, exercised through real HTTP.

The dependency has no production consumer yet -- the first ones arrive with
course CRUD next week -- so the probe routes below stand in for them. Testing
it by calling the function directly would skip everything that actually
matters here: that FastAPI resolves it, that a refused call comes back as the
shared error envelope, and that it runs after authentication rather than
instead of it.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.core.security import hash_password
from app.models import User
from app.services.rate_limit import get_rate_limiter
from tests.api.fakes import AllowAllRateLimiter

PASSWORD = "mật-khẩu-đủ-dài"


@pytest.fixture
async def probe_client(
    app: FastAPI, db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    """The app plus one route per role rule under test."""

    @app.get("/api/v1/_probe/instructor")
    async def instructor_only(
        user: Annotated[User, Depends(require_role("instructor"))],
    ) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/api/v1/_probe/admin")
    async def admin_only(
        user: Annotated[User, Depends(require_role("admin"))],
    ) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/api/v1/_probe/staff")
    async def instructor_or_admin(
        user: Annotated[User, Depends(require_role("instructor", "admin"))],
    ) -> dict[str, str]:
        return {"role": user.role}

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Signing in counts against the login limit, which would otherwise reach
    # for a real Redis and remember these addresses between runs.
    app.dependency_overrides[get_rate_limiter] = AllowAllRateLimiter
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def signed_in_as(
    client: AsyncClient, session: AsyncSession, role: str
) -> dict[str, str]:
    """Create a user with `role`, sign in, and return the auth header."""
    email = f"{role}@example.com"
    session.add(
        User(email=email, full_name=role.title(), password_hash=hash_password(PASSWORD), role=role)
    )
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize(
    "role,path,allowed",
    [
        ("instructor", "/api/v1/_probe/instructor", True),
        ("student", "/api/v1/_probe/instructor", False),
        ("admin", "/api/v1/_probe/instructor", False),
        ("admin", "/api/v1/_probe/admin", True),
        ("instructor", "/api/v1/_probe/admin", False),
        ("student", "/api/v1/_probe/admin", False),
        ("instructor", "/api/v1/_probe/staff", True),
        ("admin", "/api/v1/_probe/staff", True),
        ("student", "/api/v1/_probe/staff", False),
    ],
)
async def test_only_the_listed_roles_get_in(
    probe_client: AsyncClient,
    db_session: AsyncSession,
    role: str,
    path: str,
    allowed: bool,
) -> None:
    """Admin is not a superset on purpose.

    `require_role("instructor")` means instructors, not "instructors and
    anyone more important". An endpoint that admins should also reach says so:
    `require_role("instructor", "admin")`. Implicit escalation is the kind of
    rule nobody remembers when writing the next endpoint.
    """
    headers = await signed_in_as(probe_client, db_session, role)

    response = await probe_client.get(path, headers=headers)

    assert response.status_code == (200 if allowed else 403)


async def test_a_refusal_uses_the_shared_error_envelope(
    probe_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await signed_in_as(probe_client, db_session, "student")

    response = await probe_client.get("/api/v1/_probe/instructor", headers=headers)

    detail = response.json()["detail"]
    assert detail["code"] == "PERMISSION_DENIED"
    assert detail["message"]


async def test_no_token_is_401_not_403(probe_client: AsyncClient) -> None:
    """Authentication comes first: "who are you" before "may you"."""
    response = await probe_client.get("/api/v1/_probe/instructor")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


async def test_an_invalid_token_is_401_not_403(probe_client: AsyncClient) -> None:
    response = await probe_client.get(
        "/api/v1/_probe/instructor", headers={"Authorization": "Bearer nonsense"}
    )

    assert response.status_code == 401


async def test_the_role_is_read_from_the_database_not_the_token(
    probe_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A token minted before a promotion still opens the new doors.

    The claim inside the access token is a snapshot from issue time; the row is
    the truth. Reading the row is also what makes taking a role *away* effective
    immediately instead of fifteen minutes later.
    """
    headers = await signed_in_as(probe_client, db_session, "student")
    assert (await probe_client.get("/api/v1/_probe/instructor", headers=headers)).status_code == 403

    user = await db_session.scalar(
        select(User).where(User.email == "student@example.com")
    )
    user.role = "instructor"
    await db_session.flush()

    response = await probe_client.get("/api/v1/_probe/instructor", headers=headers)

    assert response.status_code == 200
    assert response.json()["role"] == "instructor"


async def test_a_locked_account_is_refused_before_the_role_is_considered(
    probe_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await signed_in_as(probe_client, db_session, "instructor")
    user = await db_session.scalar(
        select(User).where(User.email == "instructor@example.com")
    )
    user.locked_at = datetime.now(tz=UTC)
    await db_session.flush()

    response = await probe_client.get("/api/v1/_probe/instructor", headers=headers)

    assert response.status_code == 401
