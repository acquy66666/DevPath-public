"""Discount codes on the wire."""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


# --- The admin's campaigns -------------------------------------------------

#: What a code may be made of: what survives being read aloud and typed on a
#: phone. Checked after trimming and upper-casing.
CODE_PATTERN = r"^[A-Z0-9_-]{3,32}$"


class _CouponRules(BaseModel):
    """The table's CHECKs, as sentences a form can show under the right box."""

    @model_validator(mode="after")
    def _rules(self):
        value = getattr(self, "value", None)
        kind = getattr(self, "discount_type", None)
        if kind == "percent" and value is not None and value > 100:
            raise ValueError("Mức giảm theo phần trăm tối đa là 100")
        valid_from = getattr(self, "valid_from", None)
        valid_to = getattr(self, "valid_to", None)
        if valid_from is not None and valid_to is not None and valid_to <= valid_from:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")
        scope = getattr(self, "scope", None)
        course_ids = getattr(self, "course_ids", None)
        if scope == "courses" and not course_ids:
            raise ValueError("Mã theo khóa học cần ít nhất một khóa học")
        return self


class AdminCouponCreate(_CouponRules):
    code: str = Field(min_length=3, max_length=MAX_CODE_LENGTH)
    discount_type: DiscountType
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    scope: CouponScope = "site"
    course_ids: list[uuid.UUID] = []
    #: NULL: unlimited.
    max_uses: int | None = Field(default=None, ge=1)
    #: Omitted: from now.
    valid_from: datetime | None = None
    #: NULL: no end.
    valid_to: datetime | None = None

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(CODE_PATTERN, code):
            raise ValueError("Mã chỉ gồm chữ không dấu, số, gạch ngang, gạch dưới (3–32 ký tự)")
        return code


class AdminCouponUpdate(_CouponRules):
    """Only what is sent changes. The code itself never does."""

    discount_type: DiscountType | None = None
    value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    scope: CouponScope | None = None
    course_ids: list[uuid.UUID] | None = None
    max_uses: int | None = Field(default=None, ge=1)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class CouponCourseRef(BaseModel):
    id: uuid.UUID
    title: str


class AdminCouponOut(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: DiscountType
    value: Decimal
    scope: CouponScope
    courses: list[CouponCourseRef]
    max_uses: int | None
    used_count: int
    valid_from: datetime
    valid_to: datetime | None
    #: Derived: scheduled, live, exhausted or ended.
    status: str
    created_at: datetime
