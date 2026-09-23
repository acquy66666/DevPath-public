"""Discount codes on the wire."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.coupon import COUPON_SCOPES, DISCOUNT_TYPES, MAX_CODE_LENGTH

DiscountType = Literal[DISCOUNT_TYPES]  # type: ignore[valid-type]
CouponScope = Literal[COUPON_SCOPES]  # type: ignore[valid-type]


class CouponApplyIn(BaseModel):
    """A code somebody typed.

    Sent in a body rather than in the path: a coupon code ends up in nginx's
    access log, in browser history and in the `Referer` of whatever the page
    loads next if it travels in a URL. It is not a secret, but a campaign code
    leaking out of a private beta by way of a log file is a real way to lose
    one.
    """

    code: str = Field(min_length=3, max_length=MAX_CODE_LENGTH)


class CouponOut(BaseModel):
    """The coupon itself -- enough to draw "giảm 50%" next to the total.

    `used_count` and `max_uses` are deliberately absent: how much of a campaign
    is left is the shop's business, and a page that showed "còn 3 lượt" would
    be wrong the moment somebody else checked out.
    """

    model_config = ConfigDict(from_attributes=True)

    code: str
    discount_type: DiscountType
    #: A percentage for `percent`, an amount in VND for `fixed`.
    value: Decimal
    scope: CouponScope
    #: NULL means the code has no end date.
    valid_to: datetime | None


class CartDiscountOut(BaseModel):
    """What a code takes off the caller's cart, as it stands right now.

    Nothing is stored by asking: the answer is only true for this cart at this
    moment, and the checkout re-runs the same checks before it charges
    anything. Removing a course afterwards changes every number here, which is
    why the page asks again whenever the cart changes.
    """

    coupon: CouponOut
    #: The cart lines the coupon covers, so the page can mark them. Every
    #: payable line for a site-wide code.
    course_ids: list[uuid.UUID]
    #: What the cart costs without the code -- the same number `GET /cart`
    #: gives, owned lines already excluded.
    subtotal: Decimal
    #: Rounded to whole đồng; a percentage never leaves a fraction behind.
    discount: Decimal
    #: `subtotal - discount`, floored at zero.
    total: Decimal
