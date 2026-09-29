"""Rebuild the XP leaderboard from the ledger now, without waiting for 03:30.

    python -m scripts.rebuild_leaderboard

Runs the same `rebuild_current` the nightly Celery task runs, against the same
Redis: this week's, this month's and the all-time board are replaced by the
sums in `xp_events`. Run it after writing XP any way other than through the
services -- `scripts.seed_study` does, at the end -- or to check that the
boards and the ledger agree: a second run changes nothing.
"""

import asyncio

from app.core.db import SessionLocal
from app.services.leaderboard import get_board, period_of, rebuild_current, today_in_vietnam

LABELS = {"week": "tuần này", "month": "tháng này", "all": "mọi thời gian"}


async def main() -> None:
    today = today_in_vietnam()
    async with SessionLocal() as session:
        counts = await rebuild_current(session, get_board(), today=today)

    for name, count in counts.items():
        print(f"Bảng {LABELS[name]:<14} {period_of(name, today).key:<24} {count} người")


if __name__ == "__main__":
    asyncio.run(main())
