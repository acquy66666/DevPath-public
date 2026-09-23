"""The cart and the wishlist.

Two rules run through most of these. A cart may only hold something that could
actually be bought, so a course you own, teach, or cannot see is refused when
it goes in -- and a course that stops being on sale afterwards stops being
shown and stops being charged for. A wishlist is held to none of that, because
nothing is ever paid out of it.

Nothing here reads the catalogue at large: every assertion is about the
caller's own cart or wishlist, so a developer database full of seeded courses
and an empty CI database give the same answers.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, User
from app.services import commerce as commerce_service

PASSWORD = "mật-khẩu-đủ-dài"


async def make_user(session: AsyncSession, role: str = "student") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=role.title(),
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_course(
    session: AsyncSession,
    owner: User,
    *,
    price: str = "199000",
    status: str = "published",
    title: str = "Khóa học có phí",
) -> Course:
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title=title,
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal(price),
        status=status,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(course)
    await session.flush()
    return course


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


def cart_url(course: Course) -> str:
    return f"/api/v1/cart/courses/{course.id}"


def wishlist_url(course: Course) -> str:
    return f"/api/v1/wishlist/courses/{course.id}"


# --- Cart: what goes in ----------------------------------------------------


async def test_a_course_can_be_put_in_the_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["course"]["id"] for item in body["items"]] == [str(course.id)]
    assert body["total"] == "199000.00"
    assert body["items"][0]["already_enrolled"] is False


async def test_adding_the_same_course_twice_leaves_one_line(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Two clicks are one intention, and the total must not double."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.put(cart_url(course), headers=headers)
    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == "199000.00"


async def test_a_free_course_is_allowed_in_the_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Pointless on its own, but the checkout behind this has to total zero
    anyway once a 100% coupon exists, and the UI needs a way to get there."""
    course = await make_course(db_session, owner, price="0")
    headers = await sign_in(api_client, student)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == "0.00"


