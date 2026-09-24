"""Discount codes: does this one apply here, and what does it take off.

Four questions, asked in this order, because the order is what makes the
refusals readable:

1. **Is there anything to pay for?** Asked before the code is even looked up:
   "mã không tồn tại" on an empty cart is a true sentence that sends the
   reader after the wrong problem.
2. **Is this a code at all?** Unknown codes are a 404 and nothing else -- the
   answer must not depend on whether a code exists but has expired, or the
   endpoint becomes a way to enumerate campaigns.
3. **Is it live?** Not started, finished, or out of uses. Each has its own
   code and its own sentence, because "mã không dùng được" tells somebody
   holding a leaflet nothing about what to do next.
4. **Does it apply to what is in the cart?** A code for two Python courses on
   a cart full of frontend courses is not an error about the code; it is an
   error about this cart, and it says which.

**Nothing here writes.** Checking a coupon is a read, even the check the
checkout does, and the count of uses moves exactly once -- in `consume`, when
an order is actually paid for. Anything else would let a person burn a
limited code by opening the cart page.

**What it discounts is only ever what is payable now.** Lines the person has
meanwhile enrolled in are already excluded from `CartView.total`, and they are
excluded here too: a 50% coupon on a cart where half the lines are already
owned takes half off what is left, not half off a number nobody is paying.

A **percentage** is rounded to whole đồng. VND has no subunit in circulation
and the payment gateway takes an integer amount, so a discount of 74.850,50 ₫
is a total that cannot be paid; the rounding is half-up, applied to the
discount rather than the total, so the total stays exactly `subtotal -
discount` and the page can show all three numbers adding up.

A **fixed** amount never exceeds what it is taken off. A 500.000 ₫ voucher on
a 399.000 ₫ cart discounts 399.000 ₫: the total floors at zero rather than
turning into credit the system has no way to hold. A cart of free courses
follows from the same rule and takes a code for nothing off -- not a refusal,
because the cart is perfectly payable; it simply comes to nothing.

Per-person limits ("one use per account") are **not** expressible yet: there
is no redemption table, and `orders.coupon_id` -- which will answer that
question -- does not exist until the payment task. `max_uses` is a limit on
the campaign, not on the person.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Coupon, CouponCourse, User
from app.services import commerce as commerce_service
from app.services.commerce import CartView, EmptyCartError

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
#: What a discount is rounded to: one đồng.
DONG = Decimal("1")


class CouponNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "COUPON_NOT_FOUND"


class CouponNotStartedError(DomainError):
    """Real code, too early. Worth its own message: it says when to come back."""

    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_NOT_STARTED"


class CouponExpiredError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_EXPIRED"


class CouponExhaustedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_EXHAUSTED"


class CouponNotApplicableError(DomainError):
    """Live code, wrong cart -- it covers none of the courses being bought."""

    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class Discount:
    """What a coupon does to one particular cart, at one particular moment."""

    coupon: Coupon
    #: The courses the coupon covers *and* the cart is paying for. The page
    #: marks these lines; a site-wide coupon lists every payable line.
    course_ids: list[uuid.UUID]
    #: What the cart costs before the code -- the same number `GET /cart`
    #: answers with.
    subtotal: Decimal
    discount: Decimal
    #: `subtotal - discount`, never below zero.
    total: Decimal
    #: `discount` shared out over `course_ids` by `split_discount`. The order
    #: freezes these onto its lines; courses not in here take nothing off.
    line_discounts: dict[uuid.UUID, Decimal]


def normalize(code: str) -> str:
    """The form codes are stored and compared in: trimmed and upper-case.

    `ck_coupons_code_upper` keeps the column in this form, so the lookup is a
    plain equality on a unique index rather than a function over the table --
    and two campaigns cannot exist as `TET2026` and `tet2026`.
    """
    return code.strip().upper()


async def find_coupon(session: AsyncSession, code: str) -> Coupon:
    """The coupon with this code, whatever case it was typed in."""
    coupon = await session.scalar(
        select(Coupon).where(Coupon.code == normalize(code))
    )
    if coupon is None:
        raise CouponNotFoundError("Mã giảm giá không tồn tại")
    return coupon


def _day(moment: datetime) -> str:
    return moment.astimezone().strftime("%d/%m/%Y")


def assert_live(coupon: Coupon, *, now: datetime | None = None) -> None:
    """The checks that are about the coupon alone, with no cart involved.

    Split out because the payment task needs exactly these again, on a coupon
    it has already looked up, at the moment the order is placed rather than at
    the moment the code was typed.
    """
    now = now or datetime.now(UTC)

    if coupon.valid_from > now:
        raise CouponNotStartedError(
            f"Mã giảm giá chỉ có hiệu lực từ ngày {_day(coupon.valid_from)}"
        )

    if coupon.valid_to is not None and coupon.valid_to <= now:
        raise CouponExpiredError(
            f"Mã giảm giá đã hết hạn ngày {_day(coupon.valid_to)}"
        )

    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise CouponExhaustedError("Mã giảm giá đã hết lượt sử dụng")


async def covered_course_ids(
    session: AsyncSession, coupon: Coupon
) -> set[uuid.UUID] | None:
    """Which courses the coupon is limited to, or None for "all of them"."""
    if coupon.scope != "courses":
        return None

    rows = await session.scalars(
        select(CouponCourse.course_id).where(CouponCourse.coupon_id == coupon.id)
    )
    return set(rows)


def _amount_off(coupon: Coupon, eligible_subtotal: Decimal) -> Decimal:
    if coupon.discount_type == "percent":
        raw = eligible_subtotal * coupon.value / HUNDRED
        return raw.quantize(DONG, rounding=ROUND_HALF_UP).quantize(ZERO)

    # Fixed: never more than what it is taken off -- see the module docstring.
    return min(coupon.value, eligible_subtotal).quantize(ZERO)


def split_discount(discount: Decimal, prices: list[Decimal]) -> list[Decimal]:
    """Share one discount out over the lines it was taken off, in whole đồng.

    Each line takes the part of the discount its price is of the total, rounded
    down; the đồng that rounding leaves over go one each to the lines rounded
    down the most (the first of them, on a tie). So the shares add up to the
    discount exactly, and none exceeds its line's price -- a share only reaches
    the price when the discount is the whole subtotal, and then every share is
    exact and nothing is left over.

    This is what lets an order carry one discount and each instructor still be
    told what *their* course actually sold for.
    """
    subtotal = sum(prices, ZERO)
    discount = min(discount, subtotal)
    if discount <= ZERO:
        return [ZERO for _ in prices]

    exact = [discount * price / subtotal for price in prices]
    shares = [value.to_integral_value(rounding=ROUND_FLOOR) for value in exact]

    leftover = int(discount - sum(shares, ZERO))
    # `sorted` is stable under `reverse=True` too, so a tie keeps list order.
    by_remainder = sorted(
        range(len(prices)), key=lambda index: exact[index] - shares[index], reverse=True
    )
    for index in by_remainder[:leftover]:
        shares[index] += DONG

    return [share.quantize(ZERO) for share in shares]


async def apply_to_cart(
    session: AsyncSession,
    code: str,
    user: User,
    *,
    cart: CartView | None = None,
    now: datetime | None = None,
) -> Discount:
    """What this code would take off this person's cart, right now.

    Reads the cart itself unless the caller already has it -- the checkout will,
    because it is about to turn that same cart into an order and must not read
    a different one in between.
    """
    if cart is None:
        cart = await commerce_service.get_cart(session, user)

    payable = [line for line in cart.lines if not line.already_enrolled]
    if not payable:
        # Before looking the code up: a coupon that "does not apply" to an
        # empty cart would be a true sentence that sends the reader after the
        # wrong problem.
        raise EmptyCartError("Giỏ hàng chưa có khóa học nào cần thanh toán")

    coupon = await find_coupon(session, code)
    assert_live(coupon, now=now)

    covered = await covered_course_ids(session, coupon)
    eligible = [
        line for line in payable if covered is None or line.course.id in covered
    ]
    if not eligible:
        raise CouponNotApplicableError(
            "Mã giảm giá không áp dụng cho khóa học nào trong giỏ hàng"
        )

    eligible_subtotal = sum((line.course.price for line in eligible), ZERO)
    discount = _amount_off(coupon, eligible_subtotal)
    shares = split_discount(discount, [line.course.price for line in eligible])

    return Discount(
        coupon=coupon,
        course_ids=[line.course.id for line in eligible],
        subtotal=cart.total,
        discount=discount,
        total=max(cart.total - discount, ZERO).quantize(ZERO),
        line_discounts={
            line.course.id: share for line, share in zip(eligible, shares, strict=True)
        },
    )


async def consume(session: AsyncSession, coupon_id: uuid.UUID) -> None:
    """Record one use, or refuse if the last one was taken meanwhile.

    The guard is in the `WHERE` clause, so two checkouts finishing at the same
    instant on the ninety-ninth use of a hundred-use code are settled by the
    row lock Postgres takes for the `UPDATE`: the second one matches no row and
    is told the code is finished. Reading `used_count` and writing back
    `used_count + 1` would let both read ninety-nine and both write a hundred.

    Callers commit: this runs inside the transaction that also writes the
    order, so a payment that fails to record cannot burn a use.
    """
    result = await session.execute(
        update(Coupon)
        .where(
            Coupon.id == coupon_id,
            (Coupon.max_uses.is_(None)) | (Coupon.used_count < Coupon.max_uses),
        )
        .values(used_count=Coupon.used_count + 1)
    )
    if result.rowcount == 0:
        raise CouponExhaustedError("Mã giảm giá đã hết lượt sử dụng")
