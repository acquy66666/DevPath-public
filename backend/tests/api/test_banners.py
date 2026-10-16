"""Homepage banners: the admin arranging them, the homepage reading them.

What must hold: a picture can only come from the banner upload folder; a link
is a path here or an http(s) address, never `javascript:`; what the homepage
gets is switched on, inside its window, in order, and never more than five;
replacing or deleting a banner removes its old picture.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Banner
from app.services import banners as banners_service
from app.services.storage import get_storage
from tests.api.fakes import FakeStorage
from tests.api.publishing import admin_headers
from tests.api.test_commerce import make_user, sign_in

ADMIN = "/api/v1/admin/banners"


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
async def admin(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await admin_headers(api_client, db_session)


async def upload(client: AsyncClient, headers: dict, name: str = "tet.png") -> str:
    response = await client.post(
        f"{ADMIN}/upload-url",
        json={"filename": name, "content_type": "image/png", "size_bytes": 200_000},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["storage_key"]


async def create(client: AsyncClient, headers: dict, **body) -> dict:
    body.setdefault("image_key", await upload(client, headers))
    response = await client.post(ADMIN, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_only_an_admin_manages_banners(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    assert (await api_client.get(ADMIN)).status_code == 401
    student = await make_user(db_session)
    headers = await sign_in(api_client, student)
    assert (await api_client.get(ADMIN, headers=headers)).status_code == 403
    ticket = await api_client.post(
        f"{ADMIN}/upload-url",
        json={"filename": "x.png", "content_type": "image/png", "size_bytes": 10},
        headers=headers,
    )
    assert ticket.status_code == 403
    assert storage.signed == []


async def test_the_upload_ticket_signs_a_fresh_key_in_the_banner_folder(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    first = await upload(api_client, admin, "Khuyến mãi.PNG")
    second = await upload(api_client, admin, "Khuyến mãi.PNG")
    too_big = await api_client.post(
        f"{ADMIN}/upload-url",
        json={"filename": "big.png", "content_type": "image/png", "size_bytes": 9 * 1024 * 1024},
        headers=admin,
    )
    not_image = await api_client.post(
        f"{ADMIN}/upload-url",
        json={"filename": "x.pdf", "content_type": "application/pdf", "size_bytes": 10},
        headers=admin,
    )

    assert first.startswith("banners/") and first.endswith(".png")
    assert first != second
    assert [signed.key for signed in storage.signed] == [first, second]
    assert too_big.status_code == 422
    assert not_image.status_code == 422


async def test_the_declared_size_is_signed_in(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    """The bucket holds the PUT to the size the admin's browser declared."""
    response = await api_client.post(
        f"{ADMIN}/upload-url",
        json={"filename": "tet.png", "content_type": "image/png", "size_bytes": 765_432},
        headers=admin,
    )

    assert response.status_code == 200
    signed = storage.signed[-1]
    assert signed.key == response.json()["storage_key"]
    assert signed.size_bytes == 765_432


