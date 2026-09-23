"""Discount codes: what applies, what refuses, and what the counter does.

Three groups, and they are about different things on purpose.

The **refusals** are checked one at a time because each one has to arrive with
its own code: a page that can only say "mã không dùng được" makes somebody
holding a leaflet guess whether to try again tomorrow, buy something else, or
give up.

The **arithmetic** is checked on numbers chosen so that a wrong rounding rule
or a wrong base cannot produce the right answer by accident -- a percentage
that lands on half a đồng, a fixed amount larger than the cart, a cart with a
line the person meanwhile came to own.

The **counter** is checked separately from both, because it is the only thing
here that writes, and the whole design of it is that typing a code does not
move it.

Every assertion is about the caller's own cart and one coupon this test made,
so a developer database full of seeded courses and an empty CI database give
the same answers.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coupon, CouponCourse, Course, Enrollment, User
from app.services import commerce as commerce_service
from app.services import coupons as coupons_service
from tests.api.test_commerce import make_course, make_user, sign_in

NOW = datetime.now(UTC)
YESTERDAY = NOW - timedelta(days=1)
TOMORROW = NOW + timedelta(days=1)


async def make_coupon(
    session: AsyncSession,
    *,
    code: str | None = None,
    discount_type: str = "percent",
    value: str = "50",
    scope: str = "site",
    max_uses: int | None = None,
    used_count: int = 0,
    valid_from: datetime = YESTERDAY,
    valid_to: datetime | None = None,
    courses: tuple[Course, ...] = (),
) -> Coupon:
    """A coupon, live by default, with its dates spelled out.

    `valid_from` is never left to the column default: the default is filled in
    by Postgres, and reading it back afterwards would be a lazy load in an
    async session -- the kind of failure that has nothing to do with coupons.
    """
    coupon = Coupon(
        code=code or f"GIAM{uuid.uuid4().hex[:8].upper()}",
        discount_type=discount_type,
        value=Decimal(value),
        scope=scope,
        max_uses=max_uses,
        used_count=used_count,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(coupon)
    await session.flush()

    for course in courses:
        session.add(CouponCourse(coupon_id=coupon.id, course_id=course.id))
    await session.flush()

    return coupon


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


async def apply(client: AsyncClient, code: str, headers: dict[str, str]):
    return await client.post(
        "/api/v1/cart/coupon", json={"code": code}, headers=headers
    )


# --- What a coupon takes off -----------------------------------------------


async def test_a_percentage_comes_off_the_whole_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner, price="199000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 200
    body = response.json()
    assert body["subtotal"] == "199000.00"
    assert body["discount"] == "99500.00"
    assert body["total"] == "99500.00"
    assert body["course_ids"] == [str(course.id)]
    assert body["coupon"]["code"] == coupon.code
    assert body["coupon"]["discount_type"] == "percent"


async def test_a_fixed_amount_comes_off_the_total(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner, price="199000")
    coupon = await make_coupon(db_session, discount_type="fixed", value="50000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["discount"] == "50000.00"
    assert body["total"] == "149000.00"


async def test_a_voucher_bigger_than_the_cart_stops_at_zero(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The remainder is not credit: there is nowhere to keep it, and a
    negative total is a number no payment gateway will take."""
    course = await make_course(db_session, owner, price="199000")
    coupon = await make_coupon(db_session, discount_type="fixed", value="500000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["discount"] == "199000.00"
    assert body["total"] == "0.00"


async def test_a_percentage_is_rounded_to_whole_dong(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """15% of 99.999 ₫ is 14.999,85 ₫ — an amount VNPay cannot be asked for."""
    course = await make_course(db_session, owner, price="99999")
    coupon = await make_coupon(db_session, discount_type="percent", value="15")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["discount"] == "15000.00"
    # And the three numbers still add up, which is why the rounding is applied
    # to the discount rather than to the total.
    assert body["total"] == "84999.00"


async def test_a_line_the_person_already_owns_is_not_discounted(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """It is not being paid for, so taking a percentage off it would show a
    discount bigger than the bill."""
    paying = await make_course(db_session, owner, price="199000")
    owned = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{paying.id}", headers=headers)
    await api_client.put(f"/api/v1/cart/courses/{owned.id}", headers=headers)

    db_session.add(Enrollment(user_id=student.id, course_id=owned.id))
    await db_session.flush()
    coupon = await make_coupon(db_session, discount_type="percent", value="50")

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["subtotal"] == "199000.00"
    assert body["discount"] == "99500.00"
    assert body["course_ids"] == [str(paying.id)]


async def test_a_cart_of_free_courses_takes_the_code_and_saves_nothing(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Not a refusal: the cart is payable, it just comes to nothing. Refusing
    would mean explaining why a valid code is "invalid" on a valid cart."""
    free = await make_course(db_session, owner, price="0")
    coupon = await make_coupon(db_session, discount_type="fixed", value="100000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{free.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["discount"] == "0.00"
    assert body["total"] == "0.00"


# --- Scope ------------------------------------------------------------------


async def test_a_course_scoped_coupon_only_touches_its_own_courses(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    covered = await make_course(db_session, owner, price="199000")
    other = await make_course(db_session, owner, price="199000")
    coupon = await make_coupon(
        db_session,
        discount_type="percent",
        value="50",
        scope="courses",
        courses=(covered,),
    )
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{covered.id}", headers=headers)
    await api_client.put(f"/api/v1/cart/courses/{other.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["subtotal"] == "398000.00"
    assert body["discount"] == "99500.00"
    assert body["total"] == "298500.00"
    assert body["course_ids"] == [str(covered.id)]


async def test_a_coupon_for_courses_that_are_not_in_the_cart_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """A live code and a wrong cart. The message is about the cart."""
    elsewhere = await make_course(db_session, owner)
    in_cart = await make_course(db_session, owner)
    coupon = await make_coupon(db_session, scope="courses", courses=(elsewhere,))
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{in_cart.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COUPON_NOT_APPLICABLE"


async def test_a_site_coupon_lists_every_payable_line(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    first = await make_course(db_session, owner, price="100000")
    second = await make_course(db_session, owner, price="200000")
    coupon = await make_coupon(db_session, discount_type="fixed", value="30000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{first.id}", headers=headers)
    await api_client.put(f"/api/v1/cart/courses/{second.id}", headers=headers)

    body = (await apply(api_client, coupon.code, headers)).json()

    assert set(body["course_ids"]) == {str(first.id), str(second.id)}
    assert body["total"] == "270000.00"


# --- Refusals ---------------------------------------------------------------


async def test_an_unknown_code_is_a_404(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, "KHONGCOMANAY", headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COUPON_NOT_FOUND"


async def test_a_code_typed_in_lower_case_with_spaces_still_works(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Phones capitalise nothing and people paste with whitespace."""
    course = await make_course(db_session, owner, price="199000")
    coupon = await make_coupon(db_session, code="TET2026", value="10")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, "  tet2026 ", headers)

    assert response.status_code == 200
    assert response.json()["coupon"]["code"] == coupon.code


async def test_a_coupon_that_has_not_started_says_when_it_does(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    starts = NOW + timedelta(days=7)
    coupon = await make_coupon(db_session, valid_from=starts)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "COUPON_NOT_STARTED"
    assert starts.astimezone().strftime("%d/%m/%Y") in detail["message"]


async def test_an_expired_coupon_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    coupon = await make_coupon(
        db_session, valid_from=NOW - timedelta(days=30), valid_to=YESTERDAY
    )
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COUPON_EXPIRED"


async def test_a_coupon_with_no_end_date_never_expires(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    coupon = await make_coupon(db_session, valid_to=None)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 200
    assert response.json()["coupon"]["valid_to"] is None


async def test_a_coupon_that_is_out_of_uses_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    coupon = await make_coupon(db_session, max_uses=100, used_count=100)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COUPON_EXHAUSTED"


async def test_the_last_use_is_still_a_use(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """99 of 100 used is a working coupon -- off-by-one in the other direction
    would quietly kill the last one of every campaign."""
    course = await make_course(db_session, owner)
    coupon = await make_coupon(db_session, max_uses=100, used_count=99)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    assert (await apply(api_client, coupon.code, headers)).status_code == 200


async def test_an_empty_cart_is_told_about_the_cart_not_the_code(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    """Even for a code that does not exist: "mã không tồn tại" on an empty cart
    sends the reader after the wrong problem."""
    headers = await sign_in(api_client, student)

    response = await apply(api_client, "KHONGCOMANAY", headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CART_EMPTY"


async def test_a_cart_of_only_owned_courses_has_nothing_to_discount(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    await db_session.flush()
    coupon = await make_coupon(db_session)

    response = await apply(api_client, coupon.code, headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CART_EMPTY"


async def test_a_course_withdrawn_from_sale_is_not_discounted(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The cart stops charging for it, so the coupon must stop counting it."""
    staying = await make_course(db_session, owner, price="199000")
    leaving = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{staying.id}", headers=headers)
    await api_client.put(f"/api/v1/cart/courses/{leaving.id}", headers=headers)

    leaving.status = "draft"
    await db_session.flush()
    coupon = await make_coupon(db_session, discount_type="percent", value="50")

    body = (await apply(api_client, coupon.code, headers)).json()

    assert body["subtotal"] == "199000.00"
    assert body["discount"] == "99500.00"
    assert body["course_ids"] == [str(staying.id)]


async def test_a_signed_out_visitor_cannot_try_a_code(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/cart/coupon", json={"code": "TET2026"})

    assert response.status_code == 401


async def test_a_code_too_short_to_be_one_is_refused_before_the_database(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await apply(api_client, "ab", headers)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


# --- The counter ------------------------------------------------------------


async def test_trying_a_code_does_not_use_it_up(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The whole reason the count moves at payment time: otherwise a limited
    campaign could be emptied by people opening the cart page."""
    course = await make_course(db_session, owner)
    coupon = await make_coupon(db_session, max_uses=1)
    headers = await sign_in(api_client, student)
    await api_client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)

    await apply(api_client, coupon.code, headers)
    await apply(api_client, coupon.code, headers)

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 0


async def test_consuming_a_coupon_records_one_use(
    db_session: AsyncSession
) -> None:
    coupon = await make_coupon(db_session, max_uses=2)

    await coupons_service.consume(db_session, coupon.id)

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 1


async def test_the_use_after_the_last_one_is_refused(
    db_session: AsyncSession
) -> None:
    """What two checkouts racing for the last use look like from the loser's
    side: the `UPDATE` matches no row, and nothing is written."""
    coupon = await make_coupon(db_session, max_uses=1)

    await coupons_service.consume(db_session, coupon.id)

    with pytest.raises(coupons_service.CouponExhaustedError):
        await coupons_service.consume(db_session, coupon.id)

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 1


async def test_an_unlimited_coupon_keeps_counting(db_session: AsyncSession) -> None:
    """`max_uses` NULL means no ceiling -- and the count still moves, because
    "how many times was this used" is a question worth answering."""
    coupon = await make_coupon(db_session, max_uses=None)

    for _ in range(3):
        await coupons_service.consume(db_session, coupon.id)

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 3


# --- What the table itself refuses ------------------------------------------


async def test_a_percentage_over_a_hundred_cannot_be_stored(
    db_session: AsyncSession
) -> None:
    """Not only the admin screen will write this table: a seed script and a
    psql session are each one typo away from handing money back."""
    with pytest.raises(IntegrityError):
        await make_coupon(db_session, discount_type="percent", value="150")
    await db_session.rollback()


async def test_a_code_in_lower_case_cannot_be_stored(
    db_session: AsyncSession
) -> None:
    """Otherwise `tet2026` and `TET2026` would be two campaigns, and the
    lookup would find whichever one was typed."""
    with pytest.raises(IntegrityError):
        await make_coupon(db_session, code="tet2026")
    await db_session.rollback()


async def test_a_campaign_cannot_end_before_it_starts(
    db_session: AsyncSession
) -> None:
    with pytest.raises(IntegrityError):
        await make_coupon(db_session, valid_from=TOMORROW, valid_to=YESTERDAY)
    await db_session.rollback()


async def test_more_uses_than_the_campaign_allows_cannot_be_stored(
    db_session: AsyncSession
) -> None:
    """The floor under the conditional UPDATE in the service."""
    with pytest.raises(IntegrityError):
        await make_coupon(db_session, max_uses=10, used_count=11)
    await db_session.rollback()


# --- The service, called the way the checkout will call it ------------------


async def test_the_checkout_can_hand_in_the_cart_it_already_read(
    db_session: AsyncSession, student: User, owner: User
) -> None:
    """The payment task turns one particular cart into an order; re-reading it
    inside the coupon check would be a second read of a moving thing."""
    course = await make_course(db_session, owner, price="199000")
    await commerce_service.add_to_cart(db_session, course.id, student)
    cart = await commerce_service.get_cart(db_session, student)
    coupon = await make_coupon(db_session, discount_type="percent", value="25")

    discount = await coupons_service.apply_to_cart(
        db_session, coupon.code, student, cart=cart
    )

    assert discount.subtotal == Decimal("199000.00")
    assert discount.discount == Decimal("49750.00")
    assert discount.total == Decimal("149250.00")