async def test_the_total_is_the_sum_of_the_lines(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    first = await make_course(db_session, owner, price="199000")
    second = await make_course(db_session, owner, price="450000.50")
    headers = await sign_in(api_client, student)

    await api_client.put(cart_url(first), headers=headers)
    response = await api_client.put(cart_url(second), headers=headers)

    assert response.json()["total"] == "649000.50"


async def test_your_own_course_cannot_be_bought(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CANNOT_BUY_OWN_COURSE"


async def test_a_course_you_are_already_enrolled_in_cannot_be_bought(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The refusal belongs here rather than at checkout, where the person has
    already chosen how to pay."""
    course = await make_course(db_session, owner)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    await db_session.flush()
    headers = await sign_in(api_client, student)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_ENROLLED"


async def test_a_draft_course_is_not_in_anyones_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner, status="draft")
    headers = await sign_in(api_client, student)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_an_instructor_cannot_cart_their_own_draft_either(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """The owner may *see* their own draft, so the visibility check alone would
    let this through. It answers the same 404 as for anyone else rather than
    the 409 the ownership rule would give -- a draft is not on sale to its
    author any more than to a stranger."""
    course = await make_course(db_session, owner, status="draft")
    headers = await sign_in(api_client, owner)

    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_a_missing_course_is_a_404(
    api_client: AsyncClient, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.put(
        f"/api/v1/cart/courses/{uuid.uuid4()}", headers=headers
    )

    assert response.status_code == 404


async def test_the_cart_has_a_ceiling(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fifty in production; two here, so the test does not create fifty courses."""
    monkeypatch.setattr(commerce_service, "MAX_CART_ITEMS", 2)
    headers = await sign_in(api_client, student)

    for index in range(2):
        course = await make_course(db_session, owner, title=f"Khóa {index}")
        assert (await api_client.put(cart_url(course), headers=headers)).status_code == 200

    one_too_many = await make_course(db_session, owner, title="Khóa thừa")
    response = await api_client.put(cart_url(one_too_many), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CART_FULL"


async def test_a_full_cart_still_accepts_what_is_already_in_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-adding writes nothing, so the ceiling has no reason to refuse it."""
    monkeypatch.setattr(commerce_service, "MAX_CART_ITEMS", 1)
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.put(cart_url(course), headers=headers)
    response = await api_client.put(cart_url(course), headers=headers)

    assert response.status_code == 200


# --- Cart: what comes out --------------------------------------------------


async def test_an_untouched_account_has_an_empty_cart(
    api_client: AsyncClient, student: User
) -> None:
    """No cart row exists yet; the answer is still a cart, not a 404."""
    headers = await sign_in(api_client, student)

    response = await api_client.get("/api/v1/cart", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": "0.00"}


async def test_a_course_can_be_taken_out(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(cart_url(course), headers=headers)

    response = await api_client.delete(cart_url(course), headers=headers)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": "0.00"}


async def test_taking_out_what_is_not_there_is_not_an_error(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.delete(cart_url(course), headers=headers)

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_the_cart_can_be_emptied(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    first = await make_course(db_session, owner, title="Một")
    second = await make_course(db_session, owner, title="Hai")
    headers = await sign_in(api_client, student)
    await api_client.put(cart_url(first), headers=headers)
    await api_client.put(cart_url(second), headers=headers)

    response = await api_client.delete("/api/v1/cart", headers=headers)

    assert response.status_code == 204
    after = await api_client.get("/api/v1/cart", headers=headers)
    assert after.json()["items"] == []


async def test_a_course_withdrawn_from_sale_leaves_the_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """It is not deleted behind the person's back -- it stops being shown and
    stops being charged for, which is what "what you can buy now" means."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(cart_url(course), headers=headers)

    course.status = "draft"
    await db_session.flush()

    response = await api_client.get("/api/v1/cart", headers=headers)

    assert response.json() == {"items": [], "total": "0.00"}


async def test_a_line_bought_in_the_meantime_is_marked_and_not_charged_for(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Enrolling in another tab is the ordinary way this happens."""
    free = await make_course(db_session, owner, price="0", title="Miễn phí")
    paid = await make_course(db_session, owner, price="199000", title="Có phí")
    headers = await sign_in(api_client, student)
    await api_client.put(cart_url(free), headers=headers)
    await api_client.put(cart_url(paid), headers=headers)

    db_session.add(Enrollment(user_id=student.id, course_id=free.id))
    await db_session.flush()

    body = (await api_client.get("/api/v1/cart", headers=headers)).json()

    owned = {item["course"]["id"]: item["already_enrolled"] for item in body["items"]}
    assert owned == {str(free.id): True, str(paid.id): False}
    assert body["total"] == "199000.00"


async def test_one_cart_per_person(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    mine = await sign_in(api_client, student)
    await api_client.put(cart_url(course), headers=mine)

    someone_else = await sign_in(api_client, await make_user(db_session, "student"))
    response = await api_client.get("/api/v1/cart", headers=someone_else)

    assert response.json()["items"] == []


async def test_the_cart_needs_a_session(api_client: AsyncClient) -> None:
    assert (await api_client.get("/api/v1/cart")).status_code == 401


# --- Wishlist --------------------------------------------------------------


async def test_a_course_can_be_saved_for_later(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.put(wishlist_url(course), headers=headers)

    assert response.status_code == 204
    listing = (await api_client.get("/api/v1/wishlist", headers=headers)).json()
    assert [item["course"]["id"] for item in listing["items"]] == [str(course.id)]
    assert listing["total"] == 1


async def test_saving_twice_saves_once(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.put(wishlist_url(course), headers=headers)
    response = await api_client.put(wishlist_url(course), headers=headers)

    assert response.status_code == 204
    listing = (await api_client.get("/api/v1/wishlist", headers=headers)).json()
    assert listing["total"] == 1


async def test_a_course_you_are_enrolled_in_can_still_be_saved(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Where the wishlist deliberately parts company with the cart: nothing is
    ever paid out of it, so refusing would buy nothing."""
    course = await make_course(db_session, owner)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    await db_session.flush()
    headers = await sign_in(api_client, student)

    response = await api_client.put(wishlist_url(course), headers=headers)

    assert response.status_code == 204


async def test_a_draft_course_cannot_be_saved(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner, status="draft")
    headers = await sign_in(api_client, student)

    response = await api_client.put(wishlist_url(course), headers=headers)

    assert response.status_code == 404


async def test_a_saved_course_can_be_unsaved(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(wishlist_url(course), headers=headers)

    response = await api_client.delete(wishlist_url(course), headers=headers)

    assert response.status_code == 204
    listing = (await api_client.get("/api/v1/wishlist", headers=headers)).json()
    assert listing["items"] == []


async def test_unsaving_what_was_never_saved_is_not_an_error(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.delete(wishlist_url(course), headers=headers)

    assert response.status_code == 204


async def test_a_withdrawn_course_leaves_the_wishlist_and_its_count(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The count is taken through the same filter as the listing, so "trang 2 /
    7" cannot promise a page the filter then empties."""
    shown = await make_course(db_session, owner, title="Còn bán")
    withdrawn = await make_course(db_session, owner, title="Đã gỡ")
    headers = await sign_in(api_client, student)
    await api_client.put(wishlist_url(shown), headers=headers)
    await api_client.put(wishlist_url(withdrawn), headers=headers)

    withdrawn.status = "draft"
    await db_session.flush()

    listing = (await api_client.get("/api/v1/wishlist", headers=headers)).json()

    assert [item["course"]["id"] for item in listing["items"]] == [str(shown.id)]
    assert listing["total"] == 1


async def test_the_wishlist_pages(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    headers = await sign_in(api_client, student)
    for index in range(3):
        course = await make_course(db_session, owner, title=f"Khóa {index}")
        await api_client.put(wishlist_url(course), headers=headers)

    response = await api_client.get(
        "/api/v1/wishlist", headers=headers, params={"page": 2, "page_size": 2}
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["page"] == 2


async def test_saved_ids_come_back_on_their_own(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """What the heart on a catalogue card is drawn from."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(wishlist_url(course), headers=headers)

    response = await api_client.get("/api/v1/wishlist/course-ids", headers=headers)

    assert response.json() == {"course_ids": [str(course.id)]}


async def test_one_wishlist_per_person(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    await api_client.put(wishlist_url(course), headers=await sign_in(api_client, student))

    someone_else = await sign_in(api_client, await make_user(db_session, "student"))
    response = await api_client.get("/api/v1/wishlist", headers=someone_else)

    assert response.json()["items"] == []


async def test_the_wishlist_needs_a_session(api_client: AsyncClient) -> None:
    assert (await api_client.get("/api/v1/wishlist")).status_code == 401