async def test_a_banner_takes_its_picture_from_the_ticket_and_goes_last(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    first = await create(api_client, admin, title="  Tết sale  ", link_url="/khoa-hoc")
    second = await create(api_client, admin, title="Khóa mới", link_url="https://example.com/a")

    assert first["title"] == "Tết sale"
    assert first["image_url"].startswith("https://cdn.example/banners/")
    assert first["status"] == "live"
    assert second["position"] == first["position"] + 1


@pytest.mark.parametrize(
    "key", ["avatars/abc/me.png", "videos/x/original.mp4", "banners/", "banners/a/b.png"]
)
async def test_a_picture_from_anywhere_else_is_refused(
    api_client: AsyncClient, admin: dict, storage: FakeStorage, key: str
) -> None:
    response = await api_client.post(ADMIN, json={"title": "X", "image_key": key}, headers=admin)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "BANNER_IMAGE_KEY_INVALID"


@pytest.mark.parametrize(
    "link", ["javascript:alert(1)", "//evil.example/x", "ftp://files.example", "khoa-hoc"]
)
async def test_a_link_is_a_path_here_or_a_web_address(
    api_client: AsyncClient, admin: dict, storage: FakeStorage, link: str
) -> None:
    key = await upload(api_client, admin)
    response = await api_client.post(
        ADMIN, json={"title": "X", "image_key": key, "link_url": link}, headers=admin
    )
    assert response.status_code == 422


async def test_an_end_before_the_start_is_refused(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    key = await upload(api_client, admin)
    response = await api_client.post(
        ADMIN,
        json={
            "title": "X",
            "image_key": key,
            "starts_at": "2031-06-10T00:00:00+07:00",
            "ends_at": "2031-06-01T00:00:00+07:00",
        },
        headers=admin,
    )
    assert response.status_code == 422


async def test_the_homepage_gets_what_is_on_and_in_its_window_in_order(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    now = datetime(2031, 6, 15, 12, tzinfo=UTC)
    day = timedelta(days=1)

    def banner(title: str, position: int, **fields) -> Banner:
        return Banner(
            title=title, image_url=f"https://cdn.example/banners/{title}.png", position=position,
            **fields,
        )

    db_session.add_all(
        [
            banner("second", 2),
            banner("first", -2),
            banner("switched-off", -1, is_active=False),
            banner("not-yet", 0, starts_at=now + day),
            banner("over", 0, ends_at=now - day),
            banner("in-window", 1, starts_at=now - day, ends_at=now + day),
        ]
    )
    await db_session.flush()

    titles = [b.title for b in await banners_service.list_live(db_session, now=now)]

    mine = [title for title in titles if title in {"first", "in-window", "second"}]
    assert mine == ["first", "in-window", "second"][: len(mine)]
    assert "first" in titles
    assert {"switched-off", "not-yet", "over"}.isdisjoint(titles)
    assert len(titles) <= banners_service.MAX_LIVE

    public = await api_client.get("/api/v1/banners")
    assert public.status_code == 200


async def test_the_homepage_shows_five_at_most(db_session: AsyncSession) -> None:
    db_session.add_all(
        Banner(title=f"b{i}", image_url=f"https://cdn.example/banners/b{i}.png", position=-10 + i)
        for i in range(7)
    )
    await db_session.flush()

    live = await banners_service.list_live(db_session)

    assert [b.title for b in live] == ["b0", "b1", "b2", "b3", "b4"]


async def test_a_new_picture_replaces_the_old_one_in_the_bucket(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    banner = await create(api_client, admin, title="Cũ", link_url="/khoa-hoc")
    old_key = banner["image_url"].removeprefix("https://cdn.example/")
    new_key = await upload(api_client, admin, "moi.webp")

    response = await api_client.patch(
        f"{ADMIN}/{banner['id']}",
        json={"title": "Mới", "image_key": new_key, "link_url": None, "is_active": False},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Mới"
    assert body["image_url"] == f"https://cdn.example/{new_key}"
    assert body["link_url"] is None
    assert body["status"] == "off"
    assert storage.deleted_prefixes == [old_key]


async def test_an_order_is_every_banner_once(
    api_client: AsyncClient, admin: dict, storage: FakeStorage
) -> None:
    await create(api_client, admin, title="A")
    await create(api_client, admin, title="B")
    everyone = [b["id"] for b in (await api_client.get(ADMIN, headers=admin)).json()]

    reversed_order = await api_client.put(
        f"{ADMIN}/order", json={"ids": everyone[::-1]}, headers=admin
    )
    partial = await api_client.put(f"{ADMIN}/order", json={"ids": everyone[:1]}, headers=admin)

    assert [b["id"] for b in reversed_order.json()] == everyone[::-1]
    if len(everyone) > 1:
        assert partial.status_code == 400
        assert partial.json()["detail"]["code"] == "INVALID_ORDER"


async def test_deleting_a_banner_removes_its_picture(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, storage: FakeStorage
) -> None:
    banner = await create(api_client, admin, title="Tạm")

    response = await api_client.delete(f"{ADMIN}/{banner['id']}", headers=admin)
    again = await api_client.delete(f"{ADMIN}/{banner['id']}", headers=admin)

    assert response.status_code == 204
    assert storage.deleted_prefixes == [banner["image_url"].removeprefix("https://cdn.example/")]
    assert again.status_code == 404
