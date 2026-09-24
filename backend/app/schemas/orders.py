"""Orders on the wire."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.coupon import MAX_CODE_LENGTH
from app.models.order import ORDER_STATUSES, PAYMENT_PROVIDERS
from app.schemas.courses import CourseCardOut

OrderStatus = Literal[ORDER_STATUSES]  # type: ignore[valid-type]
PaymentProvider = Literal[PAYMENT_PROVIDERS]  # type: ignore[valid-type]


class OrderCreate(BaseModel):
    """What checkout sends: at most a coupon code.

    No list of courses and no amount. Both come from the cart on the server --
    a client that could name its own lines, or its own total, would be a client
    that can set its own price.
    """

    coupon_code: str | None = Field(default=None, min_length=3, max_length=MAX_CODE_LENGTH)


class OrderItemOut(BaseModel):
    """One line of the receipt.

    `unit_price` rather than the course's price today: what was paid is a fact
    about the day of the sale, and `course.price` is what the course costs now.
    Both are here, and they are allowed to differ.
    """

    course: CourseCardOut
    unit_price: Decimal


class OrderOut(BaseModel):
    """An order, as its buyer sees it.

    `status` is the authoritative one, read from our own database: the result
    page is reached by a redirect from the bank, and what a redirect carries in
    its query string is not evidence of anything.
    """

    code: str
    status: OrderStatus
    items: list[OrderItemOut]
    #: VND, all three frozen when the order was written.
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    coupon_code: str | None
    payment_provider: PaymentProvider
    #: The gateway's transaction id -- what a person quotes when asking their
    #: bank or us about a payment. NULL until the money actually moves.
    provider_txn_id: str | None
    #: The gateway's refusal code, so the page can tell "bạn đã hủy" from
    #: "thẻ không đủ số dư".
    failure_code: str | None
    paid_at: datetime | None
    created_at: datetime


class PaymentUrlOut(BaseModel):
    """Where to send the browser. Signed, and good for a few minutes only."""

    payment_url: str
