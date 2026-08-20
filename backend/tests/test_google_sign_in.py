"""Account handling for Google sign-in.

The HTTP round trip with Google is somewhere else entirely (see
app/services/google_oauth.py); by the time these functions run, the identity
is already established. What is left is the part that can go wrong quietly:
which account does this identity belong to.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import RefreshToken, User
from app.services.auth import AccountLockedError, sign_in_with_google
from app.services.google_oauth import GoogleIdentity

IDENTITY = GoogleIdentity(
    sub="google-sub-0001",
    email="ngoc@example.com",
    email_verified=True,
    full_name="Ngọc Google",
    picture="https://lh3.googleusercontent.com/avatar",
)


def identity(**overrides) -> GoogleIdentity:
    return GoogleIdentity(**{**IDENTITY.__dict__, **overrides})


async def user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def test_first_google_sign_in_creates_a_student(db_session: AsyncSession) -> None:
    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.email == IDENTITY.email
    assert tokens.user.full_name == IDENTITY.full_name
    assert tokens.user.role == "student"
    assert tokens.user.oauth_provider == "google"
    assert tokens.user.oauth_sub == IDENTITY.sub


async def test_a_google_account_has_no_password(db_session: AsyncSession) -> None:
    """Nothing to guess: the account can only be opened through Google."""
    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.password_hash is None


async def test_google_sign_in_counts_as_a_verified_email(
    db_session: AsyncSession,
) -> None:
    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.email_verified_at is not None


async def test_google_sign_in_opens_a_session(db_session: AsyncSession) -> None:
    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    rows = list(
        await db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == tokens.user.id)
        )
    )
    assert len(rows) == 1
    assert tokens.access_token
    assert tokens.refresh_token


async def test_email_is_normalised_the_same_way_as_registration(
    db_session: AsyncSession,
) -> None:
    await sign_in_with_google(db_session, identity=identity(email="  Ngoc@Example.COM "))

    assert await user_by_email(db_session, "ngoc@example.com")


async def test_signing_in_again_reuses_the_same_account(
    db_session: AsyncSession,
) -> None:
    first = await sign_in_with_google(db_session, identity=IDENTITY)

    second = await sign_in_with_google(db_session, identity=IDENTITY)

    assert first.user.id == second.user.id


async def test_a_changed_google_email_follows_the_subject_not_the_address(
    db_session: AsyncSession,
) -> None:
    """`sub` is the stable identifier; an address can be renamed or reassigned."""
    first = await sign_in_with_google(db_session, identity=IDENTITY)

    second = await sign_in_with_google(
        db_session, identity=identity(email="ngoc.moi@example.com")
    )

    assert second.user.id == first.user.id
    assert second.user.email == "ngoc.moi@example.com"


async def test_google_links_into_an_existing_password_account(
    db_session: AsyncSession,
) -> None:
    """Same person, same address: one account, two ways in."""
    existing = User(
        email=IDENTITY.email,
        full_name="Ngọc Đăng Ký Bằng Mật Khẩu",
        password_hash=hash_password("mật-khẩu-cũ-dài"),
    )
    db_session.add(existing)
    await db_session.flush()

    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.id == existing.id
    assert tokens.user.oauth_sub == IDENTITY.sub
    # The password still works -- linking adds a way in, it does not take one away.
    assert tokens.user.password_hash == existing.password_hash


async def test_linking_keeps_the_name_the_user_chose(db_session: AsyncSession) -> None:
    db_session.add(
        User(
            email=IDENTITY.email,
            full_name="Tên Tự Đặt",
            password_hash=hash_password("mật-khẩu-cũ-dài"),
        )
    )
    await db_session.flush()

    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.full_name == "Tên Tự Đặt"


async def test_unverified_google_email_never_links_to_an_account(
    db_session: AsyncSession,
) -> None:
    """The whole merge rests on the address being proven.

    A Workspace domain can hand out an account whose address Google has not
    verified; merging on that claim would be an account takeover.
    """
    db_session.add(
        User(
            email=IDENTITY.email,
            full_name="Chủ Tài Khoản Thật",
            password_hash=hash_password("mật-khẩu-cũ-dài"),
        )
    )
    await db_session.flush()

    with pytest.raises(Exception) as raised:
        await sign_in_with_google(db_session, identity=identity(email_verified=False))

    assert getattr(raised.value, "code", None) == "GOOGLE_EMAIL_NOT_VERIFIED"


async def test_unverified_google_email_cannot_create_an_account_either(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(Exception) as raised:
        await sign_in_with_google(db_session, identity=identity(email_verified=False))

    assert getattr(raised.value, "code", None) == "GOOGLE_EMAIL_NOT_VERIFIED"
    assert await user_by_email(db_session, IDENTITY.email) is None


async def test_locked_account_cannot_come_in_through_google(
    db_session: AsyncSession,
) -> None:
    """Otherwise locking an account would only close one of its two doors."""
    db_session.add(
        User(
            email=IDENTITY.email,
            full_name="Bị Khóa",
            password_hash=hash_password("mật-khẩu-cũ-dài"),
            locked_at=datetime.now(tz=UTC),
        )
    )
    await db_session.flush()

    with pytest.raises(AccountLockedError):
        await sign_in_with_google(db_session, identity=IDENTITY)


async def test_google_sign_in_records_the_login_time(db_session: AsyncSession) -> None:
    tokens = await sign_in_with_google(db_session, identity=IDENTITY)

    assert tokens.user.last_login_at is not None


async def test_a_missing_name_falls_back_to_the_address(
    db_session: AsyncSession,
) -> None:
    """full_name is NOT NULL; Google does not always send one."""
    tokens = await sign_in_with_google(db_session, identity=identity(full_name=None))

    assert tokens.user.full_name == "ngoc"
