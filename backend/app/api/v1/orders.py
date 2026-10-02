"""Orders, and the payment URL that pays for one.

Both routes here are about the caller's own orders and take no user id. The
third piece of the flow -- the gateway's callback -- is not here: it belongs to
nobody, is authenticated by a signature rather than a token, and answers in
VNPay's dialect instead of ours, so it lives in `payments.py`.
"""

from typing import Annotated

from fastapi import APIRouter, Path, Request, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.categories import CategoryOut
from app.schemas.courses import CourseCardBase, CourseCardOut, CourseInstructorOut
from app.schemas.orders import OrderCreate, OrderItemOut, OrderOut, PaymentUrlOut
from app.services import orders as orders_service
from app.services.orders import OrderView

router = APIRouter(prefix="/orders", tags=["orders"])

OrderCode = Annotated[str, Path(min_length=8, max_length=20)]


def _order_out(view: OrderView) -> OrderOut:
    order = view.order
    return OrderOut(
        code=order.code,
        status=order.status,
        items=[
            OrderItemOut(
                course=CourseCardOut(
                    **CourseCardBase.model_validate(line.course).model_dump(),
                    instructor=CourseInstructorOut.model_validate(line.instructor),
                    category=CategoryOut.model_validate(line.category),
                ),
                unit_price=line.unit_price,
            )
            for line in view.lines
        ],
        subtotal=order.subtotal,
        discount=order.discount,
        total=order.total,
        coupon_code=order.coupon_code,
        payment_provider=order.payment_provider,
        provider_txn_id=order.provider_txn_id,
        failure_code=order.failure_code,
        paid_at=order.paid_at,
        created_at=order.created_at,
    )


def client_ip(request: Request) -> str:
    """The buyer's address, for `vnp_IpAddr`.

    `X-Forwarded-For` is trusted because in this deployment nginx sets it and
    nothing else can reach the app. It is worth saying that out loud, since
    trusting that header is a mistake in general -- here the field is only ever
    shown back to us in VNPay's reports, and nothing is decided from it.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "127.0.0.1"


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate, current_user: CurrentUser, session: DbSession
) -> OrderOut:
    """Turn my cart into an order at today's prices, and quote me a total.

    The body carries a coupon code at most: the lines and the amount are read
    from the cart on the server, because a client that names its own total is a
    client that sets its own price.

    Nothing is paid and nothing is used up yet -- the cart is left alone, and a
    coupon's count only moves when the money arrives. Refusals are the cart's
    and the coupon's own: 409 `CART_EMPTY`, 404 `COUPON_NOT_FOUND`, 409
    `COUPON_EXPIRED` and the rest, all worded exactly as they are on the cart
    page, because they are the same rules checked again at the last moment.
    """
    return _order_out(
        await orders_service.create_from_cart(
            session, current_user, coupon_code=payload.coupon_code
        )
    )


@router.get("/{code}", response_model=OrderOut)
async def get_order(
    code: OrderCode, current_user: CurrentUser, session: DbSession
) -> OrderOut:
    """One of my orders, and the authoritative answer to "did it go through".

    This is what the page the bank redirects to asks. The query string that
    redirect carries says the same thing, but it arrives through a browser,
    and a browser is something its owner can edit.

    Somebody else's order is a 404, not a 403: the code is the only thing an
    outsider could guess at, and confirming a guess is the whole attack.
    """
    return _order_out(await orders_service.get_for_user(session, code, current_user))


@router.post("/{code}/payment-url", response_model=PaymentUrlOut)
async def create_payment_url(
    code: OrderCode, request: Request, current_user: CurrentUser, session: DbSession
) -> PaymentUrlOut:
    """A signed VNPay URL for one of my pending orders.

    POST rather than GET: it is not a page, it mints a fresh signed string with
    a fifteen-minute life, and it must never be cached by anything.

    Can be asked for again -- somebody who closed the bank's tab needs a way
    back -- but only within the order's window (30 minutes) and while its
    coupon and courses still stand: 409 `ORDER_EXPIRED` otherwise, with a
    sentence saying which. 409 `ORDER_NOT_PAYABLE` once the order is settled, and 503
    `PAYMENT_NOT_CONFIGURED` on a server with no merchant credentials, which
    says so rather than building a URL the gateway would refuse.
    """
    return PaymentUrlOut(
        payment_url=await orders_service.payment_url(
            session,
            code,
            current_user,
            settings=get_settings(),
            ip_address=client_ip(request),
        )
    )
