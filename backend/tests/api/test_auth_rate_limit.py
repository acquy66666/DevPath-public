"""How many times one person may knock on the sign-in door.

bcrypt already makes each guess cost the server a quarter of a second; these
limits stop a script from simply making a great many of them. Two shapes of
attack, two keys:

* many passwords against one account -- counted per email address;
* one password against many accounts -- counted per client address.

Registration is counted per client address, against a script filling the
users table. Changing a password is counted per account, against somebody at
an unlocked laptop guessing the current password with a live access token.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import User
from app.services.rate_limit import get_rate_limiter
from tests.api.fakes import MemoryRateLimiter

PASSWORD = "mật-khẩu-đủ-dài"


@pytest.fixture
def limiter(app: FastAPI, api_client: AsyncClient) -> MemoryRateLimiter:
    """Installed after `api_client`, so it replaces the allow-all default."""
    memory = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: memory
    return memory


@pytest.fixture
def small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same rules with numbers small enough to reach in a test."""
    settings = get_settings()
    monkeypatch.setattr(settings, "login_attempts_per_email", 3)
    monkeypatch.setattr(settings, "login_attempts_per_ip", 5)
    monkeypatch.setattr(settings, "registrations_per_ip", 2)
    monkeypatch.setattr(settings, "password_changes_per_user", 2)


async def make_user(session: AsyncSession) -> User:
    user = User(
        email=f"hocvien-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học Viên",
        password_hash=hash_password(PASSWORD),
        role="student",
    )
    session.add(user)
    await session.flush()
    return user


async def login(client: AsyncClient, email: str, password: str = PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


def from_address(app: FastAPI, address: str) -> AsyncClient:
    """A client whose requests arrive from `address`."""
    transport = ASGITransport(app=app, client=(address, 4321))
    return AsyncClient(transport=transport, base_url="http://test")


def assert_limited(response) -> None:
    assert response.status_code == 429, response.text
    assert response.json()["detail"]["code"] == "AUTH_RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0


@pytest.mark.usefixtures("small_limits")
async def test_guessing_one_accounts_password_is_cut_off(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    user = await make_user(db_session)
    for _ in range(3):
        assert (await login(api_client, user.email, "sai-mật-khẩu")).status_code == 401

    # The right password is refused too: telling a guesser "this one would have
    # worked" is the one thing the limit exists to stop.
    assert_limited(await login(api_client, user.email))


@pytest.mark.usefixtures("small_limits")
async def test_the_account_limit_follows_the_address_not_the_spelling(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    user = await make_user(db_session)
    for _ in range(3):
        await login(api_client, user.email.upper(), "sai-mật-khẩu")

    assert_limited(await login(api_client, user.email))


@pytest.mark.usefixtures("small_limits")
async def test_the_account_limit_holds_across_client_addresses(
    app: FastAPI, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    user = await make_user(db_session)
    for number in range(3):
        async with from_address(app, f"203.0.113.{number}") as client:
            await login(client, user.email, "sai-mật-khẩu")

    async with from_address(app, "203.0.113.99") as client:
        assert_limited(await login(client, user.email))


@pytest.mark.usefixtures("small_limits")
async def test_spraying_many_accounts_from_one_address_is_cut_off(
    app: FastAPI, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    async with from_address(app, "198.51.100.7") as client:
        for number in range(5):
            response = await login(client, f"nguoi-{number}@example.com", "123456")
            assert response.status_code == 401

        assert_limited(await login(client, "nguoi-moi@example.com", "123456"))

    # Somebody else, somewhere else, is not caught by it.
    user = await make_user(db_session)
    async with from_address(app, "198.51.100.8") as client:
        assert (await login(client, user.email)).status_code == 200


@pytest.mark.usefixtures("small_limits")
async def test_the_window_ends(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    user = await make_user(db_session)
    for _ in range(3):
        await login(api_client, user.email, "sai-mật-khẩu")
    assert_limited(await login(api_client, user.email))

    limiter.now += get_settings().login_window_seconds

    assert (await login(api_client, user.email)).status_code == 200


@pytest.mark.usefixtures("small_limits")
async def test_registering_many_accounts_from_one_address_is_cut_off(
    app: FastAPI, limiter: MemoryRateLimiter
) -> None:
    async with from_address(app, "192.0.2.10") as client:
        for number in range(2):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"moi-{number}-{uuid.uuid4().hex[:6]}@example.com",
                    "password": PASSWORD,
                    "full_name": "Người Mới",
                },
            )
            assert response.status_code == 201, response.text

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "thu-ba@example.com", "password": PASSWORD, "full_name": "Thứ Ba"},
        )

    assert_limited(response)


@pytest.mark.usefixtures("small_limits")
async def test_guessing_the_current_password_with_a_live_token_is_cut_off(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    user = await make_user(db_session)
    signed_in = await login(api_client, user.email)
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}

    for _ in range(2):
        response = await api_client.post(
            "/api/v1/users/me/password",
            json={"current_password": "doan-mo-thoi", "new_password": "mật-khẩu-mới-dài"},
            headers=headers,
        )
        assert response.status_code == 400, response.text

    response = await api_client.post(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": "mật-khẩu-mới-dài"},
        headers=headers,
    )
    assert_limited(response)


async def test_the_production_limits_leave_room_for_a_classroom() -> None:
    """A lab full of students behind one NAT address signs in at the same time.

    Not a rule anybody can test against a real network, so the numbers are
    pinned here with the reason next to them: one class is about forty people,
    and each of them may mistype once.
    """
    settings = get_settings()
    assert settings.login_attempts_per_ip >= 80
    assert settings.registrations_per_ip >= 40
    assert settings.login_attempts_per_email <= 10
