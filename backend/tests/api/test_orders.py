"""Buying a cart: the order, the payment URL, and VNPay's callback.

The callback tests are the ones that matter. VNPay retries an IPN until it is
answered "00", so a handler that enrols on every delivery enrols twice; a
handler that believes an unsigned request lets anyone enrol themselves for
free; and a handler that believes the amount in the callback lets anyone enrol
themselves for a thousand đồng. All three are one line of code away, and all
three are checked here against a callback signed exactly the way the gateway
signs it.

No merchant account is needed for any of this: the signature is the whole
protocol, and a test can produce a real one with a test secret.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Coupon, Course, Enrollment, Order, OrderItem, PaymentEvent, User
from app.services import vnpay
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_coupons import make_coupon

TMN_CODE = "DEMOCODE"
SECRET = "SANDBOX-SECRET-FOR-TESTS"


@pytest.fixture
def vnpay_configured() -> Iterator[str]:
    """Merchant credentials for the duration of one test.

    `get_settings` is cached for the process, so the object is edited in place
    and put back afterwards -- the same thing the storage tests do.
    """
    settings = get_settings()
    before = (settings.vnpay_tmn_code, settings.vnpay_hash_secret)
    object.__setattr__(settings, "vnpay_tmn_code", TMN_CODE)
    object.__setattr__(settings, "vnpay_hash_secret", SECRET)

    yield SECRET

    object.__setattr__(settings, "vnpay_tmn_code", before[0])
    object.__setattr__(settings, "vnpay_hash_secret", before[1])


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


async def add(client: AsyncClient, course: Course, headers: dict[str, str]) -> None:
    await client.put(f"/api/v1/cart/courses/{course.id}", headers=headers)


async def checkout(
    client: AsyncClient, headers: dict[str, str], coupon: str | None = None
) -> dict:
    response = await client.post(
        "/api/v1/orders",
        json={"coupon_code": coupon} if coupon else {},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def callback(
    code: str,
    amount: str,
    *,
    secret: str = SECRET,
    response_code: str = "00",
    transaction_status: str = "00",
    transaction_no: str = "14201234",
) -> dict[str, str]:
    """A VNPay IPN, signed the way the gateway signs one."""
    params = {
        "vnp_Amount": str(int(Decimal(amount) * 100)),
        "vnp_BankCode": "NCB",
        "vnp_CardType": "ATM",
        "vnp_OrderInfo": f"Thanh toan don hang {code}",
        "vnp_PayDate": "20260924153500",
        "vnp_ResponseCode": response_code,
        "vnp_TmnCode": TMN_CODE,
        "vnp_TransactionNo": transaction_no,
        "vnp_TransactionStatus": transaction_status,
        "vnp_TxnRef": code,
    }
    return {**params, "vnp_SecureHash": vnpay.sign(params, secret)}


async def send_ipn(client: AsyncClient, params: dict[str, str]):
    return await client.get("/api/v1/payments/vnpay/ipn", params=params)


# --- Making an order --------------------------------------------------------


async def test_a_cart_becomes_an_order_at_todays_prices(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    first = await make_course(db_session, owner, price="199000")
    second = await make_course(db_session, owner, price="300000")
    headers = await sign_in(api_client, student)
    await add(api_client, first, headers)
    await add(api_client, second, headers)

    order = await checkout(api_client, headers)

    assert order["status"] == "pending"
    assert order["subtotal"] == "499000.00"
    assert order["discount"] == "0.00"
    assert order["total"] == "499000.00"
    assert {item["course"]["id"] for item in order["items"]} == {
        str(first.id),
        str(second.id),
    }
    assert order["code"].startswith("DP")
    assert order["paid_at"] is None


async def test_an_order_does_not_empty_the_cart(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Nothing has been paid for yet. A checkout somebody abandons at the bank
    and comes back from must not have eaten what they picked."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)

    await checkout(api_client, headers)

    cart = (await api_client.get("/api/v1/cart", headers=headers)).json()
    assert len(cart["items"]) == 1


async def test_an_empty_cart_cannot_be_checked_out(
    api_client: AsyncClient, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.post("/api/v1/orders", json={}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CART_EMPTY"


async def test_a_course_bought_meanwhile_is_left_off_the_order(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """It is already excluded from the cart's total; refusing the whole
    checkout over it would be a dead end with no button to press."""
    paying = await make_course(db_session, owner, price="199000")
    owned = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, paying, headers)
    await add(api_client, owned, headers)
    db_session.add(Enrollment(user_id=student.id, course_id=owned.id))
    await db_session.flush()

    order = await checkout(api_client, headers)

    assert [item["course"]["id"] for item in order["items"]] == [str(paying.id)]
    assert order["total"] == "199000.00"


async def test_the_price_on_the_order_does_not_follow_the_course_afterwards(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The whole reason `order_items.unit_price` exists: a sale next week must
    not rewrite what somebody was charged today."""
    course = await make_course(db_session, owner, price="500000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    course.price = Decimal("100000")
    await db_session.flush()

    again = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert again["items"][0]["unit_price"] == "500000.00"
    assert again["total"] == "500000.00"


async def test_a_coupon_is_frozen_onto_the_order_but_not_used_up(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Used up at payment, not at checkout: an abandoned checkout must not
    spend a use of a limited campaign."""
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="25", max_uses=5)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)

    order = await checkout(api_client, headers, coupon.code)

    assert order["subtotal"] == "400000.00"
    assert order["discount"] == "100000.00"
    assert order["total"] == "300000.00"
    assert order["coupon_code"] == coupon.code

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 0


async def line_discounts(session: AsyncSession, code: str) -> dict[uuid.UUID, Decimal]:
    rows = await session.execute(
        select(OrderItem.course_id, OrderItem.discount)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.code == code)
    )
    return dict(rows.tuples().all())


async def test_the_discount_is_frozen_onto_the_lines_it_was_taken_off(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """A coupon for one course, in a cart with two courses by two people.

    Whoever teaches the other course must not see their revenue shrink
    because of it -- and reading the coupon's scope again later cannot tell
    them, because the scope can be edited after the sale.
    """
    other = await make_user(db_session, "instructor")
    covered = await make_course(db_session, owner, price="400000")
    uncovered = await make_course(db_session, other, price="300000")
    coupon = await make_coupon(
        db_session, discount_type="percent", value="30", scope="courses", courses=(covered,)
    )
    headers = await sign_in(api_client, student)
    await add(api_client, covered, headers)
    await add(api_client, uncovered, headers)

    order = await checkout(api_client, headers, coupon.code)

    assert order["discount"] == "120000.00"
    assert await line_discounts(db_session, order["code"]) == {
        covered.id: Decimal("120000.00"),
        uncovered.id: Decimal("0.00"),
    }


async def test_the_line_discounts_add_up_to_the_order_discount(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    courses = [await make_course(db_session, owner, price="199000") for _ in range(3)]
    coupon = await make_coupon(db_session, discount_type="fixed", value="100000")
    headers = await sign_in(api_client, student)
    for course in courses:
        await add(api_client, course, headers)

    order = await checkout(api_client, headers, coupon.code)

    shares = await line_discounts(db_session, order["code"])
    assert sum(shares.values()) == Decimal(order["discount"]) == Decimal("100000")
    assert sorted(shares.values()) == [Decimal("33333"), Decimal("33333"), Decimal("33334")]


async def test_an_order_without_a_coupon_discounts_no_line(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)

    order = await checkout(api_client, headers)

    assert await line_discounts(db_session, order["code"]) == {course.id: Decimal("0.00")}


async def test_a_coupon_that_expired_since_the_cart_page_is_refused_at_checkout(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    coupon = await make_coupon(
        db_session,
        valid_from=datetime.now(UTC) - timedelta(days=30),
        valid_to=datetime.now(UTC) - timedelta(days=1),
    )
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)

    response = await api_client.post(
        "/api/v1/orders", json={"coupon_code": coupon.code}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COUPON_EXPIRED"


async def test_a_signed_out_visitor_cannot_check_out(api_client: AsyncClient) -> None:
    assert (await api_client.post("/api/v1/orders", json={})).status_code == 401


# --- Reading an order -------------------------------------------------------


async def test_somebody_elses_order_is_a_404(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Not a 403: the code is the only thing an outsider could guess at, and
    confirming a guess is the whole of what they were after."""
    course = await make_course(db_session, owner)
    mine = await sign_in(api_client, student)
    await add(api_client, course, mine)
    order = await checkout(api_client, mine)

    stranger = await make_user(db_session, "student")
    theirs = await sign_in(api_client, stranger)

    response = await api_client.get(f"/api/v1/orders/{order['code']}", headers=theirs)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ORDER_NOT_FOUND"


# --- The payment URL --------------------------------------------------------


async def test_the_payment_url_is_signed_and_carries_the_order(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="399000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    response = await api_client.post(
        f"/api/v1/orders/{order['code']}/payment-url", headers=headers
    )

    assert response.status_code == 200
    url = response.json()["payment_url"]
    assert f"vnp_TxnRef={order['code']}" in url
    assert "vnp_Amount=39900000" in url
    assert "vnp_SecureHash=" in url


async def test_a_server_without_merchant_credentials_says_so(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """503 and a sentence, like storage and the AI assistant: the feature is
    absent from this deployment, not broken by the request."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    settings = get_settings()
    before = settings.vnpay_hash_secret
    object.__setattr__(settings, "vnpay_hash_secret", "")
    try:
        response = await api_client.post(
            f"/api/v1/orders/{order['code']}/payment-url", headers=headers
        )
    finally:
        object.__setattr__(settings, "vnpay_hash_secret", before)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PAYMENT_NOT_CONFIGURED"


async def test_an_order_that_is_already_paid_cannot_be_paid_again(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    await send_ipn(api_client, callback(order["code"], order["total"]))

    response = await api_client.post(
        f"/api/v1/orders/{order['code']}/payment-url", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ORDER_NOT_PAYABLE"


# --- A pending order does not wait forever ----------------------------------
#
# An order freezes its prices and its coupon when it is placed, and a payment
# URL can be asked for again. Without a deadline on the *order* -- not just on
# each URL -- a checkout placed during a sale stays payable at the sale price
# for ever: past the coupon's end date, past its last use, past an admin ending
# the campaign, past the course leaving the shop. Place a hundred orders while
# the code is live, pay them next month.


async def age(session: AsyncSession, code: str, minutes: int) -> None:
    """Move an order's placing back in time."""
    order = await session.scalar(select(Order).where(Order.code == code))
    order.created_at = datetime.now(UTC) - timedelta(minutes=minutes)
    await session.flush()


async def ask_to_pay(client: AsyncClient, code: str, headers: dict[str, str]):
    return await client.post(f"/api/v1/orders/{code}/payment-url", headers=headers)


def assert_expired(response) -> None:
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ORDER_EXPIRED"


async def test_an_order_left_past_its_window_gets_no_new_payment_url(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    await age(db_session, order["code"], get_settings().order_payment_window_minutes)

    assert_expired(await ask_to_pay(api_client, order["code"], headers))
    # Still pending, not cancelled: a payment begun inside the window may yet
    # be reported, and money that moved is honoured.
    status = await db_session.scalar(select(Order.status).where(Order.code == order["code"]))
    assert status == "pending"


async def test_money_that_moved_inside_the_window_is_honoured_after_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """VNPay's callback can land after the deadline for a payment made before
    it. The deadline stops new URLs; it never refuses a payment."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    await age(db_session, order["code"], get_settings().order_payment_window_minutes + 5)

    response = await send_ipn(api_client, callback(order["code"], order["total"]))

    assert response.json()["RspCode"] == "00"


async def test_a_payment_url_never_outlives_its_order(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Five minutes left on the order: the bank page gets five, not fifteen."""
    settings = get_settings()
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    await age(db_session, order["code"], settings.order_payment_window_minutes - 5)
    placed = await db_session.scalar(
        select(Order.created_at).where(Order.code == order["code"])
    )

    response = await ask_to_pay(api_client, order["code"], headers)

    assert response.status_code == 200, response.text
    expire = response.json()["payment_url"].split("vnp_ExpireDate=")[1].split("&")[0]
    expires = datetime.strptime(expire, vnpay.TIME_FORMAT).replace(tzinfo=vnpay.VIETNAM)
    assert expires <= placed + timedelta(minutes=settings.order_payment_window_minutes)
    assert expires < datetime.now(UTC) + timedelta(minutes=settings.vnpay_expire_minutes)


async def test_a_coupon_ended_after_checkout_stops_the_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """An admin ending a leaked code has to stop the orders already placed
    with it, not only the next ones."""
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)

    coupon.valid_to = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    assert_expired(await ask_to_pay(api_client, order["code"], headers))


async def test_a_coupon_used_up_after_checkout_stops_the_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Uses are counted when money arrives, so any number of orders can be
    placed on the last one. The URL is where that has to stop."""
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50", max_uses=1)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)

    coupon.used_count = 1
    await db_session.flush()

    assert_expired(await ask_to_pay(api_client, order["code"], headers))


async def test_a_coupon_deleted_after_checkout_stops_the_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Deleting sets `orders.coupon_id` to NULL and leaves the frozen discount
    behind -- a discount with nothing left to check it against."""
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)

    await db_session.delete(coupon)
    await db_session.flush()
    db_session.expire_all()

    assert_expired(await ask_to_pay(api_client, order["code"], headers))


async def test_a_course_withdrawn_after_checkout_stops_the_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    course.status = "draft"
    await db_session.flush()

    assert_expired(await ask_to_pay(api_client, order["code"], headers))


async def test_an_order_inside_its_window_with_everything_on_sale_is_payable(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50", max_uses=5)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)
    await age(db_session, order["code"], 10)

    response = await ask_to_pay(api_client, order["code"], headers)

    assert response.status_code == 200, response.text
    assert "vnp_Amount=20000000" in response.json()["payment_url"]


# --- The callback -----------------------------------------------------------


async def test_a_valid_ipn_pays_the_order_and_enrols_the_buyer(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    first = await make_course(db_session, owner, price="199000")
    second = await make_course(db_session, owner, price="300000")
    headers = await sign_in(api_client, student)
    await add(api_client, first, headers)
    await add(api_client, second, headers)
    order = await checkout(api_client, headers)

    response = await send_ipn(api_client, callback(order["code"], order["total"]))

    assert response.status_code == 200
    assert response.json() == {"RspCode": "00", "Message": "Confirm Success"}

    paid = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None
    assert paid["provider_txn_id"] == "14201234"

    enrolled = set(
        await db_session.scalars(
            select(Enrollment.course_id).where(Enrollment.user_id == student.id)
        )
    )
    assert enrolled == {first.id, second.id}

    # And what was bought is out of the cart, without touching anything else.
    cart = (await api_client.get("/api/v1/cart", headers=headers)).json()
    assert cart["items"] == []


async def test_paying_records_the_purchase_as_a_purchase(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """`enrollments.source` is how "who paid for what" is answered later
    without reconstructing it from orders."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    await send_ipn(api_client, callback(order["code"], order["total"]))

    source = await db_session.scalar(
        select(Enrollment.source).where(
            Enrollment.user_id == student.id, Enrollment.course_id == course.id
        )
    )
    assert source == "purchase"


async def test_paying_moves_the_students_counter_once(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    await send_ipn(api_client, callback(order["code"], order["total"]))
    await db_session.refresh(course)

    assert course.students_count == 1


async def test_an_ipn_with_a_forged_signature_changes_nothing(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """The attack this endpoint exists to refuse: a stranger's HTTP request
    saying an order was paid."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    forged = callback(order["code"], order["total"], secret="NOT-THE-SECRET")
    response = await send_ipn(api_client, forged)

    assert response.json() == {"RspCode": "97", "Message": "Invalid signature"}

    still = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert still["status"] == "pending"
    assert (
        await db_session.scalar(
            select(Enrollment.id).where(Enrollment.user_id == student.id)
        )
        is None
    )


async def test_the_same_ipn_twice_pays_once(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """VNPay really does retry until it is answered "00", so this is the
    ordinary case rather than an edge one."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    params = callback(order["code"], order["total"])

    first = await send_ipn(api_client, params)
    second = await send_ipn(api_client, params)

    assert first.json()["RspCode"] == "00"
    assert second.json() == {"RspCode": "02", "Message": "Order already confirmed"}

    enrolments = list(
        await db_session.scalars(
            select(Enrollment.id).where(Enrollment.user_id == student.id)
        )
    )
    assert len(enrolments) == 1
    await db_session.refresh(course)
    assert course.students_count == 1


async def test_an_ipn_for_an_order_nobody_has_is_told_so(
    api_client: AsyncClient, vnpay_configured: str
) -> None:
    response = await send_ipn(api_client, callback("DP260924ZZZZZZ", "199000"))

    assert response.json() == {"RspCode": "01", "Message": "Order not found"}


async def test_an_ipn_about_a_different_amount_is_refused(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Signed by VNPay and still wrong: it is not about this order, whatever
    the reference says."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    response = await send_ipn(api_client, callback(order["code"], "1000"))

    assert response.json() == {"RspCode": "04", "Message": "Invalid amount"}
    still = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert still["status"] == "pending"


async def test_a_refused_payment_fails_the_order_and_enrols_nobody(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Answered "00" all the same: the callback was delivered and understood,
    which is what that code means. Retrying it would not change the answer."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    response = await send_ipn(
        api_client,
        callback(
            order["code"],
            order["total"],
            response_code="24",
            transaction_status="02",
        ),
    )

    assert response.json()["RspCode"] == "00"
    failed = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert failed["status"] == "failed"
    assert failed["failure_code"] == "24"
    assert (
        await db_session.scalar(
            select(Enrollment.id).where(Enrollment.user_id == student.id)
        )
        is None
    )


async def test_a_successful_request_about_a_failed_transaction_is_not_a_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """The two codes disagree, and believing only the first one is how an
    unpaid order gets enrolled."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    await send_ipn(
        api_client,
        callback(order["code"], order["total"], transaction_status="02"),
    )

    failed = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert failed["status"] == "failed"


async def test_paying_uses_the_coupon_exactly_once(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50", max_uses=5)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)
    params = callback(order["code"], order["total"])

    await send_ipn(api_client, params)
    await send_ipn(api_client, params)

    used = await db_session.scalar(
        select(Coupon.used_count).where(Coupon.id == coupon.id)
    )
    assert used == 1


async def test_a_campaign_that_ran_out_meanwhile_still_honours_the_payment(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """The money has already moved. The choice is to honour the order or to
    refuse somebody who has paid, and the second one is not a choice -- so the
    use goes unrecorded and `orders.coupon_id` keeps the truth."""
    course = await make_course(db_session, owner, price="400000")
    coupon = await make_coupon(db_session, discount_type="percent", value="50", max_uses=1)
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers, coupon.code)

    # Somebody else takes the last use between checkout and the callback.
    coupon.used_count = 1
    await db_session.flush()

    response = await send_ipn(api_client, callback(order["code"], order["total"]))

    assert response.json()["RspCode"] == "00"
    paid = (
        await api_client.get(f"/api/v1/orders/{order['code']}", headers=headers)
    ).json()
    assert paid["status"] == "paid"
    assert (
        await db_session.scalar(
            select(Enrollment.id).where(Enrollment.user_id == student.id)
        )
        is not None
    )


# --- The log ----------------------------------------------------------------


async def test_every_callback_is_written_down_before_it_is_judged(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    vnpay_configured: str,
) -> None:
    """Including the forged one -- especially the forged one."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)
    order_id = await db_session.scalar(
        select(Order.id).where(Order.code == order["code"])
    )

    await send_ipn(api_client, callback(order["code"], order["total"], secret="WRONG"))
    await send_ipn(api_client, callback(order["code"], order["total"]))

    events = list(
        await db_session.scalars(
            select(PaymentEvent).where(PaymentEvent.order_id == order_id)
        )
    )

    # Told apart by what they say rather than by their order: inside one
    # transaction `now()` is the transaction's start, so both rows carry the
    # same `created_at` and sorting by it decides nothing.
    assert len(events) == 2
    assert {event.signature_valid for event in events} == {False, True}
    assert all(event.provider == "vnpay" for event in events)
    assert all(event.payload["vnp_TxnRef"] == order["code"] for event in events)


async def test_a_callback_naming_no_order_is_kept_too(
    api_client: AsyncClient, db_session: AsyncSession, vnpay_configured: str
) -> None:
    """The row that says somebody is probing the endpoint, or that our own
    references have gone wrong. `order_id` is nullable exactly for it."""
    stray = f"DP260924{uuid.uuid4().hex[:6].upper()}"

    await send_ipn(api_client, callback(stray, "199000"))

    event = await db_session.scalar(
        select(PaymentEvent).where(PaymentEvent.payload["vnp_TxnRef"].astext == stray)
    )
    assert event is not None
    assert event.order_id is None
    assert event.signature_valid is True


async def test_a_server_with_no_secret_cannot_verify_anything(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """An empty key would "verify" whatever a stranger signed with the same
    empty key, which is the one failure mode worse than refusing everything."""
    course = await make_course(db_session, owner, price="199000")
    headers = await sign_in(api_client, student)
    await add(api_client, course, headers)
    order = await checkout(api_client, headers)

    settings = get_settings()
    before = settings.vnpay_hash_secret
    object.__setattr__(settings, "vnpay_hash_secret", "")
    try:
        response = await send_ipn(api_client, callback(order["code"], order["total"], secret=""))
    finally:
        object.__setattr__(settings, "vnpay_hash_secret", before)

    assert response.json()["RspCode"] == "97"
