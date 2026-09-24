"""Buying what is in the cart: the order, the payment URL, and the callback.

Three steps, and the interesting part is which of them is allowed to decide
that money has been paid.

**Creating an order** freezes a quote: the courses, each at today's price, the
coupon as it applies right now, and a total. From that moment the numbers stop
moving -- a sale that starts an hour later does not change what the gateway was
asked to charge, and a campaign that is edited does not change what a receipt
says. The cart is *not* emptied here: nothing has been paid for yet, and an
abandoned checkout that ate somebody's cart is a bug they experience as lost
work.

**The payment URL** is a signed string; building one commits to nothing.

**The IPN decides.** VNPay calls the backend directly, server to server, and
that callback -- not the browser coming back from the bank -- is what moves an
order to `paid` and enrols anybody. The browser's return URL carries the same
parameters, but a browser is a thing a person controls: treating it as proof of
payment means anyone who can read a query string can enrol themselves for free.
So the return URL is a page that *asks this API what happened*, and this module
never reads it.

Everything the callback does happens in one transaction: the event log, the
order's new state, the enrolments, the coupon's use, the cart lines going away.
A crash halfway through would otherwise leave a paid order whose buyer cannot
open the course, which is the one failure that costs a person money.

The callback is also **answered in VNPay's own dialect** -- `{"RspCode": ...,
"Message": ...}` with HTTP 200 even for a refusal -- because VNPay retries
anything else. Our error envelope is for our own frontend; the gateway has
never heard of it.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import Select, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DomainError
from app.models import (
    Cart,
    CartItem,
    Category,
    Course,
    Order,
    OrderItem,
    PaymentEvent,
    User,
)
from app.services import commerce as commerce_service
from app.services import coupons as coupons_service
from app.services import enrollments as enrollments_service
from app.services import vnpay
from app.services.commerce import EmptyCartError

ZERO = Decimal("0.00")

#: No I, O, 0 or 1: the code gets read out loud and typed back in.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_RANDOM_LENGTH = 6
#: How many times to try again if a generated code is already taken. One
#: collision in 32^6 is already unlikely; three in a row is not a thing that
#: happens, and a loop with no end is a request that never answers.
CODE_ATTEMPTS = 5


class OrderNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "ORDER_NOT_FOUND"


class OrderCodeError(DomainError):
    """Could not find an unused order code, which is not a thing that happens."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "ORDER_CODE_UNAVAILABLE"


class OrderNotPayableError(DomainError):
    """Already paid, already failed, or cancelled. Not a thing to pay twice."""

    status_code = status.HTTP_409_CONFLICT
    code = "ORDER_NOT_PAYABLE"


