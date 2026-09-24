"""Talking to VNPay: building a payment URL, and checking one came back.

Two pure functions and a URL builder, with no database and no HTTP client --
everything here is a string operation, which is what makes it testable without
a merchant account and what makes the tests worth anything.

**The whole protocol is one canonical string.** Every parameter whose name
starts with `vnp_` and has a value, sorted by name, joined as
`key=value&key=value` with both halves URL-encoded, HMAC-SHA512'd with the
merchant's secret. Getting that string wrong is the one way this integration
fails: the signature simply does not match and VNPay refuses the payment with
nothing that says why. So it is built in exactly one place, `canonical()`, and
both the outgoing URL and the incoming check use it -- a payment URL whose
query VNPay cannot verify is impossible to produce, because the query is the
canonical string.

Three details that are easy to get wrong and are written down here rather than
learned twice:

* **The amount is in 1/100 đồng.** 399.000 ₫ travels as `39900000`. VNPay
  rejects a decimal point outright.
* **Times are Vietnam time**, `yyyyMMddHHmmss`, with no zone marker on them.
  Vietnam has no daylight saving, so a fixed +07:00 offset is exact and needs
  no timezone database on whatever machine this runs on.
* **Empty values are left out of the signature.** VNPay's own implementation
  skips them; including one produces a signature that is correct by every rule
  except theirs.

`vnp_OrderInfo` is deliberately written without diacritics. It is a field that
travels through a query string, a bank's system and a settlement report, and
"Thanh toan don hang DP260924ABC123" arrives intact everywhere, which "Thanh
toán đơn hàng" does not.
"""

import hashlib
import hmac
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote_plus

#: The API version this module speaks. The signing rules differ between 2.0.0
#: and 2.1.0, so it is not a formality.
VERSION = "2.1.0"
COMMAND = "pay"
CURRENCY = "VND"
LOCALE = "vn"
#: The merchant category. "other" is what a course sale is, in VNPay's list.
ORDER_TYPE = "other"

#: VNPay counts money in 1/100 đồng: the amount is multiplied by this.
AMOUNT_SCALE = 100

#: Vietnam is UTC+7 the whole year round, so a fixed offset is exact -- and
#: does not depend on a tz database being installed in the container.
VIETNAM = timezone(timedelta(hours=7))
TIME_FORMAT = "%Y%m%d%H%M%S"

#: Both `vnp_ResponseCode` and `vnp_TransactionStatus` say this when the money
#: actually moved. They are checked separately: the first is about the request,
#: the second about the transaction, and they can disagree.
SUCCESS_CODE = "00"

#: The signature itself is not part of what is signed.
UNSIGNED_FIELDS = frozenset({"vnp_SecureHash", "vnp_SecureHashType"})


def canonical(params: Mapping[str, str]) -> str:
    """The exact string VNPay signs, and the exact query it expects.

    Sorted by parameter name, `key=value` pairs joined with `&`, both halves
    URL-encoded the `quote_plus` way (a space becomes `+`). Anything that is
    not a `vnp_` parameter, the two signature fields, and anything with an
    empty value are left out -- all three exactly as VNPay's own code does it.
    """
    signed = {
        key: str(value)
        for key, value in params.items()
        if key.startswith("vnp_") and key not in UNSIGNED_FIELDS and str(value) != ""
    }
    return "&".join(
        f"{quote_plus(key)}={quote_plus(value)}" for key, value in sorted(signed.items())
    )


def sign(params: Mapping[str, str], secret: str) -> str:
    """HMAC-SHA512 of the canonical string, lower-case hex."""
    return hmac.new(
        secret.encode("utf-8"), canonical(params).encode("utf-8"), hashlib.sha512
    ).hexdigest()


def verify(params: Mapping[str, str], secret: str) -> bool:
    """Whether these parameters really came from VNPay.

    Compared with `compare_digest`, which takes the same time whatever the
    first wrong character is -- the endpoint is public, and a comparison that
    returns early tells anyone who can time it how much of a forged signature
    was right.

    A callback with no signature at all is false rather than an error: it is
    the same answer, and there is exactly one place that has to handle it.
    """
    received = str(params.get("vnp_SecureHash", ""))
    if not received:
        return False

    return hmac.compare_digest(sign(params, secret).lower(), received.lower())


def payment_parameters(
    *,
    tmn_code: str,
    return_url: str,
    code: str,
    amount: Decimal,
    ip_address: str,
    now: datetime,
    expire_minutes: int,
) -> dict[str, str]:
    """The parameters of one payment request, ready to be signed.

    Separate from the URL so a test can read the fields without parsing a
    query string, and so the IPN tests can sign a reply with the same rules.
    """
    created = now.astimezone(VIETNAM)
    expires = created + timedelta(minutes=expire_minutes)

    return {
        "vnp_Version": VERSION,
        "vnp_Command": COMMAND,
        "vnp_TmnCode": tmn_code,
        # int(), not round(): prices are NUMERIC(12,2) and a course price is
        # whole đồng, so this is exact -- and a stray fraction of a đồng should
        # surface as a mismatch at the gateway, not be rounded into the amount
        # somebody is charged.
        "vnp_Amount": str(int(amount * AMOUNT_SCALE)),
        "vnp_CurrCode": CURRENCY,
        "vnp_TxnRef": code,
        "vnp_OrderInfo": f"Thanh toan don hang {code}",
        "vnp_OrderType": ORDER_TYPE,
        "vnp_Locale": LOCALE,
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": ip_address,
        "vnp_CreateDate": created.strftime(TIME_FORMAT),
        # Without this a payment URL stays payable forever: somebody could open
        # it next month, pay yesterday's price, and be enrolled by an IPN for
        # an order everyone has forgotten.
        "vnp_ExpireDate": expires.strftime(TIME_FORMAT),
    }


def payment_url(
    *,
    base_url: str,
    secret: str,
    parameters: Mapping[str, str],
) -> str:
    """The URL to send the browser to.

    The query is the canonical string itself, with the signature appended, so
    what VNPay verifies is character-for-character what was signed. Building
    the query any other way -- `urlencode`, a dict comprehension, anything --
    is how the two drift apart over one space or one colon.
    """
    query = canonical(parameters)
    return f"{base_url}?{query}&vnp_SecureHash={sign(parameters, secret)}"


def paid_successfully(params: Mapping[str, str]) -> bool:
    """Whether a verified callback says the money moved.

    Both codes, not either: `vnp_ResponseCode` answers "was the request all
    right", `vnp_TransactionStatus` answers "did the transaction go through".
    A request that was fine about a payment that failed carries "00" in the
    first and something else in the second.
    """
    return (
        str(params.get("vnp_ResponseCode", "")) == SUCCESS_CODE
        and str(params.get("vnp_TransactionStatus", "")) == SUCCESS_CODE
    )


def amount_of(params: Mapping[str, str]) -> Decimal | None:
    """The đồng a callback is about, or None if it did not carry a number."""
    raw = str(params.get("vnp_Amount", ""))
    try:
        return Decimal(raw) / AMOUNT_SCALE
    except (ArithmeticError, ValueError):
        return None
