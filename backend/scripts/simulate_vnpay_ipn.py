"""Send the callback VNPay would send, so the flow can be run without a bank.

    python -m scripts.simulate_vnpay_ipn DP260924ABC123
    python -m scripts.simulate_vnpay_ipn DP260924ABC123 --fail
    python -m scripts.simulate_vnpay_ipn DP260924ABC123 --response-code 51

The IPN is the only thing in the payment flow that cannot be reached by
clicking: VNPay's servers call the backend directly, which needs a registered
merchant *and* a public address for them to call. Everything on this side of it
-- the signature, the idempotency, the enrolment, the cart going empty -- is
ours, and this script exercises all of it by signing a callback with the same
secret the backend verifies with and posting it to the real endpoint.

**It proves what it can and no more.** What it cannot prove is that VNPay's own
page accepts our payment URL; that needs `VNPAY_TMN_CODE` from a real merchant
registration. What it does prove is everything that happens after the money
moves, which is the part where a mistake costs somebody their course.

It signs -- it does not cheat. The request goes through the same route, the
same signature check and the same handler as a real callback, so a broken
signature check would show up here as a refusal, not as a pass.
"""

import argparse
import asyncio
from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Order
from app.services import vnpay

#: Reached from inside the backend container, where this is meant to run.
DEFAULT_API = "http://localhost:8000"

#: A few of VNPay's refusal codes, for `--response-code`.
REFUSALS = {
    "24": "khách hàng hủy giao dịch",
    "51": "tài khoản không đủ số dư",
    "75": "ngân hàng đang bảo trì",
}


async def _order(session: AsyncSession, code: str) -> Order:
    order = await session.scalar(select(Order).where(Order.code == code.upper()))
    if order is None:
        raise SystemExit(
            f"Không có đơn hàng {code}. Tạo đơn bằng nút Thanh toán ở /gio-hang, "
            "mã đơn nằm trên trang kết quả."
        )
    return order


def _params(order: Order, *, response_code: str, transaction_status: str) -> dict[str, str]:
    """Exactly the fields VNPay sends on an IPN, signed the same way."""
    params = {
        "vnp_Amount": str(int(order.total * vnpay.AMOUNT_SCALE)),
        "vnp_BankCode": "NCB",
        "vnp_BankTranNo": f"VNP{order.code[-8:]}",
        "vnp_CardType": "ATM",
        "vnp_OrderInfo": f"Thanh toan don hang {order.code}",
        "vnp_PayDate": datetime.now(vnpay.VIETNAM).strftime(vnpay.TIME_FORMAT),
        "vnp_ResponseCode": response_code,
        "vnp_TmnCode": get_settings().vnpay_tmn_code,
        # Stands in for the bank's own id: derived from the order so that
        # running this twice sends the same one, the way a retry does.
        "vnp_TransactionNo": str(int(order.created_at.timestamp()))[-8:],
        "vnp_TransactionStatus": transaction_status,
        "vnp_TxnRef": order.code,
    }
    return {
        **params,
        "vnp_SecureHash": vnpay.sign(params, get_settings().vnpay_hash_secret),
    }


def _money(amount: Decimal) -> str:
    return f"{int(amount):,}".replace(",", ".")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("code", help="Mã đơn hàng, ví dụ DP260924ABC123.")
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Giả lập thanh toán thất bại (mặc định mã 24: khách tự hủy).",
    )
    parser.add_argument(
        "--response-code",
        default=None,
        help="Mã lỗi cụ thể của VNPay: " + ", ".join(f"{k} ({v})" for k, v in REFUSALS.items()),
    )
    parser.add_argument("--api", default=DEFAULT_API, help=f"Mặc định {DEFAULT_API}.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.vnpay_enabled:
        raise SystemExit(
            "Chưa cấu hình VNPAY_TMN_CODE và VNPAY_HASH_SECRET trong infra/.env. "
            "Giá trị bất kỳ cũng chạy được ở máy dev — script này ký bằng đúng "
            "secret backend dùng để kiểm. Nhớ `docker compose restart backend`."
        )

    failed = args.fail or args.response_code is not None
    response_code = args.response_code or ("24" if args.fail else "00")

    async with SessionLocal() as session:
        order = await _order(session, args.code)
        params = _params(
            order,
            response_code=response_code,
            transaction_status="02" if failed else "00",
        )

    print(f"đơn hàng : {order.code} — {_money(order.total)} ₫ ({order.status})")
    print(f"giả lập  : {'thất bại' if failed else 'thành công'}, mã {response_code}")

    async with httpx.AsyncClient(base_url=args.api, timeout=30) as client:
        answer = await client.get("/api/v1/payments/vnpay/ipn", params=params)

    print(f"IPN trả  : {answer.status_code} {answer.text}")

    async with SessionLocal() as session:
        after = await _order(session, args.code)

    print(f"đơn hàng : {after.status}", end="")
    if after.paid_at is not None:
        print(f" lúc {after.paid_at:%d/%m/%Y %H:%M}, mã giao dịch {after.provider_txn_id}")
    elif after.failure_code:
        print(f", mã lỗi {after.failure_code}")
    else:
        print()

    if after.status == "paid":
        print("\nHọc viên đã được ghi danh các khóa trong đơn, giỏ hàng đã bỏ các dòng đó.")
    print("Gửi lại lệnh này lần nữa để xem chống trùng: IPN sẽ trả RspCode 02.")


if __name__ == "__main__":
    asyncio.run(main())
