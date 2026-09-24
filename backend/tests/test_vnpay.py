"""Signing and checking VNPay callbacks.

The entire integration rests on one string: the sorted, URL-encoded list of
`vnp_` parameters that gets HMAC'd. Get it wrong and the failure is a
signature mismatch with no explanation, at a gateway nobody can debug from
here. So the canonical string is pinned **by hand** below -- written out from
the specification, not read back from the implementation -- and everything
else is checked against it.

No database, no merchant account, no network: these are the tests that can
prove the protocol is right before anybody has credentials.
"""

import hashlib
import hmac
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import parse_qsl, urlparse

from app.services import vnpay

SECRET = "SANDBOX-SECRET"

PARAMS = {
    "vnp_Amount": "39900000",
    "vnp_Command": "pay",
    "vnp_CreateDate": "20260924153000",
    "vnp_CurrCode": "VND",
    "vnp_IpAddr": "127.0.0.1",
    "vnp_Locale": "vn",
    "vnp_OrderInfo": "Thanh toan don hang DP260924ABC123",
    "vnp_OrderType": "other",
    "vnp_ReturnUrl": "http://localhost:3000/thanh-toan/ket-qua",
    "vnp_TmnCode": "DEMOCODE",
    "vnp_TxnRef": "DP260924ABC123",
    "vnp_Version": "2.1.0",
}

#: Written out by hand from the spec: sorted by name, `quote_plus` on both
#: halves -- so a space is `+`, a colon is `%3A`, a slash is `%2F`.
CANONICAL = (
    "vnp_Amount=39900000"
    "&vnp_Command=pay"
    "&vnp_CreateDate=20260924153000"
    "&vnp_CurrCode=VND"
    "&vnp_IpAddr=127.0.0.1"
    "&vnp_Locale=vn"
    "&vnp_OrderInfo=Thanh+toan+don+hang+DP260924ABC123"
    "&vnp_OrderType=other"
    "&vnp_ReturnUrl=http%3A%2F%2Flocalhost%3A3000%2Fthanh-toan%2Fket-qua"
    "&vnp_TmnCode=DEMOCODE"
    "&vnp_TxnRef=DP260924ABC123"
    "&vnp_Version=2.1.0"
)


def test_the_canonical_string_is_what_the_specification_describes() -> None:
    assert vnpay.canonical(PARAMS) == CANONICAL


def test_the_signature_is_hmac_sha512_of_that_string() -> None:
    expected = hmac.new(
        SECRET.encode(), CANONICAL.encode(), hashlib.sha512
    ).hexdigest()

    assert vnpay.sign(PARAMS, SECRET) == expected


def test_parameters_arrive_in_any_order_and_sign_the_same() -> None:
    """Dict order is whatever the caller's code happened to do; the signature
    must not be."""
    shuffled = dict(reversed(list(PARAMS.items())))

    assert vnpay.sign(shuffled, SECRET) == vnpay.sign(PARAMS, SECRET)


def test_the_signature_fields_are_not_part_of_what_is_signed() -> None:
    """Otherwise verifying a callback could never reproduce its own hash."""
    with_hash = {
        **PARAMS,
        "vnp_SecureHash": "whatever",
        "vnp_SecureHashType": "HMACSHA512",
    }

    assert vnpay.canonical(with_hash) == CANONICAL


def test_anything_that_is_not_a_vnp_parameter_is_left_out() -> None:
    """Our own query parameters on a return URL must not change the hash."""
    assert vnpay.canonical({**PARAMS, "utm_source": "email"}) == CANONICAL


def test_an_empty_value_is_left_out() -> None:
    """VNPay's own implementation skips these, so including one produces a
    signature that is right by every rule except the only one that counts."""
    assert vnpay.canonical({**PARAMS, "vnp_BankCode": ""}) == CANONICAL


def test_verify_accepts_what_sign_produced() -> None:
    signed = {**PARAMS, "vnp_SecureHash": vnpay.sign(PARAMS, SECRET)}

    assert vnpay.verify(signed, SECRET) is True


def test_verify_accepts_a_signature_in_upper_case() -> None:
    """VNPay has sent both cases over the years; the hex is the same number."""
    signed = {**PARAMS, "vnp_SecureHash": vnpay.sign(PARAMS, SECRET).upper()}

    assert vnpay.verify(signed, SECRET) is True


def test_verify_refuses_a_changed_amount() -> None:
    """The forgery that matters: the same callback with a smaller bill."""
    signed = {**PARAMS, "vnp_SecureHash": vnpay.sign(PARAMS, SECRET)}
    tampered = {**signed, "vnp_Amount": "100"}

    assert vnpay.verify(tampered, SECRET) is False


