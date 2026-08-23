"""Giving an account a picture.

Same two-step shape as a video upload -- the backend signs a URL, the browser
does the PUT, then says it finished -- with one extra worry. The key comes back
through the client, so most of what is checked here is that a key from anywhere
but the caller's own folder gets nowhere.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import User
from app.services.storage import get_storage
from tests.api.fakes import FakeStorage, RefusingStorage

PASSWORD = "mật-khẩu-đủ-dài"


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


async def make_user(session: AsyncSession, *, avatar_url: str | None = None) -> User:
    user = User(
        email=f"hoc-vien-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash=hash_password(PASSWORD),
        role="student",
        avatar_url=avatar_url,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def avatar_body(**overrides) -> dict:
    return {
        "filename": "chan-dung.png",
        "content_type": "image/png",
        "size_bytes": 200 * 1024,
        **overrides,
    }


async def ticket_for(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    response = await client.post(
        "/api/v1/users/me/avatar", json=avatar_body(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


# --- Asking for a URL ------------------------------------------------------


async def test_the_key_lands_in_the_callers_own_folder(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar", json=avatar_body(), headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["storage_key"].startswith(f"avatars/{user.id}/")
    assert body["storage_key"].endswith(".png")
    assert body["upload_url"].startswith("https://bucket.example/")


async def test_the_signed_content_type_and_ttl_match_the_ticket(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """R2 signs the content type in, so the browser has to send back this one."""
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    body = await ticket_for(
        api_client, headers, content_type="image/webp", filename="anh.webp"
    )

    key, content_type, expires_in = storage.signed[-1]
    assert key == body["storage_key"]
    assert content_type == body["content_type"] == "image/webp"
    assert key.endswith(".webp")
    assert expires_in == get_settings().upload_url_ttl_seconds


async def test_every_ticket_gets_a_fresh_key(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """The URL is public and cached: reusing a key would show the old picture."""
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    first = await ticket_for(api_client, headers)
    second = await ticket_for(api_client, headers)

    assert first["storage_key"] != second["storage_key"]


async def test_signing_alone_does_not_change_the_account(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """A ticket nobody uses must leave the picture the account already had."""
    user = await make_user(db_session, avatar_url="https://cdn.example/anh-cu.png")
    headers = await sign_in(api_client, user)

    await ticket_for(api_client, headers)

    await db_session.refresh(user)
    assert user.avatar_url == "https://cdn.example/anh-cu.png"


async def test_an_svg_is_not_an_avatar(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """SVG can carry script, and the bucket serves back the type it was given."""
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar",
        json=avatar_body(content_type="image/svg+xml", filename="anh.svg"),
        headers=headers,
    )

    assert response.status_code == 422
    assert storage.signed == []


async def test_a_pdf_is_not_an_avatar(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar",
        json=avatar_body(content_type="application/pdf", filename="cv.pdf"),
        headers=headers,
    )

    assert response.status_code == 422
    assert storage.signed == []


async def test_a_picture_over_the_limit_is_refused_before_it_is_uploaded(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar",
        json=avatar_body(size_bytes=6 * 1024 * 1024),
        headers=headers,
    )

    assert response.status_code == 422
    assert storage.signed == []


async def test_signing_requires_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    response = await api_client.post("/api/v1/users/me/avatar", json=avatar_body())

    assert response.status_code == 401
    assert storage.signed == []


# --- Confirming the upload -------------------------------------------------


async def test_confirming_puts_the_picture_on_the_account(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)
    ticket = await ticket_for(api_client, headers)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": ticket["storage_key"]},
        headers=headers,
    )

    assert response.status_code == 200
    expected = f"https://cdn.example/{ticket['storage_key']}"
    assert response.json()["avatar_url"] == expected
    await db_session.refresh(user)
    assert user.avatar_url == expected


async def test_a_replaced_picture_is_deleted_from_the_bucket(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    stale_key = f"avatars/{user.id}/cu.png"
    user.avatar_url = f"https://cdn.example/{stale_key}"
    await db_session.flush()
    headers = await sign_in(api_client, user)
    ticket = await ticket_for(api_client, headers)

    await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": ticket["storage_key"]},
        headers=headers,
    )

    assert storage.deleted_prefixes == [stale_key]


async def test_a_google_picture_is_never_deleted_from_our_bucket(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """That URL belongs to Google. Handing it to our bucket makes no sense."""
    user = await make_user(
        db_session, avatar_url="https://lh3.googleusercontent.com/a/anh-google"
    )
    headers = await sign_in(api_client, user)
    ticket = await ticket_for(api_client, headers)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": ticket["storage_key"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert storage.deleted_prefixes == []


async def test_a_bucket_that_refuses_to_delete_does_not_cost_the_upload(
    api_client: AsyncClient, app: FastAPI, db_session: AsyncSession
) -> None:
    refusing = RefusingStorage()
    app.dependency_overrides[get_storage] = lambda: refusing
    user = await make_user(db_session, avatar_url=None)
    headers = await sign_in(api_client, user)
    user.avatar_url = f"https://cdn.example/avatars/{user.id}/cu.png"
    await db_session.flush()
    ticket = await ticket_for(api_client, headers)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": ticket["storage_key"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["avatar_url"].endswith(ticket["storage_key"])


async def test_a_key_from_someone_elses_folder_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """The whole reason the key is checked: it arrives from the client."""
    user = await make_user(db_session)
    stranger = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": f"avatars/{stranger.id}/anh-cua-nguoi-khac.png"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AVATAR_KEY_NOT_OWNED"
    await db_session.refresh(user)
    assert user.avatar_url is None
    assert storage.deleted_prefixes == []


async def test_a_key_that_climbs_out_of_the_folder_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": f"avatars/{user.id}/../../videos/bai-giang.mp4"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AVATAR_KEY_NOT_OWNED"


async def test_a_key_that_only_looks_like_the_callers_folder_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """`avatars/<id>-something/` shares a prefix with `avatars/<id>/` as text."""
    user = await make_user(db_session)
    headers = await sign_in(api_client, user)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": f"avatars/{user.id}-khac/anh.png"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AVATAR_KEY_NOT_OWNED"


async def test_confirming_requires_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    user = await make_user(db_session)

    response = await api_client.post(
        "/api/v1/users/me/avatar/complete",
        json={"storage_key": f"avatars/{user.id}/anh.png"},
    )

    assert response.status_code == 401


async def test_storage_that_was_never_configured_answers_503(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deliberate: the rest of the profile page runs fine without a bucket."""
    settings = get_settings()
    original = settings.r2_account_id
    object.__setattr__(settings, "r2_account_id", "")
    try:
        user = await make_user(db_session)
        headers = await sign_in(api_client, user)

        response = await api_client.post(
            "/api/v1/users/me/avatar", json=avatar_body(), headers=headers
        )

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "STORAGE_NOT_CONFIGURED"
    finally:
        object.__setattr__(settings, "r2_account_id", original)
