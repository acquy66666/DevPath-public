"""The gateway's callback. The one route in this API that answers to a robot.

Everything about it is different from the rest, and every difference has the
same cause: **VNPay is the client here, not our frontend.**

* **No authentication.** It is called by VNPay's servers, which have no account
  and no token. What takes the place of a token is the HMAC signature on the
  parameters, checked before a single one of them is believed.
* **No error envelope.** It answers `{"RspCode": "...", "Message": "..."}`,
  VNPay's own shape, because that is what VNPay parses.
* **HTTP 200 for every outcome**, including refusals. A non-200 -- or a body it
  cannot read -- makes VNPay treat the callback as undelivered and send it
  again, so answering "order not found" with a 404 would buy a retry loop
  instead of an answer.
* **GET, with everything in the query string**, which is what the specification
  says and not something to improve on.

This is *not* where the browser lands after paying. That is a page on the
frontend, which asks `GET /orders/{code}` what really happened -- what the
browser carries back is written in a query string the person can edit.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import DbSession
from app.services import orders as orders_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/vnpay/ipn", include_in_schema=True)
async def vnpay_ipn(request: Request, session: DbSession) -> JSONResponse:
    """VNPay telling us what happened to a payment.

    Answers, all with HTTP 200: `00` confirm success, `01` order not found,
    `02` order already confirmed, `04` invalid amount, `97` invalid signature.

    Whatever the answer, the callback itself is written to `payment_events`
    first -- including the ones with a bad signature, which are the ones worth
    keeping.
    """
    params = dict(request.query_params)

    rsp_code, message = await orders_service.handle_vnpay_ipn(
        session, params, settings=get_settings()
    )

    return JSONResponse({"RspCode": rsp_code, "Message": message})