def test_verify_refuses_a_signature_from_another_merchant_secret() -> None:
    signed = {**PARAMS, "vnp_SecureHash": vnpay.sign(PARAMS, "SOMEBODY-ELSE")}

    assert vnpay.verify(signed, SECRET) is False


def test_verify_refuses_a_callback_with_no_signature_at_all() -> None:
    assert vnpay.verify(PARAMS, SECRET) is False


# --- The payment request ----------------------------------------------------


def parameters(amount: str = "399000") -> dict[str, str]:
    return vnpay.payment_parameters(
        tmn_code="DEMOCODE",
        return_url="http://localhost:3000/thanh-toan/ket-qua",
        code="DP260924ABC123",
        amount=Decimal(amount),
        ip_address="127.0.0.1",
        now=datetime(2026, 9, 24, 8, 30, tzinfo=UTC),
        expire_minutes=15,
    )


def test_the_amount_travels_in_hundredths_of_a_dong() -> None:
    """399.000 ₫ is `39900000`. A decimal point is rejected outright."""
    assert parameters()["vnp_Amount"] == "39900000"
    assert "." not in parameters()["vnp_Amount"]


def test_times_are_vietnam_time_and_have_no_zone_marker() -> None:
    """08:30 UTC is 15:30 in Hanoi, and the field carries no offset -- VNPay
    reads it as local time whatever the server's clock is set to."""
    built = parameters()

    assert built["vnp_CreateDate"] == "20260924153000"
    assert built["vnp_ExpireDate"] == "20260924154500"


def test_a_payment_request_carries_every_field_the_gateway_requires() -> None:
    built = parameters()

    assert built["vnp_Version"] == "2.1.0"
    assert built["vnp_Command"] == "pay"
    assert built["vnp_CurrCode"] == "VND"
    assert built["vnp_Locale"] == "vn"
    assert built["vnp_TxnRef"] == "DP260924ABC123"
    assert built["vnp_TmnCode"] == "DEMOCODE"
    assert built["vnp_IpAddr"] == "127.0.0.1"
    assert built["vnp_ReturnUrl"].endswith("/thanh-toan/ket-qua")


def test_the_order_info_carries_no_diacritics() -> None:
    """It travels through a query string, a bank's system and a settlement
    report; "Thanh toán" does not survive all three the way "Thanh toan" does.
    """
    info = parameters()["vnp_OrderInfo"]

    assert info.isascii()
    assert "DP260924ABC123" in info


def test_the_url_is_the_signed_string_with_the_signature_on_the_end() -> None:
    """Built any other way, the query and the hash drift apart over one space
    or one colon -- and the only symptom is a refusal with no reason."""
    built = parameters()

    url = vnpay.payment_url(
        base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        secret=SECRET,
        parameters=built,
    )

    assert url.startswith("https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?")
    assert url.endswith(f"&vnp_SecureHash={vnpay.sign(built, SECRET)}")


def test_a_url_parsed_back_out_of_the_browser_still_verifies() -> None:
    """The round trip that actually happens: VNPay reads the query, we read a
    callback, and both sides have to agree about the same characters."""
    url = vnpay.payment_url(
        base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        secret=SECRET,
        parameters=parameters(),
    )

    received = dict(parse_qsl(urlparse(url).query))

    assert vnpay.verify(received, SECRET) is True


# --- Reading a callback -----------------------------------------------------


def test_success_needs_both_codes() -> None:
    """A request that was fine about a payment that failed carries "00" in the
    first field and something else in the second."""
    assert vnpay.paid_successfully(
        {"vnp_ResponseCode": "00", "vnp_TransactionStatus": "00"}
    )
    assert not vnpay.paid_successfully(
        {"vnp_ResponseCode": "00", "vnp_TransactionStatus": "02"}
    )
    assert not vnpay.paid_successfully(
        {"vnp_ResponseCode": "24", "vnp_TransactionStatus": "00"}
    )
    assert not vnpay.paid_successfully({})


def test_the_amount_comes_back_out_of_hundredths() -> None:
    assert vnpay.amount_of({"vnp_Amount": "39900000"}) == Decimal("399000")


def test_a_callback_without_a_readable_amount_answers_none() -> None:
    """Rather than raising: it is one more thing the handler refuses, not an
    exception that has to be caught around the money path."""
    assert vnpay.amount_of({}) is None
    assert vnpay.amount_of({"vnp_Amount": "ba trăm nghìn"}) is None