class PaymentNotConfiguredError(DomainError):
    """No merchant credentials on this server.

    503 and a sentence saying so, like storage and the AI assistant: the
    feature is absent from the deployment, not broken by the request.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "PAYMENT_NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class OrderLine:
    """One line of a receipt: the course, and what it cost that day."""

    course: Course
    instructor: User
    category: Category
    unit_price: Decimal


@dataclass(frozen=True, slots=True)
class OrderView:
    order: Order
    lines: list[OrderLine]


# --- Reading ---------------------------------------------------------------


def _lines_query(order_id: uuid.UUID) -> Select:
    """The receipt's lines, with no visibility filter anywhere in it.

    Deliberate, and the same reasoning as the list of enrolments: a course
    taken off sale afterwards must not make an old receipt unprintable. The two
    inner joins are safe for the same reason -- both of those foreign keys are
    RESTRICT, so the rows they point at cannot have gone anywhere.
    """
    return (
        select(Course, User, Category, OrderItem.unit_price)
        .select_from(OrderItem)
        .join(Course, Course.id == OrderItem.course_id)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.created_at, OrderItem.id)
    )


async def _view(session: AsyncSession, order: Order) -> OrderView:
    rows = (await session.execute(_lines_query(order.id))).all()
    return OrderView(
        order=order,
        lines=[
            OrderLine(
                course=course,
                instructor=instructor,
                category=category,
                unit_price=price,
            )
            for course, instructor, category, price in rows
        ],
    )


async def get_for_user(session: AsyncSession, code: str, user: User) -> OrderView:
    """One of the caller's own orders, by the code printed on it.

    Somebody else's order is a 404 rather than a 403: the code is the only
    thing an outsider could guess, and telling them a guess was right is the
    whole of what they were after.
    """
    order = await session.scalar(
        select(Order).where(Order.code == code.strip().upper(), Order.user_id == user.id)
    )
    if order is None:
        raise OrderNotFoundError("Không tìm thấy đơn hàng")

    return await _view(session, order)


# --- Creating --------------------------------------------------------------


def _new_code(now: datetime) -> str:
    stamp = now.astimezone(vnpay.VIETNAM).strftime("%y%m%d")
    tail = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_RANDOM_LENGTH))
    return f"DP{stamp}{tail}"


async def create_from_cart(
    session: AsyncSession,
    user: User,
    *,
    coupon_code: str | None = None,
    now: datetime | None = None,
) -> OrderView:
    """Turn what is in the cart into an order, at today's prices.

    The coupon is checked here, against this cart, by the same code the cart
    page used -- an expired code typed twenty minutes ago is refused now, with
    the same message. What it is *not* is used up: that happens when the money
    arrives, so an abandoned checkout does not spend a use.

    Lines the buyer already owns are left out rather than refused. They are
    already excluded from the cart's total, and refusing the whole checkout
    because one line became theirs in another tab would be a dead end with no
    button to press.
    """
    now = now or datetime.now(UTC)

    cart = await commerce_service.get_cart(session, user)
    payable = [line for line in cart.lines if not line.already_enrolled]
    if not payable:
        raise EmptyCartError("Giỏ hàng chưa có khóa học nào cần thanh toán")

    discount = ZERO
    coupon_id: uuid.UUID | None = None
    stored_code: str | None = None
    if coupon_code:
        applied = await coupons_service.apply_to_cart(
            session, coupon_code, user, cart=cart, now=now
        )
        discount = applied.discount
        coupon_id = applied.coupon.id
        stored_code = applied.coupon.code

    values = {
        "user_id": user.id,
        "subtotal": cart.total,
        "discount": discount,
        "total": (cart.total - discount).quantize(ZERO),
        "coupon_id": coupon_id,
        "coupon_code": stored_code,
        "status": "pending",
        "payment_provider": "vnpay",
    }

    # ON CONFLICT DO NOTHING and look at what came back, rather than catching an
    # IntegrityError: a caught constraint violation poisons the transaction and
    # would take the savepoint dance to recover from. Here a taken code simply
    # writes nothing and the loop tries another one.
    order_id = None
    for _ in range(CODE_ATTEMPTS):
        order_id = await session.scalar(
            insert(Order)
            .values(code=_new_code(now), **values)
            .on_conflict_do_nothing(constraint="uq_orders_code")
            .returning(Order.id)
        )
        if order_id is not None:
            break

    if order_id is None:
        # Five collisions in 32^6 does not happen; if it somehow does, the
        # honest answer is a failure rather than a sixth try.
        raise OrderCodeError("Không tạo được mã đơn hàng, thử lại giúp mình nhé")

    order = await session.get_one(Order, order_id)

    for line in payable:
        session.add(
            OrderItem(
                order_id=order.id,
                course_id=line.course.id,
                # Read from the course, not from the cart's total: this is the
                # number that must still be true on a receipt printed next year.
                unit_price=line.course.price,
            )
        )

    await session.commit()
    return await _view(session, order)


# --- Paying ----------------------------------------------------------------


async def payment_url(
    session: AsyncSession,
    code: str,
    user: User,
    *,
    settings: Settings,
    ip_address: str,
    now: datetime | None = None,
) -> str:
    """A signed VNPay URL for one of the caller's pending orders.

    Re-requestable on purpose: a person who closed the bank's page has an order
    sitting there and needs a way back to it, and building the URL again costs
    nothing and changes nothing.
    """
    view = await get_for_user(session, code, user)
    order = view.order

    if order.status != "pending":
        raise OrderNotPayableError("Đơn hàng này không còn chờ thanh toán")

    if not settings.vnpay_enabled:
        raise PaymentNotConfiguredError(
            "Máy chủ chưa cấu hình cổng thanh toán VNPay. "
            "Xem backend/README.md, mục Thanh toán."
        )

    parameters = vnpay.payment_parameters(
        tmn_code=settings.vnpay_tmn_code,
        return_url=settings.vnpay_return_url,
        code=order.code,
        amount=order.total,
        ip_address=ip_address,
        now=now or datetime.now(UTC),
        expire_minutes=settings.vnpay_expire_minutes,
    )

    return vnpay.payment_url(
        base_url=settings.vnpay_payment_url,
        secret=settings.vnpay_hash_secret,
        parameters=parameters,
    )


async def _clear_purchased_lines(
    session: AsyncSession, user_id: uuid.UUID, course_ids: list[uuid.UUID]
) -> None:
    """Take what was just bought out of the buyer's cart.

    Only those lines: a cart may hold courses that were not part of this order,
    and emptying it would throw away an intention nobody paid for or cancelled.
    """
    cart_id = await session.scalar(select(Cart.id).where(Cart.user_id == user_id))
    if cart_id is None:
        return

    await session.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.course_id.in_(course_ids)
        )
    )


async def _mark_paid(
    session: AsyncSession, order: Order, params: dict[str, str], now: datetime
) -> None:
    """Everything that follows from the money having arrived."""
    order.status = "paid"
    order.paid_at = now
    # The gateway's own id for the transaction, which is what a refund or a
    # reconciliation is done by. `vnp_TxnRef` is the fallback because it is our
    # own code and always there: a paid order with no reference at all cannot
    # be stored (`ck_orders_paid_evidence`) and must not be lost over a field
    # the gateway left out.
    order.provider_txn_id = (
        str(params.get("vnp_TransactionNo") or "").strip()
        or str(params.get("vnp_BankTranNo") or "").strip()
        or order.code
    )

    course_ids = list(
        await session.scalars(
            select(OrderItem.course_id).where(OrderItem.order_id == order.id)
        )
    )
    for course_id in course_ids:
        await enrollments_service.grant(
            session, course_id, order.user_id, source="purchase"
        )

    await _clear_purchased_lines(session, order.user_id, course_ids)

    if order.coupon_id is not None:
        try:
            await coupons_service.consume(session, order.coupon_id)
        except coupons_service.CouponExhaustedError:
            # The campaign ran out between checkout and the callback. The money
            # has already moved, so the choice is to honour the order or to
            # refuse somebody who has paid -- and the second one is not a
            # choice. The use goes unrecorded (`ck_coupons_uses_left` will not
            # store an overspend); `orders.coupon_id` is the true record of who
            # used what, which is why the column exists.
            pass


def _record_event(
    session: AsyncSession,
    order: Order | None,
    params: dict[str, str],
    *,
    valid: bool,
) -> None:
    """Write the callback down before anything is decided about it."""
    session.add(
        PaymentEvent(
            order_id=order.id if order is not None else None,
            provider="vnpay",
            payload=dict(params),
            signature_valid=valid,
        )
    )


async def handle_vnpay_ipn(
    session: AsyncSession,
    params: dict[str, str],
    *,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[str, str]:
    """VNPay's server-to-server callback. Returns (RspCode, Message).

    The codes are VNPay's, not ours: "00" confirm success, "01" order not
    found, "02" order already confirmed, "04" invalid amount, "97" invalid
    signature. Every one of them goes back with HTTP 200, because VNPay reads
    the body and retries anything it cannot read.

    The order of the checks is the order in which a wrong answer would be
    expensive:

    1. **Signature**, before the parameters are believed at all. An unsigned
       callback is a stranger's HTTP request.
    2. **Order**, then **amount**. An amount that does not match what we asked
       for means this callback is not about this order, whatever it says.
    3. **State**. A retried callback about an order that is already settled is
       answered "02" and changes nothing -- this is the check that stops a
       second enrolment and a second coupon use.

    Every branch writes the event first, so the log tells the same story
    whether the callback was accepted or thrown away.
    """
    now = now or datetime.now(UTC)
    # With no secret there is nothing to check a signature against, and an
    # empty key would "verify" whatever a stranger signed with the same empty
    # key. An unconfigured server does not guess.
    valid = settings.vnpay_enabled and vnpay.verify(params, settings.vnpay_hash_secret)

    code = str(params.get("vnp_TxnRef", "")).strip()
    order = None
    if code:
        order = await session.scalar(
            # FOR UPDATE: two copies of the same callback -- which VNPay really
            # does send -- would otherwise both read a pending order and both
            # enrol its buyer. The second one waits here, then finds the state
            # the first one left and answers "02".
            select(Order).where(Order.code == code).with_for_update()
        )

    _record_event(session, order, params, valid=valid)

    if not valid:
        await session.commit()
        return "97", "Invalid signature"

    if order is None:
        await session.commit()
        return "01", "Order not found"

    amount = vnpay.amount_of(params)
    if amount is None or amount != order.total:
        await session.commit()
        return "04", "Invalid amount"

    if order.status != "pending":
        await session.commit()
        return "02", "Order already confirmed"

    if vnpay.paid_successfully(params):
        await _mark_paid(session, order, params, now)
    else:
        order.status = "failed"
        order.failure_code = str(params.get("vnp_ResponseCode", ""))[:10] or None

    await session.commit()
    return "00", "Confirm Success"
