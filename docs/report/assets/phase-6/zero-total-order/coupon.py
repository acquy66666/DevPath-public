"""A throwaway 100 % code for the UI drill, and its removal.

    docker compose exec -T backend python - create < coupon.py    prints the code
    docker compose exec -T backend python - delete <CODE> < coupon.py

Written straight to the table, like scripts/seed_coupons.py: the rules live in
its CHECK constraints. Deleted only after `scripts.purge_e2e` has removed the
drill's order (orders.coupon_id is SET NULL, so the order would survive it
anyway, but the drill leaves nothing behind).
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as db:
        if sys.argv[1] == "create":
            code = f"MIENPHI{uuid.uuid4().hex[:6].upper()}"
            await db.execute(
                text(
                    "insert into coupons (code, discount_type, value, scope, max_uses, valid_from)"
                    " values (:code, 'percent', 100, 'site', 5, :since)"
                ),
                {"code": code, "since": datetime.now(UTC) - timedelta(hours=1)},
            )
            print(code)
        else:
            deleted = await db.execute(
                text("delete from coupons where code = :code"), {"code": sys.argv[2]}
            )
            print(f"deleted {deleted.rowcount} coupon(s)")
    await engine.dispose()


asyncio.run(main())
